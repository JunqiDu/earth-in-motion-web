"""Auditable numerical and reference diagnostics for the Phase 3B pilot.

These helpers deliberately inspect the actual cached arrays and Level-1
metadata.  They do not choose classifier parameters or change Phase 4/5.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import rasterio


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _node_text(root: ET.Element, name: str) -> str:
    for element in root.iter():
        if _local_name(element) == name and element.text:
            return element.text.strip()
    raise KeyError(f"{name} not found in LUT")


def find_measurement(product_root: str | Path, polarization: str = "HH") -> Path:
    matches = sorted(Path(product_root).rglob(f"*_{polarization}.tif"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one {polarization} measurement TIFF below {product_root}; found {matches}")
    return matches[0]


def find_lut(product_root: str | Path, representation: str = "Gamma", polarization: str = "HH") -> Path:
    matches = sorted(Path(product_root).rglob(f"lut{representation}_{polarization}.xml"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one LUT below {product_root}; found {matches}")
    return matches[0]


def parse_lut(path: str | Path) -> dict[str, np.ndarray | float | int]:
    """Read an RCM gain LUT; positions are sample columns, not row indices."""
    root = ET.parse(path).getroot()
    first = int(float(_node_text(root, "pixelFirstLutValue")))
    step = int(float(_node_text(root, "stepSize")))
    offset = float(_node_text(root, "offset"))
    gain_text = _node_text(root, "gains")
    gains = np.fromstring(gain_text, sep=" ", dtype="float64")
    if gains.size == 0 or step == 0:
        raise ValueError(f"Invalid RCM LUT: {path}")
    positions = first + step * np.arange(gains.size)
    return {"first": first, "step": step, "offset": offset, "positions": positions, "gains": gains}


def lut_gain_at_columns(lut: dict[str, np.ndarray | float | int], columns: np.ndarray) -> np.ndarray:
    """Apply the RCM LUT's documented stepwise sample-column lookup.

    ScanSAR gains are supplied at a coarser column stride.  SNAP uses the
    preceding LUT sample for a pixel within that stride; linearly
    interpolating those values caused a reproducible ~2.3e-4 relative mismatch
    in the SC30MB audit.
    """
    positions = np.asarray(lut["positions"], dtype=float)
    gains = np.asarray(lut["gains"], dtype=float)
    columns = np.asarray(columns, dtype=float)
    first, step = float(lut["first"]), float(lut["step"])
    index = np.floor((columns - first) / step).astype(int)
    if np.any(index < 0) or np.any(index >= gains.size):
        raise ValueError("Requested sample falls outside LUT support")
    return gains[index]


def choose_interior_samples(measurement: str | Path, count: int = 3) -> list[dict[str, int]]:
    """Return stable valid pixels away from an image edge and saturation."""
    with rasterio.open(measurement) as src:
        data = src.read(1)
    height, width = data.shape
    targets = [(height // 3, width // 3), (height // 2, width // 2), (2 * height // 3, 2 * width // 3)]
    selected: list[dict[str, int]] = []
    for row, col in targets:
        found = None
        for radius in range(0, 101):
            r0, r1 = max(64, row - radius), min(height - 64, row + radius + 1)
            c0, c1 = max(64, col - radius), min(width - 64, col + radius + 1)
            window = data[r0:r1, c0:c1]
            valid = np.argwhere((window > 0) & (window < np.iinfo(window.dtype).max))
            if valid.size:
                rr, cc = valid[len(valid) // 2]
                found = {"row": int(r0 + rr), "col": int(c0 + cc)}
                break
        if found is None:
            raise RuntimeError(f"No safe interior sample near {(row, col)}")
        selected.append(found)
    return selected[:count]


def raw_dn_at_samples(measurement: str | Path, samples: list[dict[str, int]]) -> np.ndarray:
    with rasterio.open(measurement) as src:
        data = src.read(1)
    return np.asarray([data[item["row"], item["col"]] for item in samples], dtype="float64")


def finite_distribution(values: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not values.size:
        return {"count": 0, "p1": np.nan, "p5": np.nan, "median": np.nan, "p95": np.nan, "p99": np.nan, "min": np.nan, "max": np.nan}
    p1, p5, med, p95, p99 = np.percentile(values, [1, 5, 50, 95, 99])
    return {"count": int(values.size), "p1": float(p1), "p5": float(p5), "median": float(med), "p95": float(p95), "p99": float(p99), "min": float(values.min()), "max": float(values.max())}


def parse_geojson_crs(path: str | Path) -> str | None:
    data = __import__("json").loads(Path(path).read_text())
    crs = data.get("crs")
    if isinstance(crs, dict):
        props = crs.get("properties", {})
        return props.get("name") or props.get("href")
    return None
