from __future__ import annotations
import importlib.util
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
import zipfile

SERVER_PATH = Path(__file__).resolve().parents[1] / "mcp_server.py"
spec = importlib.util.spec_from_file_location("mbe_mcp_server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(server)

ANALYZER_PATH = SERVER_PATH.parents[1] / "skills" / "automated-validation" / "scripts" / "bedrock_audit.py"
analyzer_spec = importlib.util.spec_from_file_location("mbe_bedrock_audit", ANALYZER_PATH)
analyzer = importlib.util.module_from_spec(analyzer_spec)
assert analyzer_spec and analyzer_spec.loader
analyzer_spec.loader.exec_module(analyzer)


class SchemaTests(unittest.TestCase):
    def test_nineteen_tools_and_closed_schemas(self):
        self.assertEqual(len(server.TOOLS), 19)
        for tool in server.TOOLS:
            schema = tool["inputSchema"]
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(schema["type"], "object")
            self.assertTrue(set(schema["required"]).issubset(schema["properties"]))
            self.assertEqual(tool["annotations"]["readOnlyHint"], tool["name"] not in {"create_addon_project", "create_addon_item", "create_addon_block", "create_addon_recipe", "create_addon_entity", "create_entity_with_mct"})
            self.assertFalse(tool["annotations"]["destructiveHint"])
        creator = server.TOOL_BY_NAME["create_addon_project"]
        self.assertFalse(creator["annotations"]["readOnlyHint"])
        self.assertFalse(creator["annotations"]["idempotentHint"])

    def test_create_addon_project_generates_linked_manifests_and_unique_uuids(self):
        from unittest.mock import patch
        import uuid as uuid_module
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_project", {
                    "project_directory": "example-addon",
                    "display_name": "Example Add-On",
                    "description": "A test starter project.",
                    "target_game_version": "1.26.50",
                })
            self.assertEqual(result["status"], "created")
            root = Path(result["project_directory"])
            bp = json.loads((root / "behavior_packs/example-addon_BP/manifest.json").read_text(encoding="utf-8"))
            rp = json.loads((root / "resource_packs/example-addon_RP/manifest.json").read_text(encoding="utf-8"))
            bp_uuid = bp["header"]["uuid"]
            bp_module_uuid = bp["modules"][0]["uuid"]
            rp_uuid = rp["header"]["uuid"]
            rp_module_uuid = rp["modules"][0]["uuid"]
            self.assertEqual(bp["dependencies"], [{"uuid": rp_uuid, "version": [1, 0, 0]}])
            self.assertEqual(bp["header"]["min_engine_version"], [1, 26, 50])
            self.assertEqual(rp["header"]["min_engine_version"], [1, 26, 50])
            ids = [bp_uuid, bp_module_uuid, rp_uuid, rp_module_uuid]
            self.assertEqual(len(ids), len(set(ids)))
            for value in ids:
                self.assertEqual(str(uuid_module.UUID(value)), value)
            self.assertTrue((root / "README.md").is_file())
            self.assertTrue((root / "PROJECT_STATE.md").is_file())
            self.assertEqual(result["features_generated"], [])
            self.assertEqual(result["runtime_status"], "NOT RUN")

    def test_create_addon_project_refuses_existing_destination_without_touching_it(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            existing = Path(td) / "my-addon"
            existing.mkdir()
            sentinel = existing / "keep.txt"
            sentinel.write_text("preserve me", encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_project", {
                    "project_directory": "my-addon",
                    "display_name": "Existing Add-On",
                    "description": "Do not overwrite this.",
                    "target_game_version": "1.26.50",
                })
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve me")
            self.assertEqual(list(existing.iterdir()), [sentinel])

    def test_create_addon_project_rejects_paths_and_bad_versions_before_writing(self):
        good = {"project_directory": "fresh-addon", "display_name": "Fresh Add-On", "description": "Starter.", "target_game_version": "1.26.50"}
        for unsafe in ("../escape", "folder/nested", "C:\\outside", ".", "..", "bad--slug", "UPPER"):
            with self.subTest(project_directory=unsafe):
                args = dict(good, project_directory=unsafe)
                with self.assertRaisesRegex(ValueError, "project_directory"):
                    server._validate_arguments("create_addon_project", args)
        for version in ("1.26", "1.26.50-preview", "v1.26.50", "1..50", "001.26.50"):
            with self.subTest(target_game_version=version):
                args = dict(good, target_game_version=version)
                with self.assertRaisesRegex(ValueError, "target_game_version"):
                    server._validate_arguments("create_addon_project", args)

    def test_create_addon_project_is_listed_as_write_capable(self):
        listing = server.handle_message({"jsonrpc": "2.0", "id": 9, "method": "tools/list", "params": {}})
        creator = next(tool for tool in listing["result"]["tools"] if tool["name"] == "create_addon_project")
        self.assertFalse(creator["annotations"]["readOnlyHint"])
        self.assertFalse(creator["annotations"]["idempotentHint"])
        self.assertIn("new", creator["description"].lower())

    def test_rejects_extra_argument(self):
        with self.assertRaisesRegex(ValueError, "unexpected argument"):
            server._validate_arguments("audit_pack", {"candidate_path": "x.mcaddon", "delete": True})

    def test_domain_enum_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "domain must be one of"):
            server._validate_arguments("get_resource_graph", {"archive_path": "x.mcaddon", "domain": "arbitrary"})

    def test_protocol_init_and_tools_list(self):
        init = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(init["result"]["serverInfo"]["version"], server.SERVER_VERSION)
        listing = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual({t["name"] for t in listing["result"]["tools"]}, set(server.TOOL_BY_NAME))



    def test_manifest_versions_sync_with_server(self):
        root = SERVER_PATH.parents[1]
        with (root / "plugin.json").open(encoding="utf-8") as f:
            manifest = json.load(f)
        with (root / ".codex-plugin" / "plugin.json").open(encoding="utf-8") as f:
            compat = json.load(f)
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(manifest["version"], version)
        self.assertEqual(compat["version"], version)
        self.assertEqual(server.SERVER_VERSION, version)
        self.assertEqual(analyzer.TOOL_VERSION, version)
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"# Minecraft Bedrock Engineer — {server.SERVER_VERSION}", readme)
        self.assertRegex(readme, rf"(?m)^## {re.escape(server.SERVER_VERSION)}:")
        prompts = manifest["extensions"]["com.openai"]["interface"]["defaultPrompt"]
        self.assertEqual(prompts, compat["interface"]["defaultPrompt"])
        self.assertEqual(len(prompts), 3)
        self.assertLessEqual(len(server.WORKFLOW_INSTRUCTIONS), 512)
        self.assertIn("inspect_archive", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("compare_baseline", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("create_addon_project", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("create_addon_item", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("create_addon_recipe", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("create_addon_entity", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("MCT CLI", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("Audit/reference tools are read-only", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("create_addon_recipe", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("diff_packs", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("search_mojang_samples", server.WORKFLOW_INSTRUCTIONS)

    def test_filter_graph_matches_actual_edge_schema_for_all_domains(self):
        graph = {
            "definitions": {
                "geometry": {"geometry.test": []},
                "animations": {"animation.test": []},
                "animation_controllers": {"controller.animation.test": []},
                "render_controllers": {"controller.render.test": []},
                "ui_files": {"RP/ui/test.json": []},
                "localization_keys": {"gui.test": []},
            },
            "edges": [
                {"source_file": "RP/entity/a.json", "source_pointer": "$/geometry/default", "reference_kind": "client_geometry", "referenced_value": "geometry.test", "target_domain": "geometry", "target_files": ["RP/models/a.geo.json"], "status": "resolved", "confidence": "HIGH"},
                {"source_file": "RP/entity/a.json", "source_pointer": "$/animations/idle", "reference_kind": "client_animations", "referenced_value": "animation.test", "target_domain": "animations", "target_files": ["RP/animations/a.json"], "status": "resolved", "confidence": "HIGH"},
                {"source_file": "RP/entity/a.json", "source_pointer": "$/animation_controllers/controller", "reference_kind": "client_animation_controllers", "referenced_value": "controller.animation.test", "target_domain": "animation_controllers", "target_files": ["RP/animation_controllers/a.json"], "status": "resolved", "confidence": "HIGH"},
                {"source_file": "RP/entity/a.json", "source_pointer": "$/render_controllers/0", "reference_kind": "client_render_controllers", "referenced_value": "controller.render.test", "target_domain": "render_controllers", "target_files": ["RP/render_controllers/a.json"], "status": "resolved", "confidence": "HIGH"},
                {"source_file": "RP/entity/a.json", "source_pointer": "$/textures/default", "reference_kind": "texture_path", "referenced_value": "textures/entity/test", "target_domain": "textures", "target_files": ["RP/textures/entity/test.png"], "status": "resolved", "confidence": "MEDIUM"},
                {"source_file": "RP/ui/test.json", "source_pointer": "$/texture", "reference_kind": "ui_resource_path", "referenced_value": "textures/ui/test", "target_domain": "ui_files", "target_files": ["RP/textures/ui/test.png"], "status": "resolved", "confidence": "MEDIUM"},
                {"source_file": "RP/texts/en_US.lang", "source_pointer": "line:4", "reference_kind": "possible_localization_key", "referenced_value": "gui.test", "target_domain": "localization_keys", "target_files": ["RP/texts/en_US.lang"], "status": "heuristic_unresolved", "confidence": "LOW"},
            ],
        }
        expected = {
            "geometry": {"geometry.test", "geometry.test"},
            "animations": {"animation.test"},
            "controllers": {"controller.animation.test", "controller.render.test"},
            "textures": {"textures/entity/test"},
            "ui": {"textures/ui/test", "textures/ui/geometry.test"},
            "localization": {"gui.test"},
        }
        # A UI value can contain the word "geometry" or look like a texture
        # path; explicit target_domain must keep it out of unrelated filters.
        graph["edges"].append({"source_file": "RP/ui/geometry_panel.json", "source_pointer": "$/texture", "reference_kind": "ui_resource_path", "referenced_value": "textures/ui/geometry.test", "target_domain": "ui_files", "target_files": ["RP/ui/geometry_panel.json"], "status": "resolved", "confidence": "MEDIUM"})
        for domain, values in expected.items():
            with self.subTest(domain=domain):
                result = server._filter_graph(graph, domain)
                actual_values = {str(edge["referenced_value"]) for edge in result["edges"]}
                self.assertEqual(actual_values, values, f"{domain}: {actual_values}")
                self.assertEqual(set(result["definitions"]), {
                    "geometry": {"geometry"},
                    "animations": {"animations"},
                    "controllers": {"animation_controllers", "render_controllers"},
                    "textures": set(),
                    "ui": {"ui_files"},
                    "localization": {"localization_keys"},
                }[domain])
                self.assertEqual(result["edge_count"], len(result["edges"]))
                self.assertEqual(sum(result["status_counts"].values()), len(result["edges"]))

    def test_filter_graph_does_not_use_heuristics_to_override_explicit_target_domain(self):
        graph = {"definitions": {}, "edges": [
            {"source_file": "RP/ui/geometry_panel.json", "source_pointer": "$/geometry", "reference_kind": "ui_resource_path", "referenced_value": "geometry.fake", "target_domain": "ui_files", "status": "resolved"},
            {"source_file": "RP/entity/test.json", "source_pointer": "$/whatever", "reference_kind": "custom_ref", "referenced_value": "geometry.real", "target_domain": "geometry", "status": "resolved"},
        ]}
        self.assertEqual([e["referenced_value"] for e in server._filter_graph(graph, "geometry")["edges"]], ["geometry.real"])
        self.assertEqual([e["referenced_value"] for e in server._filter_graph(graph, "ui")["edges"]], ["geometry.fake"])


    def test_filter_graph_all_returns_unfiltered_graph(self):
        graph = {"definitions": {"geometry": {}}, "edges": [], "edge_count": 0}
        self.assertIs(server._filter_graph(graph, "all"), graph)

    def test_loot_table_cycle_detection_handles_long_chains_without_recursion(self):
        count = 1005
        files = {}
        parsed = {}
        for index in range(count):
            path = f"BP/loot_tables/regression/{index:04d}.json"
            target = f"loot_tables/regression/{(index + 1) % count:04d}.json"
            value = {"pools": [{"rolls": 1, "entries": [{"type": "loot_table", "name": target}]}]}
            files[path] = json.dumps(value).encode("utf-8")
            parsed[path] = value
        findings = []
        graph = analyzer.audit_reference_graph(files, parsed, findings)
        self.assertEqual(graph["edge_count"], count)
        cycles = [f for f in findings if f["title"] == "Recursive loot-table reference cycle"]
        self.assertEqual(len(cycles), 1)


    def test_diff_pack_summary_detects_file_finding_and_reference_regressions(self):
        def edge(status, value="geometry.test", pointer="$/geometry/default"):
            return {"source_file": "RP/entity/test.json", "source_pointer": pointer, "reference_kind": "client_geometry", "referenced_value": value, "target_domain": "geometry", "status": status, "confidence": "HIGH" if status == "resolved" else "LOW"}
        baseline_report = {
            "tool_version": "0.8.0",
            "candidate": {"path": "baseline.mcaddon", "sha256": "a" * 64},
            "findings": [
                {"title": "Existing issue", "path": "RP/entity/old.json", "severity": "LOW", "confidence": "MEDIUM", "evidence": "old", "impact": "old", "recommendation": "review"},
                {"title": "Severity drift", "path": "RP/entity/test.json", "severity": "LOW", "confidence": "MEDIUM", "evidence": "old", "impact": "old", "recommendation": "review"},
            ],
            "reference_graph": {"edges": [edge("resolved")]}
        }
        comparison = {
            "tool_version": "0.8.0",
            "candidate": {"path": "candidate.mcaddon", "sha256": "b" * 64},
            "baseline": baseline_report["candidate"],
            "file_diff": {"added": ["RP/new.json"], "removed": ["RP/removed.json"], "modified": ["RP/entity/test.json"]},
            "findings": [
                {"title": "New issue", "path": "RP/new.json", "severity": "HIGH", "confidence": "HIGH", "evidence": "new", "impact": "impact", "recommendation": "fix"},
                {"title": "Severity drift", "path": "RP/entity/test.json", "severity": "MEDIUM", "confidence": "HIGH", "evidence": "current", "impact": "impact", "recommendation": "fix"},
                {"title": "File changed relative to baseline", "path": "RP/entity/test.json", "severity": "INFO", "confidence": "MEDIUM", "evidence": "content changed", "impact": "review", "recommendation": "review"},
                {"title": "Baseline: legacy warning", "path": "RP/legacy.json", "severity": "INFO", "confidence": "MEDIUM", "evidence": "baseline-only", "impact": "old", "recommendation": "old"},
            ],
            "reference_graph": {"edges": [edge("heuristic_unresolved"), edge("heuristic_unresolved", "geometry.new_missing", "$/geometry/alternate")]},
        }
        result = server._summarize_pack_diff(comparison, baseline_report)
        self.assertEqual(result["summary"]["files_added"], 1)
        self.assertEqual(result["summary"]["files_removed"], 1)
        self.assertEqual(result["summary"]["files_modified"], 1)
        self.assertEqual(result["summary"]["new_findings"], 1)
        self.assertEqual(result["summary"]["resolved_findings"], 1)
        self.assertEqual(result["summary"]["severity_escalations"], 1)
        self.assertEqual(result["summary"]["reference_regressions"], 1)
        self.assertEqual(result["summary"]["new_unresolved_references"], 1)
        self.assertEqual(result["recommendation"], "HOLD")
        self.assertTrue(result["read_only"])
        self.assertEqual(result["runtime_status"], "NOT RUN")

    def test_diff_pack_output_caps_samples(self):
        base = {"tool_version": "0.8.0", "candidate": {}, "findings": [], "reference_graph": {"edges": []}}
        comparison = {"tool_version": "0.8.0", "candidate": {}, "baseline": {}, "file_diff": {"added": [f"f-{i:03}.json" for i in range(130)], "removed": [], "modified": []}, "findings": [], "reference_graph": {"edges": []}}
        result = server._summarize_pack_diff(comparison, base)
        self.assertEqual(result["file_diff"]["added"]["count"], 130)
        self.assertEqual(len(result["file_diff"]["added"]["items"]), server._DIFF_SAMPLE_LIMIT)
        self.assertTrue(result["file_diff"]["added"]["truncated"])

    def test_diff_pack_duplicate_edges_are_matched_as_occurrences(self):
        def edge(status):
            return {"source_file": "RP/entity/test.json", "source_pointer": "$/geometry/default", "reference_kind": "client_geometry", "referenced_value": "geometry.test", "target_domain": "geometry", "status": status, "confidence": "LOW"}
        baseline = {"tool_version": "0.8.0", "candidate": {}, "findings": [], "reference_graph": {"edges": [edge("resolved"), edge("resolved"), edge("unresolved")]}}
        comparison = {"tool_version": "0.8.0", "candidate": {}, "baseline": {}, "file_diff": {"added": [], "removed": [], "modified": []}, "findings": [], "reference_graph": {"edges": [edge("unresolved"), edge("unresolved"), edge("unresolved")]}}
        result = server._summarize_pack_diff(comparison, baseline)
        self.assertEqual(result["summary"]["reference_regressions"], 2)
        self.assertEqual(result["summary"]["new_unresolved_references"], 0)

    def test_diff_pack_new_unresolved_reference_requires_review(self):
        baseline = {"tool_version": "0.8.0", "candidate": {}, "findings": [], "reference_graph": {"edges": []}}
        edge = {"source_file": "RP/entity/test.json", "source_pointer": "$/geometry/default", "reference_kind": "client_geometry", "referenced_value": "geometry.missing", "target_domain": "geometry", "status": "heuristic_unresolved", "confidence": "LOW"}
        comparison = {"tool_version": "0.8.0", "candidate": {}, "baseline": {}, "file_diff": {"added": [], "removed": [], "modified": []}, "findings": [], "reference_graph": {"edges": [edge]}}
        result = server._summarize_pack_diff(comparison, baseline)
        self.assertEqual(result["summary"]["new_unresolved_references"], 1)
        self.assertEqual(result["recommendation"], "REVIEW")

    def test_diff_pack_reports_severity_deescalations_in_summary(self):
        finding_old = {"title": "Known issue", "path": "RP/a.json", "severity": "HIGH", "confidence": "HIGH"}
        finding_new = {"title": "Known issue", "path": "RP/a.json", "severity": "LOW", "confidence": "HIGH"}
        baseline = {"tool_version": "0.8.0", "candidate": {}, "findings": [finding_old], "reference_graph": {"edges": []}}
        comparison = {"tool_version": "0.8.0", "candidate": {}, "baseline": {}, "file_diff": {"added": [], "removed": [], "modified": []}, "findings": [finding_new], "reference_graph": {"edges": []}}
        result = server._summarize_pack_diff(comparison, baseline)
        self.assertEqual(result["summary"]["severity_deescalations"], 1)
        self.assertEqual(result["finding_delta"]["severity_deescalations"]["count"], 1)

    def test_diff_pack_rejects_malformed_findings_and_overlapping_file_buckets(self):
        baseline = {"tool_version": "0.8.0", "candidate": {}, "findings": [], "reference_graph": {"edges": []}}
        base_comparison = {"tool_version": "0.8.0", "candidate": {}, "baseline": {}, "file_diff": {"added": [], "removed": [], "modified": []}, "findings": [], "reference_graph": {"edges": []}}
        malformed = {**base_comparison, "findings": [{"path": "RP/a.json", "severity": "HIGH"}]}
        with self.assertRaisesRegex(RuntimeError, "finding is missing"):
            server._summarize_pack_diff(malformed, baseline)
        overlapping = {**base_comparison, "file_diff": {"added": ["RP/a.json"], "removed": ["RP/a.json"], "modified": []}}
        with self.assertRaisesRegex(RuntimeError, "buckets overlap"):
            server._summarize_pack_diff(overlapping, baseline)
        invalid_severity = {**base_comparison, "findings": [{"title": "Issue", "path": "RP/a.json", "severity": "SEVERE"}]}
        with self.assertRaisesRegex(RuntimeError, "severity is invalid"):
            server._summarize_pack_diff(invalid_severity, baseline)


    def test_diff_pack_rejects_unsafe_file_diff_paths(self):
        base = {"tool_version": "0.8.1", "candidate": {}, "findings": [], "reference_graph": {"edges": []}}
        for unsafe_path in (
            "../outside.json", "RP/../outside.json", "/absolute.json", "C:/outside.json",
            "RP/./odd.json", "RP\\..\\outside.json", "RP/a.json\x00bad",
            "RP\\models\\a.json", "RP//models/a.json", "RP/models//a.json",
            "RP/models/", "RP/models/\tbad.json", "RP/models/line\nbreak.json",
        ):
            with self.subTest(path=unsafe_path):
                comparison = {"tool_version": "0.8.1", "candidate": {}, "baseline": {}, "file_diff": {"added": [unsafe_path], "removed": [], "modified": []}, "findings": [], "reference_graph": {"edges": []}}
                with self.assertRaisesRegex(RuntimeError, "invalid path|absolute path|traversal|non-canonical"):
                    server._summarize_pack_diff(comparison, base)

    def test_diff_pack_rejects_noncanonical_separator_aliases_before_overlap_checks(self):
        base = {"tool_version": "0.8.3", "candidate": {}, "findings": [], "reference_graph": {"edges": []}}
        aliases = {"added": ["RP/models/a.json"], "removed": ["RP\\models\\a.json"], "modified": []}
        comparison = {"tool_version": "0.8.3", "candidate": {}, "baseline": {}, "file_diff": aliases, "findings": [], "reference_graph": {"edges": []}}
        with self.assertRaisesRegex(RuntimeError, "non-canonical path separator"):
            server._summarize_pack_diff(comparison, base)

    def test_diff_pack_accepts_canonical_nested_relative_paths(self):
        base = {"tool_version": "0.8.3", "candidate": {}, "findings": [], "reference_graph": {"edges": []}}
        comparison = {"tool_version": "0.8.3", "candidate": {}, "baseline": {}, "file_diff": {"added": ["RP/models/entity/a.geo.json"], "removed": [], "modified": []}, "findings": [], "reference_graph": {"edges": []}}
        result = server._summarize_pack_diff(comparison, base)
        self.assertEqual(result["file_diff"]["added"]["items"], ["RP/models/entity/a.geo.json"])

    def test_diff_pack_verifies_baseline_artifact_hash_provenance(self):
        baseline_hash = "a" * 64
        candidate_hash = "b" * 64
        baseline = {"tool_version": "0.8.1", "candidate": {"path": "baseline.mcaddon", "sha256": baseline_hash}, "findings": [], "reference_graph": {"edges": []}}
        comparison = {"tool_version": "0.8.1", "candidate": {"path": "candidate.mcaddon", "sha256": candidate_hash}, "baseline": {"path": "baseline.mcaddon", "sha256": baseline_hash}, "file_diff": {"added": [], "removed": [], "modified": []}, "findings": [], "reference_graph": {"edges": []}}
        result = server._summarize_pack_diff(comparison, baseline)
        self.assertEqual(result["artifact_provenance"], {"status": "verified", "candidate_sha256": candidate_hash, "baseline_sha256": baseline_hash, "baseline_hash_match": True})

        mismatched = {**comparison, "baseline": {"path": "baseline.mcaddon", "sha256": "c" * 64}}
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            server._summarize_pack_diff(mismatched, baseline)

    def test_diff_pack_rejects_malformed_artifact_hashes(self):
        baseline = {"tool_version": "0.8.1", "candidate": {"sha256": "not-a-hash"}, "findings": [], "reference_graph": {"edges": []}}
        comparison = {"tool_version": "0.8.1", "candidate": {}, "baseline": {}, "file_diff": {"added": [], "removed": [], "modified": []}, "findings": [], "reference_graph": {"edges": []}}
        with self.assertRaisesRegex(RuntimeError, "SHA-256 is malformed"):
            server._summarize_pack_diff(comparison, baseline)


    def test_diff_pack_matches_exact_severity_before_pairing_duplicate_fingerprints(self):
        old_low = {"title": "Repeated issue", "path": "RP/a.json", "severity": "LOW", "confidence": "MEDIUM"}
        old_medium = {"title": "Repeated issue", "path": "RP/a.json", "severity": "MEDIUM", "confidence": "MEDIUM"}
        new_medium = {"title": "Repeated issue", "path": "RP/a.json", "severity": "MEDIUM", "confidence": "HIGH"}
        new_high = {"title": "Repeated issue", "path": "RP/a.json", "severity": "HIGH", "confidence": "HIGH"}
        baseline = {"tool_version": "0.8.2", "candidate": {}, "findings": [old_low, old_medium], "reference_graph": {"edges": []}}
        comparison = {"tool_version": "0.8.2", "candidate": {}, "baseline": {}, "file_diff": {"added": [], "removed": [], "modified": []}, "findings": [new_medium, new_high], "reference_graph": {"edges": []}}
        result = server._summarize_pack_diff(comparison, baseline)
        self.assertEqual(result["summary"]["severity_escalations"], 1)
        self.assertEqual(result["summary"]["severity_deescalations"], 0)
        self.assertEqual(result["summary"]["new_findings"], 0)
        self.assertEqual(result["summary"]["resolved_findings"], 0)
        self.assertEqual(result["finding_delta"]["severity_escalations"]["items"][0]["baseline"], "LOW")
        self.assertEqual(result["finding_delta"]["severity_escalations"]["items"][0]["candidate"], "HIGH")

    def test_diff_pack_pairs_closest_duplicate_severity_when_counts_differ(self):
        old_low = {"title": "Repeated issue", "path": "RP/a.json", "severity": "LOW"}
        old_blocker = {"title": "Repeated issue", "path": "RP/a.json", "severity": "BLOCKER"}
        new_high = {"title": "Repeated issue", "path": "RP/a.json", "severity": "HIGH"}
        baseline = {"tool_version": "0.8.2", "candidate": {}, "findings": [old_low, old_blocker], "reference_graph": {"edges": []}}
        comparison = {"tool_version": "0.8.2", "candidate": {}, "baseline": {}, "file_diff": {"added": [], "removed": [], "modified": []}, "findings": [new_high], "reference_graph": {"edges": []}}
        result = server._summarize_pack_diff(comparison, baseline)
        self.assertEqual(result["summary"]["severity_deescalations"], 1)
        self.assertEqual(result["finding_delta"]["severity_deescalations"]["items"][0]["baseline"], "BLOCKER")
        self.assertEqual(result["finding_delta"]["severity_deescalations"]["items"][0]["candidate"], "HIGH")
        self.assertEqual(result["summary"]["resolved_findings"], 1)
        self.assertEqual(result["finding_delta"]["no_longer_reported"]["items"][0]["severity"], "LOW")

    def test_diff_packs_runs_read_only_against_archives(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline = root / "baseline.mcaddon"
            candidate = root / "candidate.mcaddon"
            with zipfile.ZipFile(baseline, "w") as archive:
                archive.writestr("BP/one.txt", "old")
                archive.writestr("BP/stable.txt", "same")
            with zipfile.ZipFile(candidate, "w") as archive:
                archive.writestr("BP/one.txt", "new")
                archive.writestr("BP/stable.txt", "same")
                archive.writestr("RP/added.txt", "new file")
            before = {p.name: p.read_bytes() for p in (baseline, candidate)}
            old = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
            os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = td
            try:
                result = server.call_tool("diff_packs", {"candidate_path": "candidate.mcaddon", "baseline_path": "baseline.mcaddon"})
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["summary"]["files_added"], 1)
                self.assertEqual(result["summary"]["files_modified"], 1)
                self.assertEqual(result["runtime_status"], "NOT RUN")
                self.assertTrue(result["read_only"])
                self.assertEqual(before, {p.name: p.read_bytes() for p in (baseline, candidate)})
            finally:
                if old is None:
                    os.environ.pop("MINECRAFT_BEDROCK_WORKSPACE", None)
                else:
                    os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = old

    def test_archive_safety_rejects_cumulative_uncompressed_limit(self):
        from unittest.mock import patch
        from archive_safety import MAX_MEMBER_BYTES, validate_zip_limits
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "fixture.zip"
            archive.write_bytes(b"PK\x03\x04placeholder")
            class FakeInfo:
                filename = "payload.bin"
                file_size = MAX_MEMBER_BYTES
                def is_dir(self): return False
            class FakeZip:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def infolist(self): return [FakeInfo() for _ in range(5)]
            with patch("archive_safety.zipfile.is_zipfile", return_value=True), patch("archive_safety.zipfile.ZipFile", return_value=FakeZip()):
                with self.assertRaisesRegex(ValueError, "cumulative|uncompressed bytes"):
                    validate_zip_limits(archive)

    def test_analyzer_cli_loader_checks_limits_before_hashing(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "fixture.mcaddon"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("small.txt", "fixture")
            findings = []
            with patch.object(analyzer, "validate_zip_limits", side_effect=ValueError("test archive limit")), patch.object(analyzer, "sha256_file", side_effect=AssertionError("must not hash before limits")):
                files, meta = analyzer.load_archive(str(archive), findings)
            self.assertEqual(files, {})
            self.assertFalse(meta["archive_valid"])
            self.assertIsNone(meta["sha256"])
            self.assertTrue(any(f["title"] == "Archive cannot be opened safely" for f in findings))

    def test_initialize_tools_call_error_and_path_guard_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "fixture.mcaddon"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("BP/manifest.json", "{}")
            old = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
            os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = td
            try:
                init = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
                tools = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
                call = server.handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "inspect_archive", "arguments": {"archive_path": "fixture.mcaddon"}}})
                bad = server.handle_message({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "inspect_archive", "arguments": {"archive_path": str(root.parent / "outside.mcaddon")}}})
                self.assertEqual(init["result"]["serverInfo"]["version"], server.SERVER_VERSION)
                self.assertEqual(len(tools["result"]["tools"]), 19)
                self.assertEqual(call["result"]["structuredContent"]["status"], "completed")
                self.assertTrue(bad["result"]["isError"])
                self.assertEqual(bad["result"]["structuredContent"]["status"], "error")
            finally:
                if old is None:
                    os.environ.pop("MINECRAFT_BEDROCK_WORKSPACE", None)
                else:
                    os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = old

    def test_timeout_is_reported_as_structured_error(self):
        from unittest.mock import patch
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "fixture.mcaddon"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("BP/manifest.json", "{}")
            old = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
            os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = td
            try:
                with patch.object(server.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="audit", timeout=120)):
                    result = server.call_tool("audit_pack", {"candidate_path": "fixture.mcaddon"})
                self.assertEqual(result["error"]["code"], "TIMEOUT")
            finally:
                if old is None:
                    os.environ.pop("MINECRAFT_BEDROCK_WORKSPACE", None)
                else:
                    os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = old

    def test_tool_call_errors_are_structured(self):
        result = server.call_tool("audit_pack", {"candidate_path": "x.mcaddon", "delete": True})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")

    def test_archive_member_count_limit(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "fixture.mcaddon"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("small.txt", "fixture")
            class FakeInfo:
                filename = "small.txt"
                file_size = 1
                def is_dir(self): return False
            class FakeZip:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def infolist(self): return [FakeInfo()] * (server.MAX_ARCHIVE_MEMBERS + 1)
            old = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
            os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = td
            try:
                with patch.object(server.zipfile, "ZipFile", return_value=FakeZip()):
                    with self.assertRaisesRegex(ValueError, "member count"):
                        server._resolve_archive("fixture.mcaddon")
            finally:
                if old is None:
                    os.environ.pop("MINECRAFT_BEDROCK_WORKSPACE", None)
                else:
                    os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = old

    def test_rejects_declared_oversized_archive_without_extracting(self):
        from unittest.mock import patch
        from archive_safety import MAX_MEMBER_BYTES, validate_zip_limits
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "fixture.mcaddon"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("small.txt", "fixture")
            class FakeInfo:
                filename = "payload.bin"
                file_size = MAX_MEMBER_BYTES + 1
                def is_dir(self): return False
            class FakeZip:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def infolist(self): return [FakeInfo()]
            with patch("archive_safety.zipfile.is_zipfile", return_value=True), patch("archive_safety.zipfile.ZipFile", return_value=FakeZip()):
                with self.assertRaisesRegex(ValueError, "per-member limit"):
                    validate_zip_limits(archive)

    def test_archive_limits_are_shared_with_analyzer(self):
        from archive_safety import MAX_ARCHIVE_BYTES, MAX_ARCHIVE_MEMBERS, MAX_MEMBER_BYTES, MAX_UNCOMPRESSED_BYTES
        analyzer_path = SERVER_PATH.parents[1] / "skills" / "automated-validation" / "scripts" / "bedrock_audit.py"
        source = analyzer_path.read_text(encoding="utf-8")
        self.assertIn("from archive_safety import", source)
        self.assertIn("validate_zip_limits", source)
        self.assertEqual(MAX_ARCHIVE_BYTES, 256 * 1024 * 1024)
        self.assertEqual(MAX_UNCOMPRESSED_BYTES, 512 * 1024 * 1024)
        self.assertEqual(MAX_ARCHIVE_MEMBERS, 50_000)
        self.assertEqual(MAX_MEMBER_BYTES, 128 * 1024 * 1024)

    def test_workspace_path_and_archive_inspection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "fixture.mcaddon"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("BP/manifest.json", "{}")
                zf.writestr("RP/entity/test.json", "{}")
                zf.writestr("../escape.json", "{}")
            old = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
            os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = td
            try:
                report = server.call_tool("inspect_archive", {"archive_path": "fixture.mcaddon"})
                self.assertEqual(report["status"], "completed")
                self.assertIn("../escape.json", report["unsafe_paths"])
                self.assertFalse(report["payloads_read"])
                bad = server.call_tool("inspect_archive", {"archive_path": str(Path(td).parent / "outside.mcaddon" )})
                self.assertEqual(bad["status"], "error")
            finally:
                if old is None:
                    os.environ.pop("MINECRAFT_BEDROCK_WORKSPACE", None)
                else:
                    os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = old



    def test_mojang_sample_search_finds_exact_identifier_and_domain_example(self):
        item_result = server.call_tool("search_mojang_samples", {
            "query": "minecraft:apple", "category": "item", "limit": 5
        })
        self.assertEqual(item_result["status"], "completed")
        self.assertEqual(item_result["target_version"], "1.26.50.4")
        self.assertTrue(any(row["path"] == "behavior_pack/items/apple.json" for row in item_result["results"]))
        self.assertEqual(item_result["source_archive_sha256"], "c0b6151f5f9a0c31ebe3c909dfc82d97f12473ed2c6e039aa7e22d667042026c")

        geometry_result = server.call_tool("search_mojang_samples", {
            "query": "geometry goat", "category": "geometry", "limit": 3
        })
        self.assertEqual(geometry_result["status"], "completed")
        self.assertEqual(geometry_result["results"][0]["path"], "resource_pack/models/entity/goat.geo.json")
        self.assertIsNotNone(geometry_result["results"][0]["bundled_reference"])


    def test_bundled_full_mojang_index_is_loaded_by_mcp_search(self):
        if not server.MOJANG_SAMPLE_INDEX.is_file():
            self.skipTest("full Mojang index is absent from a minimal source checkout")
        payload = server._load_mojang_sample_index()
        self.assertEqual(payload.get("index_mode"), "full_index")
        self.assertEqual(payload.get("target_version"), "1.26.50.4")
        self.assertEqual(len(payload["entries"]), 22252)

        result = server.call_tool("search_mojang_samples", {
            "query": "minecraft:apple", "category": "item", "limit": 5
        })
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["index_mode"], "full_index")
        self.assertTrue(any(row["path"] == "behavior_pack/items/apple.json" for row in result["results"]))

    def test_mojang_sample_search_uses_explicit_curated_fallback_without_full_index(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            missing_index = Path(td) / "not-packaged.json.gz"
            with patch.object(server, "MOJANG_SAMPLE_INDEX", missing_index):
                result = server.call_tool("search_mojang_samples", {
                    "query": "minecraft:apple", "category": "item", "limit": 5
                })
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["index_mode"], "curated_fallback")
        self.assertFalse(result["index_stats"]["full_index_available"])
        self.assertGreaterEqual(result["index_stats"]["curated_fallback_entry_count"], 1)
        self.assertEqual(result["source_archive_sha256"], "c0b6151f5f9a0c31ebe3c909dfc82d97f12473ed2c6e039aa7e22d667042026c")
        self.assertTrue(any(row["path"] == "behavior_pack/items/apple.json" for row in result["results"]))

    def test_mojang_sample_search_has_bounded_results_and_defaults(self):
        result = server.call_tool("search_mojang_samples", {"query": "texture"})
        self.assertEqual(result["status"], "completed")
        self.assertGreater(len(result["results"]), 0)
        self.assertLessEqual(len(result["results"]), 10)
        self.assertEqual(result["truncated"], result["total_matches"] > 10)
        self.assertIn(result["index_mode"], {"full_index", "curated_fallback"})
        self.assertEqual(result["category"], "all")

    def test_mojang_sample_search_rejects_invalid_category_limit_and_blank_query(self):
        with self.assertRaisesRegex(ValueError, "category must be one of"):
            server._validate_arguments("search_mojang_samples", {"query": "item", "category": "made_up"})
        with self.assertRaisesRegex(ValueError, "limit must be between"):
            server._validate_arguments("search_mojang_samples", {"query": "item", "limit": 21})
        with self.assertRaisesRegex(ValueError, "limit must be an integer"):
            server._validate_arguments("search_mojang_samples", {"query": "item", "limit": True})
        with self.assertRaisesRegex(ValueError, "query must contain"):
            server._validate_arguments("search_mojang_samples", {"query": "   "})

    def test_read_mojang_sample_returns_bundled_example_and_verified_hash(self):
        result = server.call_tool("read_mojang_sample", {"sample_path": "behavior_pack/items/apple.json"})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["source"], "bundled_curated_sample")
        self.assertTrue(result["content_hash_matches_index"])
        self.assertIn('"minecraft:item"', result["content_excerpt"])
        self.assertEqual(result["sample_path"], "behavior_pack/items/apple.json")

    def test_read_mojang_sample_refuses_unsafe_or_unindexed_path(self):
        bad = server.call_tool("read_mojang_sample", {"sample_path": "../escape.json"})
        self.assertEqual(bad["status"], "error")
        self.assertEqual(bad["error"]["code"], "INVALID_ARGUMENT")
        unknown = server.call_tool("read_mojang_sample", {"sample_path": "behavior_pack/not-real.json"})
        self.assertEqual(unknown["status"], "error")
        self.assertIn("not present", unknown["error"]["message"])

    def test_read_mojang_sample_can_read_one_indexed_file_from_workspace_archive(self):
        from unittest.mock import patch
        import gzip
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "source.zip"
            sample_bytes = b'{"format_version":"1.26.30","minecraft:item":{"description":{"identifier":"demo:thing"}}}\n'
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("behavior_pack/items/example.json", sample_bytes)
            index_path = root / "index.json.gz"
            payload = {
                "target_version": "1.26.50.4", "archive_sha256": __import__("hashlib").sha256(archive.read_bytes()).hexdigest(),
                "entries": [{"path": "behavior_pack/items/example.json", "category": "item",
                             "size_bytes": len(sample_bytes), "sha256": __import__("hashlib").sha256(sample_bytes).hexdigest(),
                             "identifiers": ["demo:thing"], "json_parsed": True}]
            }
            with gzip.open(index_path, "wt", encoding="utf-8") as out:
                json.dump(payload, out)
            with patch.object(server, "MOJANG_SAMPLE_INDEX", index_path), patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("read_mojang_sample", {
                    "sample_path": "behavior_pack/items/example.json", "archive_path": "source.zip"
                })
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["source"], "user_supplied_archive")
            self.assertTrue(result["content_hash_matches_index"])
            self.assertIn("demo:thing", result["content_excerpt"])




    def test_read_mojang_sample_rejects_archive_with_wrong_source_digest(self):
        from unittest.mock import patch
        import gzip
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "source.zip"
            sample_bytes = b'{"minecraft:item":{"description":{"identifier":"demo:thing"}}}\n'
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("behavior_pack/items/example.json", sample_bytes)
            index_path = root / "index.json.gz"
            payload = {
                "target_version": "1.26.50.4",
                "archive_sha256": "a" * 64,
                "entries": [{"path": "behavior_pack/items/example.json", "category": "item",
                             "size_bytes": len(sample_bytes), "sha256": __import__("hashlib").sha256(sample_bytes).hexdigest(),
                             "identifiers": ["demo:thing"], "json_parsed": True}],
            }
            with gzip.open(index_path, "wt", encoding="utf-8") as out:
                json.dump(payload, out)
            with patch.object(server, "MOJANG_SAMPLE_INDEX", index_path), patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("read_mojang_sample", {
                    "sample_path": "behavior_pack/items/example.json", "archive_path": "source.zip"
                })
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["code"], "SAMPLE_ARCHIVE_VERSION_MISMATCH")
            self.assertEqual(result["error"]["details"]["expected_archive_sha256"], "a" * 64)
            self.assertNotEqual(result["error"]["details"]["actual_archive_sha256"], "a" * 64)


class CreatorToolsIntegrationTests(unittest.TestCase):
    def _scaffold(self, workspace: Path):
        from unittest.mock import patch
        with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(workspace)}):
            result = server.call_tool("create_addon_project", {
                "project_directory": "test-addon", "display_name": "Test Add-on",
                "description": "MCT integration regression fixture.", "target_game_version": "1.26.50"
            })
        self.assertEqual(result["status"], "created")
        return workspace / "test-addon"

    def test_mct_status_and_catalog_do_not_install_when_cli_is_missing(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}), patch.object(server.shutil, "which", return_value=None):
            status = server.call_tool("creator_tools_status", {})
            catalog = server.call_tool("creator_tools_catalog", {})
        self.assertEqual(status["status"], "mct_not_installed")
        self.assertFalse(status["automatic_install_performed"])
        self.assertFalse(status["npx_used"])
        self.assertEqual(set(status["tools"]), {"node", "npm", "mct"})
        self.assertEqual(catalog["status"], "not_available")
        self.assertFalse(catalog["automatic_install_performed"])

    def test_mct_handoff_requires_a_safe_template_id_and_entity_slug(self):
        base = {"project_directory": "test-addon", "template_id": "cow", "entity_slug": "swamp_golem"}
        for field, value in (("template_id", "../cow"), ("template_id", "cow;whoami"), ("entity_slug", "../escape"), ("entity_slug", "UPPER_CASE")):
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, "template_id|entity_slug"):
                    server._validate_arguments("create_entity_with_mct", dict(base, **{field: value}))

    def test_mct_handoff_without_cli_leaves_original_project_untouched(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            project = self._scaffold(Path(td))
            sentinel = project / "README.md"
            original = sentinel.read_bytes()
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}), patch.object(server.shutil, "which", return_value=None):
                result = server.call_tool("create_entity_with_mct", {
                    "project_directory": "test-addon", "template_id": "cow", "entity_slug": "swamp_golem"
                })
            self.assertEqual(result["status"], "not_available")
            self.assertFalse(result["writes_applied"])
            self.assertEqual(sentinel.read_bytes(), original)
            self.assertFalse((project / "behavior_packs/test-addon_BP/entities/swamp_golem.json").exists())

    def test_mct_staged_handoff_merges_only_new_files_after_clean_diff(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            project = self._scaffold(Path(td))
            original_manifest = (project / "behavior_packs/test-addon_BP/manifest.json").read_bytes()
            catalog = {"status": "completed", "catalog": {"galleryTemplates": [{"id": "swamp_golem", "type": 4}]}}
            fake_diff = {
                "recommendation": "REVIEW",
                "summary": {"files_added": 2, "new_findings": 0, "reference_regressions": 0},
                "finding_delta": {"new": {"items": []}, "severity_escalations": {"items": []}},
                "reference_delta": {"new_unresolved": {"items": []}, "resolved_to_unresolved": {"items": []}},
            }
            invoked = {}

            def fake_mct_command(command, cwd, timeout=60):
                invoked["command"] = command
                staged = Path(cwd)
                (staged / "behavior_packs/test-addon_BP/entities/swamp_golem.json").write_text(json.dumps({
                    "format_version": "1.20.50",
                    "minecraft:entity": {
                        "description": {"identifier": "test_addon:swamp_golem", "is_spawnable": True, "is_summonable": True},
                        "components": {"minecraft:health": {"value": 20, "max": 20}, "minecraft:physics": {}},
                    },
                }) + "\n", encoding="utf-8")
                (staged / "resource_packs/test-addon_RP/entity/swamp_golem.entity.json").write_text(json.dumps({
                    "format_version": "1.10.0",
                    "minecraft:client_entity": {"description": {"identifier": "test_addon:swamp_golem"}},
                }) + "\n", encoding="utf-8")
                return {"exit_code": 0, "timed_out": False, "stdout": "ok", "stderr": ""}

            with (
                patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}),
                patch.object(server.shutil, "which", return_value="/usr/bin/mct"),
                patch.object(server, "_creator_tools_catalog", return_value=catalog),
                patch.object(server, "_mct_command", side_effect=fake_mct_command),
                patch.object(server, "_run_audit", return_value={"synthetic": True}),
                patch.object(server, "_summarize_pack_diff", return_value=fake_diff),
            ):
                result = server.call_tool("create_entity_with_mct", {
                    "project_directory": "test-addon", "template_id": "swamp_golem", "entity_slug": "swamp_golem"
                })

            self.assertEqual(result["status"], "created")
            self.assertEqual(len(result["files_created"]), 2)
            self.assertEqual(result["audit"]["recommendation"], "REVIEW")
            self.assertEqual((project / "behavior_packs/test-addon_BP/manifest.json").read_bytes(), original_manifest)
            self.assertTrue((project / "behavior_packs/test-addon_BP/entities/swamp_golem.json").is_file())
            self.assertTrue((project / "resource_packs/test-addon_RP/entity/swamp_golem.entity.json").is_file())
            command = invoked["command"]
            self.assertEqual(command[1:4], ["add", "swamp_golem", "swamp_golem"])
            for flag in ("--offline", "--isolated", "--yes", "--single", "--json"):
                self.assertIn(flag, command)
            self.assertNotIn("npx", command)

    def test_mct_tools_have_closed_schemas_and_explicit_write_annotations(self):
        for name in ("creator_tools_status", "creator_tools_catalog", "validate_with_mct", "create_entity_with_mct"):
            self.assertFalse(server.TOOL_BY_NAME[name]["inputSchema"]["additionalProperties"])
        self.assertTrue(server.TOOL_BY_NAME["creator_tools_status"]["annotations"]["readOnlyHint"])
        self.assertTrue(server.TOOL_BY_NAME["creator_tools_catalog"]["annotations"]["openWorldHint"])
        self.assertTrue(server.TOOL_BY_NAME["validate_with_mct"]["annotations"]["readOnlyHint"])
        self.assertFalse(server.TOOL_BY_NAME["create_entity_with_mct"]["annotations"]["readOnlyHint"])
        self.assertFalse(server.TOOL_BY_NAME["create_entity_with_mct"]["annotations"]["destructiveHint"])
        self.assertTrue(server.TOOL_BY_NAME["create_entity_with_mct"]["annotations"]["openWorldHint"])


