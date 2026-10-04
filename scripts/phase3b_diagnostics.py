#!/usr/bin/env python
"""Generate Phase 3B diagnostic evidence without changing scientific outputs."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.phase3b_diagnostics import (
    choose_interior_samples, find_lut, find_measurement, finite_distribution,
    lut_gain_at_columns, parse_geojson_crs, parse_lut, raw_dn_at_samples,
)
from analysis.rcm_level1 import pilot_inventory
from analysis.rcm_preprocessing import CommonGrid, calibrate_dn_power, render_snap_graph, run_snap_graph
from analysis.water_classification import cleanup_mask

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/phase3b"
CACHE = OUT / "cache/pilot"
GRID = CommonGrid()


def _pilot() -> pd.DataFrame:
    return pilot_inventory(pd.read_csv(OUT / "level1_inventory.csv")).set_index("observation_id")


def _reference_mask(path: Path, observation_id: str | None = None) -> np.ndarray:
    data = json.loads(path.read_text())
    shapes = []
    for feature in data.get("features", []):
        if observation_id and feature.get("properties", {}).get("observation_id") != observation_id:
            continue
        shapes.append((shape(feature["geometry"]), 1))
    return rasterize(shapes, out_shape=(GRID.height, GRID.width), transform=GRID.transform,
                     dtype="uint8", fill=0, all_touched=False).astype(bool)


def _fold_parameters() -> tuple[str, str, dict[str, dict[str, float]]]:
    metrics = pd.read_csv(OUT / "validation_metrics.csv")
    # The corrected baseline selected C2; use the actual held-out threshold
    # per scene only for *diagnostic area accounting*, not a new method.
    summary = json.loads((OUT / "validation_summary.json").read_text())
    selected = summary["selected_candidate"]
    representation = summary.get("selected_representation", "Gamma0")
    rows = metrics[(metrics.candidate_id == selected) & (metrics.representation == representation)]
    parameters: dict[str, dict[str, float]] = {}
    for _, row in rows.iterrows():
        params = json.loads(row.thresholds)
        group = row.mode_group
        parameters[row.observation_id] = params
    return selected, representation, parameters


def _selected_prediction(arr, sid: str, mode_group: str, candidate: str, representation: str, params: dict[str, dict[str, float]], noise_floor_hv: float) -> np.ndarray:
    values = params[sid]
    threshold = values["global_hh"] if "global_hh" in values else values[f"{mode_group}_hh"]
    prefix = "gamma" if representation == "Gamma0" else "sigma"
    predicted = arr[f"{prefix}_hh_db"] < threshold
    if candidate == "C2_group_hh_hv":
        hv_threshold = values[f"{mode_group}_hv"]
        usable = np.isfinite(arr[f"{prefix}_hv_db"]) & (arr[f"{prefix}_hv_db"] >= noise_floor_hv + 3.0)
        predicted &= (~usable) | (arr[f"{prefix}_hv_db"] < hv_threshold)
    return predicted


def _hv_noise_floor(product_root: str) -> float:
    files = list(Path(product_root).rglob("noiseLevels_HV.xml"))
    if not files:
        return float("-inf")
    text = files[0].read_text(errors="replace")
    values = [float(value) for value in re.findall(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[Ee][-+]?\d+)?", text.split("<noiseLevelValues", 1)[-1])]
    return max(values) if values else float("-inf")


def summarize() -> None:
    pilot = _pilot()
    permanent_path = OUT.parent / "phase4/egs_permanent_water_reference.geojson"
    frames_path = OUT.parent / "phase4/egs_open_water_flood_frames.geojson"
    permanent = _reference_mask(permanent_path)
    distributions, masks = [], []
    candidate, representation, parameters = _fold_parameters()
    for sid, row in pilot.iterrows():
        arr = np.load(CACHE / sid / "grid_arrays.npz")
        valid = arr["common_valid"].astype(bool)
        egs = _reference_mask(frames_path, row.egs_observation_id)
        for representation in ("gamma", "sigma"):
            for pol in ("hh", "hv"):
                for units, key in (("linear_power", f"{representation}_{pol}_power"), ("dB", f"{representation}_{pol}_db")):
                    distributions.append({"observation_id": sid, "beam_mode": row.beam_mode,
                                          "mode_group": row.mode_group, "representation": representation.title(),
                                          "polarization": pol.upper(), "units": units,
                                          **finite_distribution(arr[key][valid])})
        noise_floor = _hv_noise_floor(row.source_product)
        raw_water = _selected_prediction(arr, sid, row.mode_group, candidate, representation, parameters, noise_floor) & valid
        flood_pre_cleanup = raw_water & ~permanent
        flood_post_cleanup = cleanup_mask(flood_pre_cleanup, valid, min_component_pixels=2)
        entries = {
            "valid": valid, "fixed_semantic_permanent_reference": permanent & valid,
            "egs_open_water_flood_reference": egs & valid, "classified_water_before_semantic_subtraction": raw_water,
            "candidate_flood_before_cleanup": flood_pre_cleanup, "candidate_flood_after_cleanup": flood_post_cleanup,
        }
        for label, mask in entries.items():
            masks.append({"observation_id": sid, "mask": label, "pixels": int(mask.sum()),
                          "area_ha": float(mask.sum() * GRID.pixel_area_ha), "fraction_of_valid_pct": float(mask.sum() / valid.sum() * 100)})
    pd.DataFrame(distributions).to_csv(OUT / "calibrated_value_distributions.csv", index=False)
    pd.DataFrame(masks).to_csv(OUT / "mask_area_audit.csv", index=False)
    reference = {
        "grid_crs": GRID.crs, "grid_shape": [GRID.height, GRID.width], "pixel_rule": "pixel-centre (all_touched=false)",
        "permanent_reference": {"path": str(permanent_path), "source_crs": parse_geojson_crs(permanent_path),
                                "pixels": int(permanent.sum()), "area_ha": float(permanent.sum() * GRID.pixel_area_ha),
                                "semantic": "fixed EGS semantic permanent-water reference; not normal or pre-event water"},
        "egs_open_water_frames": {"path": str(frames_path), "source_crs": parse_geojson_crs(frames_path),
                                  "per_observation": {sid: {"egs_observation_id": row.egs_observation_id,
                                  "pixels": int(_reference_mask(frames_path, row.egs_observation_id).sum()),
                                  "area_ha": float(_reference_mask(frames_path, row.egs_observation_id).sum() * GRID.pixel_area_ha)}
                                  for sid, row in pilot.iterrows()}},
        "alignment_note": "Both Phase 4 reference GeoJSON files declare EPSG:32610, matching the fixed grid. Their semantic permanent-water geometry cannot be used as a same-date shoreline registration truth during a flood; a source-to-reference shoreline offset gate is therefore not claimed from this pilot.",
    }
    (OUT / "reference_rasterization_audit.json").write_text(json.dumps(reference, indent=2))
    _figures(pilot, permanent, frames_path, candidate, representation, parameters)


def _figures(pilot: pd.DataFrame, permanent: np.ndarray, frames_path: Path, candidate: str, representation: str, parameters: dict[str, dict[str, float]]) -> None:
    figure_dir = OUT / "qa_figures"
    figure_dir.mkdir(exist_ok=True)
    for sid in ("20251214T142421Z", "20251215T015036Z"):
        row = pilot.loc[sid]
        arr = np.load(CACHE / sid / "grid_arrays.npz")
        valid = arr["common_valid"].astype(bool)
        egs = _reference_mask(frames_path, row.egs_observation_id)
        classified = _selected_prediction(arr, sid, row.mode_group, candidate, representation, parameters, _hv_noise_floor(row.source_product)) & valid & ~permanent
        classified = cleanup_mask(classified, valid, min_component_pixels=2)
        fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), constrained_layout=True)
        im = axes[0].imshow(np.ma.masked_invalid(arr["gamma_hh_db"]), cmap="gray", vmin=-25, vmax=0)
        axes[0].contour(permanent, levels=[0.5], colors="#4c78a8", linewidths=0.8)
        axes[0].set_title(f"{sid}: Gamma0 HH (dB)\nblue = fixed semantic reference")
        fig.colorbar(im, ax=axes[0], shrink=0.8, label="dB")
        axes[1].imshow(valid, cmap="Greys", vmin=0, vmax=1)
        axes[1].contour(egs, levels=[0.5], colors="#e45756", linewidths=1.0)
        axes[1].set_title("Valid grid and EGS class-2 reference\nred = open-water flood class")
        view = np.zeros((*valid.shape, 3), dtype=float)
        view[..., 0] = classified
        view[..., 1] = egs
        view[..., 2] = permanent
        axes[2].imshow(view)
        axes[2].set_title("Diagnostic overlay\nred = prediction, green = EGS, blue = semantic reference")
        for ax in axes:
            ax.set_xticks([]); ax.set_yticks([])
        fig.savefig(figure_dir / f"{sid}_diagnostic.png", dpi=180)
        plt.close(fig)


def lut_qa() -> None:
    pilot = _pilot()
    targets = ["20251214T142421Z", "20251215T015036Z"]
    cache = OUT / "cache/lut_qa"
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    for sid in targets:
        row = pilot.loc[sid]
        measurement = find_measurement(row.source_product, "HH")
        gamma_lut = parse_lut(find_lut(row.source_product, "Gamma", "HH"))
        sigma_lut = parse_lut(find_lut(row.source_product, "Sigma", "HH"))
        samples = choose_interior_samples(measurement)
        dns = raw_dn_at_samples(measurement, samples)
        columns = np.array([x["col"] for x in samples])
        direct_gamma = calibrate_dn_power(dns, lut_gain_at_columns(gamma_lut, columns), float(gamma_lut["offset"]))
        direct_sigma = calibrate_dn_power(dns, lut_gain_at_columns(sigma_lut, columns), float(sigma_lut["offset"]))
        manifest = next(Path(row.source_product).rglob("manifest.safe"))
        for number, (sample, dn, expected_gamma, expected_sigma) in enumerate(zip(samples, dns, direct_gamma, direct_sigma), start=1):
            scene = cache / sid
            scene.mkdir(parents=True, exist_ok=True)
            graph = scene / f"sample_{number}.xml"
            output = scene / f"gamma_sample_{number}.tif"
            render_snap_graph(ROOT / "config/snap/phase3b_calibration_lut_qa.xml", graph,
                              SOURCE_MANIFEST=str(manifest.resolve()), POLARIZATION="HH",
                              PIXEL_REGION=f"{sample['col'] - 1},{sample['row'] - 1},3,3", OUTPUT_PRODUCT=str(output.resolve()))
            run_snap_graph(graph, heap="-J-Xmx4G")
            with rasterio.open(output) as src:
                snap_gamma = float(src.read(1)[1, 1])
            sigma_graph = scene / f"sigma_sample_{number}.xml"
            sigma_output = scene / f"sigma_sample_{number}.tif"
            render_snap_graph(ROOT / "config/snap/phase3b_sigma_lut_qa.xml", sigma_graph,
                              SOURCE_MANIFEST=str(manifest.resolve()), POLARIZATION="HH",
                              PIXEL_REGION=f"{sample['col'] - 1},{sample['row'] - 1},3,3", OUTPUT_PRODUCT=str(sigma_output.resolve()))
            run_snap_graph(sigma_graph, heap="-J-Xmx4G")
            with rasterio.open(sigma_output) as src:
                snap_sigma = float(src.read(1)[1, 1])
            gamma_rel = abs(snap_gamma - expected_gamma) / expected_gamma
            sigma_rel = abs(snap_sigma - expected_sigma) / expected_sigma
            rows.append({"observation_id": sid, "beam_mode": row.beam_mode, "sample": number,
                         **sample, "dn": float(dn), "expected_sigma_power": float(expected_sigma),
                         "snap_sigma_power": snap_sigma, "sigma_relative_error": float(sigma_rel),
                         "expected_gamma_power": float(expected_gamma), "snap_gamma_power": snap_gamma,
                         "gamma_relative_error": float(gamma_rel),
                         "pass_native_sigma_1e-5": bool(sigma_rel <= 1e-5)})
    report = pd.DataFrame(rows)
    report.to_csv(OUT / "calibration_lut_qa.csv", index=False)
    if not report["pass_native_sigma_1e-5"].all():
        raise RuntimeError("Formal LUT QA failed; inspect calibration_lut_qa.csv before classification")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("summarize", "lut-qa"))
    args = parser.parse_args()
    if args.step == "summarize":
        summarize()
        print(f"Wrote diagnostics to {OUT}")
    else:
        lut_qa()
        print((OUT / "calibration_lut_qa.csv").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
