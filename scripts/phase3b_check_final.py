#!/usr/bin/env python
"""Read-only final artifact smoke check. Does not run SNAP, train, or tune."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import rasterio
from analysis.physical_constraints import sha256_file


def run():
    out = ROOT / "data/processed/phase3b/rf_v2_final"
    manifest = json.loads((out / "final_run_manifest.json").read_text())
    for relative, expected in manifest["artifacts"].items():
        path = out.parent / relative
        assert path.exists() and sha256_file(path) == expected, str(path)
    protected = json.loads((out / "qa/protected_inputs_before.json").read_text())
    for relative, expected in protected.items():
        assert sha256_file(ROOT / relative) == expected, relative
    for name in ("raw_egs", "legacy"):
        rows = pd.read_csv(out / ("final_validation_metrics_" + name + ".csv"))
        assert len(rows) == 5 and rows.observation_id.is_unique
        assert rows.evaluation_pixels.eq(40000).all()
        np.testing.assert_allclose(rows.predicted_area_ha, (rows.tp_pixels + rows.fp_pixels) * .09)
        np.testing.assert_allclose(rows.reference_area_ha, (rows.tp_pixels + rows.fn_pixels) * .09)
        np.testing.assert_allclose(rows.area_bias_ha, rows.predicted_area_ha - rows.reference_area_ha)
        assert (rows.tp_pixels + rows.fp_pixels + rows.fn_pixels + rows.tn_pixels).eq(40000).all()
    qa = json.loads((out / "final_coverage_qa.json").read_text())
    for row in qa["scenes"]:
        assert row["valid_pixels"] == 40000 and row["previous_common_valid_unchanged"]
        assert row["rf_v1_probability_max_abs_difference"] == 0
    for path in (out / "masks").glob("*.tif"):
        with rasterio.open(path) as src:
            assert src.crs.to_epsg() == 32610
            assert src.transform.a == 30 and src.transform.e == -30
            assert src.shape == ((100, 44) if "fresh" in path.name else (200, 200))
    status = json.loads((out / "final_gate_status.json").read_text())
    assert status["status"] in ("GO", "FINAL EXPERIMENTAL FAIL")
    assert status["frozen"] and not status["additional_research_allowed"]
    assert not (out.parent / "method_config_v1.json").exists()
    print(f"PASS: manifest, {len(protected)} protected files, coverage, unchanged RF scores, five-scene area identities, geometry, frozen stop")


if __name__ == "__main__":
    run()
