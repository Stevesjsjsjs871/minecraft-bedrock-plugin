from __future__ import annotations

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = ROOT / "server" / "mcp_server.py"
spec = importlib.util.spec_from_file_location("mbe_mcp_server_texture_tests", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(server)


class GenerateTextureToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(self.workspace)})
        self.env.start()
        result = server.call_tool("create_addon_project", {
            "project_directory": "texture-test-addon",
            "display_name": "Texture Test Add-On",
            "description": "Temporary test scaffold.",
            "target_game_version": "1.26.50",
        })
        self.assertEqual(result["status"], "created", result)
        self.project = self.workspace / "texture-test-addon"
        self.rp = self.project / "resource_packs" / "texture-test-addon_RP"
        (self.rp / "textures" / "blocks").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def call_texture(self, **overrides):
        args = {
            "project_directory": "texture-test-addon",
            "output_path": "textures/blocks/generated.png",
            "width": 16,
            "height": 16,
            "style": "ore_veins",
            "base_color": "#333333",
            "accent_color": "#FFAA00",
            "seed": 7,
            "alpha": 255,
        }
        args.update(overrides)
        return server.call_tool("generate_texture", args)

    def test_tool_is_registered_with_closed_write_schema(self):
        response = server.handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}
        })
        tools = response["result"]["tools"]
        tool = next(item for item in tools if item["name"] == "generate_texture")
        self.assertFalse(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["annotations"]["destructiveHint"])
        self.assertFalse(tool["annotations"]["idempotentHint"])
        self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertIn("output_path", tool["inputSchema"]["required"])

    def test_creates_real_png_inside_linked_resource_pack(self):
        result = self.call_texture()
        self.assertEqual(result["status"], "created", result)
        self.assertEqual(result["runtime_status"], "NOT RUN")
        self.assertEqual(result["generator_status"], "PROCEDURAL_STARTER")
        output = self.rp / "textures" / "blocks" / "generated.png"
        self.assertTrue(output.is_file())
        self.assertEqual(output.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(result["output_path"], "textures/blocks/generated.png")

    def test_defaults_work_when_only_required_fields_are_supplied(self):
        result = server.call_tool("generate_texture", {
            "project_directory": "texture-test-addon",
            "output_path": "textures/blocks/defaults.png",
        })
        self.assertEqual(result["status"], "created", result)
        self.assertEqual(result["width"], 16)
        self.assertEqual(result["height"], 16)
        self.assertEqual(result["style"], "pixel_noise")

    def test_rejects_traversal_absolute_and_windows_paths(self):
        for output_path in (
            "../escape.png",
            "textures/../escape.png",
            "textures/../../escape.png",
            "/tmp/escape.png",
            "textures\\\\blocks\\\\escape.png",
        ):
            with self.subTest(output_path=output_path):
                result = self.call_texture(output_path=output_path)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
        self.assertFalse((self.workspace / "escape.png").exists())

    def test_rejects_invalid_dimensions_and_colors(self):
        for args in ({"width": 0}, {"height": 1025}, {"base_color": "red"}, {"alpha": 256}):
            with self.subTest(args=args):
                result = self.call_texture(**args)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")

    def test_refuses_to_overwrite_existing_texture(self):
        output = self.rp / "textures" / "blocks" / "generated.png"
        output.write_bytes(b"preserve existing asset")
        result = self.call_texture()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(output.read_bytes(), b"preserve existing asset")

    def test_rejects_symlink_escape(self):
        outside = self.workspace / "outside"
        outside.mkdir()
        textures = self.rp / "textures"
        shutil.rmtree(textures)
        try:
            textures.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable on this host")
        result = self.call_texture()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
        self.assertFalse((outside / "blocks" / "generated.png").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
