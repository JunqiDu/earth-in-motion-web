"""Independent physical and spatial constraints for the Phase 3B pilot.

This module deliberately does *not* read EGS class-2 flood labels.  It only
prepares static, independently sourced context and applies deterministic
constraints to an already-classified SAR candidate.  EGS class-2 belongs in
the validation runner, never in these functions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.warp import reproject
from scipy import ndimage
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform
from pyproj import CRS, Transformer

from .rcm_preprocessing import CommonGrid
from .water_classification import cleanup_mask


# AAFC 2020 land-use codes: cropland, annual cropland, and their respective
# recently-converted subclasses.  These are all explicitly Cropland in the
# AAFC product class table; pasture and generic grassland are intentionally
# excluded.
AAFC_CROPLAND_CODES: tuple[int, ...] = (51, 52, 55, 56)


def sha256_file(path: str | Path) -> str:
    """Hash a local source artifact without loading it all into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_grid(src: rasterio.DatasetReader, grid: CommonGrid, *, label: str) -> None:
    if src.crs is None or src.crs.to_string() != grid.crs:
        raise ValueError(f"{label} CRS must be {grid.crs}; found {src.crs}")
    if src.shape != (grid.height, grid.width):
        raise ValueError(f"{label} shape must be {(grid.height, grid.width)}; found {src.shape}")
    if not src.transform.almost_equals(grid.transform):
        raise ValueError(f"{label} transform does not match the Phase 3B common grid")


def read_aligned_land_use(path: str | Path, grid: CommonGrid) -> tuple[np.ndarray, np.ndarray]:
    """Read the already aligned AAFC 30 m AOI extract and preserve nodata."""
    with rasterio.open(path) as src:
        _assert_grid(src, grid, label="AAFC 2020 land-use extract")
        values = src.read(1)
        valid = src.dataset_mask() > 0
        if src.nodata is not None:
            valid &= values != src.nodata
    return values.astype("int16", copy=False), valid


