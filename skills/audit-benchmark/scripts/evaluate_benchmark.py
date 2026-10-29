#!/usr/bin/env python3
"""Validate a reviewed real-pack benchmark manifest and score saved audit reports."""
from __future__ import annotations

import argparse
import hashlib
import collections
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_SCHEMA = Path(__file__).resolve().parents[1] / "references" / "benchmark-manifest.schema.json"
REPORT_SCHEMA = ROOT / "skills" / "automated-validation" / "references" / "report-schema.json"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def _resolve_contained_file(root: Path, filename: str, label: str) -> Path:
    """Resolve an input file and reject symlinks escaping its declared directory."""
    root_real = root.expanduser().resolve(strict=True)
    candidate = (root_real / filename).resolve(strict=True)
    try:
        candidate.relative_to(root_real)
    except ValueError as exc:
        raise ValueError(f"{label} resolves outside its configured directory") from exc
    if not candidate.is_file():
        raise ValueError(f"{label} is not a regular file")
    return candidate


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_schema(document: Any, schema_path: Path, label: str) -> list[str]:
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema is required; install it with `python -m pip install jsonschema`") from exc
    schema = _load_json(schema_path)
    errors = sorted(
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(document),
        key=lambda error: (list(map(str, error.absolute_path)), error.message),
    )
    return [
        f"{label} schema error at {list(error.absolute_path)}: {error.message}"
        for error in errors
    ]


def _fingerprint(finding: dict[str, Any]) -> tuple[str, str | None]:
    path = finding.get("path")
    return str(finding.get("title", "")), path if isinstance(path, str) else None


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _metric_summary(tp: int, fp: int, fn: int, severity_mismatches: int) -> dict[str, Any]:
    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and precision + recall:
        f1 = round(2 * precision * recall / (precision + recall), 6)
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "severity_mismatches": severity_mismatches,
    }


