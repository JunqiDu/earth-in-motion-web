#!/usr/bin/env python
"""Run the registered two-scene SNAP/Rasterio Phase 3B smoke test.

This intentionally processes only P01 (16M9) and P02 (SC30MB). It writes to
the ignored phase3b cache and never changes Phase 4/5 artifacts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.warp import reproject
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.rcm_preprocessing import CommonGrid, find_snap_gpt, render_snap_graph, run_snap_graph


def _aoi_wkt(grid: CommonGrid) -> str:
    bounds = box(grid.left - 2000, grid.bottom - 2000, grid.right + 2000, grid.top + 2000)
    transformer = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True)
    coordinates = [transformer.transform(x, y) for x, y in bounds.exterior.coords]
    return "POLYGON((" + ",".join(f"{x} {y}" for x, y in coordinates) + "))"


def _aggregate(source_path: Path, target_path: Path, valid_path: Path, grid: CommonGrid) -> dict[str, object]:
    with rasterio.open(source_path) as source:
        if source.count < 2:
            raise RuntimeError(f"Expected HH/HV bands, found {source.count}: {source_path}")
        arrays = []
        source_valid = np.ones((source.height, source.width), dtype="float32")
        for index in (1, 2):
            array = source.read(index).astype("float32")
            array[~np.isfinite(array) | (array <= 0)] = np.nan
            arrays.append(array)
        coverage = np.zeros((grid.height, grid.width), dtype="float32")
        reproject(source_valid, coverage, src_transform=source.transform, src_crs=source.crs,
                  dst_transform=grid.transform, dst_crs=grid.crs,
                  resampling=Resampling.average, src_nodata=0, dst_nodata=0)
        valid = coverage >= 0.95
        profile = {
            "driver": "GTiff", "height": grid.height, "width": grid.width, "count": 2,
            "dtype": "float32", "crs": grid.crs, "transform": grid.transform,
            "nodata": np.nan, "compress": "deflate",
        }
        with rasterio.open(target_path, "w", **profile) as target:
            for index, array in enumerate(arrays, start=1):
                output = np.full((grid.height, grid.width), np.nan, dtype="float32")
                reproject(array, output, src_transform=source.transform, src_crs=source.crs,
                          dst_transform=grid.transform, dst_crs=grid.crs,
                          resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
                output[~valid] = np.nan
                target.write(output, index)
                target.set_band_description(index, ("HH_gamma0_linear_power", "HV_gamma0_linear_power")[index - 1])
            target.update_tags(PHASE3B="smoke", representation="Gamma0 linear power", valid_threshold="source coverage >= 95%")
        with rasterio.open(valid_path, "w", driver="GTiff", height=grid.height, width=grid.width,
                           count=1, dtype="uint8", crs=grid.crs, transform=grid.transform, nodata=0,
                           compress="deflate") as mask:
            mask.write(valid.astype("uint8"), 1)
            mask.set_band_description(1, "valid_source_coverage_ge_95pct")
    with rasterio.open(target_path) as checked:
        if checked.crs.to_string() != grid.crs or checked.width != grid.width or checked.height != grid.height:
            raise RuntimeError(f"Fixed-grid geometry check failed for {target_path}")
        values = checked.read(1, masked=True)
        if not values.count() or not np.isfinite(values.compressed()).all():
            raise RuntimeError(f"No finite HH values in {target_path}")
        return {
            "path": str(target_path), "crs": checked.crs.to_string(),
            "width": checked.width, "height": checked.height,
            "transform": tuple(checked.transform), "nodata": checked.nodata,
            "valid_pixels": int(values.count()),
            "hh_power_min": float(values.min()), "hh_power_max": float(values.max()),
            "hh_power_mean": float(values.mean()),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpt", default=None)
    parser.add_argument("--cache", default="data/processed/phase3b/cache/smoke")
    args = parser.parse_args()
    grid = CommonGrid()
    gpt = find_snap_gpt(args.gpt)
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    root = Path("data/raw/rcm_level1")
    aoi = _aoi_wkt(grid)
    projection = escape(CRS.from_epsg(32610).to_wkt())
    scenes = [
        ("P01_16m", next(root.glob("*16M9_20251214_142421*/**/manifest.safe")), 16),
        ("P02_SC30MB", next(root.glob("*SC30MB_20251215_015036*/**/manifest.safe")), 30),
    ]
    summaries = []
    for name, manifest, spacing in scenes:
        graph = cache / f"{name}.xml"
        tc = cache / f"{name}_tc.tif"
        fixed = cache / f"{name}_tc_30m.tif"
        valid = cache / f"{name}_valid.tif"
        render_snap_graph("config/snap/phase3b_smoke.xml", graph,
                          SOURCE_MANIFEST=str(manifest.resolve()), AOI_WKT=aoi,
                          INTERMEDIATE_PIXEL_SPACING_M=str(spacing), MAP_PROJECTION_WKT="EPSG:32610",
                          OUTPUT_PRODUCT=str(tc.resolve()))
        run_snap_graph(graph, gpt=gpt, heap="-J-Xmx12G")
        summaries.append(_aggregate(tc, fixed, valid, grid))
    print("Phase 3B smoke test passed")
    for summary in summaries:
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
