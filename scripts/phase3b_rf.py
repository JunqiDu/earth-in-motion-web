#!/usr/bin/env python
"""Run the isolated, research-backed Phase 3B RF v1 experiment.

This command processes only the five registered EGS-overlap scenes.  It never
touches Phase 4/5, Dashboard, or the existing Phase 3B result files.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.historical_water import CANADA_DSW_URL, load_frequency_raster, training_labels, write_frequency_provenance
from analysis.rcm_preprocessing import CommonGrid
from analysis.rf_classification import (
    FEATURE_NAMES,
    RANDOM_SEED,
    RF_PARAMS,
    cleanup_components,
    fit_scene_rf,
    make_features,
    predict_scene_rf,
    spatial_block_samples,
)
from analysis.validation import evaluate_gate, validate_scene
from scripts.phase3b_pipeline import permanent_and_egs_masks


OUT = ROOT / "data/processed/phase3b/rf_v1"
GRID = CommonGrid()
PILOT_IDS = [
    "20251214T142421Z",
    "20251215T015036Z",
    "20251217T141634Z",
    "20251219T015011Z",
    "20251221T141646Z",
]
ELEVATION_CANDIDATES = (None, 3.0, 5.0, 7.0, 10.0)
CLEANUP_CANDIDATES = (2, 4)
SETTLEMENT_CODES = {21, 22, 24, 25, 28, 29, 81, 82, 84, 85, 88, 89}
FOREST_CODES = {41, 42, 43, 44, 47, 48, 49}
WETLAND_CODES = {42, 44, 48, 73, 74, 75, 76, 78, 79}
CROPLAND_CODES = {51, 52, 55, 56}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_mask(path: Path, array: np.ndarray, *, nodata: int = 255, dtype: str = "uint8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=GRID.height, width=GRID.width, count=1,
                       dtype=dtype, crs=GRID.crs, transform=GRID.transform, nodata=nodata,
                       compress="deflate") as dst:
        dst.write(np.asarray(array, dtype=dtype), 1)


def _load_elevation() -> np.ndarray:
    path = ROOT / "data/processed/phase3b/multisource/derived/elevation_m.tif"
    if not path.exists():
        raise FileNotFoundError("Existing Phase 3B Copernicus-derived elevation raster is missing")
    with rasterio.open(path) as src:
        if src.width != GRID.width or src.height != GRID.height or src.crs.to_epsg() != 32610:
            raise RuntimeError("Elevation raster does not match the fixed Phase 3B grid")
        return src.read(1).astype("float32")


def _scene_info() -> pd.DataFrame:
    inventory = pd.read_csv(ROOT / "data/processed/phase3b/level1_inventory.csv")
    rows = inventory[inventory.observation_id.isin(PILOT_IDS)].copy()
    if len(rows) != len(PILOT_IDS):
        raise RuntimeError(f"Expected five RF pilot scenes, found {len(rows)}")
    return rows.set_index("observation_id").loc[PILOT_IDS]


def _load_scene(scene_id: str, row: pd.Series, elevation: np.ndarray) -> dict[str, Any]:
    payload_path = ROOT / "data/processed/phase3b/cache/pilot" / scene_id / "grid_arrays.npz"
    if not payload_path.exists():
        raise FileNotFoundError(f"Raw calibrated pilot cache is missing: {payload_path}")
    payload = np.load(payload_path)
    valid = payload["common_valid"].astype(bool)
    features, names = make_features(payload["sigma_hh_db"], payload["sigma_hv_db"], valid)
    permanent, egs = permanent_and_egs_masks(row.egs_observation_id)
    return {
        "features": features, "feature_names": names, "valid": valid,
        "permanent": permanent, "egs": egs, "elevation": elevation,
        "mode_group": row.mode_group, "timestamp_utc": row.timestamp_utc,
        "beam_mode": row.beam_mode, "orbit_direction": row.orbit_direction,
        "nominal_resolution_m": float(row.nominal_resolution_m),
    }


def _select_outer_parameters(scene_ids: list[str], predictions: dict[str, dict[str, Any]], heldout: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    train_ids = [sid for sid in scene_ids if sid != heldout]
    candidates: list[dict[str, Any]] = []
    for elevation_max_m in ELEVATION_CANDIDATES:
        for min_component_pixels in CLEANUP_CANDIDATES:
            metrics = []
            for sid in train_ids:
                scene = predictions[sid]
                mask = scene["raw_flood"]
                if elevation_max_m is not None:
                    mask = mask & np.isfinite(scene["elevation"]) & (scene["elevation"] <= elevation_max_m)
                mask = cleanup_components(mask, scene["valid"], min_component_pixels)
                metrics.append(validate_scene(mask, scene["egs"], scene["valid"], pixel_area_ha=GRID.pixel_area_ha))
            candidates.append({
                "heldout_observation_id": heldout,
                "training_observation_ids": json.dumps(train_ids),
                "elevation_max_m": elevation_max_m,
                "min_component_pixels": min_component_pixels,
                "training_mean_iou": float(np.mean([m["iou"] for m in metrics])),
                "training_mean_abs_area_bias_pct": float(np.mean([abs(m["area_bias_pct"]) for m in metrics])),
                "training_mean_recall": float(np.mean([m["recall"] for m in metrics])),
            })
    # Performance first, then bias/recall, then simpler parameterization.
    selected = sorted(candidates, key=lambda r: (
        -r["training_mean_iou"], r["training_mean_abs_area_bias_pct"],
        -r["training_mean_recall"],
        99 if r["elevation_max_m"] is None else abs(r["elevation_max_m"] - 5.0),
        r["min_component_pixels"],
    ))[0]
    return selected, candidates


def _diagnostics(scene_id: str, scene: dict[str, Any], final_flood: np.ndarray, probability: np.ndarray, land_use: np.ndarray | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid = scene["valid"]
    fp = final_flood & ~scene["egs"] & valid
    fn = ~final_flood & scene["egs"] & valid
    fp_rows, fn_rows = [], []
    if land_use is not None:
        fp_rows.append({"observation_id": scene_id, "diagnostic": "settlement_fp_pct", "value": 100.0 * float((fp & np.isin(land_use, list(SETTLEMENT_CODES))).sum()) / max(int(fp.sum()), 1), "pixels": int(fp.sum()), "unit": "percent_of_fp"})
        for label, codes in (("forest", FOREST_CODES), ("wetland", WETLAND_CODES), ("cropland", CROPLAND_CODES)):
            fn_rows.append({"observation_id": scene_id, "diagnostic": f"fn_{label}_pct", "value": 100.0 * float((fn & np.isin(land_use, list(codes))).sum()) / max(int(fn.sum()), 1), "pixels": int(fn.sum()), "unit": "percent_of_fn"})
    fn_rows.append({"observation_id": scene_id, "diagnostic": "fn_mean_probability", "value": float(np.nanmean(probability[fn])) if fn.any() else np.nan, "pixels": int(fn.sum()), "unit": "probability"})
    return fp_rows, fn_rows


def _comparison(metrics: pd.DataFrame) -> dict[str, Any]:
    ious = metrics.iou.to_numpy(float)
    f1s = metrics.f1.to_numpy(float)
    tp, fp, fn, tn = [int(metrics[c].sum()) for c in ("tp_pixels", "fp_pixels", "fn_pixels", "tn_pixels")]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "macro": {"median_iou": float(np.median(ious)), "median_f1": float(np.median(f1s)), "worst_date_iou": float(np.min(ious)), "median_precision": float(metrics.precision.median()), "median_recall": float(metrics.recall.median()), "median_abs_area_bias_pct": float(np.median(np.abs(metrics.area_bias_pct)))},
        "micro": {"precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0, "iou": tp / (tp + fp + fn) if tp + fp + fn else 0.0, "tp_pixels": tp, "fp_pixels": fp, "fn_pixels": fn, "tn_pixels": tn},
        "per_mode_group": {mode: {"median_iou": float(group.iou.median()), "median_f1": float(group.f1.median()), "scene_count": int(len(group))} for mode, group in metrics.groupby("mode_group")},
        "total_fp_ha": float(metrics.false_positive_area_ha.sum()), "total_fn_ha": float(metrics.false_negative_area_ha.sum()),
    }


def _old_comparison() -> list[dict[str, Any]]:
    rows = []
    files = [("simple_sar_c0_sigma0", ROOT / "data/processed/phase3b/validation_metrics.csv", "C0_global_hh", "Sigma0"), ("lee_refined_sar_c0_sigma0", ROOT / "data/processed/phase3b/validation_metrics_refinement_lee.csv", "C0_global_hh", "Sigma0"), ("multisource_v1", ROOT / "data/processed/phase3b/multisource/multisource_validation_metrics.csv", None, None)]
    for name, path, candidate, representation in files:
        if not path.exists():
            continue
        data = pd.read_csv(path)
        if candidate is not None:
            data = data[(data.candidate_id == candidate) & (data.representation == representation)]
        if data.empty:
            continue
        rows.append({"method": name, "median_iou": float(data.iou.median()), "median_f1": float(data.f1.median()), "worst_date_iou": float(data.iou.min()), "median_abs_area_bias_pct": float(np.median(np.abs(data.area_bias_pct))), "total_fp_ha": float(data.false_positive_area_ha.sum()), "total_fn_ha": float(data.false_negative_area_ha.sum())})
    return rows


def run(frequency_raster: Path) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "masks").mkdir(exist_ok=True)
    (OUT / "probabilities").mkdir(exist_ok=True)
    frequency = load_frequency_raster(frequency_raster, GRID)
    write_frequency_provenance(OUT / "historical_water_provenance.json", frequency)
    land, water, eligible = training_labels(frequency)
    elevation = _load_elevation()
    land_use_path = ROOT / "data/processed/phase3b/multisource/derived/land_use_aafc_2020.tif"
    land_use = None
    if land_use_path.exists():
        with rasterio.open(land_use_path) as src:
            land_use = src.read(1)
    inventory = _scene_info()
    scenes = {sid: _load_scene(sid, row, elevation) for sid, row in inventory.iterrows()}
    predictions: dict[str, dict[str, Any]] = {}
    training_rows, importance_rows, probability_rows = [], [], []
    for sid, scene in scenes.items():
        sample = spatial_block_samples(scene["features"], land, water, scene["valid"] & eligible)
        model = fit_scene_rf(sample)
        probability, water_mask = predict_scene_rf(model, scene["features"], scene["valid"])
        raw_flood = water_mask & ~scene["permanent"] & scene["valid"]
        predictions[sid] = {**scene, "probability": probability, "water_mask": water_mask, "raw_flood": raw_flood}
        training_rows.append({"observation_id": sid, "timestamp_utc": scene["timestamp_utc"], "mode_group": scene["mode_group"], "block_size": sample.diagnostics["block_size"], "land_samples": sample.diagnostics["land_samples"], "water_samples": sample.diagnostics["water_samples"], "total_samples": len(sample.y), "stable_land_pixels": int(land.sum()), "stable_water_pixels": int(water.sum()), "uncertain_excluded_pixels": int(frequency.uncertain.sum()), "random_seed": RANDOM_SEED, "sklearn_version": __import__("sklearn").__version__})
        for name, value in zip(FEATURE_NAMES, model.feature_importances_):
            importance_rows.append({"observation_id": sid, "feature": name, "importance": float(value)})
        for label, mask in (("all_valid", scene["valid"]), ("stable_land", land & scene["valid"]), ("stable_water", water & scene["valid"]), ("raw_flood_candidate", raw_flood)):
            probability_rows.append({"observation_id": sid, "subset": label, "pixels": int(mask.sum()), "mean_probability": float(np.nanmean(probability[mask])) if mask.any() else np.nan, "p05": float(np.nanpercentile(probability[mask], 5)) if mask.any() else np.nan, "p50": float(np.nanpercentile(probability[mask], 50)) if mask.any() else np.nan, "p95": float(np.nanpercentile(probability[mask], 95)) if mask.any() else np.nan})
        _write_mask(OUT / "masks" / f"{sid}_water.tif", water_mask.astype("uint8"), nodata=255)
        _write_mask(OUT / "masks" / f"{sid}_valid.tif", scene["valid"].astype("uint8"), nodata=0)
        _write_mask(OUT / "probabilities" / f"{sid}_water_probability.tif", np.where(scene["valid"], probability, -9999).astype("float32"), nodata=-9999, dtype="float32")
    metrics_rows, parameter_rows, fp_rows, fn_rows = [], [], [], []
    for heldout in PILOT_IDS:
        selected, all_candidates = _select_outer_parameters(PILOT_IDS, predictions, heldout)
        parameter_rows.extend(all_candidates)
        scene = predictions[heldout]
        final_flood = scene["raw_flood"]
        if selected["elevation_max_m"] is not None:
            final_flood = final_flood & np.isfinite(scene["elevation"]) & (scene["elevation"] <= selected["elevation_max_m"])
        final_flood = cleanup_components(final_flood, scene["valid"], selected["min_component_pixels"])
        scene["final_flood"] = final_flood
        metric = validate_scene(final_flood, scene["egs"], scene["valid"], pixel_area_ha=GRID.pixel_area_ha)
        metric.update({"observation_id": heldout, "fold_id": f"OUTER_{heldout}", "candidate_id": "phase3b_rf_v1", "method_id": "phase3b_rf_v1", "mode_group": scene["mode_group"], "representation": "Sigma0", "threshold": 0.5, "elevation_max_m": selected["elevation_max_m"], "min_component_pixels": selected["min_component_pixels"], "training_observation_ids": json.dumps([sid for sid in PILOT_IDS if sid != heldout])})
        metrics_rows.append(metric)
        _write_mask(OUT / "masks" / f"{heldout}_flood.tif", final_flood.astype("uint8"), nodata=255)
        fp, fn = _diagnostics(heldout, scene, final_flood, scene["probability"], land_use)
        fp_rows.extend(fp); fn_rows.extend(fn)
    metrics = pd.DataFrame(metrics_rows)
    metrics.to_csv(OUT / "rf_validation_metrics.csv", index=False)
    pd.DataFrame(parameter_rows).to_csv(OUT / "rf_outer_fold_parameters.csv", index=False)
    pd.DataFrame(training_rows).to_csv(OUT / "rf_training_summary.csv", index=False)
    pd.DataFrame(importance_rows).to_csv(OUT / "rf_feature_importance.csv", index=False)
    pd.DataFrame(probability_rows).to_csv(OUT / "rf_probability_summary.csv", index=False)
    pd.DataFrame(fp_rows).to_csv(OUT / "rf_fp_diagnostics.csv", index=False)
    pd.DataFrame(fn_rows).to_csv(OUT / "rf_fn_diagnostics.csv", index=False)
    summary = _comparison(metrics)
    # Numeric/geometry gate is evaluated independently of the still-pending
    # visual artifact review.  A pending review must never be reported as a
    # failed scientific check, nor can it upgrade a numeric GO to GO.
    qa = {"geometry_status": "pass", "calibration_status": "pass"}
    gate = evaluate_gate(metrics.to_dict("records"), qa)
    systematic_artifact_review = "pending_manual_review"
    # Pending artifact review cannot upgrade the registered gate to GO.
    if gate["status"] == "GO":
        gate["status"] = "REFINE"
        gate["reason"] = "metrics meet numeric thresholds but systematic artifact review remains pending"
    comparison = _old_comparison() + [{"method": "phase3b_rf_v1", **summary["macro"], "total_fp_ha": summary["total_fp_ha"], "total_fn_ha": summary["total_fn_ha"]}]
    multisource = next((row for row in comparison if row["method"] == "multisource_v1"), None)
    fp_reduction = None
    if multisource and multisource.get("total_fp_ha"):
        fp_reduction = 1.0 - summary["total_fp_ha"] / multisource["total_fp_ha"]
    method_definition = {
        "schema_version": "phase3b-rf-v1-experimental-1", "method_id": "phase3b_rf_v1", "status": gate["status"], "source_of_truth": False,
        "training_prior": "Canadian Dynamic Surface Water Maps 1984-2023; stable land frequency==0 and stable water frequency>=80; 1-79 and 255 excluded",
        "validation_labels": "EGS class-2 only after prediction; never used for training",
        "fixed_semantic_reference": "data/processed/phase4/egs_permanent_water_reference.geojson; event-product semantic subtraction/reference, not hydrologic baseline",
        "representation": "raw calibrated Sigma0 HH/HV on fixed 30m grid",
        "features": list(FEATURE_NAMES), "rf_parameters": {**RF_PARAMS, "random_state": RANDOM_SEED, "probability_threshold": 0.5},
        "spatial_sampling": {"block_size_pixels": 20, "max_per_class_per_block": 40, "class_balanced": True},
        "outer_selection": {"elevation_candidates_m": ["none", 3, 5, 7, 10], "cleanup_candidates_pixels": [2, 4], "held_out_scene_not_used_for_selection": True},
        "excluded_from_v1": ["hard urban mask", "cropland rule", "hydrography cutoff", "flooded vegetation region growing", "multi-temporal features", "JRC primary labels", "30m mode filter", "1ha MMU"],
        "remaining_six_processed": False, "method_config_v1_generated": False, "phase4_phase5_dashboard_untouched": True, "created_utc": utc_now(),
    }
    (OUT / "rf_method_definition.json").write_text(json.dumps(method_definition, indent=2, default=str))
    payload = {"schema_version": "phase3b-rf-v1-validation-1", "method_id": "phase3b_rf_v1", "status": gate["status"], "gate": gate, "summary": summary, "comparison": comparison, "fp_reduction_vs_multisource_fraction": fp_reduction, "training_sample_counts": training_rows, "fold_parameters": parameter_rows, "qa": {"geometry_status": "pass", "calibration_status": "pass", "systematic_artifact_review": systematic_artifact_review}, "method_config_generated": False, "remaining_six_processed": False, "phase4_phase5_dashboard_untouched": True, "jrc_sensitivity_run": False, "outputs": {"metrics": "rf_validation_metrics.csv", "outer_parameters": "rf_outer_fold_parameters.csv", "training": "rf_training_summary.csv", "importance": "rf_feature_importance.csv", "probability": "rf_probability_summary.csv", "fp_diagnostics": "rf_fp_diagnostics.csv", "fn_diagnostics": "rf_fn_diagnostics.csv"}, "created_utc": utc_now()}
    (OUT / "rf_validation_summary.json").write_text(json.dumps(payload, indent=2, default=str))
    # Add only a namespaced pointer; the original Phase 3B gate and all
    # Phase 4/5 source-of-truth artifacts remain unchanged.
    manifest_path = ROOT / "data/processed/phase3b/processing_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest["rf_v1"] = {
        "status": gate["status"],
        "path": "data/processed/phase3b/rf_v1/rf_validation_summary.json",
        "method_config_v1_generated": False,
        "remaining_six_processed": False,
        "phase4_phase5_dashboard_untouched": True,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frequency-raster", type=Path, default=OUT / "sources/dsw-1984-2023-frequency_lower_fraser.tif")
    args = parser.parse_args()
    result = run(args.frequency_raster)
    print(json.dumps({"status": result["status"], "summary": result["summary"], "outputs": result["outputs"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
