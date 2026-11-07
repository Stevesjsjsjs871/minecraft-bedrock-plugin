from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import integrate_domain_results as integrator


HERE = Path(__file__).resolve()
PACKAGE_ROOT = HERE.parents[3]


class DomainResultIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        refs = self.root / "skills/bedrock-engineer-core/references"
        refs.mkdir(parents=True)
        source_refs = PACKAGE_ROOT / "skills/bedrock-engineer-core/references"
        for filename in ("work-order.schema.json", "domain-result.schema.json"):
            (refs / filename).write_text((source_refs / filename).read_text(encoding="utf-8"), encoding="utf-8")
        self.registry = {
            "registry_version": "1.0.0",
            "domains": [
                {"id": "core", "name": "Core", "purpose": "Coordinate", "lead_skill": "core-skill", "skills": ["core-skill"], "requires": []},
                {"id": "content", "name": "Content", "purpose": "Author", "lead_skill": "content-skill", "skills": ["content-skill"], "requires": ["core"]},
                {"id": "audit", "name": "Audit", "purpose": "Verify", "lead_skill": "audit-skill", "skills": ["audit-skill"], "requires": ["content"]},
            ],
            "capability_routes": [{"id": "conversation_files"}, {"id": "connected_workspace"}, {"id": "local_executor"}, {"id": "creator_tools_cli"}, {"id": "no_execution_route"}],
        }
        (refs / "domain-registry.json").write_text(json.dumps(self.registry), encoding="utf-8")
        self.work_schema = json.loads((refs / "work-order.schema.json").read_text(encoding="utf-8"))
        self.result_schema = json.loads((refs / "domain-result.schema.json").read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def work_order(self, *, criteria: list[str] | None = None) -> dict:
        return {
            "schema_version": "1.0.0",
            "task": {
                "request": "Implement and verify an example feature.",
                "language": "en",
                "task_type": "existing_addon_change",
                "acceptance_criteria": criteria if criteria is not None else ["All requested files are updated safely."],
            },
            "project": {
                "name": "Synthetic project",
                "source_of_truth": "test fixture",
                "target_game_version": "1.26.50",
                "pack_roots": [],
                "baseline": None,
                "constraints": [],
                "preserve": [],
            },
            "capability": {
                "route": "no_execution_route",
                "verified": False,
                "available_tools": [],
                "limitations": ["No Minecraft runtime is attached."],
            },
            "plan": {
                "selected_domains": ["core", "content"],
                "ordered_skills": ["core-skill", "content-skill"],
                "steps": [
                    {"id": "domain:core", "action": "Coordinate", "status": "PLANNED", "owner_domain": "core"},
                    {"id": "domain:content", "action": "Author", "status": "PLANNED", "owner_domain": "content"},
                    {"id": "gate:01", "action": "Review output", "status": "PLANNED", "owner_domain": None},
                ],
            },
            "changes": {"files": [{"path": "planned.json", "action": "modified", "status": "PLANNED"}, {"path": "untouched.json", "action": "inspected", "status": "VERIFIED"}]},
            "domain_results": [],
            "evidence": {"items": [], "runtime_status": "NOT RUN"},
            "status": "PLANNED",
        }

    def result(
        self, domain: str, *, status: str = "PASS", path: str | None = None,
        action: str = "modified", criterion_status: str | None = "MET",
        criterion: str = "All requested files are updated safely.", evidence: list[str] | None = None,
        runtime_status: str = "NOT RUN", next_domains: list[str] | None = None,
    ) -> dict:
        changed = [] if path is None else [{"path": path, "action": action}]
        criteria = []
        if criterion_status is not None:
            ev = evidence if evidence is not None else [f"Observed evidence for {domain}."]
            criteria.append({"criterion": criterion, "status": criterion_status, "evidence": ev})
        return {
            "domain_id": domain,
            "status": status,
            "summary": f"{domain} work completed.",
            "findings": [],
            "changed_files": changed,
            "evidence": [{"check": "synthetic static check", "status": "PASS", "details": f"checked by {domain}"}],
            "limitations": [],
            "next_domains": next_domains or [],
            "runtime_status": runtime_status,
            "criterion_results": criteria,
        }

    def integrate(self, work_order: dict, results: list[dict], **kwargs) -> dict:
        return integrator.integrate(
            work_order, results, registry=self.registry,
            work_order_schema=self.work_schema, result_schema=self.result_schema, **kwargs,
        )

    def test_all_selected_domains_and_met_criteria_complete_work_order(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core"), self.result("content")])
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["integration"]["status"], "COMPLETE")
        self.assertEqual(result["integration"]["domain_coverage"], {"expected": 2, "reported": 2, "missing": []})
        self.assertEqual(result["integration"]["acceptance"][0]["status"], "MET")

    def test_project_state_link_is_preserved_through_domain_integration(self) -> None:
        work = self.work_order()
        work["project_state"] = {
            "project_id": "12345678-1234-4234-8234-123456789abc",
            "revision": 4,
            "state_path": ".mbe/project-state.json",
            "state_sha256": "a" * 64,
            "latest_snapshot_id": "snapshot-" + "b" * 32,
            "latest_snapshot_sha256": "c" * 64,
        }
        result = self.integrate(work, [self.result("core"), self.result("content")])
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["project_state"], work["project_state"])

    def test_invalid_project_state_link_is_rejected(self) -> None:
        cases = [
            {"project_id": "not-a-uuid", "revision": 1, "state_path": ".mbe/project-state.json", "state_sha256": "a" * 64, "latest_snapshot_id": None, "latest_snapshot_sha256": None},
            {"project_id": "12345678-1234-4234-8234-123456789abc", "revision": True, "state_path": ".mbe/project-state.json", "state_sha256": "a" * 64, "latest_snapshot_id": None, "latest_snapshot_sha256": None},
            {"project_id": "12345678-1234-4234-8234-123456789abc", "revision": 1, "state_path": "../outside.json", "state_sha256": "a" * 64, "latest_snapshot_id": None, "latest_snapshot_sha256": None},
            {"project_id": "12345678-1234-4234-8234-123456789abc", "revision": 1, "state_path": ".mbe/project-state.json", "state_sha256": "A" * 64, "latest_snapshot_id": None, "latest_snapshot_sha256": None},
            {"project_id": "12345678-1234-4234-8234-123456789abc", "revision": 1, "state_path": ".mbe/project-state.json", "state_sha256": "a" * 64, "latest_snapshot_id": "snapshot-" + "b" * 32, "latest_snapshot_sha256": None},
        ]
        for link in cases:
            with self.subTest(link=link):
                work = self.work_order()
                work["project_state"] = link
                with self.assertRaises(integrator.IntegrationError):
                    self.integrate(work, [])

    def test_missing_domain_keeps_work_order_in_progress(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core")])
        self.assertEqual(result["status"], "IN_PROGRESS")
        self.assertEqual(result["integration"]["domain_coverage"]["missing"], ["content"])

    def test_failed_domain_prevents_completion(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core"), self.result("content", status="FAIL")])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["plan"]["steps"][1]["status"], "FAIL")

    def test_blocked_domain_blocks_work_order(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core"), self.result("content", status="BLOCKED")])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["integration"]["status"], "BLOCKED")

    def test_blocker_finding_blocks_work_order_even_when_domain_status_is_pass(self) -> None:
        content = self.result("content")
        content["findings"] = [{"severity": "BLOCKER", "message": "A required dependency is missing.", "confidence": "CONFIRMED"}]
        result = self.integrate(self.work_order(), [self.result("core"), content])
        self.assertEqual(result["status"], "BLOCKED")

    def test_overlapping_domain_writes_are_high_severity_review(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", path="shared/file.json"), self.result("content", path="shared/file.json")])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["integration"]["conflicts"][0]["code"], "OVERLAPPING_WRITE")
        self.assertEqual(result["integration"]["conflicts"][0]["severity"], "HIGH")

    def test_remove_versus_write_is_blocker(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", path="shared/file.json", action="removed"), self.result("content", path="shared/file.json", action="modified")])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["integration"]["conflicts"][0]["code"], "REMOVE_VS_WRITE")

    def test_case_insensitive_path_collision_is_blocker(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", path="Textures/Body.png"), self.result("content", path="textures/body.png")])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("CASE_COLLISION", {x["code"] for x in result["integration"]["conflicts"]})

    def test_inspection_and_modification_of_same_file_do_not_conflict(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", path="shared/file.json", action="inspected"), self.result("content", path="shared/file.json", action="modified")])
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["integration"]["conflicts"], [])

    def test_opposing_acceptance_claims_become_conflict(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", criterion_status="MET"), self.result("content", criterion_status="NOT MET")])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["integration"]["acceptance"][0]["status"], "CONFLICT")

    def test_unreported_acceptance_criterion_is_unverified(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", criterion_status=None), self.result("content", criterion_status=None)])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["integration"]["acceptance"][0]["status"], "UNVERIFIED")

    def test_met_criterion_requires_evidence(self) -> None:
        with self.assertRaisesRegex(integrator.IntegrationError, "requires evidence"):
            self.integrate(self.work_order(), [self.result("core", evidence=[]), self.result("content")])

    def test_unknown_domain_is_rejected(self) -> None:
        with self.assertRaisesRegex(integrator.IntegrationError, "unknown domain"):
            self.integrate(self.work_order(), [self.result("missing")])

    def test_unselected_domain_is_rejected(self) -> None:
        with self.assertRaisesRegex(integrator.IntegrationError, "not selected"):
            self.integrate(self.work_order(), [self.result("audit")])

    def test_duplicate_incoming_domain_results_are_rejected(self) -> None:
        with self.assertRaisesRegex(integrator.IntegrationError, "duplicate domain_id"):
            self.integrate(self.work_order(), [self.result("core"), self.result("core")])

    def test_existing_domain_result_requires_explicit_replacement(self) -> None:
        work = self.work_order()
        work["domain_results"] = [self.result("core")]
        with self.assertRaisesRegex(integrator.IntegrationError, "already exists"):
            self.integrate(work, [self.result("core")])

    def test_existing_domain_result_can_be_explicitly_replaced(self) -> None:
        work = self.work_order()
        work["domain_results"] = [self.result("core", status="PARTIAL")]
        result = self.integrate(work, [self.result("core", status="PASS"), self.result("content")], replace_domains=["core"])
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(len(result["domain_results"]), 2)

    def test_replacement_flag_without_stored_record_is_rejected(self) -> None:
        with self.assertRaisesRegex(integrator.IntegrationError, "without an existing result"):
            self.integrate(self.work_order(), [self.result("core")], replace_domains=["core"])

    def test_replacement_flag_requires_replacement_payload(self) -> None:
        work = self.work_order()
        work["domain_results"] = [self.result("core")]
        with self.assertRaisesRegex(integrator.IntegrationError, "no incoming replacement"):
            self.integrate(work, [self.result("content")], replace_domains=["core"])

    def test_undeclared_acceptance_criterion_is_rejected(self) -> None:
        with self.assertRaisesRegex(integrator.IntegrationError, "not declared"):
            self.integrate(self.work_order(), [self.result("core", criterion="Different criterion")])

    def test_parent_traversal_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(integrator.IntegrationError, "unsafe path"):
            self.integrate(self.work_order(), [self.result("core", path="../outside.json")])

    def test_absolute_and_windows_paths_are_rejected(self) -> None:
        for unsafe in ("/tmp/outside.json", "C:/outside.json", "folder\\file.json"):
            with self.subTest(path=unsafe), self.assertRaises(integrator.IntegrationError):
                self.integrate(self.work_order(), [self.result("core", path=unsafe)])

    def test_duplicate_path_claim_inside_one_domain_is_rejected(self) -> None:
        result = self.result("core", path="same.json")
        result["changed_files"].append(dict(result["changed_files"][0]))
        with self.assertRaisesRegex(integrator.IntegrationError, "more than once"):
            self.integrate(self.work_order(), [result])

    def test_unknown_handoff_domain_is_rejected(self) -> None:
        with self.assertRaisesRegex(integrator.IntegrationError, "unknown next domains"):
            self.integrate(self.work_order(), [self.result("core", next_domains=["ghost-domain"])])

    def test_runtime_status_is_not_inferred_from_static_pass(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core"), self.result("content")])
        self.assertEqual(result["evidence"]["runtime_status"], "NOT RUN")

    def test_all_domain_runtime_checks_must_be_tested_for_runtime_tested(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", runtime_status="RUNTIME TESTED"), self.result("content", runtime_status="RUNTIME TESTED")])
        self.assertEqual(result["evidence"]["runtime_status"], "RUNTIME TESTED")

    def test_mixed_runtime_states_are_partial(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", runtime_status="RUNTIME TESTED"), self.result("content", runtime_status="NOT RUN")])
        self.assertEqual(result["evidence"]["runtime_status"], "PARTIAL")

    def test_planned_file_entry_is_replaced_and_unrelated_entry_preserved(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", path="planned.json"), self.result("content")])
        files = result["changes"]["files"]
        planned = [x for x in files if x["path"] == "planned.json"]
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0]["status"], "APPLIED")
        self.assertTrue(any(x["path"] == "untouched.json" for x in files))

    def test_domain_evidence_is_namespaced_and_preserved(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core"), self.result("content")])
        checks = [x["check"] for x in result["evidence"]["items"]]
        self.assertIn("core:synthetic static check", checks)
        self.assertIn("content:synthetic static check", checks)

    def test_next_domain_hints_are_deduplicated_and_exclude_completed_domains(self) -> None:
        result = self.integrate(self.work_order(), [self.result("core", next_domains=["content", "audit"]), self.result("content", next_domains=["audit"])])
        self.assertEqual(result["integration"]["next_domains"], ["audit"])

    def test_no_results_leave_work_order_planned(self) -> None:
        result = self.integrate(self.work_order(), [])
        self.assertEqual(result["status"], "PLANNED")
        self.assertEqual(result["integration"]["status"], "PLANNED")

    def test_not_applied_file_status_is_not_promoted_to_applied(self) -> None:
        result = self.result("core", path="new.json", status="NOT APPLIED")
        result["changed_files"][0]["status"] = "NOT APPLIED"
        integrated = self.integrate(self.work_order(), [result, self.result("content")])
        entry = next(x for x in integrated["changes"]["files"] if x["path"] == "new.json")
        self.assertEqual(entry["status"], "NOT APPLIED")

    def test_duplicate_json_keys_are_rejected(self) -> None:
        path = self.root / "duplicate.json"
        path.write_text('{"domain_id":"core","domain_id":"content"}', encoding="utf-8")
        with self.assertRaisesRegex(integrator.IntegrationError, "duplicate JSON key"):
            integrator.read_json(path)

    def test_output_is_not_overwritten_without_explicit_flag(self) -> None:
        path = self.root / "result.json"
        path.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(integrator.IntegrationError, "pass --overwrite"):
            integrator._atomic_write(path, "replace", overwrite=False)
        self.assertEqual(path.read_text(encoding="utf-8"), "keep")

    def test_explicit_overwrite_is_atomic_and_allowed(self) -> None:
        path = self.root / "result.json"
        path.write_text("old", encoding="utf-8")
        integrator._atomic_write(path, "new", overwrite=True)
        self.assertEqual(path.read_text(encoding="utf-8"), "new")

    def test_cli_writes_integrated_work_order_only_to_explicit_output(self) -> None:
        work_path = self.root / "work.json"
        core_path = self.root / "core.json"
        content_path = self.root / "content.json"
        out_path = self.root / "integrated.json"
        work_path.write_text(json.dumps(self.work_order()), encoding="utf-8")
        core_path.write_text(json.dumps(self.result("core")), encoding="utf-8")
        content_path.write_text(json.dumps(self.result("content")), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = integrator.main([
                "--package-root", str(self.root), "--work-order", str(work_path),
                "--result", str(core_path), "--result", str(content_path), "--output", str(out_path),
            ])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out_path.read_text(encoding="utf-8"))["status"], "COMPLETE")
        self.assertTrue(stdout.getvalue().strip().startswith("{"))
        self.assertEqual(json.loads(work_path.read_text(encoding="utf-8"))["domain_results"], [])

    def test_cli_returns_one_for_valid_but_incomplete_work_order(self) -> None:
        work_path = self.root / "work.json"
        result_path = self.root / "core.json"
        work_path.write_text(json.dumps(self.work_order()), encoding="utf-8")
        result_path.write_text(json.dumps(self.result("core")), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = integrator.main([
                "--package-root", str(self.root), "--work-order", str(work_path), "--result", str(result_path),
            ])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "IN_PROGRESS")
        self.assertFalse((self.root / "work_order.integrated.json").exists())

    def test_cli_returns_two_for_invalid_input(self) -> None:
        work_path = self.root / "broken.json"
        work_path.write_text("{bad json", encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = integrator.main(["--package-root", str(self.root), "--work-order", str(work_path)])
        self.assertEqual(code, 2)
        self.assertIn("ERROR:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
