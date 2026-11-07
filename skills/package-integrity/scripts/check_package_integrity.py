#!/usr/bin/env python3
"""Compatibility shim for the Skills-only package release checker.

The previous package-integrity checker validated a retired server/registry
architecture. It is intentionally no longer a release gate. This file keeps
old local command paths from invoking that legacy logic and delegates to the
canonical Skills-only checker instead.
"""
from __future__ import annotations
import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).with_name("check_skills_package.py")
    runpy.run_path(str(target), run_name="__main__")
