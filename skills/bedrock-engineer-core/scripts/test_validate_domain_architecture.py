from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_domain_architecture as validator  # noqa: E402


class DomainArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for slug in ("core-skill", "content-skill", "audit-skill", "domain-result-integration", "project-state-management", "change-impact-analysis"):
            folder = self.root / "skills" / slug
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text(
                f"---\nname: {slug}\ndescription: Test domain Skill {slug}.\n---\n# {slug}\n",
                encoding="utf-8",
            )
        (self.root / "skills/bedrock-engineer-core/references").mkdir(parents=True)
        domains = [
            {"id": "core", "name": "Core", "purpose": "Coordinate tasks.", "lead_skill": "core-skill", "skills": ["core-skill", "domain-result-integration", "project-state-management"], "requires": [], "output_contract": ["plan", "Domain Result integration"]},
            {"id": "content", "name": "Content", "purpose": "Author content.", "lead_skill": "content-skill", "skills": ["content-skill"], "requires": ["core"], "output_contract": ["files"]},
            {"id": "audit", "name": "Audit", "purpose": "Validate content.", "lead_skill": "audit-skill", "skills": ["audit-skill", "change-impact-analysis"], "requires": ["content"], "output_contract": ["evidence"]},
        ]
        self.registry = {
            "registry_version": "1.0.0",
            "architecture": {
                "id": "domain-based-hybrid",
                "integration_model": "skills-only",
                "hard_boundaries": ["No MCP service, client, registry, transport or plugin-owned backend."],
            },
            "domains": domains,
            "workflow_profiles": {
                "test": {
                    "required_domains": ["core", "content"],
                    "optional_domains": ["audit"],
                    "delivery_gates": ["tests"],
                }
            },
            "capability_routes": [
                {"id": "conversation_files"}, {"id": "connected_workspace"},
                {"id": "local_executor"}, {"id": "creator_tools_cli"},
                {"id": "no_execution_route"},
            ],
        }
        self._write_registry()
        self._write_schema("work-order.schema.json", ["schema_version", "task", "project", "capability", "plan", "changes", "evidence", "status"])
        self._write_schema("domain-result.schema.json", ["domain_id", "status", "summary", "findings", "changed_files", "evidence", "limitations"])
        (self.root / "ARCHITECTURE.md").write_text(
            "# Domain-Based Hybrid\n\n## Skills-only\n\n## Task lifecycle\n\n## Domain Result integration\n\n`integrate_domain_results.py`\n\n## Project State Management\n\n`project_state.py`\n\n## Change Impact Analysis\n\n`analyze_change_impact.py`\n",
            encoding="utf-8",
        )
        planner_dir = self.root / "skills/bedrock-engineer-core/scripts"
        planner_dir.mkdir(parents=True, exist_ok=True)
        (planner_dir / "plan_domain_work.py").write_text(
            "def resolve_domain_order(): pass\ndef build_work_order(): pass\n_validate_work_order()\nno_execution_route runtime_status NOT RUN\ninclude_skills --include-skill\n",
            encoding="utf-8",
        )
        (planner_dir / "test_plan_domain_work.py").write_text("# focused planner tests\n", encoding="utf-8")
        (planner_dir / "integrate_domain_results.py").write_text(
            "def integrate(): pass\ndef _detect_conflicts(): pass\n--replace-domain criterion_results runtime_status CASE_COLLISION REMOVE_VS_WRITE\n",
            encoding="utf-8",
        )
        (planner_dir / "test_integrate_domain_results.py").write_text("# focused integration tests\n", encoding="utf-8")
        skill = self.root / "skills/domain-result-integration/SKILL.md"
        skill.write_text("---\nname: domain-result-integration\ndescription: Integrate Domain Result hand-offs.\n---\nUse integrate_domain_results.py\n", encoding="utf-8")
        state_dir = self.root / "skills/bedrock-engineer-core/scripts"
        (state_dir / "project_state.py").write_text(
            'def init_project(): pass\ndef inspect_project(): pass\ndef capture_project(): pass\ndef restore_revision(): pass\ndef recover_project(): pass\n--expected-revision event_hash sha256 "project_files_changed": False\n',
            encoding="utf-8",
        )
        (state_dir / "test_project_state.py").write_text("# focused project state tests\n", encoding="utf-8")
        (self.root / "skills/project-state-management/SKILL.md").write_text(
            "---\nname: project-state-management\ndescription: Manage durable project state.\n---\nUse project_state.py under .mbe/. Snapshots are metadata; never restore source files.\n",
            encoding="utf-8",
        )
        (self.root / "skills/change-impact-analysis/SKILL.md").write_text(
            "---\nname: change-impact-analysis\ndescription: Analyze static change impact.\n---\nUse analyze_change_impact.py for a read-only reverse dependency report.\n",
            encoding="utf-8",
        )
        (state_dir / "analyze_change_impact.py").write_text(
            'def analyze_project(): pass\ndef _walk_project(): pass\ndef _resolve_asset_path(): pass\n--changed-path reverse UNRESOLVED_IDENTIFIER AMBIGUOUS_IDENTIFIER os.scandir DEFAULT_IGNORES --max-total-bytes\n',
            encoding="utf-8",
        )
        (state_dir / "test_analyze_change_impact.py").write_text("# focused change impact tests\n", encoding="utf-8")
        (self.root / "skills/bedrock-engineer-core/references/change-impact.schema.json").write_text(
            json.dumps({"type": "object", "required": ["schema_version", "project_root_name", "changed_paths", "impact", "summary", "coverage", "edges", "findings", "limitations"], "properties": {}}),
            encoding="utf-8",
        )
        self._write_schema("project-state.schema.json", ["schema_version", "project", "revision", "created_at", "updated_at", "latest_snapshot", "last_complete_snapshot", "records", "history", "last_event_hash", "integrity"])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_registry(self) -> None:
        (self.root / validator.REGISTRY_PATH).write_text(
            json.dumps(self.registry, indent=2), encoding="utf-8"
        )

    def _write_schema(self, filename: str, required: list[str]) -> None:
        path = self.root / "skills/bedrock-engineer-core/references" / filename
        properties = {x: {} for x in required}
        if filename == "work-order.schema.json":
            properties["domain_results"] = {"items": {"$ref": "domain-result.schema.json"}}
            properties["project_state"] = {"type": "object", "required": ["project_id", "revision", "state_path", "state_sha256"]}
        document = {"type": "object", "required": required, "properties": properties}
        if filename == "project-state.schema.json":
            document["$defs"] = {}
        path.write_text(json.dumps(document), encoding="utf-8")

    def _check(self, check_id: str, report: dict) -> str:
        return next(x["status"] for x in report["checks"] if x["id"] == check_id)


    def test_current_registry_has_14_domains_and_59_unique_skills(self) -> None:
        registry_path = HERE.parent / "references/domain-registry.json"
        current = json.loads(registry_path.read_text(encoding="utf-8"))
        assigned = [skill for domain in current["domains"] for skill in domain["skills"]]
        self.assertEqual(len(current["domains"]), 14)
        self.assertEqual(len(assigned), 59)
        self.assertEqual(len(set(assigned)), 59)
        self.assertNotIn("entity-authoring", assigned)
        self.assertIn("entity-authoring-pipeline", assigned)
        self.assertIn("domain-result-integration", assigned)
        self.assertIn("project-state-management", assigned)
        self.assertIn("change-impact-analysis", assigned)

    def test_current_registry_dependencies_are_acyclic(self) -> None:
        registry_path = HERE.parent / "references/domain-registry.json"
        current = json.loads(registry_path.read_text(encoding="utf-8"))
        graph = {domain["id"]: domain["requires"] for domain in current["domains"]}
        self.assertFalse(validator._has_cycle(graph))
        self.assertTrue(all(dep in graph for deps in graph.values() for dep in deps))

    def test_current_work_order_and_result_schemas_parse(self) -> None:
        refs = HERE.parent / "references"
        work = json.loads((refs / "work-order.schema.json").read_text(encoding="utf-8"))
        result = json.loads((refs / "domain-result.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(work["properties"]["domain_results"]["items"]["$ref"], "domain-result.schema.json")
        self.assertIn("domain_id", result["required"])
        self.assertIn("criterion_results", result["properties"])
        self.assertIn("runtime_status", result["properties"])
        self.assertIn("integration", work["properties"])
        self.assertIn("project_state", work["properties"])

    def test_valid_architecture_passes(self) -> None:
        self.assertEqual(validator.validate(self.root)["status"], "PASS")

    def test_unregistered_skill_fails_coverage(self) -> None:
        self.registry["domains"][1]["skills"].remove("content-skill")
        self._write_registry()
        self.assertEqual(self._check("skill-coverage", validator.validate(self.root)), "FAIL")

    def test_registered_missing_skill_fails_coverage(self) -> None:
        self.registry["domains"][1]["skills"].append("ghost-skill")
        self._write_registry()
        self.assertEqual(self._check("skill-coverage", validator.validate(self.root)), "FAIL")

    def test_duplicate_primary_assignment_fails(self) -> None:
        self.registry["domains"][2]["skills"].append("content-skill")
        self._write_registry()
        self.assertEqual(self._check("unique-primary-membership", validator.validate(self.root)), "FAIL")

    def test_unknown_domain_dependency_fails(self) -> None:
        self.registry["domains"][2]["requires"].append("missing-domain")
        self._write_registry()
        self.assertEqual(self._check("domain-dependencies", validator.validate(self.root)), "FAIL")

    def test_dependency_cycle_fails(self) -> None:
        self.registry["domains"][0]["requires"] = ["audit"]
        self._write_registry()
        self.assertEqual(self._check("domain-dependency-dag", validator.validate(self.root)), "FAIL")

    def test_profile_unknown_domain_fails(self) -> None:
        self.registry["workflow_profiles"]["test"]["optional_domains"].append("unknown")
        self._write_registry()
        self.assertEqual(self._check("workflow-profiles", validator.validate(self.root)), "FAIL")

    def test_profile_required_optional_overlap_fails(self) -> None:
        self.registry["workflow_profiles"]["test"]["optional_domains"].append("core")
        self._write_registry()
        self.assertEqual(self._check("workflow-profiles", validator.validate(self.root)), "FAIL")

    def test_lead_skill_must_belong_to_domain(self) -> None:
        self.registry["domains"][1]["lead_skill"] = "core-skill"
        self._write_registry()
        self.assertEqual(self._check("domain-shape", validator.validate(self.root)), "FAIL")

    def test_skill_frontmatter_name_must_match_directory(self) -> None:
        p = self.root / "skills/content-skill/SKILL.md"
        p.write_text("---\nname: wrong-name\ndescription: Incorrect.\n---\n", encoding="utf-8")
        self.assertEqual(self._check("skill-frontmatter", validator.validate(self.root)), "FAIL")

    def test_skill_frontmatter_is_required(self) -> None:
        p = self.root / "skills/content-skill/SKILL.md"
        p.write_text("# no frontmatter\n", encoding="utf-8")
        self.assertEqual(self._check("skill-frontmatter", validator.validate(self.root)), "FAIL")

    def test_missing_domain_result_schema_fails(self) -> None:
        (self.root / validator.DOMAIN_RESULT_PATH).unlink()
        self.assertEqual(self._check("domain-result-schema", validator.validate(self.root)), "FAIL")

    def test_work_order_required_fields_are_enforced(self) -> None:
        self._write_schema("work-order.schema.json", ["task", "project"])
        self.assertEqual(self._check("work-order-schema", validator.validate(self.root)), "FAIL")

    def test_missing_no_execution_route_fails(self) -> None:
        self.registry["capability_routes"] = self.registry["capability_routes"][:-1]
        self._write_registry()
        self.assertEqual(self._check("capability-routes", validator.validate(self.root)), "FAIL")

    def test_non_skills_only_architecture_fails(self) -> None:
        self.registry["architecture"]["integration_model"] = "hybrid-mcp"
        self._write_registry()
        self.assertEqual(self._check("architecture-identity", validator.validate(self.root)), "FAIL")

    def test_missing_architecture_document_fails(self) -> None:
        (self.root / "ARCHITECTURE.md").unlink()
        self.assertEqual(self._check("architecture-document", validator.validate(self.root)), "FAIL")

    def test_missing_domain_planner_fails(self) -> None:
        (self.root / validator.DOMAIN_PLANNER_PATH).unlink()
        self.assertEqual(self._check("domain-planner", validator.validate(self.root)), "FAIL")

    def test_missing_domain_planner_tests_fails(self) -> None:
        (self.root / validator.DOMAIN_PLANNER_TEST_PATH).unlink()
        self.assertEqual(self._check("domain-planner-tests", validator.validate(self.root)), "FAIL")


    def test_missing_domain_result_integrator_fails(self) -> None:
        (self.root / validator.DOMAIN_INTEGRATOR_PATH).unlink()
        self.assertEqual(self._check("domain-result-integrator", validator.validate(self.root)), "FAIL")

    def test_missing_domain_result_integrator_tests_fails(self) -> None:
        (self.root / validator.DOMAIN_INTEGRATOR_TEST_PATH).unlink()
        self.assertEqual(self._check("domain-result-integrator-tests", validator.validate(self.root)), "FAIL")

    def test_missing_domain_result_integration_skill_fails(self) -> None:
        (self.root / "skills/domain-result-integration/SKILL.md").unlink()
        self.assertEqual(self._check("domain-result-integration-skill", validator.validate(self.root)), "FAIL")

    def test_domain_planner_cannot_import_legacy_runtime(self) -> None:
        p = self.root / validator.DOMAIN_PLANNER_PATH
        p.write_text("import subprocess\ndef resolve_domain_order(): pass\ndef build_work_order(): pass\n_validate_work_order()\nno_execution_route runtime_status NOT RUN include_skills --include-skill\n", encoding="utf-8")
        self.assertEqual(self._check("domain-planner", validator.validate(self.root)), "FAIL")

    def test_missing_change_impact_analyzer_fails(self) -> None:
        (self.root / validator.CHANGE_IMPACT_SCRIPT_PATH).unlink()
        self.assertEqual(self._check("change-impact-analyzer", validator.validate(self.root)), "FAIL")

    def test_change_impact_analyzer_cannot_import_runtime_or_network(self) -> None:
        path = self.root / validator.CHANGE_IMPACT_SCRIPT_PATH
        path.write_text("import subprocess\ndef analyze_project(): pass\ndef _walk_project(): pass\ndef _resolve_asset_path(): pass\n--changed-path reverse UNRESOLVED_IDENTIFIER AMBIGUOUS_IDENTIFIER os.scandir DEFAULT_IGNORES --max-total-bytes\n", encoding="utf-8")
        self.assertEqual(self._check("change-impact-analyzer", validator.validate(self.root)), "FAIL")

    def test_missing_change_impact_tests_fails(self) -> None:
        (self.root / validator.CHANGE_IMPACT_TEST_PATH).unlink()
        self.assertEqual(self._check("change-impact-analyzer-tests", validator.validate(self.root)), "FAIL")

    def test_missing_change_impact_skill_fails(self) -> None:
        (self.root / validator.CHANGE_IMPACT_SKILL_PATH).unlink()
        self.assertEqual(self._check("change-impact-analysis-skill", validator.validate(self.root)), "FAIL")

    def test_missing_change_impact_schema_fields_fails(self) -> None:
        (self.root / validator.CHANGE_IMPACT_SCHEMA_PATH).write_text(json.dumps({"type": "object", "required": ["changed_paths"]}), encoding="utf-8")
        self.assertEqual(self._check("change-impact-report-schema", validator.validate(self.root)), "FAIL")

    def test_invalid_registry_json_fails(self) -> None:
        (self.root / validator.REGISTRY_PATH).write_text("{not json", encoding="utf-8")
        self.assertEqual(self._check("registry-json", validator.validate(self.root)), "FAIL")

    def test_duplicate_enum_values_fail_domain_result_schema(self) -> None:
        schema_path = self.root / validator.DOMAIN_RESULT_PATH
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["properties"]["status"] = {"enum": ["PASS", "PARTIAL", "PARTIAL"]}
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        self.assertEqual(self._check("domain-result-schema", validator.validate(self.root)), "FAIL")

    def test_missing_project_state_manager_fails(self) -> None:
        (self.root / validator.PROJECT_STATE_PATH).unlink()
        self.assertEqual(self._check("project-state-manager", validator.validate(self.root)), "FAIL")

    def test_missing_project_state_manager_tests_fails(self) -> None:
        (self.root / validator.PROJECT_STATE_TEST_PATH).unlink()
        self.assertEqual(self._check("project-state-manager-tests", validator.validate(self.root)), "FAIL")

    def test_missing_project_state_management_skill_fails(self) -> None:
        (self.root / validator.PROJECT_STATE_SKILL_PATH).unlink()
        self.assertEqual(self._check("project-state-management-skill", validator.validate(self.root)), "FAIL")

    def test_missing_project_state_schema_fails(self) -> None:
        (self.root / validator.PROJECT_STATE_SCHEMA_PATH).unlink()
        self.assertEqual(self._check("project-state-schema", validator.validate(self.root)), "FAIL")

    def test_work_order_without_project_state_link_fails(self) -> None:
        schema_path = self.root / validator.WORK_ORDER_PATH
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["properties"].pop("project_state")
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        self.assertEqual(self._check("work-order-project-state-link", validator.validate(self.root)), "FAIL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
