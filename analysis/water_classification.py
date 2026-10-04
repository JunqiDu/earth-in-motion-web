"""Explainable, pre-registered water classification candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import ndimage


@dataclass
class MethodConfig:
    version: str = "phase3b-candidates-v1"
    candidate_id: str = "C1_group_hh"
    thresholds_db: dict[str, float] = field(default_factory=dict)
    min_component_pixels: int = 2
    connectivity: int = 2
    use_hv: bool = False


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    values = np.asarray(values, dtype="float64")
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("Cannot compute Otsu threshold from empty values")
    hist, edges = np.histogram(values, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    # Otsu's between-class variance.  Keep all calculations in the raw
    # histogram-count domain, but compute each class mean explicitly.  The
    # previous expression omitted the total-count factor in the numerator;
    # with skewed SAR backscatter it selected a sparse high-backscatter tail
    # as the split, then ``HH < threshold`` labelled almost the whole AOI as
    # water.
    weight = hist.astype(float)
    cumulative = np.cumsum(weight)
    cumulative_mean = np.cumsum(weight * centers)
    total = cumulative[-1]
    other = total - cumulative
    other_mean_sum = cumulative_mean[-1] - cumulative_mean
    mean_a = np.divide(cumulative_mean, cumulative, out=np.zeros_like(cumulative_mean), where=cumulative > 0)
    mean_b = np.divide(other_mean_sum, other, out=np.zeros_like(other_mean_sum), where=other > 0)
    score = cumulative * other * (mean_a - mean_b) ** 2
    score[(cumulative == 0) | (other == 0)] = 0.0
    return float(centers[np.argmax(score)])


def cleanup_mask(mask: np.ndarray, valid: np.ndarray, *, min_component_pixels: int = 2, connectivity: int = 2) -> np.ndarray:
    structure = ndimage.generate_binary_structure(2, connectivity)
    labels, count = ndimage.label(mask & valid, structure=structure)
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    cleaned = (labels > 0) & (sizes[labels] >= min_component_pixels) & valid
    # Only fill one-pixel holes.  binary_fill_holes by itself would fill every
    # enclosed cavity, which changes the registered morphology rule.
    holes = ndimage.binary_fill_holes(cleaned, structure=structure) & ~cleaned & valid
    hole_labels, hole_count = ndimage.label(holes, structure=structure)
    hole_sizes = np.bincount(hole_labels.ravel(), minlength=hole_count + 1)
    one_pixel_holes = (hole_labels > 0) & (hole_sizes[hole_labels] == 1)
    return (cleaned | one_pixel_holes) & valid


def classify_scene(hh_db: np.ndarray, hv_db: np.ndarray | None, valid: np.ndarray, mode_group: str, config: MethodConfig, *, noise_floor_hv: float | None = None, hv_threshold_db: float | None = None) -> dict[str, np.ndarray]:
    hh_db = np.asarray(hh_db, dtype=float)
    valid = np.asarray(valid, dtype=bool)
    threshold = config.thresholds_db.get(mode_group, config.thresholds_db.get("global"))
    if threshold is None:
        threshold = otsu_threshold(hh_db[valid])
    water = (hh_db < threshold) & valid
    hv_used = np.zeros(valid.shape, dtype=bool)
    if config.use_hv and hv_db is not None:
        hv_db = np.asarray(hv_db, dtype=float)
        hv_used = valid & np.isfinite(hv_db)
        if noise_floor_hv is not None:
            hv_used &= hv_db >= noise_floor_hv + 3.0
        # Keep the registered HH decision when HV is unusable.  When HV is
        # usable, require a fixed pooled-training HV threshold; no date-specific
        # ratio rule is allowed.
        hv_threshold = hv_threshold_db if hv_threshold_db is not None else float(np.nanmedian(hv_db[hv_used]))
        water &= (~hv_used) | (hv_db < hv_threshold)
    water = cleanup_mask(water, valid, min_component_pixels=config.min_component_pixels, connectivity=config.connectivity)
    return {"water": water, "valid": valid, "hv_used": hv_used, "threshold_db": np.asarray(threshold)}


def flood_extension(water: np.ndarray, permanent_water: np.ndarray, valid: np.ndarray) -> np.ndarray:
    return np.asarray(water, dtype=bool) & ~np.asarray(permanent_water, dtype=bool) & np.asarray(valid, dtype=bool)


def candidate_definitions() -> list[dict[str, Any]]:
    return [
        {"candidate_id": "C0_global_hh", "description": "one global Gamma0-HH threshold", "use_hv": False},
        {"candidate_id": "C1_group_hh", "description": "one fixed HH threshold per mode group", "use_hv": False},
        {"candidate_id": "C2_group_hh_hv", "description": "C1 plus a pooled group HV threshold where HV is >=3 dB above the conservative AOI noise floor", "use_hv": True},
    ]


def fit_threshold(values: np.ndarray, labels: np.ndarray, *, bins: int = 256) -> dict[str, float]:
    """Fit one registered threshold using only the supplied training pixels."""
    values = np.asarray(values, dtype=float)
    labels = np.asarray(labels, dtype=bool)
    finite = np.isfinite(values)
    values, labels = values[finite], labels[finite]
    initial = otsu_threshold(values, bins=bins)
    candidates = np.arange(initial - 3.0, initial + 3.001, 0.5)
    best = initial
    best_iou = -1.0
    best_bias = float("inf")
    for threshold in candidates:
        predicted = values < threshold
        tp = np.sum(predicted & labels)
        fp = np.sum(predicted & ~labels)
        fn = np.sum(~predicted & labels)
        iou = float(tp / (tp + fp + fn)) if tp + fp + fn else 0.0
        bias = abs(float(predicted.mean() - labels.mean()))
        if (iou > best_iou + 1e-12 or
                (abs(iou - best_iou) <= 1e-12 and (bias < best_bias - 1e-12 or
                 (abs(bias - best_bias) <= 1e-12 and abs(threshold - initial) < abs(best - initial))))):
            best, best_iou, best_bias = float(threshold), iou, bias
    return {"threshold_db": best, "otsu_db": float(initial), "training_iou": best_iou, "training_abs_area_fraction_bias": best_bias}
