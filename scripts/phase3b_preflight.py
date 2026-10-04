#!/usr/bin/env python
"""Create the metadata-only Phase 3B inventory and preflight manifest.

This command never runs SNAP and never opens the large imagery rasters. Use it
before the five-scene pilot to establish a reproducible input audit.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Allow ``python scripts/phase3b_preflight.py`` from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.rcm_level1 import PILOT, discover_products, pilot_inventory, verify_product
from analysis.rcm_preprocessing import CommonGrid, SnapUnavailableError, find_snap_gpt, snap_diagnostics, snap_operator_check
from analysis.water_classification import candidate_definitions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/raw/rcm_level1")
    parser.add_argument("--output", default="data/processed/phase3b")
    parser.add_argument("--skip-checksum", action="store_true")
    parser.add_argument("--force", action="store_true", help="replace an existing Phase 3B result set")
    args = parser.parse_args()
    output = Path(args.output)
    if (output / "phase3b_final_gate.json").exists() and not args.force:
        print("Existing Phase 3B final gate found; preflight is non-destructive. Use --force only to start a new registered run.")
        return 0
    output.mkdir(parents=True, exist_ok=True)
    inventory = discover_products(args.root)
    checks = [] if args.skip_checksum else [verify_product(path) for path in inventory["source_product"]]
    check_by_product = {item["product"]: item for item in checks}
    inventory["input_product_hash"] = inventory["source_product"].map(lambda p: check_by_product.get(p, {}).get("input_product_hash"))
    inventory["vendor_checksum_verified"] = inventory["source_product"].map(lambda p: check_by_product.get(p, {}).get("status") == "ok")
    pilot_lookup = {pd.Timestamp(value[0], tz="UTC").floor("s"): (key, value[3]) for key, value in PILOT.items()}
    timestamps = pd.to_datetime(inventory["timestamp_utc"], utc=True).dt.floor("s")
    inventory["pilot_id"] = timestamps.map(lambda value: pilot_lookup.get(value, (pd.NA, pd.NA))[0])
    inventory["egs_observation_id"] = timestamps.map(lambda value: pilot_lookup.get(value, (pd.NA, pd.NA))[1])
    inventory.to_csv(output / "level1_inventory.csv", index=False)
    pilot = pilot_inventory(inventory)
    pd.DataFrame({
        "observation_id": pilot["observation_id"],
        "valid_pixels": pd.NA,
        "valid_pct": pd.NA,
        "geometry_status": "not_run_snap",
        "noise_floor_status_hh": "not_run_snap",
        "noise_floor_status_hv": "not_run_snap",
        "calibration_representation": "Gamma0_linear_power_pending",
        "classification_method_version": pd.NA,
        "validation_status": "pilot_pending",
        "comparability_category": pilot["mode_group"].map({"stripmap16_desc": "direct_egs_overlap", "scansar30_asc": "direct_egs_overlap"}).fillna("unclassified"),
        "warnings": "SNAP terrain correction not run",
    }).to_csv(output / "observation_qa.csv", index=False)
    pd.DataFrame(columns=[
        "observation_id", "fold_id", "candidate_id", "mode_group", "representation",
        "tp_pixels", "fp_pixels", "fn_pixels", "tn_pixels", "precision", "recall", "f1", "iou",
        "predicted_area_ha", "reference_area_ha", "area_bias_ha", "area_bias_pct",
        "boundary_f1_30m", "boundary_f1_60m",
    ]).to_csv(output / "validation_metrics.csv", index=False)
    (output / "method_candidates.json").write_text(json.dumps(candidate_definitions(), indent=2))
    (output / "validation_summary.json").write_text(json.dumps({"status": "PENDING_SNAP", "pilot_rows": int(len(pilot)), "method_config_generated": False}, indent=2))
    (output / "common_grid.json").write_text(json.dumps(CommonGrid().as_dict(), indent=2))
    manifest = {
        "schema_version": "phase3b-preflight-1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(Path(args.root)),
        "inventory_rows": int(len(inventory)),
        "pilot_rows": int(len(pilot)),
        "checksums_skipped": bool(args.skip_checksum),
        "checksum_statuses": {status: sum(item.get("status") == status for item in checks) for status in sorted({item.get("status") for item in checks})},
        "common_grid": CommonGrid().as_dict(),
        "snap_gpt": None,
        "snap_status": "not_found",
        "phase4_phase5_untouched": True,
    }
    try:
        manifest["snap_gpt"] = str(find_snap_gpt())
        manifest["snap_status"] = "available"
        manifest["snap_diagnostics"] = snap_diagnostics()
        manifest["snap_operators"] = snap_operator_check()
    except SnapUnavailableError as exc:
        manifest["snap_error"] = str(exc)
    (output / "processing_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"Inventory: {len(inventory)} products; pilot: {len(pilot)}")
    print(f"Wrote {output / 'level1_inventory.csv'}")
    print(f"SNAP status: {manifest['snap_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
