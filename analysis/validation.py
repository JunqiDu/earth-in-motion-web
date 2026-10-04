"""Pixel, area, and boundary validation for the Phase 3B pilot."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
from scipy import ndimage


def confusion_metrics(predicted: np.ndarray, reference: np.ndarray, valid: np.ndarray | None = None, pixel_area_ha: float = 0.09) -> dict[str, float]:
    predicted = np.asarray(predicted, dtype=bool)
    reference = np.asarray(reference, dtype=bool)
    valid = np.ones(predicted.shape, dtype=bool) if valid is None else np.asarray(valid, dtype=bool)
    tp = int((predicted & reference & valid).sum())
    fp = int((predicted & ~reference & valid).sum())
    fn = int((~predicted & reference & valid).sum())
    tn = int((~predicted & ~reference & valid).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    predicted_area = (tp + fp) * pixel_area_ha
    reference_area = (tp + fn) * pixel_area_ha
    bias = predicted_area - reference_area
    return {
        "tp_pixels": tp, "fp_pixels": fp, "fn_pixels": fn, "tn_pixels": tn,
        "precision": precision, "recall": recall, "f1": f1, "iou": iou,
        "predicted_area_ha": predicted_area, "reference_area_ha": reference_area,
        "area_bias_ha": bias, "area_bias_pct": 100.0 * bias / reference_area if reference_area else 0.0,
        "false_positive_area_ha": fp * pixel_area_ha,
        "false_negative_area_ha": fn * pixel_area_ha,
    }


def boundary_f1(predicted: np.ndarray, reference: np.ndarray, valid: np.ndarray | None = None, tolerance_pixels: int = 1) -> float:
    valid = np.ones(predicted.shape, dtype=bool) if valid is None else np.asarray(valid, dtype=bool)
    pred_edge = np.logical_xor(predicted, ndimage.binary_erosion(predicted)) & valid
    ref_edge = np.logical_xor(reference, ndimage.binary_erosion(reference)) & valid
    pred_near_ref = pred_edge & (ndimage.distance_transform_edt(~ref_edge) <= tolerance_pixels)
    ref_near_pred = ref_edge & (ndimage.distance_transform_edt(~pred_edge) <= tolerance_pixels)
    p = pred_near_ref.sum() / pred_edge.sum() if pred_edge.sum() else 0.0
    r = ref_near_pred.sum() / ref_edge.sum() if ref_edge.sum() else 0.0
    return float(2 * p * r / (p + r)) if p + r else 0.0


def add_boundary_metrics(metrics: dict[str, Any], predicted: np.ndarray, reference: np.ndarray, valid: np.ndarray | None = None) -> dict[str, Any]:
    metrics = dict(metrics)
    metrics["boundary_f1_30m"] = boundary_f1(predicted, reference, valid, 1)
    metrics["boundary_f1_60m"] = boundary_f1(predicted, reference, valid, 2)
    return metrics


def boundary_distance_summary(predicted: np.ndarray, reference: np.ndarray, valid: np.ndarray | None = None) -> dict[str, float]:
    """Return symmetric boundary distance diagnostics in pixels."""
    predicted = np.asarray(predicted, dtype=bool)
    reference = np.asarray(reference, dtype=bool)
    valid = np.ones(predicted.shape, dtype=bool) if valid is None else np.asarray(valid, dtype=bool)
    pred_edge = np.logical_xor(predicted, ndimage.binary_erosion(predicted)) & valid
    ref_edge = np.logical_xor(reference, ndimage.binary_erosion(reference)) & valid
    if not pred_edge.any() or not ref_edge.any():
        return {"median_offset_px": float("inf"), "p95_offset_px": float("inf"), "n_pred_edge": int(pred_edge.sum()), "n_ref_edge": int(ref_edge.sum())}
    pred_to_ref = ndimage.distance_transform_edt(~ref_edge)[pred_edge]
    ref_to_pred = ndimage.distance_transform_edt(~pred_edge)[ref_edge]
    distances = np.concatenate([pred_to_ref, ref_to_pred])
    return {"median_offset_px": float(np.median(distances)), "p95_offset_px": float(np.percentile(distances, 95)), "n_pred_edge": int(pred_edge.sum()), "n_ref_edge": int(ref_edge.sum())}


def validate_scene(predicted: np.ndarray, reference: np.ndarray, valid: np.ndarray | None = None, *, pixel_area_ha: float = 0.09) -> dict[str, Any]:
    """Stable scene-level validation interface used by the pilot notebook."""
    return add_boundary_metrics(confusion_metrics(predicted, reference, valid, pixel_area_ha), predicted, reference, valid)


def evaluate_gate(metrics: Iterable[dict[str, Any]] | Any, qa: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply the registered GO/REFINE/FAIL thresholds to per-date metrics."""
    rows = list(metrics)
    if not rows:
        return {"status": "FAIL", "reason": "no validation metrics"}
    if len(rows) != 5:
        return {"status": "FAIL", "reason": f"expected exactly five pilot rows, found {len(rows)}", "scene_count": len(rows)}
    mode_groups = {row.get("mode_group") for row in rows}
    if not {"stripmap16_desc", "scansar30_asc"}.issubset(mode_groups):
        return {"status": "FAIL", "reason": "both registered mode groups are required", "scene_count": len(rows)}
    ious = np.array([float(row["iou"]) for row in rows])
    f1s = np.array([float(row["f1"]) for row in rows])
    biases = np.abs(np.array([float(row.get("area_bias_pct", 0.0)) for row in rows]))
    median_iou, median_f1 = float(np.median(ious)), float(np.median(f1s))
    reasons = []
    if median_iou < 0.35 or (ious < 0.25).sum() >= 2:
        status = "FAIL"; reasons.append("IoU below fail gate")
    elif median_iou < 0.50 or median_f1 < 0.67 or (ious < 0.35).any() or (f1s < 0.52).any() or float(np.median(biases)) > 25 or (biases > 50).any():
        status = "REFINE"; reasons.append("pilot does not yet meet GO thresholds")
    else:
        status = "GO"
    if qa and qa.get("geometry_status") not in (None, "pass", "passed"):
        status = "FAIL"; reasons.append("geometry gate failed")
    if qa and qa.get("calibration_status") not in (None, "pass", "passed"):
        status = "FAIL"; reasons.append("calibration gate failed")
    if qa and qa.get("systematic_artifact_review") not in (None, "pass", "passed"):
        status = "FAIL"; reasons.append("systematic artifact review failed")
    return {"status": status, "reason": "; ".join(reasons) or "all registered gates passed", "macro_median_iou": median_iou, "macro_median_f1": median_f1, "median_abs_area_bias_pct": float(np.median(biases)), "scene_count": len(rows)}
