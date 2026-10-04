"""Versioned EGS vector snapshots: one reprojection and center rasterization."""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from shapely.geometry import box, mapping, shape

from .physical_constraints import sha256_file


def geometry_mask(geometry, grid):
    if geometry.is_empty:
        return np.zeros((grid.height, grid.width), bool)
    return rasterize([(mapping(geometry), 1)], out_shape=(grid.height, grid.width),
                     transform=grid.transform, all_touched=False, dtype="uint8").astype(bool)


def stage_raw_reference(product_folder: Path, destination: Path, grid, *, timestamp_utc: str):
    """Snapshot original classes and product footprint, never a Phase4 mask."""
    flood_file = next(product_folder.glob("Flood_*.shp"))
    footprint_file = next(product_folder.glob("Footprint_*.shp"))
    raw = gpd.read_file(flood_file)
    footprint = gpd.read_file(footprint_file)
    if raw.crs is None or footprint.crs is None:
        raise ValueError("Original EGS CRS must be explicit")
    features = []
    area = box(*grid.bounds)
    projected = raw.to_crs(grid.crs)
    for category in (1, 2):
        geometry = projected.loc[projected["class"].eq(category)].geometry.union_all().intersection(area)
        features.append({"type": "Feature", "properties": {"class": category,
                         "timestamp_utc": timestamp_utc, "source_product": product_folder.name},
                         "geometry": mapping(geometry)})
    extent = footprint.to_crs(grid.crs).geometry.union_all().intersection(area)
    features.append({"type": "Feature", "properties": {"role": "valid_footprint"}, "geometry": mapping(extent)})
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": grid.crs}}, "features": features}))
    sources = sorted({p for f in (flood_file, footprint_file) for p in f.parent.glob(f.stem + ".*") if p.is_file()})
    return {"product": product_folder.name, "timestamp_utc": timestamp_utc,
            "class_semantics": {"1": "EGS semantic permanent water", "2": "EGS satellite-visible open-water flood"},
            "source_crs": str(raw.crs), "target_crs": grid.crs,
            "source_files": {str(p): sha256_file(p) for p in sources},
            "source_url": "https://data.eodms-sgdot.nrcan-rncan.gc.ca/public/EGS/2025/Flood/CAN/BC/" + product_folder.name + ".zip",
            "snapshot": str(destination), "snapshot_sha256": sha256_file(destination),
            "grid": grid.as_dict(), "rasterization": "center, all_touched=False; one reprojection, one rasterization",
            "phase4_intermediate_used": False}


def load_raw_reference(path: Path, grid):
    data = json.loads(path.read_text())
    if data["crs"]["properties"]["name"] != grid.crs:
        raise ValueError("Reference snapshot CRS mismatch")
    classes = {f["properties"].get("class"): shape(f["geometry"]) for f in data["features"] if "class" in f["properties"]}
    footprint = next(shape(f["geometry"]) for f in data["features"] if f["properties"].get("role") == "valid_footprint")
    return geometry_mask(classes[2], grid), geometry_mask(footprint, grid), geometry_mask(classes[1], grid)
