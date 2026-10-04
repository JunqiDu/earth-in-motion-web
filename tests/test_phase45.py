"""Offline integration regressions; run with standard-library unittest."""
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.phase45_contract import method_selection, impact_contract
from scripts.phase45_validate import validate


def no_network(*args, **kwargs):
    raise AssertionError("Unexpected external request in snapshot regression")


class Phase45IntegrationTests(unittest.TestCase):
    def test_offline_contract_and_numerical_regression(self):
        with patch.object(socket.socket, "connect", no_network):
            result = validate(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["roads"]["clipped_way_count"], 234)
        self.assertFalse(result["scientific_outputs_recomputed"])

    def test_frozen_method_selection_and_grid_boundary(self):
        selection = method_selection(ROOT)
        self.assertEqual(selection["phase3b_status"], "FINAL EXPERIMENTAL FAIL")
        self.assertFalse(selection["level1_promoted"])
        self.assertIn("20 m", selection["grid_boundary"])
        self.assertIn("30 m", selection["grid_boundary"])
        self.assertIn("not a risk score", impact_contract(234)["priority_order"])

    def test_phase5_snapshot_calculations_from_both_working_directories(self):
        notebook = json.loads((ROOT / "notebooks/05_impact_analysis.ipynb").read_text())
        saved = pd.read_csv(ROOT / "data/processed/phase5/priority_grid_impact.csv").set_index("grid_id")
        old_cwd = Path.cwd()
        try:
            for cwd in (ROOT, ROOT / "notebooks"):
                os.chdir(cwd)
                namespace = {}
                with patch.object(socket.socket, "connect", no_network), contextlib.redirect_stdout(io.StringIO()):
                    for index in (3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 31, 33):
                        exec(compile("".join(notebook["cells"][index]["source"]), f"phase5-cell-{index}", "exec"), namespace)
                        namespace["display"] = lambda *a, **k: None
                current = namespace["priority"].set_index("grid_id")
                self.assertEqual(set(current.index), set(saved.index))
                for column in ("baseline_water_ratio_pct", "event_water_ratio_pct", "recovery_water_ratio_pct",
                               "event_minus_baseline_pp", "event_gain_area_ha", "road_count_direct",
                               "road_intersection_m", "bridge_count_direct", "alr_overlap_ha",
                               "community_distance_to_cell_gain_m"):
                    np.testing.assert_allclose(current.loc[saved.index, column], saved[column], rtol=1e-8, atol=1e-7)
                self.assertEqual(len(namespace["roads"]), 234)
                self.assertEqual(len(namespace["evidence_chain"]), 10)
        finally:
            os.chdir(old_cwd)

    def test_phase4_stage_alignment_reuses_committed_snapshot(self):
        notebook = json.loads((ROOT / "notebooks/04_change_detection.ipynb").read_text())
        observations = pd.read_csv(ROOT / "data/processed/phase4/event_observations.csv", parse_dates=["timestamp_utc"])
        namespace = {"pd": pd, "np": np, "plt": plt, "Path": Path, "egs_df": observations,
                     "display": lambda *a, **k: None}
        old_cwd = Path.cwd()
        try:
            os.chdir(ROOT)
            with patch.object(socket.socket, "connect", no_network), patch.object(plt, "show"), contextlib.redirect_stdout(io.StringIO()):
                exec(compile("".join(notebook["cells"][30]["source"]), "phase4-stage-cell", "exec"), namespace)
            saved = pd.read_csv(ROOT / "data/processed/phase4/rcm_stage_alignment.csv")
            np.testing.assert_allclose(namespace["rcm_stage_alignment"].offset_to_stage_anchor_hours,
                                       saved.offset_to_stage_anchor_hours)
            self.assertEqual(len(namespace["hydrologic_stage_summary"]), 15)
        finally:
            os.chdir(old_cwd)
            plt.close("all")


if __name__ == "__main__":
    unittest.main()
