#!/usr/bin/env python
"""Formal, leakage-safe multisource refinement for the Phase 3B Pilot.

This runner is intentionally limited to the five existing RCM/EGS overlap
scenes.  It never launches SNAP, changes Phase 4/5, creates a frozen method
configuration, or processes the remaining six Level-1 acquisitions.
"""
from __future__ import annotations

import argparse
import hashlib
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.physical_constraints import (
    AAFC_CROPLAND_CODES,
    PhysicalContext,
    apply_multisource_constraints,
    prepare_physical_context,
    sha256_file,
)
from analysis.rcm_level1 import PILOT
from analysis.rcm_preprocessing import CommonGrid
from analysis.validation import evaluate_gate, validate_scene
from scripts.phase3b_pipeline import permanent_and_egs_masks


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/phase3b"
MULTI = OUT / "multisource"
SOURCES = MULTI / "sources"
DERIVED = MULTI / "derived"
MASKS = MULTI / "masks"
CACHE = OUT / "cache/refinement_lee"
GRID = CommonGrid()
PILOT_IDS = [pd.Timestamp(item[0]).strftime("%Y%m%dT%H%M%SZ") for item in PILOT.values()]
METHOD_ID = "phase3b_multisource_v1"
ELEVATION_CANDIDATES_M = (3.0, 5.0, 7.0, 10.0)
CROPLAND_MARGIN_CANDIDATES_DB = (2.0, 3.0, 4.0)