class CreateAddonEntityTests(unittest.TestCase):
    def _scaffold(self, workspace: Path):
        from unittest.mock import patch
        with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(workspace)}):
            result = server.call_tool("create_addon_project", {
                "project_directory": "test-addon", "display_name": "Test Add-on",
                "description": "Test scaffold for entity creation.", "target_game_version": "1.26.50"
            })
        self.assertEqual(result["status"], "created")
        return workspace / "test-addon"

    def test_creates_linked_entity_client_geometry_and_controller_without_fake_texture(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            project = self._scaffold(Path(td))
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_entity", {
                    "project_directory": "test-addon", "entity_name": "Forest Golem",
                    "entity_slug": "forest_golem", "target_game_version": "1.26.50"
                })
            self.assertEqual(result["status"], "created")
            self.assertEqual(result["entity_identifier"], "test_addon:forest_golem")
            self.assertEqual(result["geometry_identifier"], "geometry.test_addon.forest_golem")
            self.assertEqual(len(result["files_created"]), 4)
            bp = json.loads((project / "behavior_packs/test-addon_BP/entities/forest_golem.json").read_text(encoding="utf-8"))
            client = json.loads((project / "resource_packs/test-addon_RP/entity/forest_golem.entity.json").read_text(encoding="utf-8"))
            geo = json.loads((project / "resource_packs/test-addon_RP/models/entity/forest_golem.geo.json").read_text(encoding="utf-8"))
            controller = json.loads((project / "resource_packs/test-addon_RP/render_controllers/forest_golem.render_controllers.json").read_text(encoding="utf-8"))
            self.assertEqual(bp["minecraft:entity"]["description"]["identifier"], client["minecraft:client_entity"]["description"]["identifier"])
            self.assertEqual(client["minecraft:client_entity"]["description"]["geometry"]["default"], geo["minecraft:geometry"][0]["description"]["identifier"])
            self.assertIn(result["render_controller_identifier"], controller["render_controllers"])
            self.assertEqual(client["minecraft:client_entity"]["description"]["textures"]["default"], "textures/entity/forest_golem")
            self.assertEqual(result["texture_status"], "texture_file_not_created")
            self.assertFalse((project / "resource_packs/test-addon_RP/textures/entity/forest_golem.png").exists())
            self.assertEqual(result["runtime_status"], "NOT RUN")

    def test_accepts_existing_png_texture_and_maps_its_resource_path(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            project = self._scaffold(Path(td))
            texture = project / "resource_packs/test-addon_RP/textures/entity/bosses/forest_golem.png"
            texture.parent.mkdir(parents=True)
            texture.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fixture")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_entity", {
                    "project_directory": "test-addon", "entity_name": "Forest Golem",
                    "entity_slug": "forest_golem", "texture_path": "resource_packs/test-addon_RP/textures/entity/bosses/forest_golem.png",
                    "target_game_version": "1.26.50"
                })
            self.assertEqual(result["texture_status"], "mapped_existing_png")
            self.assertEqual(result["texture_reference"], "textures/entity/bosses/forest_golem")
            self.assertEqual(result["runtime_status"], "NOT RUN")

    def test_collision_refuses_entity_set_without_creating_partial_outputs(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            project = self._scaffold(Path(td))
            existing = project / "resource_packs/test-addon_RP/models/entity/forest_golem.geo.json"
            existing.write_text('{"keep":true}\n', encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_entity", {
                    "project_directory": "test-addon", "entity_name": "Forest Golem",
                    "entity_slug": "forest_golem", "target_game_version": "1.26.50"
                })
            self.assertEqual(result["status"], "error")
            self.assertIn("refusing to overwrite", result["error"]["message"])
            self.assertEqual(json.loads(existing.read_text(encoding="utf-8")), {"keep": True})
            self.assertFalse((project / "behavior_packs/test-addon_BP/entities/forest_golem.json").exists())
            self.assertFalse((project / "resource_packs/test-addon_RP/entity/forest_golem.entity.json").exists())

    def test_invalid_png_or_unsafe_path_is_rejected_before_writing(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            project = self._scaffold(Path(td))
            texture = project / "resource_packs/test-addon_RP/textures/entity/forest_golem.png"
            texture.write_bytes(b"not a png")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_entity", {
                    "project_directory": "test-addon", "entity_name": "Forest Golem",
                    "entity_slug": "forest_golem", "texture_path": "resource_packs/test-addon_RP/textures/entity/forest_golem.png",
                    "target_game_version": "1.26.50"
                })
            self.assertEqual(result["status"], "error")
            self.assertIn("PNG signature", result["error"]["message"])
            self.assertFalse((project / "behavior_packs/test-addon_BP/entities/forest_golem.json").exists())
        base = {"project_directory":"test-addon","entity_name":"Forest Golem","entity_slug":"forest_golem","target_game_version":"1.26.50"}
        for bad in ("../outside.png", "/tmp/a.png", "C:/outside.png", "resource_packs\\test-addon_RP/textures/entity/x.png", "resource_packs/test-addon_RP/textures/entity/../x.png"):
            with self.subTest(texture_path=bad):
                with self.assertRaisesRegex(ValueError, "texture_path"):
                    server._validate_arguments("create_addon_entity", dict(base, texture_path=bad))

    def test_entity_tool_is_write_capable_and_schema_closed(self):
        tool=server.TOOL_BY_NAME["create_addon_entity"]
        self.assertFalse(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["annotations"]["destructiveHint"])
        self.assertFalse(tool["annotations"]["idempotentHint"])
        self.assertFalse(tool["inputSchema"]["additionalProperties"])


