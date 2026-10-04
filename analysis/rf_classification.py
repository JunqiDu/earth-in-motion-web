"""Explainable, scene-specific Random Forest utilities for Phase 3B RF v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import ndimage
from sklearn.ensemble import RandomForestClassifier


FEATURE_NAMES = ("sigma0_hh_db", "sigma0_hv_db", "hh_minus_hv_db", "local_hh_std_db")
RF_PARAMS = {
    "n_estimators": 200,
    "max_depth": 12,
    "min_samples_leaf": 5,
    "max_features": "sqrt",
    "class_weight": "balanced_subsample",
}
RANDOM_SEED = 20261004


@dataclass(frozen=True)
class TrainingSample:
    X: np.ndarray
    y: np.ndarray
    diagnostics: dict[str, Any]


def local_standard_deviation(values: np.ndarray, valid: np.ndarray, size: int = 3) -> np.ndarray:
    """Compute local HH texture in dB while excluding invalid pixels."""
    values = np.asarray(values, dtype="float32")
    valid = np.asarray(valid, dtype=bool) & np.isfinite(values)
    weights = valid.astype("float32")
    filled = np.where(valid, values, 0.0).astype("float32")
    count = ndimage.uniform_filter(weights, size=size, mode="nearest") * (size * size)
    mean = ndimage.uniform_filter(filled, size=size, mode="nearest") * (size * size)
    mean = np.divide(mean, count, out=np.full_like(mean, np.nan), where=count > 0)
    second = ndimage.uniform_filter(filled * filled, size=size, mode="nearest") * (size * size)
    second = np.divide(second, count, out=np.full_like(second, np.nan), where=count > 0)
    result = np.sqrt(np.maximum(second - mean * mean, 0.0))
    result[~valid] = np.nan
    return result.astype("float32")


def make_features(sigma_hh_db: np.ndarray, sigma_hv_db: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, tuple[str, ...]]:
    hh = np.asarray(sigma_hh_db, dtype="float32")
    hv = np.asarray(sigma_hv_db, dtype="float32")
    valid = np.asarray(valid, dtype=bool)
    texture = local_standard_deviation(hh, valid, size=3)
    features = np.stack([hh, hv, hh - hv, texture], axis=-1).astype("float32")
    return features, FEATURE_NAMES


def spatial_block_samples(
    features: np.ndarray,
    stable_land: np.ndarray,
    stable_water: np.ndarray,
    valid: np.ndarray,
    *,
    block_size: int = 20,
    max_per_class_per_block: int = 40,
    random_state: int = RANDOM_SEED,
) -> TrainingSample:
    """Select balanced, reproducible samples without random pixel leakage."""
    features = np.asarray(features)
    valid = np.asarray(valid, dtype=bool)
    land = np.asarray(stable_land, dtype=bool) & valid
    water = np.asarray(stable_water, dtype=bool) & valid
    rng = np.random.default_rng(random_state)
    selected: list[tuple[int, int, int]] = []
    block_rows: list[dict[str, int]] = []
    for row in range(0, features.shape[0], block_size):
        for col in range(0, features.shape[1], block_size):
            window = np.zeros(valid.shape, dtype=bool)
            window[row : row + block_size, col : col + block_size] = True
            land_idx = np.flatnonzero(land & window)
            water_idx = np.flatnonzero(water & window)
            if land_idx.size:
                land_idx = rng.choice(land_idx, size=min(max_per_class_per_block, land_idx.size), replace=False)
            if water_idx.size:
                water_idx = rng.choice(water_idx, size=min(max_per_class_per_block, water_idx.size), replace=False)
            for flat in land_idx:
                selected.append((int(flat), 0, row // block_size * 100 + col // block_size))
            for flat in water_idx:
                selected.append((int(flat), 1, row // block_size * 100 + col // block_size))
            block_rows.append({"block_row": row // block_size, "block_col": col // block_size, "land_candidates": int((land & window).sum()), "water_candidates": int((water & window).sum()), "land_samples": int(len(land_idx)), "water_samples": int(len(water_idx))})
    if not selected:
        raise ValueError("No historical stable-land/stable-water training pixels are available")
    land_sel = [item for item in selected if item[1] == 0]
    water_sel = [item for item in selected if item[1] == 1]
    target = min(len(land_sel), len(water_sel))
    if target < 10:
        raise ValueError(f"Insufficient balanced training pixels: land={len(land_sel)}, water={len(water_sel)}")
    land_sel = list(rng.choice(land_sel, size=target, replace=False))
    water_sel = list(rng.choice(water_sel, size=target, replace=False))
    chosen = land_sel + water_sel
    flat_indices = np.array([item[0] for item in chosen], dtype=int)
    labels = np.array([item[1] for item in chosen], dtype=np.uint8)
    matrix = features.reshape(-1, features.shape[-1])[flat_indices]
    finite = np.isfinite(matrix).all(axis=1)
    matrix, labels = matrix[finite], labels[finite]
    if len(np.unique(labels)) < 2:
        raise ValueError("Training samples contain only one class after finite-value filtering")
    coordinates = [(int(flat // features.shape[1]), int(flat % features.shape[1]), int(label)) for (flat, label, _), keep in zip(chosen, finite) if keep]
    return TrainingSample(matrix, labels, {"block_size": block_size, "max_per_class_per_block": max_per_class_per_block, "random_seed": random_state, "land_samples": int((labels == 0).sum()), "water_samples": int((labels == 1).sum()), "blocks": block_rows, "selected_coordinates": coordinates})


def fit_scene_rf(sample: TrainingSample, *, random_state: int = RANDOM_SEED, params: dict[str, Any] | None = None) -> RandomForestClassifier:
    config = dict(RF_PARAMS)
    if params:
        config.update(params)
    model = RandomForestClassifier(random_state=random_state, n_jobs=1, **config)
    model.fit(sample.X, sample.y)
    return model


def predict_scene_rf(model: RandomForestClassifier, features: np.ndarray, valid: np.ndarray, threshold: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    flat = np.asarray(features).reshape(-1, features.shape[-1])
    valid = np.asarray(valid, dtype=bool)
    finite = np.isfinite(flat).all(axis=1) & valid.ravel()
    probability = np.full(flat.shape[0], np.nan, dtype="float32")
    if finite.any():
        classes = list(model.classes_)
        water_column = classes.index(1)
        probability[finite] = model.predict_proba(flat[finite])[:, water_column].astype("float32")
    probability = probability.reshape(valid.shape)
    water = (probability >= threshold) & valid
    return probability, water


def cleanup_components(mask: np.ndarray, valid: np.ndarray, min_component_pixels: int) -> np.ndarray:
    structure = ndimage.generate_binary_structure(2, 2)
    labels, count = ndimage.label(np.asarray(mask, dtype=bool) & np.asarray(valid, dtype=bool), structure=structure)
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    return (labels > 0) & (sizes[labels] >= int(min_component_pixels)) & np.asarray(valid, dtype=bool)