SOURCE_FILENAMES = {
    "land_use": "aafc_landuse_2020_aoi.tif",
    "land_use_classes": "aafc_landuse_classes.csv",
    "streams": "bc_fwa_streams_aoi.geojson",
    "rivers": "bc_fwa_rivers_aoi.geojson",
    "lakes": "bc_fwa_lakes_aoi.geojson",
    "wetlands": "bc_fwa_wetlands_aoi.geojson",
    "floodplains": "bc_historical_floodplains_aoi.geojson",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_file(name: str) -> Path:
    return SOURCES / SOURCE_FILENAMES[name]


def stage_sources(source_dir: Path) -> dict[str, str]:
    """Copy the small, AOI-clipped, independently sourced inputs once.

    ``source_dir`` is an explicitly supplied scratch folder.  The runner does
    not fetch remote data; staging makes the formal method reproducible and
    avoids startup/network coupling.
    """
    source_dir = Path(source_dir)
    aliases = {
        "land_use": "aafc_landuse_2020_aoi.tif",
        "land_use_classes": "aafc_landuse_classes.csv",
        "streams": "bc_streams.geojson",
        "rivers": "bc_rivers.geojson",
        "lakes": "bc_lakes.geojson",
        "wetlands": "bc_wetlands.geojson",
        "floodplains": "bc_floodplains.geojson",
    }
    SOURCES.mkdir(parents=True, exist_ok=True)
    staged = {}
    for name, external_name in aliases.items():
        source = source_dir / external_name
        destination = _source_file(name)
        if not source.exists():
            raise FileNotFoundError(f"Required multisource input was not found: {source}")
        if not destination.exists() or sha256_file(source) != sha256_file(destination):
            shutil.copy2(source, destination)
        staged[name] = str(destination.relative_to(ROOT))
    return staged


def _dem_paths() -> list[Path]:
    provenance_path = OUT / "dem_provenance.json"
    if not provenance_path.exists():
        raise FileNotFoundError("Missing existing Phase 3B DEM provenance")
    data = json.loads(provenance_path.read_text())
    paths = [Path(item["path"]) for item in data.get("tiles", [])]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Existing SNAP DEM cache is unavailable: {missing}")
    return paths


def _source_provenance() -> dict[str, Any]:
    files = {name: _source_file(name) for name in SOURCE_FILENAMES}
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Multisource inputs must be staged first: " + ", ".join(missing))
    dem_original = json.loads((OUT / "dem_provenance.json").read_text())
    return {
        "schema_version": "phase3b-multisource-inputs-1",
        "created_utc": utc_now(),
        "independence_boundary": "No EGS class-2 geometry, label, boundary-distance, ALR overlap, or event-derived flood layer is an input feature.",
        "aafc_2020_land_use": {
            "source": "Agriculture and Agri-Food Canada 2020 Land Use, 30 m AOI extract",
            "dataset_url": "https://open.canada.ca/data/en/dataset/7a098ea9-cc31-4d79-b326-89f6cd1fbb7d",
            "year": 2020,
            "cropland_codes": list(AAFC_CROPLAND_CODES),
            "path": str(files["land_use"].relative_to(ROOT)),
            "sha256": sha256_file(files["land_use"]),
            "class_table_path": str(files["land_use_classes"].relative_to(ROOT)),
            "class_table_sha256": sha256_file(files["land_use_classes"]),
        },
        "bc_freshwater_atlas": {
            "source": "BC Freshwater Atlas AOI extracts: streams, rivers, and lakes",
            "dataset_url": "https://open.canada.ca/data/en/dataset/92344413-8035-4c08-b996-65a9b3f62fca",
            "extraction_date_utc": utc_now(),
            "binary_mask_role": "QA and confidence context only; not a hard exclusion in multisource v1",
            "layers": {
                name: {"path": str(files[name].relative_to(ROOT)), "sha256": sha256_file(files[name])}
                for name in ("streams", "rivers", "lakes", "wetlands", "floodplains")
            },
        },
        "dem": {
            "source": "Existing ESA SNAP Copernicus 30 m Global DEM provenance",
            "phase3b_dem_provenance": str((OUT / "dem_provenance.json").relative_to(ROOT)),
            "tiles": dem_original.get("tiles", []),
        },
        "grid": GRID.as_dict(),
        "fixed_semantic_reference": {
            "path": "data/processed/phase4/egs_permanent_water_reference.geojson",
            "semantics": "fixed EGS semantic permanent-water reference",
            "not_semantics": ["normal water", "pre-event baseline", "hydrologic baseline"],
        },
    }


def prepare_context() -> PhysicalContext:
    provenance = _source_provenance()
    context = prepare_physical_context(
        grid=GRID,
        dem_paths=_dem_paths(),
        land_use_path=_source_file("land_use"),
        hydro_paths=[_source_file(name) for name in ("streams", "rivers", "lakes")],
        wetland_paths=[_source_file("wetlands")],
        output_dir=DERIVED,
        source_metadata=provenance,
    )
    MULTI.mkdir(parents=True, exist_ok=True)
    (MULTI / "multisource_source_provenance.json").write_text(json.dumps(provenance, indent=2, default=str))
    (MULTI / "multisource_method_definition.json").write_text(json.dumps({
        "method_id": METHOD_ID,
        "version": 1,
        "representation": "Sigma0-HH",
        "sar_candidate": "Existing leakage-safe LOODO C0 global HH threshold from the Lee-filtered cache; method metadata retains mode group for future matched-temporal work.",
        "filter_policy": "Existing pre-registered Lee-filtered cache; 5x5 at 16 m and 3x3 at 30 m before 30 m aggregation.",
        "constraints": {
            "elevation_candidates_m": list(ELEVATION_CANDIDATES_M),
            "cropland_extra_darkness_candidates_db": list(CROPLAND_MARGIN_CANDIDATES_DB),
            "cropland_codes": list(AAFC_CROPLAND_CODES),
            "component_cleanup": "8-connectivity, remove components under two pixels, fill one-pixel holes",
            "hydrography": "Stored as distance/connectivity QA only; not a binary exclusion.",
        },
        "reference_handling": "Classified water is reduced by the fixed EGS semantic permanent-water reference. EGS class-2 is validation only.",
        "future_temporal_interface": {
            "status": "metadata only; no change features are generated in v1",
            "required_scene_fields": ["observation_id", "timestamp_utc", "beam_mode", "mode_group", "orbit_direction", "representation", "source_resolution_m"],
            "candidate_same_mode_sequences": {
                "16M16": ["20251213T141623Z", "20251217T141634Z", "20251221T141646Z"],
                "16M9": ["20251214T142421Z", "20251218T142431Z"],
                "SC30MA": ["20251214T014240Z", "20251218T014217Z", "20251222T014227Z"],
                "SC30MB": ["20251215T015036Z", "20251219T015011Z", "20251223T015021Z"],
            },
            "future_features_not_implemented": ["delta Sigma0", "power ratio", "temporal rank", "persistent darkening", "recovery signal"],
        },
    }, indent=2, default=str))
    return context


def _load_context() -> PhysicalContext:
    # Rebuild deterministically from staged sources and existing DEM cache so
    # derived files can never silently become an untracked source of truth.
    return prepare_context()


def _pilot_inventory() -> pd.DataFrame:
    inventory = pd.read_csv(OUT / "level1_inventory.csv")
    pilot = inventory[inventory["observation_id"].isin(PILOT_IDS)].copy()
    expected = set(PILOT_IDS)
    found = set(pilot.observation_id)
    if found != expected:
        raise RuntimeError(f"Expected five pilot observations {expected}, found {found}")
    return pilot.set_index("observation_id").loc[PILOT_IDS]


def _base_thresholds() -> pd.DataFrame:
    path = OUT / "validation_metrics_refinement_lee.csv"
    data = pd.read_csv(path)
    selected = data[(data.candidate_id == "C0_global_hh") & (data.representation == "Sigma0")].copy()
    if len(selected) != 5 or set(selected.observation_id) != set(PILOT_IDS):
        raise RuntimeError("Expected five leakage-safe C0/Sigma0/Lee fold thresholds")
    selected["sar_threshold_db"] = selected["thresholds"].map(lambda text: float(json.loads(text)["global_hh"]))
    return selected.set_index("observation_id").loc[PILOT_IDS]


def _fit_fold_constraints(
    *,
    train_ids: list[str],
    base_masks: dict[str, np.ndarray],
    arrays: dict[str, dict[str, np.ndarray]],
    references: dict[str, np.ndarray],
    threshold_db: float,
    context: PhysicalContext,
) -> tuple[dict[str, float], list[dict[str, float]]]:
    """Choose only pre-registered v1 parameters from training scenes."""
    scored: list[dict[str, float]] = []
    for elevation_max_m in ELEVATION_CANDIDATES_M:
        for crop_margin_db in CROPLAND_MARGIN_CANDIDATES_DB:
            metrics = []
            for sid in train_ids:
                prediction, _ = apply_multisource_constraints(
                    base_masks[sid], arrays[sid]["sigma_hh_db"], arrays[sid]["valid"], context,
                    hh_threshold_db=threshold_db,
                    elevation_max_m=elevation_max_m,
                    cropland_extra_darkness_db=crop_margin_db,
                )
                metrics.append(validate_scene(prediction, references[sid], arrays[sid]["valid"], pixel_area_ha=GRID.pixel_area_ha))
            scored.append({
                "elevation_max_m": elevation_max_m,
                "cropland_extra_darkness_db": crop_margin_db,
                "training_mean_iou": float(np.mean([row["iou"] for row in metrics])),
                "training_mean_abs_area_bias_pct": float(np.mean([abs(row["area_bias_pct"]) for row in metrics])),
                "training_mean_recall": float(np.mean([row["recall"] for row in metrics])),
            })
    # Deterministic tie-breaks favor lower area bias, higher recall, and the
    # simplest physically plausible thresholds.  No held-out reference enters.
    best = sorted(
        scored,
        key=lambda row: (
            -row["training_mean_iou"], row["training_mean_abs_area_bias_pct"],
            -row["training_mean_recall"], abs(row["elevation_max_m"] - 5.0),
            abs(row["cropland_extra_darkness_db"] - 3.0),
        ),
    )[0]
    return {"elevation_max_m": best["elevation_max_m"], "cropland_extra_darkness_db": best["cropland_extra_darkness_db"]}, scored


def _write_mask(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path, "w", driver="GTiff", height=GRID.height, width=GRID.width,
        count=1, dtype="uint8", crs=GRID.crs, transform=GRID.transform,
        nodata=255, compress="deflate",
    ) as destination:
        destination.write(np.asarray(mask, dtype="uint8"), 1)


def _diagnostic_rows(
    *,
    observation_id: str,
    method: str,
    prediction: np.ndarray,
    reference: np.ndarray,
    valid: np.ndarray,
    context: PhysicalContext,
    permanent: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fp = prediction & ~reference & valid
    fn = ~prediction & reference & valid
    fp_rows: list[dict[str, Any]] = []
    fn_rows: list[dict[str, Any]] = []

    def append_by_category(rows: list[dict[str, Any]], kind: str, diagnostic: str, categories: dict[str, np.ndarray], mask: np.ndarray) -> None:
        total = max(int(mask.sum()), 1)
        for label, selector in categories.items():
            pixels = int((mask & selector).sum())
            rows.append({
                "observation_id": observation_id, "method": method, "kind": kind,
                "diagnostic": diagnostic, "category": label, "pixels": pixels,
                "area_ha": pixels * GRID.pixel_area_ha, "pct_of_kind": 100.0 * pixels / total,
            })

    land_classes = sorted(int(value) for value in np.unique(context.land_use[context.land_use_valid]))
    append_by_category(fp_rows, "FP", "land_use", {str(code): context.land_use == code for code in land_classes}, fp)
    append_by_category(fn_rows, "FN", "land_use", {str(code): context.land_use == code for code in land_classes}, fn)
    elevation = context.elevation_m
    append_by_category(fp_rows, "FP", "elevation_band_m", {
        "<=3": elevation <= 3, "3-5": (elevation > 3) & (elevation <= 5),
        "5-7": (elevation > 5) & (elevation <= 7), "7-10": (elevation > 7) & (elevation <= 10),
        ">10": elevation > 10,
    }, fp)
    distance = context.hydro_distance_m
    append_by_category(fp_rows, "FP", "hydro_distance_m", {
        "<=30": distance <= 30, "30-60": (distance > 30) & (distance <= 60),
        "60-90": (distance > 60) & (distance <= 90), "90-150": (distance > 90) & (distance <= 150),
        "150-300": (distance > 150) & (distance <= 300), ">300": distance > 300,
    }, fp)
    permanent_edge = np.logical_xor(permanent, ndimage.binary_erosion(permanent))
    permanent_distance = ndimage.distance_transform_edt(~permanent_edge) * GRID.resolution
    append_by_category(fn_rows, "FN", "permanent_water_boundary_m", {
        "<=30": permanent_distance <= 30, "30-60": (permanent_distance > 30) & (permanent_distance <= 60),
        ">60": permanent_distance > 60,
    }, fn)
    return fp_rows, fn_rows


def _summary(metrics: pd.DataFrame) -> dict[str, Any]:
    ious, f1s = metrics.iou.to_numpy(float), metrics.f1.to_numpy(float)
    tp, fp, fn, tn = (int(metrics[column].sum()) for column in ("tp_pixels", "fp_pixels", "fn_pixels", "tn_pixels"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "macro": {
            "median_iou": float(np.median(ious)), "median_f1": float(np.median(f1s)),
            "worst_date_iou": float(np.min(ious)), "median_precision": float(np.median(metrics.precision)),
            "median_recall": float(np.median(metrics.recall)),
            "median_abs_area_bias_pct": float(np.median(np.abs(metrics.area_bias_pct))),
        },
        "micro": {
            "tp_pixels": tp, "fp_pixels": fp, "fn_pixels": fn, "tn_pixels": tn,
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "iou": tp / (tp + fp + fn) if tp + fp + fn else 0.0,
        },
        "per_mode_group": {
            mode: {
                "scene_count": int(len(group)), "median_iou": float(group.iou.median()),
                "median_f1": float(group.f1.median()), "median_abs_area_bias_pct": float(np.median(np.abs(group.area_bias_pct))),
            }
            for mode, group in metrics.groupby("mode_group")
        },
        "total_fp_ha": float(metrics.false_positive_area_ha.sum()),
        "total_fn_ha": float(metrics.false_negative_area_ha.sum()),
        "per_date": metrics.to_dict("records"),
    }


def _comparison_row(name: str, metrics: pd.DataFrame) -> dict[str, Any]:
    summary = _summary(metrics)
    macro, micro = summary["macro"], summary["micro"]
    return {
        "method": name,
        "median_iou": macro["median_iou"], "median_f1": macro["median_f1"],
        "worst_date_iou": macro["worst_date_iou"], "median_precision": macro["median_precision"],
        "median_recall": macro["median_recall"], "median_abs_area_bias_pct": macro["median_abs_area_bias_pct"],
        "pooled_precision": micro["precision"], "pooled_recall": micro["recall"],
        "total_fp_ha": summary["total_fp_ha"], "total_fn_ha": summary["total_fn_ha"],
    }


def validate_multisource() -> dict[str, Any]:
    context = _load_context()
    pilot = _pilot_inventory()
    base_thresholds = _base_thresholds()
    permanent, _ = permanent_and_egs_masks(pilot.iloc[0].egs_observation_id)
    arrays: dict[str, dict[str, np.ndarray]] = {}
    references: dict[str, np.ndarray] = {}
    for observation_id, row in pilot.iterrows():
        payload = np.load(CACHE / observation_id / "grid_arrays.npz")
        valid = payload["common_valid"].astype(bool) & context.valid
        arrays[observation_id] = {"sigma_hh_db": payload["sigma_hh_db"], "valid": valid}
        _, references[observation_id] = permanent_and_egs_masks(row.egs_observation_id)

    rows: list[dict[str, Any]] = []
    parameters: list[dict[str, Any]] = []
    fp_rows: list[dict[str, Any]] = []
    fn_rows: list[dict[str, Any]] = []
    for heldout in PILOT_IDS:
        threshold = float(base_thresholds.loc[heldout, "sar_threshold_db"])
        base_masks: dict[str, np.ndarray] = {}
        for sid in PILOT_IDS:
            raw = (arrays[sid]["sigma_hh_db"] < threshold) & arrays[sid]["valid"] & ~permanent
            # Preserve the previously validated two-pixel cleanup before the
            # new gates; the physical module repeats it after gates so removal
            # cannot create isolated artifacts.
            from analysis.water_classification import cleanup_mask
            base_masks[sid] = cleanup_mask(raw, arrays[sid]["valid"], min_component_pixels=2)
        train_ids = [sid for sid in PILOT_IDS if sid != heldout]
        selected, all_candidates = _fit_fold_constraints(
            train_ids=train_ids, base_masks=base_masks, arrays=arrays, references=references,
            threshold_db=threshold, context=context,
        )
        parameters.append({
            "fold_id": f"LOODO_{heldout}", "heldout_observation_id": heldout,
            "training_observation_ids": json.dumps(train_ids), "sar_threshold_db": threshold,
            **selected,
            "candidate_sets": json.dumps({"elevation_max_m": ELEVATION_CANDIDATES_M, "cropland_extra_darkness_db": CROPLAND_MARGIN_CANDIDATES_DB}),
            "training_selection": json.dumps(all_candidates, sort_keys=True),
        })
        prediction, flags = apply_multisource_constraints(
            base_masks[heldout], arrays[heldout]["sigma_hh_db"], arrays[heldout]["valid"], context,
            hh_threshold_db=threshold, **selected,
        )
        metric = validate_scene(prediction, references[heldout], arrays[heldout]["valid"], pixel_area_ha=GRID.pixel_area_ha)
        metric.update({
            "observation_id": heldout, "fold_id": f"LOODO_{heldout}", "method_id": METHOD_ID,
            "representation": "Sigma0", "candidate_id": "C0_global_hh", "mode_group": pilot.loc[heldout, "mode_group"],
            "sar_threshold_db": threshold, **selected,
            "hydro_within_90m_pct": float((prediction & flags["hydro_within_90m"]).sum() / max(prediction.sum(), 1) * 100),
            "hydro_within_300m_pct": float((prediction & flags["hydro_within_300m"]).sum() / max(prediction.sum(), 1) * 100),
            "hydro_connected_pct": float((prediction & flags["hydro_connected"]).sum() / max(prediction.sum(), 1) * 100),
            "context_valid_pct": float(context.valid.mean() * 100),
        })
        rows.append(metric)
        mask_name = f"{heldout}_{METHOD_ID}_flood.tif"
        _write_mask(MASKS / mask_name, prediction)
        new_fp, new_fn = _diagnostic_rows(
            observation_id=heldout, method=METHOD_ID, prediction=prediction,
            reference=references[heldout], valid=arrays[heldout]["valid"], context=context, permanent=permanent,
        )
        fp_rows.extend(new_fp); fn_rows.extend(new_fn)

    metrics = pd.DataFrame(rows)
    fold_parameters = pd.DataFrame(parameters)
    metrics.to_csv(MULTI / "multisource_validation_metrics.csv", index=False)
    fold_parameters.to_csv(MULTI / "multisource_fold_parameters.csv", index=False)
    pd.DataFrame(fp_rows).to_csv(MULTI / "multisource_fp_diagnostics.csv", index=False)
    pd.DataFrame(fn_rows).to_csv(MULTI / "multisource_fn_diagnostics.csv", index=False)
    qa = metrics[["observation_id", "mode_group", "context_valid_pct", "hydro_within_90m_pct", "hydro_within_300m_pct", "hydro_connected_pct"]].copy()
    qa["elevation_source"] = "existing SNAP Copernicus 30 m DEM provenance"
    qa["land_use_source"] = "AAFC 2020 Land Use 30 m"
    qa["hydrography_role"] = "QA/confidence context only; no binary distance exclusion"
    qa.to_csv(MULTI / "multisource_observation_qa.csv", index=False)

    original = pd.read_csv(OUT / "validation_metrics.csv")
    original = original[(original.candidate_id == "C0_global_hh") & (original.representation == "Sigma0")].copy()
    refined = pd.read_csv(OUT / "validation_metrics_refinement_lee.csv")
    refined = refined[(refined.candidate_id == "C0_global_hh") & (refined.representation == "Sigma0")].copy()
    comparison = pd.DataFrame([
        _comparison_row("simple_sar_c0_sigma0", original),
        _comparison_row("lee_refined_sar_c0_sigma0", refined),
        _comparison_row(METHOD_ID, metrics),
    ])
    comparison.to_csv(MULTI / "multisource_comparison.csv", index=False)
    gate = evaluate_gate(metrics.to_dict("records"), {"geometry_status": "pass", "calibration_status": "pass", "systematic_artifact_review": "pass"})
    summary = {
        "schema_version": "phase3b-multisource-validation-1",
        "method_id": METHOD_ID,
        "status": gate["status"],
        "gate": gate,
        "method_config_generated": False,
        "remaining_six_processed": False,
        "sentinel2_holdout_run": False,
        "hydrography_binary_role": "none; QA/confidence only",
        "selection_policy": "LOODO; only the four training dates select elevation and cropland-darkness candidates.",
        "summary": _summary(metrics),
        "comparison": comparison.to_dict("records"),
        "outputs": {
            "metrics": "multisource_validation_metrics.csv", "fold_parameters": "multisource_fold_parameters.csv",
            "fp_diagnostics": "multisource_fp_diagnostics.csv", "fn_diagnostics": "multisource_fn_diagnostics.csv",
            "observation_qa": "multisource_observation_qa.csv", "comparison": "multisource_comparison.csv",
        },
        "created_utc": utc_now(),
    }
    (MULTI / "multisource_validation_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (MULTI / "multisource_gate.json").write_text(json.dumps({
        "status": gate["status"], "gate": gate,
        "decision": "FAIL preserves multisource v1 as an experimental result. It cannot freeze method_config_v1.json or process the remaining six scenes.",
        "method_config_v1_generated": False, "remaining_six_processed": False,
        "sentinel2_holdout_run": False, "created_utc": utc_now(),
    }, indent=2, default=str))

    # Keep the original final decision intact; attach a namespaced record only.
    manifest_path = OUT / "processing_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest["multisource_v1"] = {
        "status": gate["status"], "path": str((MULTI / "multisource_validation_summary.json").relative_to(ROOT)),
        "method_config_v1_generated": False, "remaining_six_processed": False,
        "phase4_phase5_dashboard_untouched": True,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("stage-sources", "prepare-context", "validate", "run", "status"))
    parser.add_argument("--source-dir", type=Path, help="Scratch directory holding the AOI-clipped source extracts")
    args = parser.parse_args()
    if args.step == "stage-sources":
        if args.source_dir is None:
            parser.error("stage-sources requires --source-dir")
        print(json.dumps(stage_sources(args.source_dir), indent=2))
    elif args.step == "prepare-context":
        context = prepare_context()
        print(json.dumps({"valid_pct": float(context.valid.mean() * 100), "hydro_pixels": int(context.hydrography.sum()), "cropland_pixels": int(context.cropland.sum())}, indent=2))
    elif args.step == "validate":
        print(json.dumps(validate_multisource(), indent=2, default=str))
    elif args.step == "run":
        prepare_context()
        print(json.dumps(validate_multisource(), indent=2, default=str))
    else:
        path = MULTI / "multisource_validation_summary.json"
        print(path.read_text() if path.exists() else "No multisource validation has been run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