class CreateAddonItemTests(unittest.TestCase):
    def _scaffold(self, workspace: Path):
        from unittest.mock import patch
        with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(workspace)}):
            result = server.call_tool("create_addon_project", {
                "project_directory": "test-addon", "display_name": "Test Add-on",
                "description": "Test scaffold for item creation.", "target_game_version": "1.26.50"
            })
        self.assertEqual(result["status"], "created")
        return workspace / "test-addon"

    def test_creates_item_definition_lang_and_atlas_without_fake_texture(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            project = self._scaffold(workspace)
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_item", {
                    "project_directory":"test-addon", "item_name":"Ruby Shard", "item_slug":"ruby_shard", "target_game_version":"1.26.50"
                })
            self.assertEqual(result["status"], "created")
            bp_item = project / "behavior_packs/test-addon_BP/items/ruby_shard.json"
            item = json.loads(bp_item.read_text(encoding="utf-8"))
            self.assertEqual(item["minecraft:item"]["description"]["identifier"], "test_addon:ruby_shard")
            self.assertEqual(item["minecraft:item"]["components"]["minecraft:icon"]["textures"]["default"], "ruby_shard")
            lang = project / "resource_packs/test-addon_RP/texts/en_US.lang"
            self.assertEqual(lang.read_text(encoding="utf-8"), "item.ruby_shard.name=Ruby Shard\n")
            atlas = json.loads((project / "resource_packs/test-addon_RP/textures/item_texture.json").read_text(encoding="utf-8"))
            self.assertEqual(atlas["texture_data"]["ruby_shard"]["textures"], "textures/items/ruby_shard")
            self.assertFalse((project / "resource_packs/test-addon_RP/textures/items/ruby_shard.png").exists())
            self.assertEqual(result["texture_status"], "texture_file_not_created")
            self.assertEqual(result["runtime_status"], "NOT RUN")

    def test_accepts_existing_png_at_expected_path_and_reports_it_mapped(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            texture=project/"resource_packs/test-addon_RP/textures/items/ruby_shard.png"
            texture.parent.mkdir(parents=True,exist_ok=True)
            texture.write_bytes(b"\x89PNG\r\n\x1a\n"+b"fixture-payload")
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                result=server.call_tool("create_addon_item", {"project_directory":"test-addon","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50","texture_path":"resource_packs/test-addon_RP/textures/items/ruby_shard.png"})
            self.assertEqual(result["status"],"created")
            self.assertEqual(result["texture_status"],"mapped_existing_png")
            self.assertTrue(texture.is_file())

    def test_rejects_duplicate_item_files_without_overwrite(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            existing=project / "behavior_packs/test-addon_BP/items/ruby_shard.json"
            existing.write_text('{"keep":true}\n', encoding="utf-8")
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                result=server.call_tool("create_addon_item", {"project_directory":"test-addon","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50"})
            self.assertEqual(result["status"],"error")
            self.assertIn("refusing to overwrite",result["error"]["message"])
            self.assertEqual(existing.read_text(encoding="utf-8"),'{"keep":true}\n')
            self.assertFalse((project / "resource_packs/test-addon_RP/textures/item_texture.json").exists())

    def test_rejects_non_scaffold_and_unsafe_texture_path(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); (workspace/"empty").mkdir()
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                result=server.call_tool("create_addon_item", {"project_directory":"empty","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50"})
            self.assertEqual(result["status"],"error")
            self.assertIn("scaffold",result["error"]["message"])
            base={"project_directory":"test-addon","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50"}
            for bad in ("../outside.png", "/tmp/a.png", "C:/a.png", "resource_packs\\\\test-addon_RP/textures/items/ruby_shard.png", "resource_packs/test-addon_RP/textures/items/../ruby_shard.png"):
                with self.subTest(texture_path=bad):
                    with self.assertRaisesRegex(ValueError,"texture_path"):
                        server._validate_arguments("create_addon_item",dict(base,texture_path=bad))

    def test_existing_lang_or_atlas_requires_merge_instead_of_overwrite(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            atlas=project/"resource_packs/test-addon_RP/textures/item_texture.json"
            atlas.parent.mkdir(parents=True,exist_ok=True)
            atlas.write_text('{"texture_data":[]}\n',encoding="utf-8")
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                result=server.call_tool("create_addon_item", {"project_directory":"test-addon","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50"})
            self.assertEqual(result["status"],"error")
            self.assertIn("must contain an object texture_data", result["error"]["message"])
            self.assertEqual(atlas.read_text(encoding="utf-8"), '{"texture_data":[]}\n')
            self.assertFalse((project/"behavior_packs/test-addon_BP/items/ruby_shard.json").exists())

    def test_rejects_symlinked_pack_root_before_writing(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            workspace=Path(td); project=self._scaffold(workspace)
            rp_root=project/"resource_packs/test-addon_RP"
            saved=project/"resource_packs/test-addon_RP_real"
            rp_root.rename(saved)
            rp_root.symlink_to(Path(outside), target_is_directory=True)
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                result=server.call_tool("create_addon_item", {"project_directory":"test-addon","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50"})
            self.assertEqual(result["status"],"error")
            self.assertIn("unsafe",result["error"]["message"])
            self.assertEqual(list(Path(outside).iterdir()),[])

    def test_merges_second_item_into_existing_atlas_and_localization(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td); project = self._scaffold(workspace)
            atlas_path = project / "resource_packs/test-addon_RP/textures/item_texture.json"
            atlas_path.parent.mkdir(parents=True, exist_ok=True)
            atlas_path.write_text(json.dumps({"resource_pack_name":"custom","texture_name":"atlas.items","keep_meta":True,"texture_data":{"first":{"textures":"textures/items/first"}}}, indent=2)+"\n", encoding="utf-8")
            lang_path = project / "resource_packs/test-addon_RP/texts/en_US.lang"
            lang_path.parent.mkdir(parents=True, exist_ok=True)
            lang_path.write_text("# Keep existing translation\nitem.first.name=First Item\n", encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_item", {"project_directory":"test-addon","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50"})
            self.assertEqual(result["status"], "created")
            atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
            self.assertTrue(atlas["keep_meta"])
            self.assertEqual(set(atlas["texture_data"]), {"first", "ruby_shard"})
            self.assertEqual(lang_path.read_text(encoding="utf-8"), "# Keep existing translation\nitem.first.name=First Item\nitem.ruby_shard.name=Ruby Shard\n")
            self.assertTrue((project / "behavior_packs/test-addon_BP/items/ruby_shard.json").exists())

    def test_rejects_duplicate_atlas_key_without_modifying_any_shared_file(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td); project = self._scaffold(workspace)
            atlas_path = project / "resource_packs/test-addon_RP/textures/item_texture.json"
            atlas_path.parent.mkdir(parents=True, exist_ok=True)
            original_atlas = json.dumps({"texture_data":{"ruby_shard":{"textures":"textures/items/original"}}}) + "\n"
            atlas_path.write_text(original_atlas, encoding="utf-8")
            lang_path = project / "resource_packs/test-addon_RP/texts/en_US.lang"
            lang_path.parent.mkdir(parents=True, exist_ok=True)
            original_lang = "item.keep.name=Keep\n"
            lang_path.write_text(original_lang, encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_item", {"project_directory":"test-addon","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50"})
            self.assertEqual(result["status"], "error")
            self.assertIn("already contains key", result["error"]["message"])
            self.assertEqual(atlas_path.read_text(encoding="utf-8"), original_atlas)
            self.assertEqual(lang_path.read_text(encoding="utf-8"), original_lang)
            self.assertFalse((project / "behavior_packs/test-addon_BP/items/ruby_shard.json").exists())

    def test_rejects_malformed_lang_without_modifying_atlas(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td); project = self._scaffold(workspace)
            atlas_path = project / "resource_packs/test-addon_RP/textures/item_texture.json"
            atlas_path.parent.mkdir(parents=True, exist_ok=True)
            original_atlas = json.dumps({"texture_data":{"keep":{"textures":"textures/items/keep"}}}) + "\n"
            atlas_path.write_text(original_atlas, encoding="utf-8")
            lang_path = project / "resource_packs/test-addon_RP/texts/en_US.lang"
            lang_path.parent.mkdir(parents=True, exist_ok=True)
            lang_path.write_text("malformed line without equals\n", encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_item", {"project_directory":"test-addon","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50"})
            self.assertEqual(result["status"], "error")
            self.assertIn("malformed line", result["error"]["message"])
            self.assertEqual(atlas_path.read_text(encoding="utf-8"), original_atlas)
            self.assertEqual(lang_path.read_text(encoding="utf-8"), "malformed line without equals\n")
            self.assertFalse((project / "behavior_packs/test-addon_BP/items/ruby_shard.json").exists())

    def test_rejects_duplicate_localization_key_without_overwrite(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td); project = self._scaffold(workspace)
            lang_path = project / "resource_packs/test-addon_RP/texts/en_US.lang"
            lang_path.parent.mkdir(parents=True, exist_ok=True)
            original_lang = "item.ruby_shard.name=Existing Name\n"
            lang_path.write_text(original_lang, encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_item", {"project_directory":"test-addon","item_name":"Ruby Shard","item_slug":"ruby_shard","target_game_version":"1.26.50"})
            self.assertEqual(result["status"], "error")
            self.assertIn("already exists", result["error"]["message"])
            self.assertEqual(lang_path.read_text(encoding="utf-8"), original_lang)
            self.assertFalse((project / "behavior_packs/test-addon_BP/items/ruby_shard.json").exists())

    def test_item_tool_is_write_capable_and_schema_closed(self):
        tool=server.TOOL_BY_NAME["create_addon_item"]
        self.assertFalse(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["annotations"]["idempotentHint"])
        self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertIn("create_addon_item",server.WORKFLOW_INSTRUCTIONS)



class CreateAddonBlockTests(unittest.TestCase):
    def _scaffold(self, workspace: Path):
        from unittest.mock import patch
        with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(workspace)}):
            result = server.call_tool("create_addon_project", {
                "project_directory": "block-addon", "display_name": "Block Add-on",
                "description": "Test scaffold for block creation.", "target_game_version": "1.26.50"
            })
        self.assertEqual(result["status"], "created")
        return workspace / "block-addon"

    def test_creates_block_and_terrain_atlas_mapping(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result=server.call_tool("create_addon_block", {"project_directory":"block-addon","block_name":"Ruby Ore","block_slug":"ruby_ore","target_game_version":"1.26.50"})
            self.assertEqual(result["status"], "created")
            bp=project/"behavior_packs/block-addon_BP/blocks/ruby_ore.block.json"
            block=json.loads(bp.read_text(encoding="utf-8"))
            self.assertEqual(block["minecraft:block"]["description"]["identifier"], "block_addon:ruby_ore")
            self.assertEqual(block["minecraft:block"]["components"]["minecraft:material_instances"]["*"]["texture"], "ruby_ore")
            atlas_path=project/"resource_packs/block-addon_RP/textures/terrain_texture.json"
            atlas=json.loads(atlas_path.read_text(encoding="utf-8"))
            self.assertEqual(atlas["texture_data"]["ruby_ore"]["textures"], "textures/blocks/ruby_ore")
            self.assertFalse((project/"resource_packs/block-addon_RP/textures/blocks/ruby_ore.png").exists())
            self.assertEqual(result["runtime_status"], "NOT RUN")

    def test_merges_existing_terrain_atlas_and_preserves_metadata(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            atlas_path=project/"resource_packs/block-addon_RP/textures/terrain_texture.json"
            atlas_path.parent.mkdir(parents=True,exist_ok=True)
            atlas_path.write_text(json.dumps({"texture_name":"atlas.terrain","keep":True,"texture_data":{"stone":{"textures":"textures/blocks/stone"}}})+"\n",encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result=server.call_tool("create_addon_block", {"project_directory":"block-addon","block_name":"Ruby Ore","block_slug":"ruby_ore","target_game_version":"1.26.50"})
            self.assertEqual(result["status"], "created")
            atlas=json.loads(atlas_path.read_text(encoding="utf-8"))
            self.assertTrue(atlas["keep"])
            self.assertEqual(set(atlas["texture_data"]), {"stone","ruby_ore"})

    def test_duplicate_atlas_key_fails_before_creating_block(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            atlas_path=project/"resource_packs/block-addon_RP/textures/terrain_texture.json"
            atlas_path.parent.mkdir(parents=True,exist_ok=True)
            original=json.dumps({"texture_data":{"ruby_ore":{"textures":"textures/blocks/old"}}})+"\n"
            atlas_path.write_text(original,encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result=server.call_tool("create_addon_block", {"project_directory":"block-addon","block_name":"Ruby Ore","block_slug":"ruby_ore","target_game_version":"1.26.50"})
            self.assertEqual(result["status"], "error")
            self.assertIn("already contains key",result["error"]["message"])
            self.assertEqual(atlas_path.read_text(encoding="utf-8"), original)
            self.assertFalse((project/"behavior_packs/block-addon_BP/blocks/ruby_ore.block.json").exists())

    def test_block_tool_is_write_capable_and_schema_closed(self):
        tool=server.TOOL_BY_NAME["create_addon_block"]
        self.assertFalse(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["annotations"]["idempotentHint"])
        self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertIn("create_addon_block",server.WORKFLOW_INSTRUCTIONS)


class CreateAddonRecipeTests(unittest.TestCase):
    def _scaffold(self, workspace: Path):
        from unittest.mock import patch
        with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(workspace)}):
            result = server.call_tool("create_addon_project", {
                "project_directory": "recipe-addon", "display_name": "Recipe Add-on",
                "description": "Test scaffold for recipe creation.", "target_game_version": "1.26.50"
            })
        self.assertEqual(result["status"], "created")
        return workspace / "recipe-addon"

    def _create_item(self, workspace: Path, slug: str, display: str):
        from unittest.mock import patch
        with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(workspace)}):
            result = server.call_tool("create_addon_item", {
                "project_directory":"recipe-addon", "item_name":display, "item_slug":slug, "target_game_version":"1.26.50"
            })
        self.assertEqual(result["status"], "created")
        return "recipe_addon:" + slug

    def test_creates_shapeless_recipe_for_project_item(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            custom=self._create_item(workspace,"ruby_shard","Ruby Shard")
            args={"project_directory":"recipe-addon","recipe_slug":"ruby_from_dust","recipe_type":"shapeless","result_identifier":custom,"ingredients":["minecraft:redstone","minecraft:quartz"],"target_game_version":"1.26.50"}
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                result=server.call_tool("create_addon_recipe",args)
            self.assertEqual(result["status"],"created")
            data=json.loads((project/"behavior_packs/recipe-addon_BP/recipes/ruby_from_dust.json").read_text(encoding="utf-8"))
            recipe=data["minecraft:recipe_shapeless"]
            self.assertEqual(data["format_version"],"1.20.10")
            self.assertEqual(recipe["description"]["identifier"],"recipe_addon:ruby_from_dust")
            self.assertEqual(recipe["result"],{"item":custom,"count":1})
            self.assertEqual(recipe["ingredients"],[{"item":"minecraft:redstone"},{"item":"minecraft:quartz"}])
            self.assertEqual(result["runtime_status"],"NOT RUN")

    def test_creates_shaped_recipe_with_exact_pattern_mapping(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            custom=self._create_item(workspace,"ruby_shard","Ruby Shard")
            args={"project_directory":"recipe-addon","recipe_slug":"ruby_block","recipe_type":"shaped","result_identifier":custom,"pattern":["RR","RR"],"key_mapping":{"R":custom},"result_count":1,"target_game_version":"1.26.50"}
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                result=server.call_tool("create_addon_recipe",args)
            self.assertEqual(result["status"],"created")
            data=json.loads((project/"behavior_packs/recipe-addon_BP/recipes/ruby_block.json").read_text(encoding="utf-8"))
            recipe=data["minecraft:recipe_shaped"]
            self.assertEqual(recipe["pattern"],["RR","RR"])
            self.assertEqual(recipe["key"],{"R":{"item":custom}})

    def test_custom_block_can_be_recipe_result(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                block_result=server.call_tool("create_addon_block", {"project_directory":"recipe-addon","block_name":"Ruby Ore","block_slug":"ruby_ore","target_game_version":"1.26.50"})
                self.assertEqual(block_result["status"],"created")
                recipe_result=server.call_tool("create_addon_recipe", {"project_directory":"recipe-addon","recipe_slug":"ruby_ore_recipe","recipe_type":"shaped","result_identifier":"recipe_addon:ruby_ore","pattern":["S"],"key_mapping":{"S":"minecraft:stone"},"target_game_version":"1.26.50"})
            self.assertEqual(recipe_result["status"],"created")
            recipe=json.loads((project/"behavior_packs/recipe-addon_BP/recipes/ruby_ore_recipe.json").read_text(encoding="utf-8"))
            self.assertEqual(recipe["minecraft:recipe_shaped"]["result"]["item"],"recipe_addon:ruby_ore")

    def test_rejects_custom_result_or_ingredient_not_defined_in_project(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                bad_result=server.call_tool("create_addon_recipe",{"project_directory":"recipe-addon","recipe_slug":"bad_result","recipe_type":"shapeless","result_identifier":"other_pack:missing_item","ingredients":["minecraft:stick"],"target_game_version":"1.26.50"})
                bad_ingredient=server.call_tool("create_addon_recipe",{"project_directory":"recipe-addon","recipe_slug":"bad_ingredient","recipe_type":"shapeless","result_identifier":"minecraft:diamond","ingredients":["other_pack:missing_item"],"target_game_version":"1.26.50"})
            self.assertEqual(bad_result["status"],"error")
            self.assertIn("not defined",bad_result["error"]["message"])
            self.assertEqual(bad_ingredient["status"],"error")
            self.assertIn("not defined",bad_ingredient["error"]["message"])
            recipe_dir=project/"behavior_packs/recipe-addon_BP/recipes"
            self.assertEqual(list(recipe_dir.glob("*.json")),[])

    def test_rejects_invalid_shaped_pattern_before_writing(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); self._scaffold(workspace)
            cases=[
                {"pattern":["AB","A"],"key_mapping":{"A":"minecraft:stone","B":"minecraft:dirt"}},
                {"pattern":["AX"],"key_mapping":{"A":"minecraft:stone"}},
                {"pattern":["  "],"key_mapping":{"A":"minecraft:stone"}},
                {"pattern":["A"],"key_mapping":{"AA":"minecraft:stone"}},
            ]
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                for index,extra in enumerate(cases):
                    with self.subTest(case=index):
                        args={"project_directory":"recipe-addon","recipe_slug":f"bad_recipe_{index}","recipe_type":"shaped","result_identifier":"minecraft:diamond","target_game_version":"1.26.50",**extra}
                        result=server.call_tool("create_addon_recipe",args)
                        self.assertEqual(result["status"],"error")
            recipe_dir=workspace/"recipe-addon/behavior_packs/recipe-addon_BP/recipes"
            self.assertEqual(list(recipe_dir.glob("*.json")),[])

    def test_recipe_collision_does_not_overwrite(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            workspace=Path(td); project=self._scaffold(workspace)
            recipe=project/"behavior_packs/recipe-addon_BP/recipes/ruby_from_dust.json"
            recipe.write_text('{"keep":true}\n',encoding="utf-8")
            with patch.dict(os.environ,{"MINECRAFT_BEDROCK_WORKSPACE":td}):
                result=server.call_tool("create_addon_recipe",{"project_directory":"recipe-addon","recipe_slug":"ruby_from_dust","recipe_type":"shapeless","result_identifier":"minecraft:diamond","ingredients":["minecraft:stick"],"target_game_version":"1.26.50"})
            self.assertEqual(result["status"],"error")
            self.assertTrue(recipe.read_text(encoding="utf-8").startswith('{"keep":true}'))

    def test_recipe_requires_scaffold_version_and_closed_write_tool_schema(self):
        tool=server.TOOL_BY_NAME["create_addon_recipe"]
        self.assertFalse(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["annotations"]["idempotentHint"])
        self.assertFalse(tool["inputSchema"]["additionalProperties"])
        normalized=server._validate_arguments("create_addon_recipe",{"project_directory":"recipe-addon","recipe_slug":"recipe_a","recipe_type":"shapeless","result_identifier":"minecraft:diamond","ingredients":["minecraft:stick"],"target_game_version":"1.26.50"})
        self.assertEqual(normalized["result_count"],1)
        self.assertIn("create_addon_recipe",server.WORKFLOW_INSTRUCTIONS)




class MojangSampleVersionSelectionTests(unittest.TestCase):
    PREVIEW_VERSION = "1.26.60.30-preview"

    def _preview_payload(self):
        payload = server._load_mojang_sample_index(self.PREVIEW_VERSION)
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get("target_version"), self.PREVIEW_VERSION)
        self.assertEqual(payload.get("index_mode"), "full_index")
        self.assertGreater(len(payload.get("entries", [])), 0)
        return payload

    def test_search_omitted_source_version_preserves_stable_default(self):
        result = server.call_tool("search_mojang_samples", {
            "query": "minecraft:apple", "category": "item", "limit": 5
        })
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sample_version"], "1.26.50.4")
        self.assertEqual(result["source_channel"], "stable")
        self.assertEqual(result["target_version"], "1.26.50.4")

    def test_search_accepts_explicit_indexed_stable_version(self):
        result = server.call_tool("search_mojang_samples", {
            "query": "minecraft:apple", "category": "item",
            "sample_version": "1.26.50.4", "limit": 5
        })
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sample_version"], "1.26.50.4")
        self.assertTrue(any(row["path"] == "behavior_pack/items/apple.json" for row in result["results"]))

    def test_preview_search_uses_separate_full_index_and_provenance(self):
        result = server.call_tool("search_mojang_samples", {
            "query": "behavior_pack/items", "category": "item",
            "sample_version": self.PREVIEW_VERSION, "limit": 5
        })
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["sample_version"], self.PREVIEW_VERSION)
        self.assertEqual(result["source_channel"], "preview")
        self.assertEqual(result["target_version"], self.PREVIEW_VERSION)
        self.assertEqual(result["index_mode"], "full_index")
        self.assertEqual(result["source_commit"], "4d30ae63750467771b6eccda105f732c6cb77ff7")
        self.assertIn(self.PREVIEW_VERSION, result["source_release_url"])
        self.assertGreater(len(result["results"]), 0)

    def test_preview_index_target_version_must_match_selected_source(self):
        import tempfile
        from unittest.mock import patch
        payload = dict(self._preview_payload())
        payload["target_version"] = "1.26.60.29-preview"
        with tempfile.TemporaryDirectory() as td:
            index_path = Path(td) / "wrong-version.json.gz"
            with gzip.open(index_path, "wt", encoding="utf-8") as stream:
                json.dump(payload, stream)
            corpus = dict(server.MOJANG_SAMPLE_CORPORA[self.PREVIEW_VERSION])
            corpus["index_path"] = index_path
            with patch.dict(server.MOJANG_SAMPLE_CORPORA, {self.PREVIEW_VERSION: corpus}):
                with self.assertRaisesRegex(RuntimeError, "target_version does not match"):
                    server._load_mojang_sample_index(self.PREVIEW_VERSION)

    def test_preview_index_archive_digest_must_match_pinned_release_asset(self):
        import tempfile
        from unittest.mock import patch
        payload = dict(self._preview_payload())
        payload["archive_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as td:
            index_path = Path(td) / "wrong-source.json.gz"
            with gzip.open(index_path, "wt", encoding="utf-8") as stream:
                json.dump(payload, stream)
            corpus = dict(server.MOJANG_SAMPLE_CORPORA[self.PREVIEW_VERSION])
            corpus["index_path"] = index_path
            with patch.dict(server.MOJANG_SAMPLE_CORPORA, {self.PREVIEW_VERSION: corpus}):
                with self.assertRaisesRegex(RuntimeError, "source archive SHA-256"):
                    server._load_mojang_sample_index(self.PREVIEW_VERSION)

    def test_preview_read_without_source_archive_reports_not_bundled(self):
        payload = self._preview_payload()
        entry = next(item for item in payload["entries"] if item.get("category") == "item" and str(item.get("path", "")).endswith(".json"))
        result = server.call_tool("read_mojang_sample", {
            "sample_path": entry["path"], "sample_version": self.PREVIEW_VERSION,
        })
        self.assertEqual(result["status"], "not_bundled")
        self.assertEqual(result["sample_version"], self.PREVIEW_VERSION)
        self.assertEqual(result["source_channel"], "preview")

    def test_preview_archive_digest_mismatch_is_rejected(self):
        import tempfile
        from unittest.mock import patch
        payload = self._preview_payload()
        entry = next(item for item in payload["entries"] if item.get("category") == "item" and str(item.get("path", "")).endswith(".json"))
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            archive = workspace / "wrong-preview-source.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(entry["path"], '{"not":"the pinned preview archive"}')
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(workspace)}):
                result = server.call_tool("read_mojang_sample", {
                    "sample_path": entry["path"], "sample_version": self.PREVIEW_VERSION,
                    "archive_path": str(archive),
                })
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "SAMPLE_ARCHIVE_VERSION_MISMATCH")

    def test_preview_missing_index_fails_closed_without_stable_fallback(self):
        import tempfile
        from unittest.mock import patch
        preview_corpus = dict(server.MOJANG_SAMPLE_CORPORA[self.PREVIEW_VERSION])
        with tempfile.TemporaryDirectory() as td:
            preview_corpus["index_path"] = Path(td) / "missing-preview-index.json.gz"
            with patch.dict(server.MOJANG_SAMPLE_CORPORA, {self.PREVIEW_VERSION: preview_corpus}):
                result = server.call_tool("search_mojang_samples", {
                    "query": "minecraft:apple", "sample_version": self.PREVIEW_VERSION
                })
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "SAMPLE_VERSION_NOT_INDEXED")
        self.assertEqual(result["error"]["details"]["indexed_versions"], ["1.26.50.4"])

    def test_preview_real_archive_member_roundtrip_when_ci_supplies_source(self):
        archive_text = os.environ.get("MOJANG_PREVIEW_ARCHIVE")
        if not archive_text:
            self.skipTest("real Mojang Preview archive is supplied only by the pinned index-build workflow")
        archive = Path(archive_text).resolve(strict=True)
        payload = self._preview_payload()
        entry = next(
            item for item in payload["entries"]
            if item.get("category") == "item"
            and str(item.get("path", "")).endswith(".json")
            and 0 < item.get("size_bytes", 0) <= server.MAX_SAMPLE_READ_BYTES
            and item.get("sha256")
        )
        from unittest.mock import patch
        with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(archive.parent)}):
            result = server.call_tool("read_mojang_sample", {
                "sample_path": entry["path"], "sample_version": self.PREVIEW_VERSION,
                "archive_path": str(archive),
            })
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["source"], "user_supplied_archive")
        self.assertTrue(result["content_hash_matches_index"])

    def test_unknown_sample_version_is_rejected_by_closed_tool_schema(self):
        with self.assertRaisesRegex(ValueError, "sample_version must be one of"):
            server._validate_arguments("search_mojang_samples", {
                "query": "minecraft:apple", "sample_version": "1.26.60.5"
            })

    def test_read_omitted_source_version_preserves_stable_default(self):
        result = server.call_tool("read_mojang_sample", {
            "sample_path": "behavior_pack/items/apple.json"
        })
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sample_version"], "1.26.50.4")
        self.assertEqual(result["source_channel"], "stable")


if __name__ == "__main__":
    unittest.main()
