#!/usr/bin/env python3
"""Run trusted Skills-local unittest files in isolated Python processes.

This utility executes code from the package. Review the package before use.
Only test files under the current Skills tree are discovered. Symlinked Skills
roots or test files are rejected to prevent path escape during discovery.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SUMMARY_RE = re.compile(r"Ran\s+(\d+)\s+tests?\s+in\s+([0-9.]+)s", re.I)
DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 900
MAX_TEST_FILES = 256


def _discover_tests(root: Path) -> tuple[Path, list[Path]]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"Package root is not a directory: {root}")
    skills = root / "skills"
    if skills.is_symlink() or not skills.is_dir():
        raise FileNotFoundError(f"A real Skills directory is required: {skills}")
    skills_root = skills.resolve(strict=True)
    if not skills_root.is_relative_to(root):
        raise ValueError("Skills directory resolves outside the package root")

    discovered = sorted(skills_root.rglob("test_*.py"))
    tests: list[Path] = []
    for path in discovered:
        if path.is_symlink():
            raise ValueError(f"Refusing to execute symlinked test file: {path}")
        if not path.is_file():
            continue
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(skills_root):
            raise ValueError(f"Test file resolves outside Skills root: {path}")
        tests.append(resolved)
    if len(tests) > MAX_TEST_FILES:
        raise ValueError(f"Test file count {len(tests)} exceeds limit {MAX_TEST_FILES}")
    return root, tests


def run(root: Path, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError("timeout must be a finite number of seconds")
    if not math.isfinite(timeout) or timeout <= 0 or timeout > MAX_TIMEOUT:
        raise ValueError(f"timeout must be > 0 and <= {MAX_TIMEOUT} seconds")

    root, test_files = _discover_tests(root)
    results = []
    for path in test_files:
        try:
            proc = subprocess.run(
                [sys.executable, path.name, "-v"],
                cwd=path.parent,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            match = SUMMARY_RE.search(output)
            status = "PASS" if proc.returncode == 0 and match else "FAIL"
            results.append({
                "path": path.relative_to(root).as_posix(),
                "status": status,
                "return_code": proc.returncode,
                "tests_run": int(match.group(1)) if match else None,
                "duration_seconds": float(match.group(2)) if match else None,
                "output_tail": output[-4000:],
            })
        except subprocess.TimeoutExpired as exc:
            results.append({
                "path": path.relative_to(root).as_posix(),
                "status": "TIMEOUT",
                "return_code": None,
                "tests_run": None,
                "duration_seconds": None,
                "output_tail": str(exc)[-4000:],
            })
        except OSError as exc:
            results.append({
                "path": path.relative_to(root).as_posix(),
                "status": "ERROR",
                "return_code": None,
                "tests_run": None,
                "duration_seconds": None,
                "output_tail": f"{type(exc).__name__}: {exc}"[-4000:],
            })

    summary = {
        "test_files": len(results),
        "passed_files": sum(item["status"] == "PASS" for item in results),
        "failed_files": sum(item["status"] in {"FAIL", "ERROR"} for item in results),
        "timed_out_files": sum(item["status"] == "TIMEOUT" for item in results),
    }
    summary["test_cases"] = sum(item["tests_run"] or 0 for item in results)
    return {
        "schema_version": "1.1",
        "package_root": root.name,
        "execution_policy": (
            "Executes trusted Skills test files only; each file runs in a separate process. "
            "Symlinked test paths are rejected; only the current Skills tree is scanned."
        ),
        "python_version": sys.version.split()[0],
        "summary": summary,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", nargs="?", default=".")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args(argv)
    try:
        result = run(Path(args.package_root), timeout=args.timeout)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json_path:
        output_path = Path(args.json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    for item in result["results"]:
        count = item["tests_run"] if item["tests_run"] is not None else "unknown"
        print(f"{item['status']:8} {item['path']} ({count} tests)")
    summary = result["summary"]
    return 0 if summary["test_files"] and not summary["failed_files"] and not summary["timed_out_files"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
