"""Final closed policy and contract tests; no new scientific parameter search."""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from analysis.rcm_preprocessing import CommonGrid, aggregate_power_and_coverage
from analysis.rf_final import final_masks, method_definition, final_gate
from analysis.rf_classification import make_features, spatial_block_samples, fit_scene_rf, predict_scene_rf, FEATURE_NAMES
from analysis.historical_water import HistoricalWaterLabels, training_labels
from analysis.phase3b_references import geometry_mask
from shapely.geometry import box


def test_coverage_zero_half_95_full():
    grid = CommonGrid(left=0, bottom=0, right=30, top=30, width=1, height=1)
    for fraction in (0, .5, .95, 1):
        valid = np.zeros((20, 20), bool)
        valid.flat[:round(400 * fraction)] = True
        power, coverage, mask = aggregate_power_and_coverage(np.ones((20, 20)), from_origin(0, 30, 1.5, 1.5), grid.crs, grid, source_valid=valid)
        np.testing.assert_allclose(coverage, [[fraction]], atol=1e-6)
        assert bool(mask[0, 0]) == (fraction >= .95)
    # Explicit finite zeros count as covered; do not silently drop them.
    values = np.ones((20, 20)); values[:, :10] = 0
    power, coverage, mask = aggregate_power_and_coverage(values, from_origin(0, 30, 1.5, 1.5), grid.crs, grid, source_valid=np.ones((20, 20), bool))
    np.testing.assert_allclose(coverage, 1); np.testing.assert_allclose(power, .5)
    assert mask.all()


def test_terrain_score_distance_boundaries_and_semantic_subtraction():
    p = np.full((2, 6), .90); p[:, 1] = .8999
    valid = np.ones_like(p, bool)
    elevation = np.full_like(p, 6); elevation[:, 0] = 5
    hydro = np.full_like(p, 60); hydro[:, 2] = 60.001
    permanent = np.zeros_like(valid); permanent[:, 3] = True
    masks = final_masks(p, valid, permanent, elevation, hydro)
    assert masks["normal_terrain"][:, 0].all()
    assert not masks["terrain_exception"][:, 1:4].any()
    assert masks["terrain_exception"][:, 4:].all()
    assert masks["permanent_subtraction"][:, 3].all()
    assert not masks["flood"][:, 3].any()
    assert masks["flood"].sum() == 6  # 2-pixel normal component high-score exception + 4-pixel ordinary


def test_small_component_mean_all_pixels_and_eight_connectivity():
    p = np.zeros((12, 12)); elevation = np.zeros_like(p); hydro = np.zeros_like(p)
    p[1, 1] = .9  # singleton retained
    p[1, 4:6] = [.8, 1]  # mean .9, every pixel close => retained
    p[4, 1:3] = [.9, .9]; hydro[4, 2] = 60.01  # any distant pixel rejects ALL
    p[7, 1:3] = [.899, .899]  # mean too low
    for i in range(4): p[7+i, 7+i] = .5  # diagonal normal 4-pixel component
    masks = final_masks(p, np.ones_like(p, bool), np.zeros_like(p, bool), elevation, hydro)
    assert masks["small_component_retained"].sum() == 3
    assert masks["cleanup_removed"].sum() == 4
    assert masks["normal_component"].sum() == 4
    assert masks["flood"].sum() == 7
    assert np.array_equal(masks["flood"], masks["normal_component"] | masks["small_component_retained"])


def test_rf_reproducible_training_balance_and_no_egs():
    rng = np.random.default_rng(9); hh = rng.normal(-15, 4, (20, 20)); hv = hh - 7
    valid = np.ones(hh.shape, bool)
    features, names = make_features(hh, hv, valid)
    assert names == FEATURE_NAMES
    np.testing.assert_allclose(features[..., 2], features[..., 0] - features[..., 1])
    land = hh > -15; water = ~land
    sample = spatial_block_samples(features, land, water, valid)
    assert sample.diagnostics["land_samples"] == sample.diagnostics["water_samples"]
    a = fit_scene_rf(sample); b = fit_scene_rf(sample)
    pa, _ = predict_scene_rf(a, features, valid); pb, _ = predict_scene_rf(b, features, valid)
    assert np.array_equal(pa, pb)
    definition = method_definition(CommonGrid(), CommonGrid())
    assert definition["training"]["EGS_used_for_training"] is False
    assert definition["parameter_search"] is False
    assert "no fresh-AOI training or tuning" in definition["fresh_policy"]


