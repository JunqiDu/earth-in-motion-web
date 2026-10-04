#!/usr/bin/env python
"""One final isolated RF v2 evaluation. Default invocation reads the frozen report.

Explicit --execute is allowed only before final_gate_status.json exists. Later
invocations never retune, overwrite this run, launch SNAP, or process six scenes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage

from analysis.historical_water import load_frequency_raster, training_labels
from analysis.phase3b_references import stage_raw_reference, load_raw_reference, geometry_mask
from analysis.physical_constraints import sha256_file, load_dem_to_grid, rasterize_geojson, distance_to_mask_m
from analysis.rcm_preprocessing import CommonGrid, aggregate_power_and_coverage, power_to_db
from analysis.rf_classification import make_features, spatial_block_samples, fit_scene_rf, predict_scene_rf, FEATURE_NAMES
from analysis.rf_final import METHOD_ID, method_definition, final_masks, final_gate, object_diagnostics
from analysis.validation import validate_scene
from scripts.phase3b_rf import PILOT_IDS, _scene_info, _comparison, _old_comparison
from scripts.phase3b_pipeline import permanent_and_egs_masks, _read_geojson_mask

BASE = ROOT / "data/processed/phase3b"
OUT = BASE / "rf_v2_final"
GRID = CommonGrid()
FRESH_GRID = CommonGrid(left=570110, bottom=5444740, right=571430, top=5447740, width=44, height=100)
PROTECTED = [ROOT / "app.py", ROOT / "notebooks/04_change_detection.ipynb", ROOT / "notebooks/05_impact_analysis.ipynb",
             ROOT / "data/processed/phase4", ROOT / "data/processed/phase5", BASE / "rf_v1", BASE / "multisource",
             BASE / "masks", BASE / "cache"]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str, allow_nan=False) + "\n")


def snapshot():
    paths = [p for root in PROTECTED for p in (root.rglob("*") if root.is_dir() else [root]) if p.is_file()]
    return {str(p.relative_to(ROOT)): sha256_file(p) for p in paths}


def write_grid(path, values, grid, *, dtype="uint8", nodata=255):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", count=1, width=grid.width, height=grid.height,
                       transform=grid.transform, crs=grid.crs, dtype=dtype, nodata=nodata, compress="deflate") as dst:
        dst.write(np.asarray(values, dtype=dtype), 1)


def corrected_scene(sid, grid):
    """Reaggregate existing native TC bands; do not alter old caches."""
    tc = BASE / "cache/pilot" / sid / "terrain_corrected.tif"
    powers, coverages, masks = [], [], []
    with rasterio.open(tc) as src:
        if src.crs.to_epsg() != 32610 or src.count != 4:
            raise ValueError(f"Unexpected TC geometry/band contract: {tc}")
        for band in (3, 4):  # declared terrain graph: GammaHH, GammaHV, SigmaHH, SigmaHV
            values = src.read(band)
            explicit_valid = (src.read_masks(band) > 0) & np.isfinite(values) & (values > 0)
            power, coverage, valid = aggregate_power_and_coverage(values, src.transform, str(src.crs), grid, source_valid=explicit_valid)
            powers.append(power); coverages.append(coverage); masks.append(valid)
        native_qa = {"crs": str(src.crs), "native_pixel_size_m": abs(src.transform.a), "native_shape": [src.height, src.width]}
    valid = masks[0] & masks[1]
    features, _ = make_features(power_to_db(powers[0]), power_to_db(powers[1]), valid)
    qa = {"observation_id": sid, "grid": grid.as_dict(), "native_geometry": native_qa,
          "valid_pixels": int(valid.sum()), "valid_pct": float(valid.mean() * 100),
          "minimum_hh_coverage": float(coverages[0].min()), "minimum_hv_coverage": float(coverages[1].min()),
          "source_tc_sha256": sha256_file(tc)}
    return features, valid, qa


def read_aligned(path, grid):
    with rasterio.open(path) as src:
        if src.crs.to_epsg() != 32610 or src.transform != grid.transform or src.shape != (grid.height, grid.width):
            raise ValueError(f"Misaligned ancillary: {path}")
        return src.read(1)


def diagnostic_rows(sid, masks, p, reference, valid, reference_id):
    terrain, component, errors = [], [], []
    for name in ("normal_terrain", "terrain_exception", "terrain_rejected"):
        mask = masks[name] & valid
        # Accepted terrain pixels can later be removed by cleanup. Report both.
        survived = mask & masks["flood"]
        terrain.append({"observation_id": sid, "reference_id": reference_id, "reason": name,
                        "pixels": int(mask.sum()), "tp_pixels": int((mask & reference).sum()), "fp_pixels": int((mask & ~reference).sum()),
                        "surviving_tp_pixels": int((survived & reference).sum()), "surviving_fp_pixels": int((survived & ~reference).sum())})
    for name in ("normal_component", "small_component_retained", "cleanup_removed", "permanent_subtraction"):
        mask = masks[name] & valid
        component.append({"observation_id": sid, "reference_id": reference_id, "reason": name,
                          "pixels": int(mask.sum()), "tp_pixels": int((mask & reference).sum()), "fp_pixels": int((mask & ~reference).sum())})
    pred = masks["flood"]
    for name, mask in (("FP", pred & ~reference & valid), ("FN", ~pred & reference & valid)):
        scores = p[mask]
        errors.append({"observation_id": sid, "reference_id": reference_id, "error": name, "pixels": int(mask.sum()),
                       "area_ha": float(mask.sum() * .09), "mean_score": float(scores.mean()) if len(scores) else None})
    return terrain, component, errors


def run(egs_root):
    if (OUT / "final_gate_status.json").exists():
        raise RuntimeError("Phase 3B is frozen: final evaluation already exists; use report-only invocation")
    if (OUT / "final_method_definition.json").exists():
        raise RuntimeError("An interrupted final run exists. Inspect it; automatic overwrite is prohibited")
    OUT.mkdir(parents=True, exist_ok=True)
    # Freeze BEFORE predictions and fresh-AOI performance are inspected.
    definition = method_definition(GRID, FRESH_GRID)
    definition["frozen_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(OUT / "final_method_definition.json", definition)
    before = snapshot()
    write_json(OUT / "qa/protected_inputs_before.json", before)
    inventory = _scene_info()
    observations = pd.read_csv(ROOT / "data/processed/phase4/event_observations.csv").set_index("observation_id")
    # References staged from original products, never from Phase4 exported geometries.
    reference_provenance = {"schema_version": "phase3b-references-1", "primary_raw_egs_reference": {},
                            "legacy_phase4_reference": {"path": "data/processed/phase4/egs_open_water_flood_frames.geojson",
                                                       "sha256": sha256_file(ROOT / "data/processed/phase4/egs_open_water_flood_frames.geojson"),
                                                       "contract": "20m center -> vector -> 30m center; comparison only"}}
    for sid, row in inventory.iterrows():
        ob = observations.loc[row.egs_observation_id]
        folder = egs_root / ob.source_product.removesuffix(".zip")
        target = BASE / "references/raw_egs_30m" / (sid + ".geojson")
        reference_provenance["primary_raw_egs_reference"][sid] = stage_raw_reference(folder, target, GRID, timestamp_utc=ob.timestamp_utc)
    # Fixed initial class-1 for fresh AOI (same product, not date-specific class-1).
    initial = observations.iloc[0]
    initial_folder = egs_root / initial.source_product.removesuffix(".zip")
    fresh_reference_paths = {}
    for sid in ("20251215T015036Z", "20251219T015011Z"):
        ob = observations.loc[inventory.loc[sid].egs_observation_id]
        target = BASE / "references/fresh_neighbor" / (sid + ".geojson")
        fresh_reference_paths[sid] = target
        reference_provenance.setdefault("fresh_neighbor", {})[sid] = stage_raw_reference(egs_root / ob.source_product.removesuffix(".zip"), target, FRESH_GRID, timestamp_utc=ob.timestamp_utc)
    initial_fresh = BASE / "references/fresh_neighbor/initial_semantic_reference.geojson"
    reference_provenance["fresh_initial_reference"] = stage_raw_reference(initial_folder, initial_fresh, FRESH_GRID, timestamp_utc=initial.timestamp_utc)
    for record in reference_provenance["primary_raw_egs_reference"].values():
        record["grid_sha256"] = hashlib.sha256(json.dumps(GRID.as_dict(), sort_keys=True).encode()).hexdigest()
    write_json(OUT / "final_reference_provenance.json", reference_provenance)
    sources = {
        "historical_frequency": BASE / "rf_v1/sources/dsw-1984-2023-frequency_lower_fraser.tif",
        "DSM_elevation": BASE / "multisource/derived/elevation_m.tif",
        "FWA_distance": BASE / "multisource/derived/hydrography_distance_m.tif",
        "fixed_semantic_reference": ROOT / "data/processed/phase4/egs_permanent_water_reference.geojson",
    }
    ancillary = {key: {"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)} for key, path in sources.items()}
    ancillary["historical_source_provenance"] = json.loads((BASE / "rf_v1/historical_water_provenance.json").read_text())
    ancillary["physical_source_provenance"] = json.loads((BASE / "multisource/multisource_source_provenance.json").read_text())
    ancillary["roles"] = {"ECCC": "training prior, never event truth", "EGS_class1": "semantic subtraction, never RF training", "FWA": "independent spatial proximity, not connectivity", "Copernicus": "DSM not DTM"}
    write_json(OUT / "final_ancillary_provenance.json", ancillary)
    freq = load_frequency_raster(sources["historical_frequency"], GRID)
    land, water, eligible = training_labels(freq)
    elevation = read_aligned(sources["DSM_elevation"], GRID)
    hydro = read_aligned(sources["FWA_distance"], GRID)
    permanent = _read_geojson_mask(sources["fixed_semantic_reference"])
    metrics = {"primary_raw_egs_reference": [], "legacy_phase4_reference": []}
    baseline_metrics = []
    coverage, train_rows, importances, score_rows, terrain_rows, component_rows, error_rows = [], [], [], [], [], [], []
    models = {}
    for sid, row in inventory.iterrows():
        features, valid, qa = corrected_scene(sid, GRID)
        coverage.append(qa)
        sample = spatial_block_samples(features, land, water, valid & eligible)
        model = fit_scene_rf(sample)
        models[sid] = model
        p, _ = predict_scene_rf(model, features, valid)
        # Confirm unchanged model/features against existing RF v1 probabilities.
        with rasterio.open(BASE / "rf_v1/probabilities" / (sid + "_water_probability.tif")) as src:
            old_p = src.read(1)
        qa["rf_v1_probability_max_abs_difference"] = float(np.max(np.abs(p[valid] - old_p[valid])))
        qa["previous_common_valid_unchanged"] = bool(np.array_equal(valid, np.load(BASE / "cache/pilot" / sid / "grid_arrays.npz")["common_valid"].astype(bool)))
        masks = final_masks(p, valid, permanent, elevation, hydro)
        raw_ref, egs_valid, _ = load_raw_reference(BASE / "references/raw_egs_30m" / (sid + ".geojson"), GRID)
        _, legacy_ref = permanent_and_egs_masks(row.egs_observation_id)
        for reference_id, reference, evaluation in (("primary_raw_egs_reference", raw_ref, valid & egs_valid), ("legacy_phase4_reference", legacy_ref, valid)):
            m = validate_scene(masks["flood"], reference, evaluation)
            m.update(observation_id=sid, timestamp_utc=row.timestamp_utc, mode_group=row.mode_group,
                     method_id=METHOD_ID, reference_id=reference_id, evaluation_pixels=int(evaluation.sum()),
                     **object_diagnostics(masks["flood"], reference, evaluation))
            metrics[reference_id].append(m)
            t, c, e = diagnostic_rows(sid, masks, p, reference, evaluation, reference_id)
            terrain_rows.extend(t); component_rows.extend(c); error_rows.extend(e)
            with rasterio.open(BASE / "rf_v1/masks" / (sid + "_flood.tif")) as src:
                baseline = src.read(1).astype(bool)
            b = validate_scene(baseline, reference, evaluation)
            baseline_metrics.append({**b, "observation_id": sid, "mode_group": row.mode_group, "method_id": "phase3b_rf_v1", "reference_id": reference_id})
        train_rows.append({"observation_id": sid, "mode_group": row.mode_group,
                           "land_samples": sample.diagnostics["land_samples"], "water_samples": sample.diagnostics["water_samples"],
                           "seed": sample.diagnostics["random_seed"], "EGS_used": False,
                           "selected_coordinates_sha256": hashlib.sha256(json.dumps(sample.diagnostics["selected_coordinates"]).encode()).hexdigest()})
        importances.extend({"observation_id": sid, "feature": feature, "importance": float(value)} for feature, value in zip(FEATURE_NAMES, model.feature_importances_))
        score_rows.append({"observation_id": sid, "mean_score": float(np.mean(p[valid])), "median_score": float(np.median(p[valid])), "candidate_pixels": int(masks["raw_flood"].sum())})
        for name in ("water", "flood", "reason_codes"):
            write_grid(OUT / "masks" / (sid + "_" + name + ".tif"), np.where(valid, masks[name], 255), GRID)
        write_grid(OUT / "masks" / (sid + "_valid.tif"), valid, GRID)
        write_grid(OUT / "probabilities" / (sid + "_water_probability.tif"), np.where(valid, p, -9999), GRID, dtype="float32", nodata=-9999)
        write_grid(OUT / "qa" / (sid + "_disagreement.tif"), np.where(valid & egs_valid, masks["flood"].astype(int) + 2 * raw_ref.astype(int), 255), GRID)
        print(sid, "raw IoU", round(metrics["primary_raw_egs_reference"][-1]["iou"], 4), "legacy IoU", round(metrics["legacy_phase4_reference"][-1]["iou"], 4), flush=True)
    for reference_id, rows in metrics.items():
        name = "raw_egs" if reference_id == "primary_raw_egs_reference" else "legacy"
        pd.DataFrame(rows).to_csv(OUT / ("final_validation_metrics_" + name + ".csv"), index=False)
    for name, rows in (("final_training_summary", train_rows), ("final_feature_importance", importances), ("final_probability_summary", score_rows),
                       ("final_terrain_diagnostics", terrain_rows), ("final_component_diagnostics", component_rows), ("final_fp_fn_diagnostics", error_rows),
                       ("rf_v1_comparable_metrics", baseline_metrics)):
        pd.DataFrame(rows).to_csv(OUT / (name + ".csv"), index=False)
    write_json(OUT / "final_coverage_qa.json", {"fix": "uncovered source zeros retained in average denominator; explicit mask defines zero-power coverage", "threshold": .95, "scenes": coverage, "current_five_performance_explained_by_bug": False})
    # Independent static geometry research was completed previously; preserve its limited meaning.
    geometry = {"status": "not_absolute_geometry_certification", "grid_status": "pass", "no_raster_shift": True,
                "static_FWA_QA": "median offsets 9/21/9/24/9m, P95 52.5/60/54/51/51m; historical shores and radiometric edges, not event ground truth",
                "systematic_artifact_review": "not_certified", "source": "docs/phase3b_method_research.md"}
    write_json(OUT / "final_geometry_qa.json", geometry)
    fresh_summary = fresh_check(models, egs_root, initial_fresh, fresh_reference_paths)
    write_json(OUT / "fresh_aoi_summary.json", fresh_summary)
    lut = pd.read_csv(BASE / "calibration_lut_qa.csv")
    calibration_pass = bool(lut.pass_native_sigma_1e5.all()) if "pass_native_sigma_1e5" in lut else bool(lut["pass_native_sigma_1e-5"].all())
    qa = {"calibration_status": "pass" if calibration_pass else "fail", "geometry_status": "not_certified",
          "systematic_artifact_review": "not_certified", "provenance_status": "pass"}
    gate = final_gate(metrics["primary_raw_egs_reference"], qa)
    gate["reason"] = "; ".join(gate["failed_checks"])
    write_json(OUT / "final_gate_status.json", gate)
    comparison = [{**row, "reference_id": "legacy_phase4_reference", "comparability": "historical registered methods"} for row in _old_comparison()]
    for reference_id in metrics:
        comparison.append({"method": "phase3b_rf_v1", "reference_id": reference_id, **_comparison(pd.DataFrame([r for r in baseline_metrics if r["reference_id"] == reference_id]))["macro"]})
        comparison.append({"method": METHOD_ID, "reference_id": reference_id, **_comparison(pd.DataFrame(metrics[reference_id]))["macro"]})
    pd.DataFrame(comparison).to_csv(OUT / "method_comparison.csv", index=False)
    summary = {"method_id": METHOD_ID, "status": gate["status"], "research_frozen": True,
               "primary_raw_egs_reference": _comparison(pd.DataFrame(metrics["primary_raw_egs_reference"])),
               "legacy_phase4_reference": _comparison(pd.DataFrame(metrics["legacy_phase4_reference"])),
               "fresh_aoi": fresh_summary, "same_event_adaptive_research_caveat": True,
               "no_method_config": True, "remaining_six_processed": False,
               "scientific_conclusion": "Phase 3B final experimental Level-1 method did not meet the pre-registered operational GO gate. The method is retained as validated research evidence, while the existing EGS workflow remains the production source for the prototype." if gate["status"] != "GO" else "GO numeric and QA gates met; promotion requires a separate authorized task."}
    write_json(OUT / "final_validation_summary.json", summary)
    after = snapshot()
    if before != after:
        raise RuntimeError("Protected Phase4/5/app/old Phase3B inputs changed")
    write_json(OUT / "qa/protected_inputs_verification.json", {"unchanged": True, "files": len(before)})
    write_json(OUT / "final_run_manifest.json", {"method_policy_sha256": definition["policy_sha256"],
               "code_hashes": {str(p.relative_to(ROOT)): sha256_file(p) for p in (Path(__file__), ROOT / "analysis/rf_final.py", ROOT / "analysis/phase3b_references.py", ROOT / "analysis/rcm_preprocessing.py")},
               "artifacts": {str(p.relative_to(BASE)): sha256_file(p) for p in OUT.rglob("*") if p.is_file() and p.name != "final_run_manifest.json"},
               "runtime": {"python": sys.version, "numpy": np.__version__, "rasterio": rasterio.__version__, "sklearn": __import__("sklearn").__version__}})
    return summary


def fresh_check(models, egs_root, initial_fresh, reference_paths):
    """Fresh spatial inference: train only on main AOI; never tune on this result."""
    sources = OUT / "sources/fresh_neighbor"
    required = [sources / (name + ".geojson") for name in ("streams", "rivers", "lakes")]
    if not all(p.exists() for p in required):
        pd.DataFrame(columns=["observation_id", "iou", "f1"]).to_csv(OUT / "fresh_aoi_metrics.csv", index=False)
        return {"status": "NOT_RUN_MISSING_ANCILLARY", "grid": FRESH_GRID.as_dict(), "retuned": False,
                "reason": "Minimal FWA neighboring-AOI snapshots not available; never substitute missing context or old-AOI distance"}
    hydro = distance_to_mask_m(rasterize_geojson(required, FRESH_GRID), 30)
    dem = json.loads((BASE / "dem_provenance.json").read_text())
    elevation, _ = load_dem_to_grid([tile["path"] for tile in dem["tiles"]], FRESH_GRID)
    _, _, permanent = load_raw_reference(initial_fresh, FRESH_GRID)
    rows = []
    for sid, path in reference_paths.items():
        features, valid, qa = corrected_scene(sid, FRESH_GRID)
        probability, _ = predict_scene_rf(models[sid], features, valid)
        masks = final_masks(probability, valid, permanent, elevation, hydro)
        reference, egs_valid, _ = load_raw_reference(path, FRESH_GRID)
        metric = validate_scene(masks["flood"], reference, valid & egs_valid)
        metric.update(observation_id=sid, reference_id="primary_raw_egs_reference", valid_pixels=int(valid.sum()), valid_pct=qa["valid_pct"],
                      evaluation_pixels=int((valid & egs_valid).sum()), **object_diagnostics(masks["flood"], reference, valid & egs_valid))
        rows.append(metric)
        write_grid(OUT / "masks" / (sid + "_fresh_flood.tif"), np.where(valid, masks["flood"], 255), FRESH_GRID)
    pd.DataFrame(rows).to_csv(OUT / "fresh_aoi_metrics.csv", index=False)
    return {"status": "COMPLETED_NO_RETUNING", "grid": FRESH_GRID.as_dict(), "metrics": rows,
            "training_on_fresh_AOI": False, "retuned": False, "distinct_from_main_gate": True,
            "limits": "neighboring same-event spatial holdout; EGS is not independent sensor truth; historical main-AOI training only",
            "ancillary_hashes": {str(p.relative_to(ROOT)): sha256_file(p) for p in required},
            "policy_hash": method_definition(GRID, FRESH_GRID)["policy_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="one final evaluation only; refuses existing result")
    parser.add_argument("--egs-root", type=Path)
    args = parser.parse_args()
    if args.execute:
        if args.egs_root is None:
            parser.error("--execute requires the local original EGS product --egs-root")
        result = run(args.egs_root)
    else:
        result = json.loads((OUT / "final_validation_summary.json").read_text())
    print(json.dumps(result, indent=2, default=str))