def _case_findings(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    expected_by_key: dict[tuple[str, str | None], list[dict[str, Any]]] = collections.defaultdict(list)
    actual_by_key: dict[tuple[str, str | None], list[dict[str, Any]]] = collections.defaultdict(list)
    for item in expected:
        expected_by_key[_fingerprint(item)].append(item)
    for item in actual:
        actual_by_key[_fingerprint(item)].append(item)

    tp = fp = fn = severity_mismatches = 0
    mismatches: list[dict[str, Any]] = []
    all_keys = sorted(set(expected_by_key) | set(actual_by_key), key=lambda item: (item[0], item[1] or ""))
    for title, path in all_keys:
        exp_items = expected_by_key.get((title, path), [])
        act_items = actual_by_key.get((title, path), [])
        matched = min(len(exp_items), len(act_items))
        tp += matched
        fn += len(exp_items) - matched
        fp += len(act_items) - matched
        for idx in range(matched):
            expected_severity = exp_items[idx].get("expected_severity")
            actual_severity = act_items[idx].get("severity")
            if expected_severity is not None and actual_severity != expected_severity:
                severity_mismatches += 1
                mismatches.append({
                    "kind": "severity_mismatch",
                    "title": title,
                    "path": path,
                    "expected": expected_severity,
                    "actual": actual_severity,
                })
        for item in exp_items[matched:]:
            mismatches.append({"kind": "false_negative", "title": title, "path": path, "evidence_note": item.get("evidence_note", "")})
        for item in act_items[matched:]:
            mismatches.append({"kind": "false_positive", "title": title, "path": path, "severity": item.get("severity")})

    return _metric_summary(tp, fp, fn, severity_mismatches), mismatches


def evaluate(dataset_path: Path, reports_dir: Path, artifacts_dir: Path, expected_tool_version: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    try:
        dataset = _load_json(dataset_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "INVALID", "errors": [f"Cannot read dataset JSON: {exc}"], "metrics": None, "cases": []}

    try:
        errors.extend(_validate_schema(dataset, MANIFEST_SCHEMA, "Benchmark manifest"))
    except (RuntimeError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "INVALID", "errors": [f"Cannot validate benchmark manifest: {exc}"], "metrics": None, "cases": []}
    if errors:
        return {"status": "INVALID", "errors": errors, "metrics": None, "cases": []}
    if not dataset["cases"]:
        return {
            "status": "INCOMPLETE",
            "dataset_id": dataset["dataset_id"],
            "dataset_version": dataset["dataset_version"],
            "errors": [],
            "metrics": None,
            "scored_cases": [],
            "skipped_cases": [],
            "metric_policy": "The dataset contains no real-pack cases; no benchmark metrics were computed.",
        }

    seen_case_ids: set[str] = set()
    scored_cases: list[dict[str, Any]] = []
    skipped_cases: list[dict[str, Any]] = []
    totals = {"true_positives": 0, "false_positives": 0, "false_negatives": 0, "severity_mismatches": 0}
    rule_totals: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"true_positives": 0, "false_positives": 0, "false_negatives": 0, "severity_mismatches": 0}
    )
    tool_versions: set[str] = set()

    for case in dataset["cases"]:
        case_id = case["case_id"]
        if case["target_game_version"] != dataset["target_game_version"]:
            errors.append(f"{case_id}: target game version differs from dataset target")
            continue
        if case_id in seen_case_ids:
            errors.append(f"Duplicate case_id {case_id!r}")
            continue
        seen_case_ids.add(case_id)
        rule_titles = set(case["scored_rules"])
        if not rule_titles and case["label_status"] == "reviewed":
            errors.append(f"{case_id}: reviewed case has no scored_rules")
            continue
        expected_fingerprints = [_fingerprint(item) for item in case["expected_findings"]]
        if len(expected_fingerprints) != len(set(expected_fingerprints)):
            errors.append(f"{case_id}: duplicate expected finding fingerprint (title, path); labels must be disambiguated before scoring")
            continue
        for expected in case["expected_findings"]:
            if expected["title"] not in rule_titles:
                errors.append(f"{case_id}: expected finding {expected['title']!r} is not included in scored_rules")
        if case["label_status"] == "pending":
            skipped_cases.append({"case_id": case_id, "status": "SKIPPED", "reason": "labels are pending; not included in metrics"})
            continue

        artifact_name = case.get("artifact_filename")
        if not isinstance(artifact_name, str) or Path(artifact_name).name != artifact_name or artifact_name in {".", ".."}:
            errors.append(f"{case_id}: artifact_filename must be a single filename inside --artifacts-dir")
            continue
        try:
            artifact_path = _resolve_contained_file(artifacts_dir, artifact_name, "source artifact")
            artifact_hash = _sha256_file(artifact_path)
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"{case_id}: cannot safely read source artifact: {exc}")
            continue
        if artifact_hash.lower() != case["artifact_sha256"].lower():
            errors.append(f"{case_id}: source artifact SHA-256 does not match the benchmark manifest")
            continue

        try:
            report_path = _resolve_contained_file(reports_dir, f"{case_id}.json", "audit report")
            report = _load_json(report_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
            errors.append(f"{case_id}: cannot safely read audit report: {exc}")
            continue

        try:
            report_errors = _validate_schema(report, REPORT_SCHEMA, f"{case_id} report")
        except (RuntimeError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{case_id}: cannot validate audit report: {exc}")
            continue
        if report_errors:
            errors.extend(report_errors)
            continue
        actual_hash = report.get("candidate", {}).get("sha256")
        if not isinstance(actual_hash, str) or actual_hash.lower() != case["artifact_sha256"].lower():
            errors.append(f"{case_id}: candidate SHA-256 does not match the benchmark manifest")
            continue
        tool_version = str(report.get("tool_version", ""))
        tool_versions.add(tool_version)
        if expected_tool_version and tool_version != expected_tool_version:
            errors.append(f"{case_id}: expected tool version {expected_tool_version}, report contains {tool_version!r}")
            continue

        scoped_actual = [finding for finding in report["findings"] if finding["title"] in rule_titles]
        case_metrics, mismatches = _case_findings(case["expected_findings"], scoped_actual)
        for key in totals:
            totals[key] += case_metrics[key]
        for rule_title in rule_titles:
            expected_for_rule = [item for item in case["expected_findings"] if item["title"] == rule_title]
            actual_for_rule = [item for item in scoped_actual if item["title"] == rule_title]
            per_rule, _ = _case_findings(expected_for_rule, actual_for_rule)
            for key in rule_totals[rule_title]:
                rule_totals[rule_title][key] += per_rule[key]
        scored_cases.append({
            "case_id": case_id,
            "status": "SCORED",
            "artifact_sha256": case["artifact_sha256"].lower(),
            "artifact_file_verified": True,
            "tool_version": tool_version,
            "runtime_verification_label": case["runtime_verification"],
            "scored_rules": sorted(rule_titles),
            "metrics": case_metrics,
            "mismatches": mismatches,
        })

    if errors:
        return {
            "status": "INVALID",
            "dataset_id": dataset.get("dataset_id"),
            "dataset_version": dataset.get("dataset_version"),
            "errors": errors,
            "metrics": None,
            "scored_cases": scored_cases,
            "skipped_cases": skipped_cases,
            "tool_versions_seen": sorted(tool_versions),
            "metric_policy": "Metrics withheld because at least one scored case or report failed validation.",
        }

    if not scored_cases:
        return {
            "status": "INCOMPLETE",
            "dataset_id": dataset["dataset_id"],
            "dataset_version": dataset["dataset_version"],
            "target_game_version": dataset["target_game_version"],
            "scored_case_count": 0,
            "pending_case_count": len(skipped_cases),
            "tool_versions_seen": sorted(tool_versions),
            "metrics": None,
            "scored_cases": [],
            "skipped_cases": skipped_cases,
            "metric_policy": "No reviewed case was scored; no benchmark metrics were computed.",
        }

    aggregate = _metric_summary(
        totals["true_positives"], totals["false_positives"], totals["false_negatives"], totals["severity_mismatches"]
    )
    metrics_by_rule = {
        rule: _metric_summary(values["true_positives"], values["false_positives"], values["false_negatives"], values["severity_mismatches"])
        for rule, values in sorted(rule_totals.items())
    }
    return {
        "status": "COMPLETED",
        "dataset_id": dataset["dataset_id"],
        "dataset_version": dataset["dataset_version"],
        "target_game_version": dataset["target_game_version"],
        "scored_case_count": len(scored_cases),
        "pending_case_count": len(skipped_cases),
        "tool_versions_seen": sorted(tool_versions),
        "metrics": aggregate,
        "metrics_by_rule": metrics_by_rule,
        "scored_cases": scored_cases,
        "skipped_cases": skipped_cases,
        "metric_policy": "Metrics cover only reviewed cases and explicitly listed scored_rules. Findings match exact (title, path); this is not overall accuracy and does not measure true negatives or runtime correctness.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path, help="JSON benchmark manifest")
    parser.add_argument("--reports-dir", required=True, type=Path, help="Directory with <case_id>.json audit reports")
    parser.add_argument("--artifacts-dir", required=True, type=Path, help="Directory containing the exact local artifacts named by the manifest")
    parser.add_argument("--expected-tool-version", help="Require every scored report to come from this exact analyzer version")
    parser.add_argument("--output", type=Path, help="Optional path for the JSON evaluation report")
    args = parser.parse_args()

    result = evaluate(args.dataset, args.reports_dir, args.artifacts_dir, args.expected_tool_version)
    encoded = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        except OSError as exc:
            print(f"Could not write output report: {exc}", file=sys.stderr)
            return 2
    print(encoded, end="")
    return 0 if result["status"] == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