def test_historical_label_semantics():
    f = np.array([[0, 1, 79, 80, 100, 255]], dtype="uint8"); valid = f != 255
    labels = HistoricalWaterLabels(f, valid & (f == 0), valid & (f >= 80), valid & (f > 0) & (f < 80), valid, {})
    land, water, eligible = training_labels(labels)
    assert land.tolist() == [[True, False, False, False, False, False]]
    assert water.tolist() == [[False, False, False, True, True, False]]
    assert eligible.sum() == 3


def test_mode_gate_and_final_no_refine():
    rows = [{"observation_id": str(i), "iou": .6 if i < 3 else .44, "f1": .75,
             "area_bias_pct": 0, "mode_group": "stripmap16_desc" if i < 3 else "scansar30_asc"} for i in range(5)]
    qa = dict.fromkeys(["calibration_status", "geometry_status", "systematic_artifact_review", "provenance_status"], "pass")
    gate = final_gate(rows, qa)
    assert gate["status"] == "FINAL EXPERIMENTAL FAIL"
    assert "every_mode_median_iou_ge_045" in gate["failed_checks"]
    for row in rows: row["iou"] = .6
    assert final_gate(rows, qa)["status"] == "GO"
    assert final_gate(rows, {})["status"] == "FINAL EXPERIMENTAL FAIL"


def test_center_reference_grid_contract():
    grid = CommonGrid(left=0, bottom=0, right=60, top=60, width=2, height=2)
    mask = geometry_mask(box(0, 0, 14, 60), grid)
    assert mask.sum() == 0  # touched would have marked the left column
    assert geometry_mask(box(0, 0, 16, 60), grid).sum() == 2


def test_final_artifacts_and_protection_if_present():
    root = Path("data/processed/phase3b/rf_v2_final")
    if not (root / "final_gate_status.json").exists(): return
    gate = json.loads((root / "final_gate_status.json").read_text())
    assert gate["frozen"] and not gate["remaining_six_processed"]
    assert not Path("data/processed/phase3b/method_config_v1.json").exists()
    protection = json.loads((root / "qa/protected_inputs_verification.json").read_text())
    assert protection["unchanged"]
    for path in (root / "masks").glob("*.tif"):
        with rasterio.open(path) as src:
            assert src.crs.to_epsg() == 32610 and src.transform.a == 30 and src.transform.e == -30
            assert src.shape == ((100, 44) if "fresh" in path.name else (200, 200))


def test_final_references_and_no_parameter_retuning_if_present():
    root = Path("data/processed/phase3b/rf_v2_final")
    if not (root / "final_gate_status.json").exists(): return
    provenance = json.loads((root / "final_reference_provenance.json").read_text())
    assert len(provenance["primary_raw_egs_reference"]) == 5
    for record in provenance["primary_raw_egs_reference"].values():
        assert record["phase4_intermediate_used"] is False
        assert "all_touched=False" in record["rasterization"]
        assert record["source_files"] and record["grid_sha256"]
    definition = json.loads((root / "final_method_definition.json").read_text())
    assert definition["probability_threshold"] == .5 and definition["exception_score"] == .9
    assert definition["hydro_distance_max_m"] == 60 and definition["min_component_pixels"] == 4
    fresh = json.loads((root / "fresh_aoi_summary.json").read_text())
    assert not fresh["retuned"] and not fresh["training_on_fresh_AOI"]
    assert fresh["policy_hash"] == definition["policy_sha256"]


def test_closed_runner_does_not_overwrite():
    from scripts.phase3b_final import run
    if not Path("data/processed/phase3b/rf_v2_final/final_gate_status.json").exists(): return
    try:
        run(Path("nonexistent_original_egs"))
    except RuntimeError as error:
        assert "frozen" in str(error)
    else:
        raise AssertionError("Closed final runner should refuse before any output write")
