#!/usr/bin/env python3
"""Validate a Bedrock audit report against report-schema.json (Draft 2020-12)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="JSON report emitted by bedrock_audit.py")
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "references" / "report-schema.json",
        help="JSON Schema file (default: adjacent references/report-schema.json)",
    )
    args = parser.parse_args()

    try:
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read schema/report: {exc}", file=sys.stderr)
        return 2

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("ERROR: report validation requires jsonschema; install with: python -m pip install jsonschema", file=sys.stderr)
        return 2

    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        print(f"ERROR: the report schema is invalid: {exc}", file=sys.stderr)
        return 2

    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=lambda item: list(map(str, item.absolute_path)))
    if errors:
        for error in errors:
            location = "/" + "/".join(str(part) for part in error.absolute_path) if error.absolute_path else "/"
            print(f"FAIL {location}: {error.message}")
        print(f"SUMMARY: invalid report; {len(errors)} schema violation(s)")
        return 1

    print(f"PASS: {args.report} conforms to {args.schema} (Draft 2020-12)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
