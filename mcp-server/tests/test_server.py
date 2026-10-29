from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"
spec = importlib.util.spec_from_file_location("mbe_mcp_server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(server)


class SchemaTests(unittest.TestCase):
    def test_exactly_seven_tools_and_closed_schemas(self):
        self.assertEqual(len(server.TOOLS), 7)
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
        self.assertEqual(init["result"]["serverInfo"]["version"], "0.6.7")
        listing = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual({t["name"] for t in listing["result"]["tools"]}, set(server.TOOL_BY_NAME))



    def test_manifest_versions_sync_with_server(self):
        root = SERVER_PATH.parents[1]
        with (root / "plugin.json").open(encoding="utf-8") as f:
            manifest = json.load(f)
        with (root / ".codex-plugin" / "plugin.json").open(encoding="utf-8") as f:
            compat = json.load(f)
        self.assertEqual(manifest["version"], server.SERVER_VERSION)
        self.assertEqual(compat["version"], server.SERVER_VERSION)
        prompts = manifest["extensions"]["com.openai"]["interface"]["defaultPrompt"]
        self.assertEqual(prompts, compat["interface"]["defaultPrompt"])
        self.assertEqual(len(prompts), 3)
        self.assertLessEqual(len(server.WORKFLOW_INSTRUCTIONS), 512)

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
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "fixture.mcaddon"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("small.txt", "fixture")
            class FakeInfo:
                file_size = server.MAX_UNCOMPRESSED_BYTES + 1
                def is_dir(self): return False
            class FakeZip:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def infolist(self): return [FakeInfo()]
            old = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
            os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = td
            try:
                with patch.object(server.zipfile, "ZipFile", return_value=FakeZip()):
                    with self.assertRaisesRegex(ValueError, "uncompressed bytes"):
                        server._resolve_archive("fixture.mcaddon")
            finally:
                if old is None:
                    os.environ.pop("MINECRAFT_BEDROCK_WORKSPACE", None)
                else:
                    os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = old

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
