#!/usr/bin/env python3
"""Compatibility entrypoint for the canonical visual-resource PNG validator."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "visual-resource-pipeline" / "scripts" / "png_engine.py"
    runpy.run_path(str(target), run_name="__main__")
