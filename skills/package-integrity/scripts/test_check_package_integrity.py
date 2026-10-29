from __future__ import annotations

import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("check_package_integrity.py")
spec = importlib.util.spec_from_file_location("check_package_integrity", SCRIPT)
checker = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(checker)


class PackageIntegrityTests(unittest.TestCase):
    def make_package(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / ".codex-plugin").mkdir()
        (root / "server/tests").mkdir(parents=True)
        (root / "skills/test-skill").mkdir(parents=True)
        for path in checker.REQUIRED_FILES:
            p = root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text("{}\n", encoding="utf-8")
        prompt = ["Create a feature.", "Audit an add-on."]
        root_manifest = {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "name": checker.EXPECTED_PLUGIN_NAME,
            "version": "1.0.5",
            "extensions": {"com.openai": {"interface": {"defaultPrompt": prompt}}},
        }
        compatibility_manifest = {
            "name": checker.EXPECTED_PLUGIN_NAME,
            "version": "1.0.5",
            "skills": "./skills",
            "mcpServers": "./.mcp.json",
            "interface": {"defaultPrompt": prompt},
        }
        (root / "plugin.json").write_text(json.dumps(root_manifest), encoding="utf-8")
        (root / ".codex-plugin/plugin.json").write_text(json.dumps(compatibility_manifest), encoding="utf-8")
        (root / "VERSION").write_text("1.0.5\n", encoding="utf-8")
        (root / "README.md").write_text("# Minecraft Bedrock Engineer — 1.0.5\n\nPreserved history.\n", encoding="utf-8")
        config = {"mcpServers": {checker.EXPECTED_PLUGIN_NAME: {"type": "stdio", "command": "python3", "args": ["${PLUGIN_ROOT}/server/mcp_server.py"]}}}
        (root / ".mcp.json").write_text(json.dumps(config), encoding="utf-8")
        (root / "mcp.json").write_text(json.dumps({"$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json", **config}), encoding="utf-8")
        (root / "skills/test-skill/SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A sufficiently detailed test skill description.\n---\n\n# Test\n",
            encoding="utf-8",
        )
        # Minimal static registry fixture covering each currently write-capable operation.
        tool_specs = [
            ("audit_pack", "Audit a pack.", "candidate_path", True),
            ("create_addon_project", "Create a project.", "project_directory", False),
            ("create_addon_item", "Create an item.", "project_directory", False),
            ("create_addon_block", "Create a block.", "project_directory", False),
            ("create_addon_recipe", "Create a recipe.", "project_directory", False),
        ]
        entries = []
        handlers = []
        for name, description, arg_name, read_only in tool_specs:
            kw = "" if read_only else ", read_only=False"
            entries.append(f'_tool("{name}", "{description}", {{"{arg_name}": {{"type": "string"}}}}, ["{arg_name}"]{kw})')
            handlers.append(f'    if name == "{name}":\n        return {{"status": "completed"}}')
        server = """def _tool(name, description, properties, required, *, read_only=True):
    return {"inputSchema": {"properties": properties, "required": required, "additionalProperties": False}, "annotations": {"readOnlyHint": read_only, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}}

TOOLS = [
""" + ",\n".join(entries) + "\n]\n\ndef call_tool(name, args):\n" + "\n".join(handlers) + "\n    return {'status': 'error'}\n"
        (root / "server/mcp_server.py").write_text(server, encoding="utf-8")
        (root / "skills/bedrock-development/references/mojang-samples-1.26.50.4/INDEX_METADATA.json").write_text(
            json.dumps({"target_version": "1.26.50.4", "zip_sha256": "a" * 64, "entry_count": 1, "indexed_count": 1}),
            encoding="utf-8",
        )
        index = {
            "schema_version": 1,
            "dataset_id": "mojang-bedrock-samples",
            "target_version": "1.26.50.4",
            "archive_sha256": "a" * 64,
            "archive_stats": {"entry_count": 1, "indexed_count": 1},
            "entries": [{"path": "behavior_pack/items/test.json", "category": "item", "size_bytes": 12, "sha256": "b" * 64, "identifiers": [], "json_parsed": True}],
        }
        with gzip.open(root / "skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(index, stream)

    def check_by_id(self, report, code):
        return next(check for check in report["checks"] if check["id"] == code)

    def test_valid_synthetic_package_passes_full_structural_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            report = checker.audit_package(root)
            self.assertEqual(report["status"], "PASS", report["checks"])
            self.assertEqual(report["mcp_registry"]["tool_count"], 5)
            self.assertEqual(report["mojang_samples_index"]["indexed_count"], 1)
            self.assertEqual(report["runtime_status"], "NOT RUN")

    def test_mismatched_version_markers_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            (root / "VERSION").write_text("1.0.4\n", encoding="utf-8")
            report = checker.audit_package(root)
            self.assertEqual(self.check_by_id(report, "version-markers")["status"], "FAIL")
            self.assertEqual(report["status"], "FAIL")

    def test_prompt_order_or_value_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            compat = json.loads((root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
            compat["interface"]["defaultPrompt"].reverse()
            (root / ".codex-plugin/plugin.json").write_text(json.dumps(compat), encoding="utf-8")
            report = checker.audit_package(root)
            self.assertEqual(self.check_by_id(report, "default-prompts")["status"], "FAIL")

    def test_duplicate_tool_name_fails_registry_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            server_path = root / "server/mcp_server.py"
            source = server_path.read_text(encoding="utf-8")
            source = source.replace('TOOLS = [\n', 'TOOLS = [\n    _tool("audit_pack", "Duplicate audit tool.", {"candidate_path": {"type": "string"}}, ["candidate_path"]),\n', 1)
            server_path.write_text(source, encoding="utf-8")
            report = checker.audit_package(root)
            self.assertEqual(self.check_by_id(report, "mcp-tool-registry")["status"], "FAIL")
            self.assertTrue(report["mcp_registry"]["duplicate_names"])

    def test_open_mcp_schema_factory_fails_closed_schema_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            server_path = root / "server/mcp_server.py"
            source = server_path.read_text(encoding="utf-8")
            source = source.replace(', "additionalProperties": False', '', 1)
            server_path.write_text(source, encoding="utf-8")
            report = checker.audit_package(root)
            self.assertEqual(self.check_by_id(report, "mcp-tool-registry")["status"], "FAIL")
            self.assertEqual(self.check_by_id(report, "mcp-schema-factory")["status"], "FAIL")

    def test_missing_dispatch_handler_fails_registry_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            server_path = root / "server/mcp_server.py"
            source = server_path.read_text(encoding="utf-8")
            source = source.replace('    if name == "audit_pack":\n        return {"status": "completed"}\n', "", 1)
            server_path.write_text(source, encoding="utf-8")
            report = checker.audit_package(root)
            self.assertEqual(self.check_by_id(report, "mcp-tool-registry")["status"], "FAIL")
            self.assertIn("audit_pack", report["mcp_registry"]["missing_handlers"])

    def test_unsafe_or_duplicate_sample_paths_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            index_path = root / "skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz"
            with gzip.open(index_path, "rt", encoding="utf-8") as stream:
                index = json.load(stream)
            index["entries"][0]["path"] = "../outside.json"
            with gzip.open(index_path, "wt", encoding="utf-8") as stream:
                json.dump(index, stream)
            report = checker.audit_package(root)
            self.assertEqual(self.check_by_id(report, "sample-index-content")["status"], "FAIL")

    def test_readme_heading_fix_preserves_remainder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            original_tail = "\n\nPreserved history.\n"
            (root / "README.md").write_text("# Minecraft Bedrock Engineer — 0.9.0" + original_tail, encoding="utf-8")
            checker.fix_readme_heading(root)
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), "# Minecraft Bedrock Engineer — 1.0.5" + original_tail)

    def test_readme_heading_fix_refuses_unrecognized_format_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            original = "# A different heading\n\nKeep me.\n"
            (root / "README.md").write_text(original, encoding="utf-8")
            with self.assertRaises(ValueError):
                checker.fix_readme_heading(root)
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), original)



    def test_generate_texture_is_allowed_as_explicit_write_tool(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            self.make_package(root)
            server_path = root / "server/mcp_server.py"
            source = server_path.read_text(encoding="utf-8")
            tool = '    _tool("generate_texture", "Generate a procedural PNG.", {"project_directory": {"type": "string"}, "output_path": {"type": "string"}}, ["project_directory", "output_path"], read_only=False),\n'
            source = source.replace("TOOLS = [\n", "TOOLS = [\n" + tool, 1)
            source = source.replace(
                "def call_tool(name, args):\n",
                'def call_tool(name, args):\n    if name == "generate_texture":\n        return {"status": "created"}\n',
                1,
            )
            server_path.write_text(source, encoding="utf-8")
            report = checker.audit_package(root)
            self.assertEqual(self.check_by_id(report, "mcp-tool-registry")["status"], "PASS")
            self.assertEqual(self.check_by_id(report, "mcp-write-annotations")["status"], "PASS")

if __name__ == "__main__":
    unittest.main(verbosity=2)
