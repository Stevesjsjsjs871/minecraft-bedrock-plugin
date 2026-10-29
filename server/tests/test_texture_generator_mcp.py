from __future__ import annotations

import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
import sys
from unittest.mock import patch

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
import texture_generator_mcp as texture_mcp

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class TextureGeneratorMcpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.project_name = "ruby-addon"
        self.project = self.workspace / self.project_name
        self.texture_dir = self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "blocks"
        self.texture_dir.mkdir(parents=True)
        self.output_rel = f"resource_packs/{self.project_name}_RP/textures/blocks/ruby_ore.png"
        self.fake_generator = self.workspace / "fake_generator.py"
        self.fake_generator.write_text(
            "from pathlib import Path\n"
            "PNG_SIGNATURE = b'\\x89PNG\\r\\n\\x1a\\n'\n"
            "def write_texture(output, *, width=16, height=16, style='pixel_noise', base_color='#777777', accent_color='#A0A0A0', seed=1, alpha=255, force=False):\n"
            "    path = Path(output)\n"
            "    if path.exists() and not force: raise FileExistsError(path)\n"
            "    payload = PNG_SIGNATURE + bytes([width % 256, height % 256, alpha % 256])\n"
            "    path.write_bytes(payload)\n"
            "    return {'status':'created','format':'PNG','width':width,'height':height,'style':style,'seed':seed,'bytes_written':len(payload),'generator_status':'PROCEDURAL_STARTER'}\n",
            encoding="utf-8",
        )
        env_patch = patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(self.workspace)})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        generator_patch = patch.object(texture_mcp, "GENERATOR_PATH", self.fake_generator)
        generator_patch.start()
        self.addCleanup(generator_patch.stop)

    def _call(self, args=None, *, output_path=None, project_directory=None):
        call_args = {
            "project_directory": project_directory or self.project_name,
            "output_path": output_path or self.output_rel,
        }
        if args:
            call_args.update(args)
        return texture_mcp.handle_message({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": "generate_texture", "arguments": call_args},
        })

    def test_tool_is_registered_with_closed_write_schema(self):
        listing = texture_mcp.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = listing["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["generate_texture"])
        tool = tools[0]
        self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertEqual(tool["inputSchema"]["required"], ["project_directory", "output_path"])
        self.assertFalse(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["annotations"]["destructiveHint"])
        self.assertFalse(tool["annotations"]["idempotentHint"])

    def test_initialize_and_ping_follow_jsonrpc_shape(self):
        initialized = texture_mcp.handle_message({
            "jsonrpc": "2.0", "id": 7, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
        })
        self.assertEqual(initialized["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "minecraft-bedrock-texture-generator")
        self.assertEqual(texture_mcp.handle_message({"jsonrpc": "2.0", "id": 8, "method": "ping"})["result"], {})
        self.assertIsNone(texture_mcp.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_creates_png_and_returns_structured_metadata(self):
        response = self._call({"width": 32, "height": 16, "style": "ore_veins", "base_color": "#55545A", "accent_color": "#9A5CDA", "seed": 14})
        self.assertFalse(response["result"]["isError"])
        payload = response["result"]["structuredContent"]
        self.assertEqual(payload["status"], "created")
        self.assertEqual(payload["path"], self.output_rel)
        self.assertEqual(payload["width"], 32)
        self.assertEqual(payload["height"], 16)
        self.assertEqual(payload["style"], "ore_veins")
        self.assertEqual(payload["runtime_status"], "NOT RUN")
        self.assertEqual(payload["generator_kind"], "PROCEDURAL")
        self.assertRegex(payload["sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue((self.project / self.output_rel).read_bytes().startswith(PNG_SIGNATURE))

    def test_defaults_are_applied(self):
        response = self._call()
        payload = response["result"]["structuredContent"]
        self.assertEqual((payload["width"], payload["height"]), (16, 16))
        self.assertEqual(payload["style"], "pixel_noise")
        self.assertEqual(payload["seed"], 1)

    def test_bundled_generator_creates_a_valid_png_when_available(self):
        bundled_generator = texture_mcp.ROOT / "skills" / "visual-resource-pipeline" / "scripts" / "generate_texture.py"
        if not bundled_generator.is_file():
            self.skipTest("bundled generator is not present in this isolated test fixture")
        with patch.object(texture_mcp, "GENERATOR_PATH", bundled_generator):
            response = self._call({"width": 8, "height": 4, "style": "solid", "base_color": "#123456"}, output_path=self.output_rel)
        result = response["result"]["structuredContent"]
        self.assertFalse(response["result"]["isError"])
        png = (self.project / self.output_rel).read_bytes()
        self.assertTrue(png.startswith(PNG_SIGNATURE))
        offset = len(PNG_SIGNATURE)
        chunks = []
        while offset < len(png):
            length = struct.unpack(">I", png[offset:offset + 4])[0]
            kind = png[offset + 4:offset + 8]
            payload = png[offset + 8:offset + 8 + length]
            crc = struct.unpack(">I", png[offset + 8 + length:offset + 12 + length])[0]
            self.assertEqual(zlib.crc32(kind + payload) & 0xFFFFFFFF, crc)
            chunks.append((kind, payload))
            offset += length + 12
            if kind == b"IEND":
                break
        self.assertEqual(chunks[0][0], b"IHDR")
        self.assertEqual(struct.unpack(">IIBBBBB", chunks[0][1]), (8, 4, 8, 6, 0, 0, 0))
        self.assertEqual(result["runtime_status"], "NOT RUN")

    def test_existing_destination_is_never_overwritten(self):
        output = self.project / self.output_rel
        output.write_bytes(b"do not overwrite")
        response = self._call()
        payload = response["result"]["structuredContent"]
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(payload["error"]["code"], "OUTPUT_EXISTS")
        self.assertEqual(output.read_bytes(), b"do not overwrite")

    def test_missing_parent_is_not_created_automatically(self):
        output_rel = f"resource_packs/{self.project_name}_RP/textures/entity/new/mob.png"
        response = self._call(output_path=output_rel)
        self.assertEqual(response["result"]["structuredContent"]["error"]["code"], "INVALID_ARGUMENT")
        self.assertFalse((self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "entity").exists())

    def test_rejects_traversal_absolute_and_wrong_pack_paths(self):
        invalid_paths = [
            f"resource_packs/{self.project_name}_RP/textures/../escape.png",
            "/tmp/escape.png",
            "C:/escape.png",
            f"resource_packs/another_RP/textures/blocks/escape.png",
            f"resource_packs/{self.project_name}_RP/blocks/escape.png",
            f"resource_packs/{self.project_name}_RP/textures/blocks/escape.PNG",
            f"resource_packs/{self.project_name}_RP\\textures\\blocks\\escape.png",
        ]
        for path in invalid_paths:
            with self.subTest(path=path):
                response = self._call(output_path=path)
                result = response["result"]["structuredContent"]
                self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")

    def test_rejects_extra_argument_and_boolean_dimension(self):
        extra = self._call({"surprise": True})["result"]["structuredContent"]
        boolean = self._call({"width": True})["result"]["structuredContent"]
        self.assertEqual(extra["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(boolean["error"]["code"], "INVALID_ARGUMENT")

    def test_rejects_unknown_style_and_invalid_color(self):
        unknown = self._call({"style": "neon_magic"})["result"]["structuredContent"]
        color = self._call({"base_color": "red"})["result"]["structuredContent"]
        self.assertEqual(unknown["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(color["error"]["code"], "INVALID_ARGUMENT")

    def test_rejects_symlinked_project(self):
        linked_project = self.workspace / "linked-addon"
        try:
            linked_project.symlink_to(self.project, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks are unavailable in this environment: {exc}")
        response = self._call(
            output_path="resource_packs/linked-addon_RP/textures/blocks/link.png",
            project_directory="linked-addon",
        )
        self.assertEqual(response["result"]["structuredContent"]["error"]["code"], "INVALID_ARGUMENT")

    def test_rejects_symlinked_texture_parent(self):
        linked = self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "linked"
        outside = self.workspace / "outside"
        outside.mkdir()
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks are unavailable in this environment: {exc}")
        output_path = f"resource_packs/{self.project_name}_RP/textures/linked/escape.png"
        response = self._call(output_path=output_path)
        self.assertEqual(response["result"]["structuredContent"]["error"]["code"], "INVALID_ARGUMENT")
        self.assertFalse((outside / "escape.png").exists())

    def test_unknown_tool_and_unknown_method_return_protocol_errors(self):
        unknown_tool = texture_mcp.handle_message({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"something_else","arguments":{}}})
        unknown_method = texture_mcp.handle_message({"jsonrpc":"2.0","id":2,"method":"not/a/method"})
        self.assertEqual(unknown_tool["error"]["code"], -32602)
        self.assertEqual(unknown_method["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
