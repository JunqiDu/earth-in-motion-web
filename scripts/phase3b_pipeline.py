#!/usr/bin/env python
"""Deterministic Phase 3B runner.

The command is deliberately staged.  It never writes Phase 4/5 or Dashboard
artifacts and refuses to freeze a method before the registered pilot gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy import ndimage
from shapely.geometry import box, shape
from shapely.ops import transform as shapely_transform
from pyproj import CRS, Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.rcm_level1 import PILOT, discover_products, pilot_inventory, verify_product
from analysis.rcm_preprocessing import (
    CommonGrid, aggregate_power_and_coverage, find_snap_gpt, graph_hash,
    power_to_db, render_snap_graph, run_snap_graph, snap_diagnostics,
)
from analysis.validation import boundary_distance_summary, evaluate_gate, validate_scene
from analysis.water_classification import candidate_definitions, cleanup_mask, otsu_threshold

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/phase3b"
CACHE = OUT / "cache/pilot"
GRID = CommonGrid()
PILOT_IDS = list(PILOT)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def project_aoi_wkt(buffer_m: float = 2000.0) -> str:
    aoi = box(GRID.left - buffer_m, GRID.bottom - buffer_m, GRID.right + buffer_m, GRID.top + buffer_m)
    transform = Transformer.from_crs(GRID.crs, "EPSG:4326", always_xy=True).transform
    coordinates = [transform(*xy) for xy in aoi.exterior.coords]
    return "POLYGON((" + ",".join(f"{x} {y}" for x, y in coordinates) + "))"


def find_manifest(product: Path) -> Path:
    matches = sorted(product.rglob("manifest.safe"))
    if not matches:
        raise FileNotFoundError(f"manifest.safe not found below {product}")
    return matches[0]


def inventory_with_checksums() -> pd.DataFrame:
    inventory = discover_products(ROOT / "data/raw/rcm_level1")
    checks = {item["product"]: item for item in (verify_product(p) for p in inventory["source_product"])}
    inventory["input_product_hash"] = inventory["source_product"].map(lambda p: checks[p].get("input_product_hash"))
    inventory["vendor_checksum_verified"] = inventory["source_product"].map(lambda p: checks[p].get("status") == "ok")
    timestamp_map = {pd.Timestamp(v[0], tz="UTC").floor("s"): (k, v[3]) for k, v in PILOT.items()}
    timestamps = pd.to_datetime(inventory["timestamp_utc"], utc=True).dt.floor("s")
    inventory["pilot_id"] = timestamps.map(lambda t: timestamp_map.get(t, (pd.NA, pd.NA))[0])
    inventory["egs_observation_id"] = timestamps.map(lambda t: timestamp_map.get(t, (pd.NA, pd.NA))[1])
    if not inventory["vendor_checksum_verified"].all():
        raise RuntimeError("At least one RCM product failed vendor checksum verification")
    return inventory


def dem_provenance() -> dict[str, object]:
    dem_root = Path.home() / ".snap/auxdata/dem/Copernicus 30m Global DEM"
    tiles = sorted(dem_root.glob("*.tif"))
    if not tiles:
        raise RuntimeError(f"SNAP Copernicus DEM cache not found: {dem_root}")
    return {
        "source": "ESA SNAP Copernicus 30m Global DEM",
        "snap_dem_cache": str(dem_root),
        "tiles": [{"path": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in tiles],
        "created_utc": utc_now(),
    }


def _band_index(descriptions: tuple[str | None, ...], name: str, *, fallback_order: tuple[str, ...] = ()) -> int:
    for i, desc in enumerate(descriptions, start=1):
        if desc and name.lower() in desc.lower():
            return i
    # SNAP's GeoTIFF writer does not consistently preserve Band descriptions
    # for RCM virtual bands.  The source DIMAP still records the deterministic
    # order requested by the graph, so callers may provide that order as a
    # provenance-backed fallback rather than guessing from pixel values.
    for i, fallback in enumerate(fallback_order, start=1):
        if fallback.lower() == name.lower() and i <= len(descriptions):
            return i
    raise KeyError(f"Band {name} not present: {descriptions}")


def _dimap_band_names(dim_path: Path) -> tuple[str, ...]:
    """Read SNAP DIMAP band order when GeoTIFF descriptions are absent."""
    text = dim_path.read_text(errors="replace")
    names = re.findall(r"<BAND_NAME>([^<]+)</BAND_NAME>", text)
    return tuple(name.strip() for name in names if name.strip())


def _write_npz(path: Path, arrays: dict[str, np.ndarray], metadata: dict[str, object]) -> None:
    np.savez_compressed(path, **arrays)
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2, default=str))


def _lee_filter(power: np.ndarray, valid: np.ndarray, window: int) -> np.ndarray:
    """Conventional local-mean Lee filter in linear power units.

    This is the single pre-registered physical-scale sensitivity treatment:
    5x5 native pixels for 16 m scenes and 3x3 for 30 m scenes.  Nodata and
    nonpositive values never enter its local moments.
    """
    power = np.asarray(power, dtype="float32")
    valid = np.asarray(valid, dtype=bool) & np.isfinite(power) & (power > 0)
    weights = valid.astype("float32")
    count = ndimage.uniform_filter(weights, size=window, mode="nearest") * (window * window)
    summed = ndimage.uniform_filter(np.where(valid, power, 0.0), size=window, mode="nearest") * (window * window)
    squared = ndimage.uniform_filter(np.where(valid, power * power, 0.0), size=window, mode="nearest") * (window * window)
    mean = np.divide(summed, count, out=np.zeros_like(summed), where=count > 0)
    variance = np.maximum(np.divide(squared, count, out=np.zeros_like(squared), where=count > 0) - mean * mean, 0.0)
    noise_variance = float(np.median(variance[valid]))
    weight = np.divide(variance, variance + noise_variance, out=np.zeros_like(variance), where=(variance + noise_variance) > 0)
    filtered = mean + weight * (power - mean)
    filtered[~valid] = np.nan
    return filtered.astype("float32")


def preprocess_pilot(*, cache_root: Path = CACHE, filter_policy: str = "none", qa_filename: str = "observation_qa.csv", tc_cache_root: Path | None = None) -> pd.DataFrame:
    inventory = inventory_with_checksums()
    pilot = pilot_inventory(inventory)
    if len(pilot) != 5:
        raise RuntimeError(f"Expected five registered Pilot products, found {len(pilot)}")
    cache_root.mkdir(parents=True, exist_ok=True)
    aoi = project_aoi_wkt()
    results = []
    for _, row in pilot.iterrows():
        obs = row.observation_id
        scene = cache_root / obs
        scene.mkdir(parents=True, exist_ok=True)
        tc_scene = (tc_cache_root or cache_root) / obs
        manifest = find_manifest(Path(row.source_product))
        cal_dim = tc_scene / "calibrated.dim"
        cal_graph = tc_scene / "calibration.xml"
        tc_tif = tc_scene / "terrain_corrected.tif"
        tc_graph = tc_scene / "terrain_correction.xml"
        if not cal_dim.exists():
            render_snap_graph(ROOT / "config/snap/phase3b_calibration.xml", cal_graph,
                              SOURCE_MANIFEST=str(manifest.resolve()), AOI_WKT=aoi,
                              OUTPUT_PRODUCT=str(cal_dim.resolve()))
            run_snap_graph(cal_graph, heap="-J-Xmx12G")
        if not tc_tif.exists():
            render_snap_graph(ROOT / "config/snap/phase3b_terrain_correction.xml", tc_graph,
                              SOURCE_PRODUCT=str(cal_dim.resolve()),
                              INTERMEDIATE_PIXEL_SPACING_M=str(float(row.nominal_resolution_m)),
                              OUTPUT_PRODUCT=str(tc_tif.resolve()))
            run_snap_graph(tc_graph, heap="-J-Xmx12G")
        with rasterio.open(tc_tif) as src:
            descriptions = tuple(src.descriptions)
            # SNAP 14 leaves the GeoTIFF descriptions blank for this graph.
            # The authoritative fallback is therefore the explicit
            # ``sourceBands`` sequence in phase3b_terrain_correction.xml,
            # not the calibrated DIMAP's native order.  The latter is
            # Sigma-before-Gamma and previously swapped the two representations
            # after terrain correction.
            fallback_order = (
                "Gamma0_HH", "Gamma0_HV", "Sigma0_HH", "Sigma0_HV"
            ) if src.count == 4 else ()
            source_valid = src.dataset_mask() > 0
            expected_spacing = float(row.nominal_resolution_m)
            arrays = {}
            coverages = {}
            valids = {}
            for rep in ("gamma", "sigma"):
                for pol in ("HH", "HV"):
                    band = _band_index(descriptions, f"{rep}0_{pol}", fallback_order=fallback_order)
                    source_power = src.read(band)
                    if filter_policy == "lee":
                        source_power = _lee_filter(source_power, source_valid, 5 if expected_spacing == 16.0 else 3)
                    power, coverage, valid = aggregate_power_and_coverage(
                        source_power, src.transform, str(src.crs), GRID,
                        source_valid=source_valid,
                    )
                    arrays[f"{rep}_{pol.lower()}_power"] = power
                    arrays[f"{rep}_{pol.lower()}_db"] = power_to_db(power)
                    coverages[f"{rep}_{pol.lower()}_coverage"] = coverage
                    valids[f"{rep}_{pol.lower()}_valid"] = valid
            common = valids["gamma_hh_valid"] & valids["gamma_hv_valid"]
            arrays["common_valid"] = common.astype("uint8")
            arrays.update(coverages)
            _write_npz(scene / "grid_arrays.npz", arrays, {
                "observation_id": obs, "source_product": row.source_product,
                "source_product_hash": row.input_product_hash, "tc_path": str(tc_tif),
                "grid": GRID.as_dict(), "representations": ["gamma", "sigma"],
                "filter_policy": filter_policy,
            })
            crs_ok = src.crs is not None and src.crs.to_epsg() == 32610
            spacing = abs(float(src.transform.a))
            geometry_ok = crs_ok and abs(spacing - expected_spacing) <= 0.5 and src.width > 0 and src.height > 0
            dimap_names = _dimap_band_names(cal_dim)
            calibration_ok = all(name in dimap_names for name in ("Sigma0_HH", "Sigma0_HV", "Gamma0_HH", "Gamma0_HV"))
            hv_floor = _noise_floor(row)
            results.append({
                "observation_id": obs, "timestamp_utc": row.timestamp_utc,
                "beam_mode": row.beam_mode, "mode_group": row.mode_group,
                "valid_pixels": int(common.sum()), "valid_pct": float(common.mean() * 100),
                "geometry_status": "pass" if geometry_ok else "fail",
                "noise_floor_status_hh": "not_required_for_pilot",
                "noise_floor_status_hv": "available" if np.isfinite(hv_floor) else "missing",
                "calibration_status": "bands_present" if calibration_ok else "missing_expected_bands",
                "calibration_representation": "Gamma0+Sigma0",
                "classification_method_version": "pending", "validation_status": "pilot_preprocessed",
                "comparability_category": "direct_egs_overlap",
                "warnings": "formal LUT and shoreline-offset QA pending" if filter_policy == "none" else "pre-registered Lee sensitivity cache; not adopted",
            })
    qa = pd.DataFrame(results)
    qa.to_csv(OUT / qa_filename, index=False)
    inventory.to_csv(OUT / "level1_inventory.csv", index=False)
    (OUT / "common_grid.json").write_text(json.dumps(GRID.as_dict(), indent=2))
    return qa


def _read_geojson_mask(path: Path, observation_id: str | None = None) -> np.ndarray:
    data = json.loads(path.read_text())
    crs_info = data.get("crs", {}).get("properties", {}).get("name")
    if not crs_info:
        raise ValueError(f"Reference GeoJSON must declare a CRS: {path}")
    source_crs = CRS.from_user_input(crs_info)
    target_crs = CRS.from_user_input(GRID.crs)
    transformer = None if source_crs == target_crs else Transformer.from_crs(source_crs, target_crs, always_xy=True).transform
    geometries = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        if observation_id is not None and props.get("observation_id") != observation_id:
            continue
        geometry = shape(feature["geometry"])
        if transformer is not None:
            geometry = shapely_transform(transformer, geometry)
        geometries.append((geometry, 1))
    return rasterize(geometries, out_shape=(GRID.height, GRID.width), transform=GRID.transform,
                     fill=0, dtype="uint8", all_touched=False).astype(bool)


def permanent_and_egs_masks(egs_id: str) -> tuple[np.ndarray, np.ndarray]:
    permanent = _read_geojson_mask(OUT.parent / "phase4/egs_permanent_water_reference.geojson")
    egs = _read_geojson_mask(OUT.parent / "phase4/egs_open_water_flood_frames.geojson", egs_id)
    return permanent, egs


def _noise_floor(row: pd.Series, pol: str = "HV") -> float:
    product = Path(row.source_product)
    files = list(product.rglob(f"noiseLevels_{pol}.xml"))
    if not files:
        return float("nan")
    text = files[0].read_text(errors="replace")
    values = [float(v) for v in re.findall(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[Ee][-+]?\d+)?", text.split("<noiseLevelValues", 1)[-1])]
    return float(max(values)) if values else float("nan")


def _fit_single_threshold(scene_arrays, scenes, ids, rep, group=None, hv=False):
    values = []
    labels = []
    for sid in ids:
        row = scenes[sid]
        if group and row["mode_group"] != group:
            continue
        a = scene_arrays[sid]
        key = f"{rep}_{'hv' if hv else 'hh'}_db"
        valid = a["common_valid"].astype(bool) & np.isfinite(a[key])
        # The classifier is fitted for open-water flood extension, not for
        # the fixed semantic permanent-water reference.  Permanent pixels are
        # therefore excluded from threshold fitting to avoid selecting a
        # threshold that simply rediscovers the river/lake footprint.
        valid &= ~a["permanent"]
        if hv:
            valid &= a[key] >= row["hv_noise_floor"] + 3.0
        valid &= np.isfinite(a["egs"])
        values.append(a[key][valid]); labels.append(a["egs"][valid])
    if not values:
        raise RuntimeError("No training pixels available for threshold fit")
    x, y = np.concatenate(values), np.concatenate(labels)
    initial = otsu_threshold(x)
    best = (initial, -1.0, float("inf"))
    for threshold in np.arange(initial - 3, initial + 3.001, 0.5):
        ious, biases = [], []
        for sid in ids:
            row = scenes[sid]
            if group and row["mode_group"] != group:
                continue
            a = scene_arrays[sid]
            key = f"{rep}_{'hv' if hv else 'hh'}_db"
            valid = a["common_valid"].astype(bool) & np.isfinite(a[key])
            valid &= ~a["permanent"]
            if hv:
                valid &= a[key] >= row["hv_noise_floor"] + 3.0
            pred = (a[f"{rep}_hh_db"] < threshold) if not hv else (a[key] < threshold)
            pred &= valid
            ref = a["egs"] & valid
            tp = int((pred & ref).sum()); fp = int((pred & ~ref).sum()); fn = int((~pred & ref).sum())
            ious.append(tp / (tp + fp + fn) if tp + fp + fn else 0.0)
            biases.append(abs(float(pred.mean() - ref.mean())))
        score = float(np.mean(ious)); bias = float(np.mean(biases))
        if score > best[1] + 1e-12 or (abs(score - best[1]) <= 1e-12 and bias < best[2]):
            best = (float(threshold), score, bias)
    return best[0]


def _fit_params(candidate: str, rep: str, train_ids: list[str], arrays: dict, scenes: dict) -> dict[str, float]:
    groups = ["stripmap16_desc", "scansar30_asc"]
    params = {}
    if candidate == "C0_global_hh":
        params["global_hh"] = _fit_single_threshold(arrays, scenes, train_ids, rep)
    else:
        for group in groups:
            params[f"{group}_hh"] = _fit_single_threshold(arrays, scenes, train_ids, rep, group=group)
            if candidate == "C2_group_hh_hv":
                params[f"{group}_hv"] = _fit_single_threshold(arrays, scenes, train_ids, rep, group=group, hv=True)
    return params


def _predict(candidate: str, rep: str, params: dict[str, float], scene: dict, arr: dict) -> np.ndarray:
    group = scene["mode_group"]
    hh = arr[f"{rep}_hh_db"]
    if candidate == "C0_global_hh":
        water = hh < params["global_hh"]
    else:
        water = hh < params[f"{group}_hh"]
        if candidate == "C2_group_hh_hv":
            hv = arr[f"{rep}_hv_db"]
            usable = np.isfinite(hv) & (hv >= scene["hv_noise_floor"] + 3.0)
            water &= (~usable) | (hv < params[f"{group}_hv"])
    valid = arr["common_valid"].astype(bool)
    # Convert classified water to the registered flood-extension product by
    # subtracting the fixed EGS semantic permanent-water reference.
    water &= ~arr["permanent"]
    return cleanup_mask(water, valid, min_component_pixels=2)


def _validation_report(metrics: pd.DataFrame) -> dict[str, object]:
    """Summarize strict LOODO results without hiding per-date variation."""
    report: dict[str, object] = {"strict_pixel_metrics": True, "candidates": {}}
    for (candidate, representation), subset in metrics.groupby(["candidate_id", "representation"], sort=True):
        ious, f1s = subset["iou"].to_numpy(float), subset["f1"].to_numpy(float)
        tp, fp, fn, tn = (int(subset[column].sum()) for column in ("tp_pixels", "fp_pixels", "fn_pixels", "tn_pixels"))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        micro_f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        micro_iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
        mode_rows = {}
        for mode, group in subset.groupby("mode_group"):
            mode_rows[mode] = {"median_iou": float(group.iou.median()), "median_f1": float(group.f1.median()), "scene_count": int(len(group))}
        report["candidates"][f"{candidate}__{representation}"] = {
            "macro": {"median_iou": float(np.median(ious)), "iqr_iou": float(np.percentile(ious, 75) - np.percentile(ious, 25)),
                      "median_f1": float(np.median(f1s)), "iqr_f1": float(np.percentile(f1s, 75) - np.percentile(f1s, 25))},
            "micro": {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": micro_f1, "iou": micro_iou},
            "per_mode_group": mode_rows,
            "worst_date": subset.loc[subset.iou.idxmin(), ["observation_id", "mode_group", "iou", "f1", "area_bias_pct"]].to_dict(),
            "per_date": subset[["observation_id", "mode_group", "iou", "f1", "area_bias_pct", "boundary_f1_30m", "boundary_f1_60m"]].to_dict("records"),
        }
    return report


def validate_pilot(*, cache_root: Path = CACHE, metrics_filename: str = "validation_metrics.csv", qa_filename: str = "observation_qa.csv", summary_filename: str = "validation_summary.json", primary: bool = True) -> dict[str, object]:
    inventory = inventory_with_checksums().set_index("observation_id")
    pilot = pilot_inventory(inventory.reset_index()).set_index("observation_id")
    arrays: dict[str, dict] = {}
    scenes: dict[str, dict] = {}
    for sid, row in pilot.iterrows():
        payload = np.load(cache_root / sid / "grid_arrays.npz")
        permanent, egs = permanent_and_egs_masks(row.egs_observation_id)
        arrays[sid] = {key: payload[key] for key in payload.files}
        arrays[sid]["permanent"] = permanent
        arrays[sid]["egs"] = egs
        scenes[sid] = {"mode_group": row.mode_group, "hv_noise_floor": _noise_floor(row), "egs_observation_id": row.egs_observation_id}
    rows = []
    # Gamma0 and Sigma0 are the two pre-registered calibration representations.
    # Both are evaluated here before one can be frozen; neither gets
    # date-specific parameters.
    for representation, key in (("Gamma0", "gamma"), ("Sigma0", "sigma")):
        for candidate in ("C0_global_hh", "C1_group_hh", "C2_group_hh_hv"):
            for heldout in pilot.index:
                train = [sid for sid in pilot.index if sid != heldout]
                params = _fit_params(candidate, key, train, arrays, scenes)
                pred = _predict(candidate, key, params, scenes[heldout], arrays[heldout])
                valid = arrays[heldout]["common_valid"].astype(bool)
                metric = validate_scene(pred, arrays[heldout]["egs"], valid, pixel_area_ha=GRID.pixel_area_ha)
                metric.update({"observation_id": heldout, "fold_id": f"LOODO_{heldout}", "candidate_id": candidate,
                               "mode_group": scenes[heldout]["mode_group"], "representation": representation,
                               "thresholds": json.dumps(params, sort_keys=True)})
                rows.append(metric)
    metrics = pd.DataFrame(rows)
    metrics.to_csv(OUT / metrics_filename, index=False)
    report_filename = summary_filename.replace("summary", "report")
    (OUT / report_filename).write_text(json.dumps(_validation_report(metrics), indent=2, default=str))
    summary = metrics.groupby(["candidate_id", "representation"]).agg(iou_median=("iou", "median"), f1_median=("f1", "median"), area_bias_abs_median=("area_bias_pct", lambda x: float(np.median(np.abs(x))))).reset_index()
    best_iou = float(summary.iou_median.max())
    complexity = {"C0_global_hh": 0, "C1_group_hh": 1, "C2_group_hh_hv": 2}
    eligible = summary[summary.iou_median >= best_iou - 0.02].copy()
    selected_record = sorted(eligible.to_dict("records"), key=lambda x: (complexity[x["candidate_id"]], x["representation"] != "Gamma0"))[0]
    selected = selected_record["candidate_id"]
    selected_representation = selected_record["representation"]
    selected_rows = metrics[(metrics.candidate_id == selected) & (metrics.representation == selected_representation)].to_dict("records")
    qa_table = pd.read_csv(OUT / qa_filename)
    qa = {
        "geometry_status": "pass" if (qa_table.geometry_status == "pass").all() else "fail",
        "calibration_status": "pass" if (OUT / "calibration_lut_qa.csv").exists() and pd.read_csv(OUT / "calibration_lut_qa.csv")["pass_native_sigma_1e-5"].all() else "pending_real_lut_check",
        "systematic_artifact_review": "pending",
    }
    gate = evaluate_gate(selected_rows, qa)
    result = {"status": gate["status"], "selected_candidate": selected, "selected_representation": selected_representation, "candidate_summary": summary.to_dict("records"), "gate": gate, "detailed_report": report_filename, "method_config_generated": False, "created_utc": utc_now(), "stop_reason": "Pilot does not meet the registered GO gate; Phase 4B/remaining scenes are not run."}
    if primary:
        (OUT / "method_candidates.json").write_text(json.dumps({"definitions": candidate_definitions(), "representations": ["Gamma0", "Sigma0"], "pilot_summary": summary.to_dict("records"), "selected_candidate": selected, "selected_representation": selected_representation}, indent=2, default=str))
        manifest_path = OUT / "processing_manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        manifest.update({"schema_version": "phase3b-pilot-1", "pilot_preprocessed": True, "pilot_validation_status": gate["status"], "phase4_phase5_untouched": True})
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    (OUT / summary_filename).write_text(json.dumps(result, indent=2, default=str))
    return result


def finalize_pilot() -> dict[str, object]:
    """Record the one allowed refinement and enforce the Phase 4B stop rule."""
    baseline = json.loads((OUT / "validation_summary.json").read_text())
    refinement = json.loads((OUT / "refinement_summary.json").read_text())
    base_report = json.loads((OUT / baseline["detailed_report"]).read_text())
    refine_report = json.loads((OUT / refinement["detailed_report"]).read_text())
    key = f"{baseline['selected_candidate']}__{baseline['selected_representation']}"
    base = base_report["candidates"][key]
    refined = refine_report["candidates"][key]
    median_gain = refined["macro"]["median_iou"] - base["macro"]["median_iou"]
    worst_change = refined["worst_date"]["iou"] - base["worst_date"]["iou"]
    lee_meets_adoption_rule = median_gain >= 0.03 and worst_change >= -0.02
    result = {
        "status": "FAIL",
        "final_gate_reason": "The only permitted pre-registered Lee refinement was completed, but strict LOODO metrics remain below the Phase 3B FAIL threshold. No Level-1 method is frozen and the remaining six scenes are not processed.",
        "baseline_selected": {"candidate": baseline["selected_candidate"], "representation": baseline["selected_representation"], "median_iou": base["macro"]["median_iou"], "worst_iou": base["worst_date"]["iou"]},
        "lee_refinement": {"completed": True, "median_iou": refined["macro"]["median_iou"], "worst_iou": refined["worst_date"]["iou"], "median_iou_change": median_gain, "worst_iou_change": worst_change, "passes_filter_adoption_comparison": lee_meets_adoption_rule, "used_for_remaining_scenes": False},
        "calibration_lut_check": "pass_native_sigma_1e-5",
        "phase4_phase5_dashboard_untouched": True,
        "method_config_generated": False,
        "full_11_scene_processing_started": False,
        "created_utc": utc_now(),
    }
    (OUT / "phase3b_final_gate.json").write_text(json.dumps(result, indent=2))
    manifest_path = OUT / "processing_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest.update({"final_pilot_status": "FAIL", "method_config_v1_generated": False, "full_11_scene_processing_started": False, "phase4_phase5_untouched": True})
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["dem-provenance", "preprocess-pilot", "validate-pilot", "preprocess-refinement-lee", "validate-refinement-lee", "finalize-pilot", "status"])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.step == "dem-provenance":
        (OUT / "dem_provenance.json").write_text(json.dumps(dem_provenance(), indent=2))
    elif args.step == "preprocess-pilot":
        print(preprocess_pilot().to_string(index=False))
    elif args.step == "validate-pilot":
        print(json.dumps(validate_pilot(), indent=2, default=str))
    elif args.step == "preprocess-refinement-lee":
        print(preprocess_pilot(cache_root=OUT / "cache/refinement_lee", tc_cache_root=CACHE, filter_policy="lee", qa_filename="observation_qa_refinement_lee.csv").to_string(index=False))
    elif args.step == "validate-refinement-lee":
        print(json.dumps(validate_pilot(cache_root=OUT / "cache/refinement_lee", metrics_filename="validation_metrics_refinement_lee.csv", qa_filename="observation_qa_refinement_lee.csv", summary_filename="refinement_summary.json", primary=False), indent=2, default=str))
    elif args.step == "finalize-pilot":
        print(json.dumps(finalize_pilot(), indent=2, default=str))
    else:
        print((OUT / "validation_summary.json").read_text() if (OUT / "validation_summary.json").exists() else "No validation summary yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
