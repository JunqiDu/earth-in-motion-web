import json
import numpy as np
from pathlib import Path
import rasterio
from rasterio.transform import from_origin

from analysis.physical_constraints import (
    AAFC_CROPLAND_CODES, PhysicalContext, apply_multisource_constraints,
    distance_to_mask_m, read_aligned_land_use, rasterize_geojson,
)
from analysis.rcm_level1 import discover_products, pilot_inventory
from analysis.phase3b_diagnostics import lut_gain_at_columns
from analysis.rcm_preprocessing import CommonGrid, calibrate_dn_power, power_to_db
from analysis.validation import confusion_metrics, evaluate_gate
from analysis.water_classification import MethodConfig, classify_scene, otsu_threshold
from analysis.historical_water import HistoricalWaterLabels, training_labels
from analysis.rf_classification import make_features, local_standard_deviation, spatial_block_samples
from scripts.phase3b_multisource import _fit_fold_constraints
from scripts.phase3b_rf import PILOT_IDS, _select_outer_parameters


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


def _physical_context(shape=(2, 3)):
    elevation = np.array([[4.0, 6.0, 4.0], [4.0, 4.0, 4.0]])
    land_use = np.array([[51, 51, 31], [31, 31, 31]], dtype=np.int16)
    hydro = np.zeros(shape, dtype=bool)
    return PhysicalContext(
        elevation_m=elevation,
        elevation_valid=np.ones(shape, dtype=bool),
        slope_deg=np.zeros(shape, dtype=float),
        land_use=land_use,
        land_use_valid=np.ones(shape, dtype=bool),
        hydrography=hydro,
        hydro_distance_m=distance_to_mask_m(hydro, 30.0),
        wetlands=np.zeros(shape, dtype=bool),
        provenance={},
    )


def test_cropland_margin_and_elevation_gate_keep_eligible_cropland():
    context = _physical_context()
    candidate = np.ones((2, 3), dtype=bool)
    hh_db = np.array([[-14.0, -15.0, -11.0], [-14.0, -14.0, -14.0]])
    result, flags = apply_multisource_constraints(
        candidate, hh_db, np.ones((2, 3), dtype=bool), context,
        hh_threshold_db=-10.0, elevation_max_m=5.0,
        cropland_extra_darkness_db=3.0,
        min_component_pixels=1,
    )
    # Cropland at -14 dB clears the 3 dB margin.  Cropland at 6 m fails
    # elevation, while non-cropland needs no additional darkness margin.
    assert result.tolist() == [[True, False, True], [True, True, True]]
    assert flags["cropland"].tolist() == [[True, True, False], [False, False, False]]


def test_aligned_aafc_grid_and_nodata_handling(tmp_path):
    grid = CommonGrid()
    source = tmp_path / "land_use.tif"
    values = np.full((grid.height, grid.width), 51, dtype="int16")
    values[0, 0] = -32768
    with rasterio.open(source, "w", driver="GTiff", height=grid.height, width=grid.width,
                       count=1, dtype="int16", crs=grid.crs, transform=grid.transform,
                       nodata=-32768) as destination:
        destination.write(values, 1)
    land_use, valid = read_aligned_land_use(source, grid)
    assert land_use.shape == (200, 200)
    assert not valid[0, 0]
    assert valid[1, 1]
    assert {51, 52, 55, 56} == set(AAFC_CROPLAND_CODES)


def test_land_use_grid_mismatch_is_rejected(tmp_path):
    grid = CommonGrid()
    source = tmp_path / "wrong_grid.tif"
    with rasterio.open(source, "w", driver="GTiff", height=200, width=200,
                       count=1, dtype="uint8", crs=grid.crs,
                       transform=from_origin(grid.left + 30, grid.top, 30, 30)) as destination:
        destination.write(np.zeros((200, 200), dtype="uint8"), 1)
    try:
        read_aligned_land_use(source, grid)
    except ValueError as error:
        assert "transform" in str(error)
    else:
        raise AssertionError("misaligned AAFC input was accepted")


def test_empty_hydrography_is_safe_and_not_a_binary_mask():
    grid = CommonGrid()
    hydro = rasterize_geojson([], grid)
    assert not hydro.any()
    assert np.isinf(distance_to_mask_m(hydro, grid.resolution)).all()


