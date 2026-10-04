"""SNAP orchestration and deterministic 30 m grid utilities for Phase 3B."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject


class SnapUnavailableError(RuntimeError):
    """Raised when the ESA SNAP GPT executable is not installed/configured."""


@dataclass(frozen=True)
class CommonGrid:
    crs: str = "EPSG:32610"
    left: float = 563960.0
    bottom: float = 5443240.0
    right: float = 569960.0
    top: float = 5449240.0
    resolution: float = 30.0
    width: int = 200
    height: int = 200

    @property
    def transform(self):
        return from_origin(self.left, self.top, self.resolution, self.resolution)

    @property
    def pixel_area_ha(self) -> float:
        return self.resolution * self.resolution / 10000.0

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.left, self.bottom, self.right, self.top

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update({"bounds": self.bounds, "transform": tuple(self.transform), "pixel_area_ha": self.pixel_area_ha})
        return data


def find_snap_gpt(explicit: str | Path | None = None) -> Path:
    candidates = [Path(explicit)] if explicit else []
    if not explicit and os.environ.get("SNAP_GPT"):
        candidates.append(Path(os.environ["SNAP_GPT"]))
    if not explicit:
        which = shutil.which("gpt")
        if which:
            candidates.append(Path(which))
        candidates.extend([
            Path("/Applications/esa-snap/bin/gpt"),
            Path("/Applications/snap/bin/gpt"),
            Path.home() / "Applications/esa-snap/bin/gpt",
            Path.home() / "Applications/snap/bin/gpt",
        ])
    for candidate in candidates:
        if candidate and candidate.exists() and candidate.is_file() and os.access(candidate, os.X_OK):
            # macOS /usr/sbin/gpt is not ESA SNAP's Graph Processing Tool.
            if candidate.resolve() == Path("/usr/sbin/gpt"):
                continue
            return candidate
    raise SnapUnavailableError("ESA SNAP GPT not found. Install SNAP 14 with Microwave Toolbox or set SNAP_GPT.")


def snap_diagnostics(gpt: str | Path | None = None) -> dict[str, Any]:
    """Return a small, deterministic identity check for the ESA SNAP GPT binary."""
    executable = find_snap_gpt(gpt)
    result = subprocess.run([str(executable), "--diag"], check=False, text=True, capture_output=True)
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0:
        raise SnapUnavailableError(f"SNAP GPT diagnostics failed ({result.returncode}): {text[-500:]}")
    if "SNAP" not in text and "snap" not in text.lower():
        raise SnapUnavailableError("Resolved executable did not identify itself as ESA SNAP GPT")
    return {"path": str(executable), "returncode": result.returncode, "diagnostics": text.strip()}


def snap_operator_check(gpt: str | Path | None = None) -> dict[str, Any]:
    """Verify the Phase 3B operators and RCM input format are registered."""
    executable = find_snap_gpt(gpt)
    help_result = subprocess.run([str(executable), "-h"], check=False, text=True, capture_output=True)
    format_result = subprocess.run([str(executable), "-iformat"], check=False, text=True, capture_output=True)
    help_text = (help_result.stdout or "") + "\n" + (help_result.stderr or "")
    format_text = (format_result.stdout or "") + "\n" + (format_result.stderr or "")
    required = {name: (name in help_text) for name in ("Calibration", "Terrain-Correction")}
    required["RCM input format"] = bool(__import__("re").search(r"^RCM\s+\(", format_text, __import__("re").MULTILINE))
    return {"path": str(executable), "operators": required, "all_present": all(required.values()), "help_returncode": help_result.returncode, "iformat_returncode": format_result.returncode}


def graph_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render_snap_graph(template: str | Path, output: str | Path, **parameters: str) -> Path:
    text = Path(template).read_text()
    for key, value in parameters.items():
        text = text.replace("${" + key + "}", str(value))
    Path(output).write_text(text)
    return Path(output)


def run_snap_graph(graph: str | Path, *, gpt: str | Path | None = None, heap: str = "-J-Xmx8G") -> subprocess.CompletedProcess[str]:
    executable = find_snap_gpt(gpt)
    command = [str(executable), heap, str(graph)]
    return subprocess.run(command, check=True, text=True, capture_output=True)


def preprocess_scene(product: str | Path, grid: CommonGrid, config: dict[str, Any]) -> dict[str, Any]:
    """Run one rendered SNAP graph and return provenance paths.

    The caller supplies a rendered graph or a template plus ``graph_template``
    in *config*. This function intentionally fails before any work when SNAP is
    unavailable, rather than silently falling back to a non-equivalent warp.
    """
    graph_path = Path(config.get("graph", ""))
    if not graph_path.exists():
        template = config.get("graph_template")
        if not template:
            raise ValueError("config requires graph or graph_template")
        graph_path = Path(config.get("work_dir", ".")) / f"{Path(product).stem}_phase3b.xml"
        render_snap_graph(template, graph_path, SOURCE_MANIFEST=str(config.get("manifest", product)), TARGET_CRS=grid.crs, INTERMEDIATE_PIXEL_SPACING_M=str(config.get("intermediate_pixel_spacing_m", 30)), OUTPUT_PRODUCT=str(config.get("output_product", graph_path.with_suffix('.tif'))), AOI_WKT=str(config.get("aoi_wkt", "")), DEM_NAME=str(config.get("dem_name", "")), DEM_FILE=str(config.get("dem_file", "")))
    result = run_snap_graph(graph_path, gpt=config.get("gpt"), heap=config.get("heap", "-J-Xmx8G"))
    return {"product": str(product), "graph": str(graph_path), "stdout": result.stdout, "stderr": result.stderr, "output_product": str(config.get("output_product", "")), "grid": grid.as_dict()}


def aggregate_to_grid(source: np.ndarray, source_transform, source_crs: str, grid: CommonGrid, *, nodata: float = np.nan) -> np.ndarray:
    """Area-average a continuous linear-power raster into the fixed grid."""
    destination = np.full((grid.height, grid.width), nodata, dtype="float32")
    reproject(
        source.astype("float32"), destination,
        src_transform=source_transform, src_crs=source_crs,
        dst_transform=grid.transform, dst_crs=grid.crs,
        resampling=Resampling.average, src_nodata=np.nan, dst_nodata=nodata,
    )
    return destination


def aggregate_power_and_coverage(
    source: np.ndarray,
    source_transform,
    source_crs: str,
    grid: CommonGrid,
    *,
    source_valid: np.ndarray | None = None,
    threshold: float = 0.95,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average positive linear power and return power, coverage, and valid mask."""
    source = np.asarray(source, dtype="float32")
    valid_source = np.isfinite(source) & (source > 0)
    if source_valid is not None:
        valid_source &= np.asarray(source_valid, dtype=bool)
    weighted = np.where(valid_source, source, np.nan).astype("float32")
    coverage_src = valid_source.astype("float32")
    power = np.full((grid.height, grid.width), np.nan, dtype="float32")
    coverage = np.zeros((grid.height, grid.width), dtype="float32")
    reproject(weighted, power, src_transform=source_transform, src_crs=source_crs,
              dst_transform=grid.transform, dst_crs=grid.crs, resampling=Resampling.average,
              src_nodata=np.nan, dst_nodata=np.nan)
    reproject(coverage_src, coverage, src_transform=source_transform, src_crs=source_crs,
              dst_transform=grid.transform, dst_crs=grid.crs, resampling=Resampling.average,
              src_nodata=0, dst_nodata=0)
    valid = (coverage >= threshold) & np.isfinite(power) & (power > 0)
    power[~valid] = np.nan
    return power, coverage, valid


def power_to_db(power: np.ndarray, *, floor: float = 1e-12) -> np.ndarray:
    out = np.full(power.shape, np.nan, dtype="float32")
    valid = np.isfinite(power) & (power > 0)
    out[valid] = 10.0 * np.log10(np.maximum(power[valid], floor))
    return out


def calibrate_dn_power(dn: np.ndarray, gain: np.ndarray | float, offset: np.ndarray | float = 0.0) -> np.ndarray:
    """Apply the RCM GRD LUT relation: (DN² + offset) / gain."""
    dn = np.asarray(dn, dtype="float64")
    return ((dn * dn) + np.asarray(offset)) / np.asarray(gain)


def scene_cache_key(input_product_hash: str, snap_version: str, graph_sha256: str, dem_hash: str, grid: CommonGrid) -> str:
    payload = "|".join([input_product_hash, snap_version, graph_sha256, dem_hash, repr(grid.as_dict())])
    return hashlib.sha256(payload.encode()).hexdigest()
