import numpy as np
from pathlib import Path

from analysis.rcm_level1 import discover_products, pilot_inventory
from analysis.phase3b_diagnostics import lut_gain_at_columns
from analysis.rcm_preprocessing import CommonGrid, calibrate_dn_power, power_to_db
from analysis.validation import confusion_metrics, evaluate_gate
from analysis.water_classification import MethodConfig, classify_scene, otsu_threshold


def test_common_grid_contract():
    grid = CommonGrid()
    assert grid.crs == "EPSG:32610"
    assert (grid.width, grid.height) == (200, 200)
    assert grid.bounds == (563960.0, 5443240.0, 569960.0, 5449240.0)
    assert grid.pixel_area_ha == 0.09


def test_rcm_lut_formula_and_log_conversion():
    power = calibrate_dn_power(np.array([2.0, 4.0]), gain=2.0, offset=0.0)
    np.testing.assert_allclose(power, [2.0, 8.0])
    np.testing.assert_allclose(power_to_db(power), [10 * np.log10(2), 10 * np.log10(8)])


def test_scansar_lut_uses_preceding_step_sample():
    lut = {"first": 0, "step": 10, "positions": np.array([0, 10, 20]), "gains": np.array([100.0, 200.0, 300.0]), "offset": 0.0}
    np.testing.assert_allclose(lut_gain_at_columns(lut, np.array([0, 9, 10, 19, 20])), [100, 100, 200, 200, 300])


def test_otsu_does_not_select_sparse_high_backscatter_tail():
    water = np.full(1000, -20.0)
    land = np.full(5000, -7.0)
    bright_tail = np.full(5, 18.0)
    threshold = otsu_threshold(np.concatenate([water, land, bright_tail]))
    assert -20.0 < threshold < -7.0


def test_classifier_and_permanent_water_subtraction():
    hh = np.array([[-20.0, -5.0], [-22.0, -4.0]])
    result = classify_scene(hh, None, np.ones((2, 2), bool), "stripmap16_desc", MethodConfig(thresholds_db={"stripmap16_desc": -10.0}, min_component_pixels=1))
    assert result["water"].tolist() == [[True, False], [True, False]]


def test_metrics_and_gate():
    predicted = np.array([[1, 0], [1, 0]], bool)
    reference = np.array([[1, 0], [1, 0]], bool)
    metric = confusion_metrics(predicted, reference)
    assert metric["iou"] == 1.0
    pilot_metrics = []
    for index in range(5):
        row = dict(metric)
        row["mode_group"] = "stripmap16_desc" if index < 3 else "scansar30_asc"
        pilot_metrics.append(row)
    assert evaluate_gate(pilot_metrics)["status"] == "GO"


def test_local_inventory_and_five_scene_pilot():
    if not Path("data/raw/rcm_level1").exists():
        return
    inventory = discover_products("data/raw/rcm_level1")
    assert len(inventory) == 11
    assert len(pilot_inventory(inventory)) == 5
