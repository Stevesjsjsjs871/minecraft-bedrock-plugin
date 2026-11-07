#!/usr/bin/env python3
"""Compatibility entry point for the current Skills-only checker tests."""
from __future__ import annotations
import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).with_name("test_check_skills_package.py")
    runpy.run_path(str(target), run_name="__main__")