def load_dem_to_grid(dem_paths: Iterable[str | Path], grid: CommonGrid) -> tuple[np.ndarray, np.ndarray]:
    """Mosaic SNAP's existing Copernicus DEM cache onto the common grid."""
    datasets = [rasterio.open(path) for path in dem_paths]
    if not datasets:
        raise FileNotFoundError("No Copernicus DEM tiles were supplied")
    try:
        mosaic, transform = merge(datasets)
        elevation = np.full((grid.height, grid.width), np.nan, dtype="float32")
        reproject(
            mosaic[0], elevation,
            src_transform=transform, src_crs=datasets[0].crs,
            dst_transform=grid.transform, dst_crs=grid.crs,
            src_nodata=datasets[0].nodata, dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    finally:
        for dataset in datasets:
            dataset.close()
    return elevation, np.isfinite(elevation)


def slope_degrees(elevation_m: np.ndarray, resolution_m: float) -> np.ndarray:
    """Compute terrain slope for QA only; it is not a v1 binary gate."""
    elevation_m = np.asarray(elevation_m, dtype=float)
    if not np.isfinite(elevation_m).any():
        return np.full(elevation_m.shape, np.nan, dtype="float32")
    filled = elevation_m.copy()
    filled[~np.isfinite(filled)] = float(np.nanmedian(filled))
    dz_dy, dz_dx = np.gradient(filled, resolution_m, resolution_m)
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype("float32")
    slope[~np.isfinite(elevation_m)] = np.nan
    return slope


def _geojson_crs(payload: dict[str, Any]) -> CRS:
    crs = payload.get("crs", {})
    name = crs.get("properties", {}).get("name") if isinstance(crs, dict) else None
    if not name:
        raise ValueError("Hydrography GeoJSON must declare its CRS")
    return CRS.from_user_input(name)


def rasterize_geojson(paths: Iterable[str | Path], grid: CommonGrid, *, all_touched: bool = True) -> np.ndarray:
    """Rasterize any available local vector source, tolerating an empty layer."""
    target_crs = CRS.from_user_input(grid.crs)
    geometries: list[tuple[Any, int]] = []
    for source_path in paths:
        path = Path(source_path)
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        source_crs = _geojson_crs(payload)
        transform = None if source_crs == target_crs else Transformer.from_crs(source_crs, target_crs, always_xy=True).transform
        for feature in payload.get("features", []):
            geometry_payload = feature.get("geometry")
            if not geometry_payload:
                continue
            geometry = shape(geometry_payload)
            if transform is not None:
                geometry = shapely_transform(transform, geometry)
            if not geometry.is_empty:
                geometries.append((geometry, 1))
    if not geometries:
        return np.zeros((grid.height, grid.width), dtype=bool)
    return rasterize(
        geometries, out_shape=(grid.height, grid.width), transform=grid.transform,
        fill=0, default_value=1, dtype="uint8", all_touched=all_touched,
    ).astype(bool)


def distance_to_mask_m(mask: np.ndarray, resolution_m: float) -> np.ndarray:
    """Return Euclidean pixel-centre distance; an empty source becomes inf."""
    mask = np.asarray(mask, dtype=bool)
    if not mask.any():
        return np.full(mask.shape, np.inf, dtype="float32")
    return (ndimage.distance_transform_edt(~mask) * resolution_m).astype("float32")


def components_connected_to_context(mask: np.ndarray, context_mask: np.ndarray) -> np.ndarray:
    """Flag candidate components touching a context mask without changing them."""
    mask = np.asarray(mask, dtype=bool)
    context_mask = np.asarray(context_mask, dtype=bool)
    labels, count = ndimage.label(mask, ndimage.generate_binary_structure(2, 2))
    connected = np.zeros(count + 1, dtype=bool)
    if count:
        connected[np.unique(labels[context_mask & (labels > 0)])] = True
    return (labels > 0) & connected[labels]


def _write_grid(path: Path, values: np.ndarray, grid: CommonGrid, *, dtype: str, nodata: float | int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path, "w", driver="GTiff", height=grid.height, width=grid.width,
        count=1, dtype=dtype, crs=grid.crs, transform=grid.transform,
        nodata=nodata, compress="deflate",
    ) as destination:
        destination.write(values.astype(dtype), 1)


@dataclass(frozen=True)
class PhysicalContext:
    """Static independent context aligned to the immutable 30 m grid."""

    elevation_m: np.ndarray
    elevation_valid: np.ndarray
    slope_deg: np.ndarray
    land_use: np.ndarray
    land_use_valid: np.ndarray
    hydrography: np.ndarray
    hydro_distance_m: np.ndarray
    wetlands: np.ndarray
    provenance: dict[str, Any]

    @property
    def valid(self) -> np.ndarray:
        return self.elevation_valid & self.land_use_valid

    @property
    def cropland(self) -> np.ndarray:
        return np.isin(self.land_use, AAFC_CROPLAND_CODES) & self.land_use_valid


def prepare_physical_context(
    *,
    grid: CommonGrid,
    dem_paths: Iterable[str | Path],
    land_use_path: str | Path,
    hydro_paths: Iterable[str | Path],
    wetland_paths: Iterable[str | Path] = (),
    output_dir: str | Path | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> PhysicalContext:
    """Build deterministic 30 m context layers from independent sources."""
    elevation, elevation_valid = load_dem_to_grid(dem_paths, grid)
    land_use, land_use_valid = read_aligned_land_use(land_use_path, grid)
    hydrography = rasterize_geojson(hydro_paths, grid)
    wetlands = rasterize_geojson(wetland_paths, grid)
    context = PhysicalContext(
        elevation_m=elevation,
        elevation_valid=elevation_valid,
        slope_deg=slope_degrees(elevation, grid.resolution),
        land_use=land_use,
        land_use_valid=land_use_valid,
        hydrography=hydrography,
        hydro_distance_m=distance_to_mask_m(hydrography, grid.resolution),
        wetlands=wetlands,
        provenance=dict(source_metadata or {}),
    )
    if output_dir is not None:
        output = Path(output_dir)
        elevation_out = np.where(context.elevation_valid, context.elevation_m, -9999.0)
        slope_out = np.where(context.elevation_valid, context.slope_deg, -9999.0)
        _write_grid(output / "elevation_m.tif", elevation_out, grid, dtype="float32", nodata=-9999.0)
        _write_grid(output / "slope_deg.tif", slope_out, grid, dtype="float32", nodata=-9999.0)
        _write_grid(output / "land_use_aafc_2020.tif", context.land_use, grid, dtype="int16", nodata=-32768)
        _write_grid(output / "cropland_mask.tif", context.cropland.astype("uint8"), grid, dtype="uint8", nodata=255)
        _write_grid(output / "hydrography_mask.tif", context.hydrography.astype("uint8"), grid, dtype="uint8", nodata=255)
        _write_grid(output / "hydrography_distance_m.tif", context.hydro_distance_m, grid, dtype="float32", nodata=-9999.0)
        _write_grid(output / "wetland_mask.tif", context.wetlands.astype("uint8"), grid, dtype="uint8", nodata=255)
    return context


def apply_multisource_constraints(
    sar_candidate: np.ndarray,
    hh_db: np.ndarray,
    valid: np.ndarray,
    context: PhysicalContext,
    *,
    hh_threshold_db: float,
    elevation_max_m: float,
    cropland_extra_darkness_db: float,
    min_component_pixels: int = 2,
    cleanup_after_constraints: bool = False,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Apply v1's lowland and cropland-darkness rules without hidden labels.

    Cropland remains eligible.  It needs a darkness margin relative to the
    existing SAR threshold, whereas other land-use classes do not.
    """
    sar_candidate = np.asarray(sar_candidate, dtype=bool)
    hh_db = np.asarray(hh_db, dtype=float)
    valid = np.asarray(valid, dtype=bool) & context.valid & np.isfinite(hh_db)
    elevation_ok = np.isfinite(context.elevation_m) & (context.elevation_m <= elevation_max_m)
    darkness_margin = hh_threshold_db - hh_db
    cropland_confident = (~context.cropland) | (darkness_margin >= cropland_extra_darkness_db)
    constrained = sar_candidate & valid & elevation_ok & cropland_confident
    # The formal runner starts from the already cleaned, registered SAR
    # candidate.  Re-cleaning after a plausibility gate is optional because it
    # can erase legitimate narrow flood fragments created by clipping a larger
    # component.  V1 therefore preserves the existing cleanup exactly.
    if cleanup_after_constraints:
        constrained = cleanup_mask(constrained, valid, min_component_pixels=min_component_pixels)
    context_flags = {
        "elevation_ok": elevation_ok,
        "cropland": context.cropland,
        "cropland_confident": cropland_confident,
        "hydro_within_90m": context.hydro_distance_m <= 90.0,
        "hydro_within_300m": context.hydro_distance_m <= 300.0,
        "hydro_connected": components_connected_to_context(constrained, context.hydrography),
    }
    return constrained, context_flags
