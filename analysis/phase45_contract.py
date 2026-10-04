"""Small metadata bridge for the retained EGS Phase 4/5 production workflow.

This module never runs a classifier, retrieves external data, or alters geometry.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def method_selection(repo: Path) -> dict:
    gate_path = repo / "data/processed/phase3b/rf_v2_final/final_gate_status.json"
    gate = json.loads(gate_path.read_text())
    if gate["status"] != "FINAL EXPERIMENTAL FAIL" or not gate["frozen"]:
        raise ValueError("Stage-1 integration requires the frozen final Phase 3B failure record")
    return {
        "project_stage": "Translation & Impact Communication",
        "production_spatial_source": "NRCan EGS RCM-derived operational flood extent",
        "phase3b_status": gate["status"],
        "phase3b_gate_path": str(gate_path.relative_to(repo)),
        "phase3b_gate_sha256": hashlib.sha256(gate_path.read_bytes()).hexdigest(),
        "level1_promoted": False,
        "grid_boundary": "Phase 4/5: EPSG:32610, 20 m, 300x300, 0.04 ha/pixel; frozen experimental Phase 3B: 30 m, 200x200, 0.09 ha/pixel. Do not mix masks or statistics.",
        "rationale": "Independent RCM Level-1 analysis evaluated automated flood extraction. Because the final experimental classifier did not meet the pre-registered GO gate, downstream temporal and impact analysis retains operational EGS flood extent.",
        "resolution_caveat": "Accessible Level-1 research imagery was 16 m/30 m; matching Level-1 inputs for the 5 m EGS acquisitions were unavailable locally. Finer source imagery may contribute to differences alongside processing, filtering, ancillary data, vectorization and QA; no single-cause explanation is established.",
    }


def recovery_validation(agreement: dict, rcm_timestamp: str, s2_timestamp: str) -> dict:
    from datetime import datetime

    rcm = datetime.fromisoformat(rcm_timestamp.replace("Z", "+00:00"))
    s2 = datetime.fromisoformat(s2_timestamp.replace("Z", "+00:00"))
    return {
        "prediction_source": "Fixed OBS01 EGS class-1 reference union OBS07 EGS class-2 flood",
        "prediction_observation_id": "OBS07",
        "prediction_timestamp_utc": rcm.isoformat(),
        "comparison_source": "Sentinel-2C L2A NDWI > 0; SCL exclusion; categorical mode aggregation to 20 m",
        "comparison_item_id": "S2C_T10UEV_20251227T191058_L2A",
        "comparison_timestamp_utc": s2.isoformat(),
        "temporal_offset_days": (s2 - rcm).total_seconds() / 86400,
        "analysis_crs": "EPSG:32610",
        "grid_resolution_m": 20,
        "pixel_area_ha": 0.04,
        "evaluation_pixels": int(agreement["valid_pixels"]),
        "confusion_pixels": {key: int(agreement[key]) for key in ("TP", "FP", "FN", "TN")},
        "metrics": {key: float(agreement[key]) for key in ("precision", "recall", "F1", "IoU")},
        "claim_boundary": "Recovery-period total-mapped-water agreement, not same-day validation, class-2-only flood accuracy, ground truth, or experimental RF performance.",
        "record_origin": "Existing Phase 4 agreement output; no new satellite processing",
    }


def impact_contract(road_count: int) -> dict:
    return {
        "source_observation_id": "OBS01",
        "source_timestamp_utc": "2025-12-12T14:08:24+00:00",
        "source_meaning": "Initial selected EGS class-2 open-water flood snapshot; not total event impact or measured peak",
        "road_snapshot_way_count": int(road_count),
        "roads_vector_scope": "exposed_roads.geojson retains only ways within 250 m; road_exposure.csv is the full clipped snapshot",
        "direct_road_definition": "Positive line overlap length with the OBS01 snapshot; repeated names may be distinct OSM ways",
        "priority_selection": "Mapped gain > 0 AND (increase > 5.88 pp empirical context OR road_count_direct > 0 OR bridge_count_direct > 0)",
        "priority_order": "Observed percentage-point increase descending, then mapped gain area descending; inspection shortlist, not a risk score",
        "legacy_field_semantics": {
            "baseline_water_ratio_pct": "Fixed OBS01 EGS semantic class-1 reference coverage, not pre-event observed water",
            "event_water_ratio_pct": "Fixed-reference union OBS01 flood coverage",
            "recovery_water_ratio_pct": "Fixed-reference union OBS07 flood coverage",
            "event_minus_baseline_pp": "OBS01 union coverage minus fixed-reference coverage in percentage points",
            "flood_outside_baseline_ha": "Deprecated compatibility alias for EGS open-water flood outside fixed semantic reference",
        },
        "alr_geometry_scope": "Only mapped gain overlapping ALR designation is retained, not full AOI ALR polygons or crop area",
        "community_scope": "25 retained nearest official place points; point context only, not a complete settlement or population inventory",
        "claim_boundary": "Potential exposure or proximity only; no damage, road closure, bridge failure, crop loss or population estimate",
        "regional_reporting_boundary": "Highway 1 closure reporting is regional context; the reported closure segment is outside this compact AOI",
    }


def refresh_provenance(repo: Path, output_dir: Path) -> dict:
    """Refresh hashes only when explicitly exporting Phase 5, never retrieve sources."""
    provenance = json.loads((repo / "data/processed/phase5/source_provenance.json").read_text())
    for relative in provenance["artifact_sha256"]:
        candidate = output_dir / Path(relative).name
        if not candidate.exists():
            candidate = repo / relative
        provenance["artifact_sha256"][relative] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return provenance
