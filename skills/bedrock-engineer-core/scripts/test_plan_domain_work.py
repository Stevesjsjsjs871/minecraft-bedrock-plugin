from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan_domain_work as planner  # noqa: E402


class DomainWorkPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        refs = self.root / "skills/bedrock-engineer-core/references"
        refs.mkdir(parents=True)
        domains = [
            {"id": "core", "name": "Core", "purpose": "Coordinate task intake.", "lead_skill": "core-skill", "skills": ["core-skill", "execution-skill"], "requires": [], "output_contract": ["task plan"]},
            {"id": "continuity", "name": "Continuity", "purpose": "Recover project baseline.", "lead_skill": "continuity-skill", "skills": ["continuity-skill"], "requires": ["core"], "output_contract": ["baseline"]},
            {"id": "compatibility", "name": "Compatibility", "purpose": "Research target version.", "lead_skill": "compat-skill", "skills": ["compat-skill"], "requires": ["core"], "output_contract": ["source evidence"]},
            {"id": "authoring", "name": "Authoring", "purpose": "Implement BP/RP resources.", "lead_skill": "author-skill", "skills": ["author-skill", "bundle-skill"], "requires": ["continuity", "compatibility"], "output_contract": ["files"]},
            {"id": "audit", "name": "Audit", "purpose": "Validate project changes.", "lead_skill": "audit-skill", "skills": ["audit-skill"], "requires": ["continuity"], "output_contract": ["evidence"]},
            {"id": "ui", "name": "UI", "purpose": "Edit RP UI resources.", "lead_skill": "ui-skill", "skills": ["ui-skill"], "requires": ["authoring"], "output_contract": ["UI diff"]},
        ]
        self.registry = {
            "registry_version": "1.0.0",
            "architecture": {"id": "domain-based-hybrid", "integration_model": "skills-only"},
            "domains": domains,
            "workflow_profiles": {
                "new_addon": {
                    "required_domains": ["core", "compatibility", "authoring", "audit"],
                    "optional_domains": ["ui"],
                    "delivery_gates": ["manifests and pack dependencies validated", "final resource graph reviewed"],
                },
                "research_only": {
                    "required_domains": ["core", "compatibility"],
                    "optional_domains": [],
                    "delivery_gates": ["target version confirmed"],
                },
            },
            "capability_routes": [
                {"id": "conversation_files"}, {"id": "connected_workspace"},
                {"id": "local_executor"}, {"id": "creator_tools_cli"},
                {"id": "no_execution_route"},
            ],
        }
        (refs / "domain-registry.json").write_text(json.dumps(self.registry), encoding="utf-8")
        root_schema = {
            "type": "object",
            "required": ["schema_version", "task", "project", "capability", "plan", "changes", "evidence", "status"],
            "properties": {key: {} for key in ["schema_version", "task", "project", "capability", "plan", "changes", "evidence", "status", "domain_results"]},
        }
        result_schema = {"type": "object", "required": ["domain_id", "status", "summary", "findings", "changed_files", "evidence", "limitations"]}
        (refs / "work-order.schema.json").write_text(json.dumps(root_schema), encoding="utf-8")
        (refs / "domain-result.schema.json").write_text(json.dumps(result_schema), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self, **overrides):
        args = {
            "profile_name": "new_addon",
            "request": "Create a minimal addon feature",
            "project_name": "Example Addon",
            "source_of_truth": "conversation upload (not yet inspected)",
            "package_root": self.root,
        }
        args.update(overrides)
        return planner.build_work_order(self.registry, **args)

    def test_required_domains_expand_to_stable_dependency_order(self):
        actual = planner.resolve_domain_order(self.registry, "new_addon")
        self.assertEqual(actual, ["core", "compatibility", "continuity", "authoring", "audit"])

    def test_optional_domain_is_added_with_its_transitive_dependencies(self):
        actual = planner.resolve_domain_order(self.registry, "new_addon", ["ui"])
        self.assertEqual(actual, ["core", "compatibility", "continuity", "authoring", "audit", "ui"])

    def test_profile_selection_does_not_load_unrelated_optional_domains(self):
        order = self.build()
        self.assertNotIn("ui", order["plan"]["selected_domains"])

    def test_unknown_profile_fails(self):
        with self.assertRaisesRegex(ValueError, "unknown workflow profile"):
            planner.resolve_domain_order(self.registry, "not_a_profile")

    def test_only_profile_optional_domains_can_be_added(self):
        with self.assertRaisesRegex(ValueError, "not optional"):
            planner.resolve_domain_order(self.registry, "research_only", ["ui"])

    def test_duplicate_include_domain_fails(self):
        with self.assertRaisesRegex(ValueError, "must be unique"):
            planner.resolve_domain_order(self.registry, "new_addon", ["ui", "ui"])

    def test_duplicate_required_domain_fails(self):
        self.registry["workflow_profiles"]["new_addon"]["required_domains"].append("core")
        with self.assertRaisesRegex(ValueError, "duplicate domain entries"):
            planner.resolve_domain_order(self.registry, "new_addon")

    def test_unknown_optional_domain_fails(self):
        self.registry["workflow_profiles"]["new_addon"]["optional_domains"].append("ghost")
        with self.assertRaisesRegex(ValueError, "unknown optional domains"):
            planner.resolve_domain_order(self.registry, "new_addon")

    def test_unknown_required_domain_fails(self):
        self.registry["workflow_profiles"]["new_addon"]["required_domains"].append("ghost")
        with self.assertRaisesRegex(ValueError, "unknown required domains"):
            planner.resolve_domain_order(self.registry, "new_addon")

    def test_unknown_domain_dependency_fails(self):
        self.registry["domains"][3]["requires"].append("ghost")
        with self.assertRaisesRegex(ValueError, "unknown domain"):
            planner.resolve_domain_order(self.registry, "new_addon")

    def test_duplicate_dependency_edge_fails(self):
        self.registry["domains"][1]["requires"].append("core")
        with self.assertRaisesRegex(ValueError, "duplicate dependency edges"):
            planner.resolve_domain_order(self.registry, "new_addon")

    def test_dependency_cycle_fails_with_cycle_path(self):
        self.registry["domains"][0]["requires"] = ["audit"]
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            planner.resolve_domain_order(self.registry, "new_addon")

    def test_duplicate_domain_id_fails(self):
        duplicate = dict(self.registry["domains"][0])
        self.registry["domains"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate domain id"):
            planner.resolve_domain_order(self.registry, "new_addon")

    def test_duplicate_skill_primary_owner_fails(self):
        self.registry["domains"][1]["skills"].append("core-skill")
        with self.assertRaisesRegex(ValueError, "multiple primary domains"):
            planner.resolve_domain_order(self.registry, "new_addon")

    def test_lead_skill_must_be_in_domain(self):
        self.registry["domains"][2]["lead_skill"] = "core-skill"
        with self.assertRaisesRegex(ValueError, "lead_skill must belong"):
            planner.resolve_domain_order(self.registry, "new_addon")

    def test_missing_delivery_gate_array_fails(self):
        self.registry["workflow_profiles"]["new_addon"]["delivery_gates"] = "not-an-array"
        with self.assertRaisesRegex(ValueError, "invalid delivery_gates"):
            self.build()

    def test_current_registry_all_profiles_generate_valid_work_orders(self):
        package_root = HERE.parents[2]
        registry_path = package_root / planner.REGISTRY_PATH
        live_registry = json.loads(registry_path.read_text(encoding="utf-8"))
        for profile_name in live_registry["workflow_profiles"]:
            with self.subTest(profile=profile_name):
                order = planner.build_work_order(
                    live_registry,
                    profile_name=profile_name,
                    request=f"Smoke-test workflow profile {profile_name}",
                    project_name="Synthetic profile test",
                    source_of_truth="synthetic test fixture",
                    package_root=package_root,
                )
                self.assertEqual(order["status"], "PLANNED")
                self.assertEqual(order["evidence"]["runtime_status"], "NOT RUN")
                self.assertTrue(order["plan"]["selected_domains"])

    def test_generated_work_order_matches_shared_contract(self):
        order = self.build()
        self.assertEqual(order["schema_version"], "1.0.0")
        self.assertEqual(order["status"], "PLANNED")
        self.assertEqual(order["evidence"]["runtime_status"], "NOT RUN")
        self.assertEqual(order["changes"]["files"], [])
        self.assertEqual(order["domain_results"], [])

    def test_task_type_defaults_to_profile_name(self):
        self.assertEqual(self.build()["task"]["task_type"], "new_addon")

    def test_explicit_task_type_and_acceptance_criteria_are_preserved(self):
        order = self.build(task_type="new_entity", acceptance_criteria=["entity spawns", "texture resolves"])
        self.assertEqual(order["task"]["task_type"], "new_entity")
        self.assertEqual(order["task"]["acceptance_criteria"], ["entity spawns", "texture resolves"])

    def test_profile_domains_become_ordered_skill_list_without_duplicates(self):
        order = self.build()
        self.assertEqual(order["plan"]["ordered_skills"], [
            "core-skill", "compat-skill", "continuity-skill", "author-skill", "audit-skill"
        ])

    def test_explicit_specialist_skill_is_added_after_its_domain_lead(self):
        order = self.build(include_skills=["bundle-skill"])
        self.assertEqual(order["plan"]["ordered_skills"], [
            "core-skill", "compat-skill", "continuity-skill", "author-skill", "bundle-skill", "audit-skill"
        ])

    def test_specialist_skill_from_unselected_domain_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "domains that are not selected"):
            self.build(profile_name="research_only", include_skills=["ui-skill"])

    def test_unknown_specialist_skill_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown Skills requested"):
            self.build(include_skills=["ghost-skill"])

    def test_duplicate_specialist_skill_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be unique"):
            self.build(include_skills=["bundle-skill", "bundle-skill"])

    def test_lead_skill_cannot_be_added_twice(self):
        with self.assertRaisesRegex(ValueError, "already included by their domains"):
            self.build(include_skills=["author-skill"])

    def test_domain_steps_precede_delivery_gate_steps(self):
        order = self.build()
        steps = order["plan"]["steps"]
        self.assertEqual(steps[0]["id"], "domain:core")
        self.assertEqual(steps[-2]["id"], "gate:01")
        self.assertEqual(steps[-1]["id"], "gate:02")
        self.assertTrue(all(step["status"] == "PLANNED" for step in steps))

    def test_unknown_capability_route_fails(self):
        with self.assertRaisesRegex(ValueError, "not declared"):
            self.build(capability_route="made_up_route")

    def test_capability_route_is_caller_declared_not_assumed(self):
        order = self.build(capability_route="conversation_files", capability_verified=False)
        self.assertEqual(order["capability"]["route"], "conversation_files")
        self.assertFalse(order["capability"]["verified"])

    def test_baseline_verified_requires_artifact(self):
        with self.assertRaisesRegex(ValueError, "baseline_verified requires baseline_artifact"):
            self.build(baseline_verified=True)

    def test_baseline_hash_requires_artifact(self):
        with self.assertRaisesRegex(ValueError, "requires baseline_artifact"):
            self.build(baseline_sha256="a" * 64)

    def test_non_boolean_capability_verified_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be booleans"):
            self.build(capability_verified="yes")

    def test_invalid_baseline_hash_fails(self):
        with self.assertRaisesRegex(ValueError, "64 hexadecimal"):
            self.build(baseline_artifact="baseline.mcaddon", baseline_sha256="xyz")

    def test_verified_baseline_is_explicitly_recorded(self):
        order = self.build(baseline_artifact="baseline.mcaddon", baseline_sha256="a" * 64, baseline_verified=True)
        self.assertEqual(order["project"]["baseline"], {
            "artifact": "baseline.mcaddon", "sha256": "a" * 64, "verified": True
        })

    def test_target_game_version_can_remain_unknown(self):
        self.assertIsNone(self.build()["project"]["target_game_version"])

    def test_missing_project_name_fails(self):
        with self.assertRaisesRegex(ValueError, "project_name"):
            self.build(project_name=" ")

    def test_missing_source_of_truth_fails(self):
        with self.assertRaisesRegex(ValueError, "source_of_truth"):
            self.build(source_of_truth=" ")

    def test_non_skills_only_registry_fails(self):
        self.registry["architecture"]["integration_model"] = "mcp"
        with self.assertRaisesRegex(ValueError, "Domain-Based Hybrid / Skills-only"):
            self.build()

    def test_missing_schema_fails_closed(self):
        (self.root / "skills/bedrock-engineer-core/references/domain-result.schema.json").unlink()
        with self.assertRaisesRegex(ValueError, "schemas must be present"):
            self.build()

    def test_output_refuses_to_overwrite_by_default(self):
        path = self.root / "work-order.json"
        path.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            planner._write_output(path, "replace", overwrite=False)
        self.assertEqual(path.read_text(encoding="utf-8"), "keep")

    def test_output_overwrite_is_explicit(self):
        path = self.root / "work-order.json"
        path.write_text("old", encoding="utf-8")
        planner._write_output(path, "new\n", overwrite=True)
        self.assertEqual(path.read_text(encoding="utf-8"), "new\n")

    def test_output_requires_existing_directory(self):
        path = self.root / "missing" / "work-order.json"
        with self.assertRaisesRegex(ValueError, "directory does not exist"):
            planner._write_output(path, "{}", overwrite=False)

    def test_cli_emits_json(self):
        result = subprocess.run([
            sys.executable, str(HERE / "plan_domain_work.py"),
            "--package-root", str(self.root), "--profile", "research_only",
            "--request", "Research the exact API", "--project-name", "Example",
            "--source-of-truth", "user request", "--language", "ru",
            "--target-game-version", "1.26.50",
        ], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["plan"]["selected_domains"], ["core", "compatibility"])

    def test_cli_lists_profiles_without_project_inputs(self):
        result = subprocess.run([
            sys.executable, str(HERE / "plan_domain_work.py"),
            "--package-root", str(self.root), "--list-profiles",
        ], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("new_addon", payload)
        self.assertIn("research_only", payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
