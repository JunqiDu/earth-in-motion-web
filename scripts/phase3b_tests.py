#!/usr/bin/env python
"""Run direct Phase3B assertions with temporary fixtures; pytest not required."""
from __future__ import annotations
import importlib.util
import inspect
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    count = 0
    for file in (ROOT / "tests/test_phase3b.py", ROOT / "tests/test_phase3b_final.py"):
        spec = importlib.util.spec_from_file_location(file.stem, file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"): continue
            parameters = inspect.signature(function).parameters
            if any(p != "tmp_path" for p in parameters):
                raise RuntimeError(f"Unsupported fixture: {name}")
            with tempfile.TemporaryDirectory(prefix="phase3b-test-") as tmp:
                function(**({"tmp_path": Path(tmp)} if parameters else {}))
            count += 1
            print("PASS", name)
    print(f"{count} direct tests passed (no pytest installation required)")


if __name__ == "__main__":
    run()
