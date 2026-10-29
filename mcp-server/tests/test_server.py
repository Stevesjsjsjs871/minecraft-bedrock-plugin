from __future__ import annotations

import asyncio
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"
SPEC = importlib.util.spec_from_file_location("mbe_mcp_server", SERVER_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class MCPServerTests(unittest.TestCase):
    def test_instructions_prioritize_tool_sequence_and_static_limit(self):
        self.assertIn("Use audit_archive before making claims", MODULE.INSTRUCTIONS)
        self.assertIn("never claim Minecraft runtime behavior was tested", MODULE.INSTRUCTIONS)
        self.assertLessEqual(len(MODULE.INSTRUCTIONS), 512)

    def test_tool_names_registered(self):
        async def get_names():
            return {tool.name for tool in await MODULE.mcp._tool_manager.list_tools()}
        names = asyncio.run(get_names())
        self.assertEqual(names, {
            "audit_archive", "compare_baseline", "get_resource_graph",
            "validate_manifest", "inspect_archive"
        })

    def test_rejects_missing_and_unsupported_paths(self):
        with self.assertRaises(ValueError):
            MODULE._validate_archive_path("does-not-exist.mcaddon")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "not-a-pack.txt"
            path.write_text("test")
            with self.assertRaises(ValueError):
                MODULE._validate_archive_path(str(path))

    def test_inspect_archive_does_not_extract(self):
        with tempfile.TemporaryDirectory() as td:
            archive_path = Path(td) / "sample.mcpack"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("manifest.json", "{}")
                archive.writestr("textures/entity/test.png", b"fake-png-data")
            result = MODULE.inspect_archive(str(archive_path))
            self.assertEqual(result["status"], "completed")
            self.assertFalse(result["extracted"])
            self.assertEqual(result["member_count"], 2)
            self.assertEqual(result["file_types"][".json"], 1)
            self.assertEqual(result["file_types"][".png"], 1)

    def test_all_tools_are_read_only(self):
        async def get_tools():
            return await MODULE.mcp._tool_manager.list_tools()
        tools = asyncio.run(get_tools())
        self.assertEqual(len(tools), 5)
        for tool in tools:
            annotations = tool.annotations
            self.assertTrue(annotations.readOnlyHint, tool.name)
            self.assertFalse(annotations.destructiveHint, tool.name)


if __name__ == "__main__":
    unittest.main()