def test_physical_context_has_no_egs_class2_input_field():
    assert not any("egs" in field.lower() or "reference" in field.lower()
                   for field in PhysicalContext.__dataclass_fields__)


def test_fold_parameter_selection_is_training_only_and_reproducible():
    context = _physical_context()
    train_ids = ["train_a", "train_b"]
    valid = np.ones((2, 3), dtype=bool)
    arrays = {
        "train_a": {"sigma_hh_db": np.full((2, 3), -14.0), "valid": valid},
        "train_b": {"sigma_hh_db": np.full((2, 3), -13.5), "valid": valid},
    }
    base_masks = {name: valid.copy() for name in train_ids}
    references = {
        "train_a": np.array([[True, False, True], [True, False, False]]),
        "train_b": np.array([[True, False, True], [True, False, False]]),
    }
    # There intentionally is no held-out key in any input mapping.  A result
    # demonstrates that selection accesses only the supplied training IDs.
    first, _ = _fit_fold_constraints(
        train_ids=train_ids, base_masks=base_masks, arrays=arrays,
        references=references, threshold_db=-10.0, context=context,
    )
    second, _ = _fit_fold_constraints(
        train_ids=train_ids, base_masks=base_masks, arrays=arrays,
        references=references, threshold_db=-10.0, context=context,
    )
    assert first == second
    assert first["elevation_max_m"] in {3.0, 5.0, 7.0, 10.0}
    assert first["cropland_extra_darkness_db"] in {2.0, 3.0, 4.0}


def test_historical_frequency_label_contract_and_nodata():
    frequency = np.array([[0, 80, 100], [1, 79, 255]], dtype=np.uint8)
    valid = frequency != 255
    labels = HistoricalWaterLabels(
        frequency=frequency,
        stable_land=valid & (frequency == 0),
        stable_water=valid & (frequency >= 80),
        uncertain=valid & (frequency >= 1) & (frequency <= 79),
        valid=valid,
        provenance={},
    )
    land, water, eligible = training_labels(labels)
    assert land.tolist() == [[True, False, False], [False, False, False]]
    assert water.tolist() == [[False, True, True], [False, False, False]]
    assert not eligible[1, 0] and not eligible[1, 1] and not labels.valid[1, 2]


def test_rf_features_and_texture_are_grid_aligned():
    hh = np.arange(25, dtype="float32").reshape(5, 5)
    hv = hh - 3
    valid = np.ones((5, 5), dtype=bool)
    features, names = make_features(hh, hv, valid)
    assert features.shape == (5, 5, 4)
    assert names == ("sigma0_hh_db", "sigma0_hv_db", "hh_minus_hv_db", "local_hh_std_db")
    assert np.allclose(features[..., 2], 3.0)
    assert np.isfinite(local_standard_deviation(hh, valid)).all()


def test_spatial_block_sampler_is_balanced_and_reproducible():
    features = np.zeros((40, 40, 4), dtype="float32")
    land = np.zeros((40, 40), dtype=bool); land[:20, :] = True
    water = np.zeros((40, 40), dtype=bool); water[20:, :] = True
    valid = np.ones((40, 40), dtype=bool)
    first = spatial_block_samples(features, land, water, valid, random_state=123)
    second = spatial_block_samples(features, land, water, valid, random_state=123)
    assert first.diagnostics["land_samples"] == first.diagnostics["water_samples"]
    np.testing.assert_array_equal(first.X, second.X)
    np.testing.assert_array_equal(first.y, second.y)


def test_rf_outer_selection_excludes_heldout_scene_from_parameter_choice():
    predictions = {}
    for index, scene_id in enumerate(PILOT_IDS):
        valid = np.ones((20, 20), dtype=bool)
        raw_flood = np.zeros((20, 20), dtype=bool)
        raw_flood[index : index + 2, :4] = True
        egs = np.zeros((20, 20), dtype=bool)
        egs[index : index + 2, :4] = True
        predictions[scene_id] = {
            "raw_flood": raw_flood,
            "valid": valid,
            "elevation": np.zeros((20, 20), dtype="float32"),
            "egs": egs,
        }
    _, candidates = _select_outer_parameters(PILOT_IDS, predictions, PILOT_IDS[0])
    for candidate in candidates:
        assert PILOT_IDS[0] not in json.loads(candidate["training_observation_ids"])
