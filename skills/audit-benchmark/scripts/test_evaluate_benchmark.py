from __future__ import annotations
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("evaluate_benchmark.py")
spec = importlib.util.spec_from_file_location("mbe_evaluate_benchmark", SCRIPT)
evaluator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(evaluator)

ARTIFACT_BYTES = b"unit-test artifact bytes"
HASH = hashlib.sha256(ARTIFACT_BYTES).hexdigest()


def reviewed_case(case_id: str = "case-one") -> dict:
    return {
        "case_id": case_id,
        "source_name": "Local reviewed fixture",
        "source_url": None,
        "retrieved_on": "2026-10-29",
        "artifact_sha256": HASH,
        "artifact_filename": f"{case_id}.mcaddon",
        "license_status": "local_only",
        "label_status": "reviewed",
        "target_game_version": "1.26.50",
        "pack_types": ["BP", "RP"],
        "runtime_verification": "NOT_RUN",
        "scored_rules": ["Invalid JSON", "Missing geometry reference"],
        "expected_findings": [
            {"title": "Invalid JSON", "path": "RP/broken.json", "expected_severity": "HIGH", "evidence_note": "Reviewed invalid fixture."},
            {"title": "Missing geometry reference", "path": "RP/entity/test.entity.json", "expected_severity": "MEDIUM", "evidence_note": "Reviewed missing target."}
        ],
        "review_notes": "Expected findings reviewed independently for this test."
    }


def report_document(findings: list[dict], sha: str = HASH, version: str = "0.7.8") -> dict:
    return {
        "tool_version": version,
        "candidate": {"path": "local-only.mcaddon", "sha256": sha, "archive_valid": True},
        "checks": [],
        "findings": findings,
        "file_diff": {"added": [], "removed": [], "modified": []},
        "runtime_status": "NOT RUN",
        "recommendation": "REVIEW"
    }


def finding(title: str, path: str, severity: str = "HIGH") -> dict:
    return {"title": title, "path": path, "severity": severity, "confidence": "HIGH", "evidence": "synthetic test evidence", "impact": "test", "recommendation": "review"}


class BenchmarkEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.reports = self.root / "reports"
        self.reports.mkdir()
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        (self.artifacts / "case-one.mcaddon").write_bytes(ARTIFACT_BYTES)
        self.dataset = self.root / "benchmark.json"
        self.document = {
            "schema_version": 1,
            "dataset_id": "test-benchmark",
            "dataset_version": "0.1.0",
            "target_game_version": "1.26.50",
            "cases": [reviewed_case()]
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_dataset(self):
        self.dataset.write_text(json.dumps(self.document), encoding="utf-8")

    def write_report(self, report: dict, case_id: str = "case-one"):
        (self.reports / f"{case_id}.json").write_text(json.dumps(report), encoding="utf-8")

    def test_scores_exact_title_path_and_severity_separately(self):
        self.write_dataset()
        self.write_report(report_document([
            finding("Invalid JSON", "RP/broken.json", "MEDIUM"),
            finding("Invalid JSON", "RP/unexpected.json", "HIGH")
        ]))
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts, "0.7.8")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["metrics"]["true_positives"], 1)
        self.assertEqual(result["metrics"]["false_positives"], 1)
        self.assertEqual(result["metrics"]["false_negatives"], 1)
        self.assertEqual(result["metrics"]["severity_mismatches"], 1)
        self.assertEqual(result["metrics"]["precision"], 0.5)
        self.assertEqual(result["metrics"]["recall"], 0.5)
        self.assertEqual(result["metrics"]["f1"], 0.5)
        self.assertEqual(result["metrics_by_rule"]["Invalid JSON"]["true_positives"], 1)
        self.assertEqual(result["metrics_by_rule"]["Invalid JSON"]["false_positives"], 1)
        self.assertEqual(result["metrics_by_rule"]["Missing geometry reference"]["false_negatives"], 1)

    def test_hash_mismatch_invalidates_the_whole_run(self):
        self.write_dataset()
        self.write_report(report_document([finding("Invalid JSON", "RP/broken.json")], sha="b" * 64))
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["metrics"])
        self.assertTrue(any("SHA-256" in item for item in result["errors"]))

    def test_missing_scored_report_invalidates_run(self):
        self.write_dataset()
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["metrics"])

    def test_pending_cases_are_skipped_without_a_report(self):
        pending = reviewed_case("case-pending")
        pending["label_status"] = "pending"
        pending["scored_rules"] = []
        pending["expected_findings"] = []
        self.document["cases"] = [pending]
        self.write_dataset()
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["scored_case_count"], 0)
        self.assertEqual(result["pending_case_count"], 1)
        self.assertIsNone(result["metrics"])

    def test_empty_template_never_reports_a_completed_benchmark(self):
        self.document["cases"] = []
        self.write_dataset()
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIsNone(result["metrics"])

    def test_source_artifact_hash_mismatch_invalidates_run(self):
        self.write_dataset()
        (self.artifacts / "case-one.mcaddon").write_bytes(b"changed artifact bytes")
        self.write_report(report_document([finding("Invalid JSON", "RP/broken.json")]))
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["metrics"])
        self.assertTrue(any("source artifact SHA-256" in item for item in result["errors"]))

    def test_wrong_tool_version_invalidates_run_when_pinned(self):
        self.write_dataset()
        self.write_report(report_document([] , version="0.7.7"))
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts, "0.7.8")
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["metrics"])
        self.assertTrue(any("expected tool version" in item for item in result["errors"]))


    def test_artifact_symlink_cannot_escape_artifacts_directory(self):
        outside = self.root / "outside.mcaddon"
        outside.write_bytes(ARTIFACT_BYTES)
        artifact_link = self.artifacts / "case-one.mcaddon"
        artifact_link.unlink()
        try:
            artifact_link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable on this platform")
        self.write_dataset()
        self.write_report(report_document([finding("Invalid JSON", "RP/broken.json")]))
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["metrics"])
        self.assertTrue(any("outside its configured directory" in item for item in result["errors"]))

    def test_report_symlink_cannot_escape_reports_directory(self):
        outside = self.root / "outside-report.json"
        outside.write_text(json.dumps(report_document([finding("Invalid JSON", "RP/broken.json")])), encoding="utf-8")
        report_link = self.reports / "case-one.json"
        try:
            report_link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable on this platform")
        self.write_dataset()
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["metrics"])
        self.assertTrue(any("outside its configured directory" in item for item in result["errors"]))

    def test_invalid_utf8_dataset_returns_invalid_without_traceback(self):
        self.dataset.write_bytes(b"\xff\xfe\xfa")
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["metrics"])
        self.assertTrue(any("Cannot read dataset JSON" in item for item in result["errors"]))

    def test_duplicate_expected_title_path_labels_are_rejected(self):
        case = reviewed_case()
        case["expected_findings"].append(dict(case["expected_findings"][0]))
        self.document["cases"] = [case]
        self.write_dataset()
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["metrics"])
        self.assertTrue(any("duplicate expected finding fingerprint" in item for item in result["errors"]))

    def test_duplicate_case_ids_are_rejected(self):
        self.document["cases"] = [reviewed_case("duplicate"), reviewed_case("duplicate")]
        self.write_dataset()
        result = evaluator.evaluate(self.dataset, self.reports, self.artifacts)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("Duplicate case_id" in item for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
