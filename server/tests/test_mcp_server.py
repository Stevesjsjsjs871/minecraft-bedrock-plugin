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
    def test_exactly_eight_tools_and_closed_schemas(self):
        self.assertEqual(len(server.TOOLS), 8)
        for tool in server.TOOLS:
            schema = tool["inputSchema"]
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(schema["type"], "object")
            self.assertTrue(set(schema["required"]).issubset(schema["properties"]))
            self.assertTrue(tool["annotations"]["readOnlyHint"])
            self.assertFalse(tool["annotations"]["destructiveHint"])

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
        self.assertIn("never modify/delete files", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("MCT CLI", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("stays read-only", server.WORKFLOW_INSTRUCTIONS)
        self.assertIn("diff_packs", server.WORKFLOW_INSTRUCTIONS)

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
                self.assertEqual(len(tools["result"]["tools"]), 8)
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
        self.assertIn("from archive_safety import validate_zip_limits", source)
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


if __name__ == "__main__":
    unittest.main()
