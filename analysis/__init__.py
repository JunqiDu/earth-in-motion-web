"""Phase 3B RCM Level-1 processing and validation utilities.

The package is deliberately independent from the existing Phase 4/5 notebooks.
SNAP is invoked as an external executable; importing this package never starts
SNAP or performs network access.
"""

from .rcm_level1 import discover_products, verify_product
from .rcm_preprocessing import CommonGrid, SnapUnavailableError, find_snap_gpt, preprocess_scene
from .validation import confusion_metrics, evaluate_gate, validate_scene

__all__ = [
    "CommonGrid",
    "SnapUnavailableError",
    "confusion_metrics",
    "discover_products",
    "evaluate_gate",
    "find_snap_gpt",
    "preprocess_scene",
    "validate_scene",
    "verify_product",
]
