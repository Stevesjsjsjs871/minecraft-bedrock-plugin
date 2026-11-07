#!/usr/bin/env python3
"""Compatibility entry point for the canonical PNG validation tests.

Ensure the canonical script directory is first on sys.path so that the
short import `from png_engine` resolves to visual-resource-pipeline, not this
compatibility shim.
"""
from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    canonical_dir = Path(__file__).resolve().parents[2] / "visual-resource-pipeline" / "scripts"
    sys.path.insert(0, str(canonical_dir))
    test_path = canonical_dir / "test_png_engine.py"
    runpy.run_path(str(test_path), run_name="__main__")
