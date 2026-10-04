"""Closed Phase 3B RF v2 policy: no EGS training or parameter search."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
from scipy import ndimage

from .rf_classification import FEATURE_NAMES, RANDOM_SEED, RF_PARAMS

METHOD_ID = "phase3b_rf_v2_final"
REASONS = {
    "normal_terrain": 1, "terrain_exception": 2, "terrain_rejected": 4,
    "normal_component": 8, "small_component_retained": 16,
    "cleanup_removed": 32, "permanent_subtraction": 64,
}


def method_definition(grid: Any, fresh_grid: Any) -> dict[str, Any]:
    """Pre-result specification, not a successful method_config_v1.json."""
    definition = {
        "schema_version": "phase3b-final-1", "method_id": METHOD_ID,
        "policy_frozen": True, "source_of_truth": False,
        "features": list(FEATURE_NAMES), "rf_parameters": {**RF_PARAMS, "random_state": RANDOM_SEED},
        "training": {"frequency_years": "1984-2023", "land": "frequency == 0",
                     "water": "frequency >= 80, nodata excluded", "uncertain": "1-79 excluded",
                     "block_pixels": 20, "cap_per_class_per_block": 40, "balanced": True,
                     "EGS_used_for_training": False},
        "probability_threshold": 0.50, "elevation_max_m": 5.0,
        "exception_score": 0.90, "hydro_distance_max_m": 60.0,
        "terrain_exception": "high-confidence hydrography-proximal terrain exception; not hydraulic-connectivity proof",
        "dem_semantics": "Copernicus DSM, not bare-earth DTM",
        "connectivity": 8, "min_component_pixels": 4,
        "small_exception": "mean score >= 0.90 AND ALL component pixels hydro distance <= 60 m",
        "cleanup_order": "semantic permanent-water subtraction, terrain policy, component cleanup",
        "permanent_reference": "fixed initial-product EGS semantic class 1, not normal or observed pre-event water",
        "primary_reference": "original EGS class 2 reprojected once, center-rasterized once to 30 m",
        "legacy_reference": "Phase4 20m-vectorized reference center-rasterized to 30m; comparison only",
        "grid": grid.as_dict(), "fresh_grid": fresh_grid.as_dict(),
        "fresh_policy": "same RF trained on main AOI historical labels; no fresh-AOI training or tuning",
        "parameter_search": False, "additional_iterations_allowed": False,
        "reason_bits": REASONS,
    }
    definition["policy_sha256"] = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    return definition


def final_masks(probability, valid, permanent, elevation, hydro_distance):
    """Return deterministic water/flood masks and overlapping QA reason bits."""
    p = np.asarray(probability)
    valid = np.asarray(valid, bool) & np.isfinite(p)
    permanent = np.asarray(permanent, bool)
    water = valid & (p >= 0.50)
    raw = water & ~permanent
    normal = raw & np.isfinite(elevation) & (elevation <= 5.0)
    exception = raw & np.isfinite(elevation) & (elevation > 5.0) & (p >= 0.90) & (hydro_distance <= 60.0)
    terrain = normal | exception
    labels, count = ndimage.label(terrain, np.ones((3, 3), dtype=bool))
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    keep = sizes >= 4
    keep[0] = False
    small_ids = []
    for label in range(1, count + 1):
        component = labels == label
        if sizes[label] < 4 and p[component].mean() >= 0.90 and np.all(hydro_distance[component] <= 60.0):
            keep[label] = True
            small_ids.append(label)
    small = np.isin(labels, small_ids) & terrain
    ordinary = terrain & (sizes[labels] >= 4)
    flood = keep[labels] & terrain
    flags = {"normal_terrain": normal, "terrain_exception": exception,
             "terrain_rejected": raw & ~terrain, "normal_component": ordinary,
             "small_component_retained": small, "cleanup_removed": terrain & ~flood,
             "permanent_subtraction": water & permanent}
    codes = np.zeros(p.shape, dtype="uint8")
    for name, mask in flags.items():
        codes[mask] |= REASONS[name]
    return {"water": water, "raw_flood": raw, "terrain": terrain, "flood": flood,
            "reason_codes": codes, **flags}


def object_diagnostics(predicted, reference, valid):
    labels, count = ndimage.label(reference & valid, np.ones((3, 3), bool))
    any_hit = quarter_hit = 0
    for label in range(1, count + 1):
        component = labels == label
        hits = (component & predicted).sum()
        any_hit += hits > 0
        quarter_hit += hits / component.sum() >= 0.25
    return {"reference_components": int(count), "components_detected_any": int(any_hit),
            "components_detected_25pct": int(quarter_hit),
            "object_detection_rate_25pct": float(quarter_hit / count) if count else None}


def final_gate(rows, qa):
    """Final binary decision; REFINE is no longer permitted. No missing QA pass."""
    from .validation import evaluate_gate
    rows = list(rows)
    result = evaluate_gate(rows, qa)
    checks = {
        "five_unique_scenes": len(rows) == 5 and len({r["observation_id"] for r in rows}) == 5,
        "median_iou_ge_050": bool(np.median([r["iou"] for r in rows]) >= .50),
        "median_f1_ge_067": bool(np.median([r["f1"] for r in rows]) >= .67),
        "every_iou_ge_035": all(r["iou"] >= .35 for r in rows),
        "every_f1_ge_052": all(r["f1"] >= .52 for r in rows),
        "every_mode_median_iou_ge_045": all(result.get("per_mode_median_iou", {}).get(m, 0) >= .45 for m in ("stripmap16_desc", "scansar30_asc")),
        "median_absolute_bias_le_25": bool(np.median([abs(r["area_bias_pct"]) for r in rows]) <= 25),
        "every_absolute_bias_le_50": all(abs(r["area_bias_pct"]) <= 50 for r in rows),
        **{key: qa.get(key) in ("pass", "passed") for key in
           ("calibration_status", "geometry_status", "systematic_artifact_review", "provenance_status")},
    }
    return {**result, "status": "GO" if all(checks.values()) else "FINAL EXPERIMENTAL FAIL",
            "checks": checks, "failed_checks": [key for key, value in checks.items() if not value],
            "frozen": True, "additional_research_allowed": False,
            "method_config_generated": False, "remaining_six_processed": False,
            "phase4b_promoted": False}
