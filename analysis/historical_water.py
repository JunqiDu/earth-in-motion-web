"""Historical inundation-frequency labels for the Phase 3B RF experiment.

The Canadian Dynamic Surface Water Maps are used as a *training prior*.  They
are deliberately kept separate from the EGS class-2 validation masks and the
fixed EGS semantic permanent-water reference.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

from .rcm_preprocessing import CommonGrid


CANADA_DSW_URL = (
    "https://datacube-prod-data-public.s3.ca-central-1.amazonaws.com/store/"
    "water/dynamic-surface-water/dynamic-surface-water-compilation/"
    "dsw-1984-2023-frequency.tif"
)


@dataclass(frozen=True)
class HistoricalWaterLabels:
    frequency: np.ndarray
    stable_land: np.ndarray
    stable_water: np.ndarray
    uncertain: np.ndarray
    valid: np.ndarray
    provenance: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_frequency_raster(source: str | Path, grid: CommonGrid) -> HistoricalWaterLabels:
    """Read/reproject only the fixed-grid window from an AOI or global COG.

    Nearest-neighbour is mandatory because the source values are categorical
    frequency classes.  The function accepts a small AOI extract (the normal
    checked-in workflow) or the full public COG without loading it into memory.
    """
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(
            f"Historical water raster not found: {path}. Download the AOI window "
            "or pass --frequency-raster explicitly."
        )
    destination = np.full((grid.height, grid.width), 255, dtype=np.uint8)
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata if src.nodata is not None else 255,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            dst_nodata=255,
            resampling=Resampling.nearest,
        )
        source_meta = {
            "source_crs": src.crs.to_string() if src.crs else None,
            "source_resolution_m": [float(src.transform.a), float(abs(src.transform.e))],
            "source_shape": [int(src.height), int(src.width)],
            "source_nodata": src.nodata,
        }
    valid = destination != 255
    stable_land = valid & (destination == 0)
    stable_water = valid & (destination >= 80)
    uncertain = valid & (destination >= 1) & (destination <= 79)
    provenance = {
        "dataset": "Dynamic Surface Water Maps of Canada",
        "provider": "Environment and Climate Change Canada",
        "source_url": CANADA_DSW_URL,
        "source_year_range": "1984-2023",
        "source_path": str(path),
        "source_sha256": _sha256(path),
        "access_date": date.today().isoformat(),
        "frequency_semantics": {"0": "stable land", "1-79": "uncertain/seasonal", ">=80": "stable water", "255": "nodata"},
        "grid": grid.as_dict(),
        "reprojection": "nearest-neighbour to EPSG:32610 30 m 200x200 grid",
        "source_metadata": source_meta,
        "counts": {
            "stable_land": int(stable_land.sum()),
            "stable_water": int(stable_water.sum()),
            "uncertain": int(uncertain.sum()),
            "valid": int(valid.sum()),
        },
    }
    return HistoricalWaterLabels(destination, stable_land, stable_water, uncertain, valid, provenance)


def write_frequency_provenance(path: str | Path, labels: HistoricalWaterLabels) -> None:
    Path(path).write_text(json.dumps(labels.provenance, indent=2, sort_keys=True, default=str))


def training_labels(labels: HistoricalWaterLabels, *, strict_water: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (land, water, eligible) masks for a registered label policy."""
    if strict_water:
        water = labels.valid & (labels.frequency == 100)
    else:
        water = labels.stable_water
    land = labels.stable_land
    eligible = land | water
    return land, water, eligible
