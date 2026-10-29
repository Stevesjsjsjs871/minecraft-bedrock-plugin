from __future__ import annotations

import json
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

    def _call_tool(self, name, arguments):
        return texture_mcp.handle_message({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })

    def _call(self, args=None, *, output_path=None, project_directory=None):
        call_args = {
            "project_directory": project_directory or self.project_name,
            "output_path": output_path or self.output_rel,
        }
        if args:
            call_args.update(args)
        return self._call_tool("generate_texture", call_args)

    def _register(self, *, texture_type="blocks", identifier="ruby_ore", texture_path=None, project_directory=None, extra=None):
        arguments = {
            "project_directory": project_directory or self.project_name,
            "texture_type": texture_type,
            "texture_identifier": identifier,
            "texture_path": texture_path or self.output_rel,
        }
        if extra:
            arguments.update(extra)
        return self._call_tool("register_texture_atlas", arguments)

    def _generate_real_png(self, relative_path=None, *, width=8, height=8):
        relative_path = relative_path or self.output_rel
        output = self.project / relative_path
        output.parent.mkdir(parents=True, exist_ok=True)
        bundled = texture_mcp.ROOT / "skills" / "visual-resource-pipeline" / "scripts" / "generate_texture.py"
        with patch.object(texture_mcp, "GENERATOR_PATH", bundled):
            result = self._call({"width": width, "height": height, "style": "solid", "base_color": "#123456"}, output_path=relative_path)
        self.assertFalse(result["result"]["isError"], result["result"]["structuredContent"])
        return output

    def _replace_png_idat(self, path, replacement):
        payload = path.read_bytes()
        self.assertTrue(payload.startswith(PNG_SIGNATURE))
        chunks = []
        offset = len(PNG_SIGNATURE)
        inserted = False
        while offset < len(payload):
            length = struct.unpack(">I", payload[offset:offset + 4])[0]
            kind = payload[offset + 4:offset + 8]
            data = payload[offset + 8:offset + 8 + length]
            offset += 12 + length
            if kind == b"IDAT":
                if not inserted:
                    chunks.append((kind, replacement))
                    inserted = True
                continue
            chunks.append((kind, data))
        self.assertTrue(inserted, "test PNG must contain an IDAT chunk")
        rebuilt = bytearray(PNG_SIGNATURE)
        for kind, data in chunks:
            rebuilt.extend(struct.pack(">I", len(data)))
            rebuilt.extend(kind)
            rebuilt.extend(data)
            rebuilt.extend(struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
        path.write_bytes(rebuilt)

    def test_tool_is_registered_with_closed_write_schema(self):
        listing = texture_mcp.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = listing["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["generate_texture", "register_texture_atlas"])
        generate_tool, atlas_tool = tools
        self.assertFalse(generate_tool["inputSchema"]["additionalProperties"])
        self.assertEqual(generate_tool["inputSchema"]["required"], ["project_directory", "output_path"])
        self.assertFalse(atlas_tool["inputSchema"]["additionalProperties"])
        self.assertEqual(set(atlas_tool["inputSchema"]["required"]), {"project_directory", "texture_type", "texture_identifier", "texture_path"})
        self.assertFalse(generate_tool["annotations"]["readOnlyHint"])
        self.assertFalse(generate_tool["annotations"]["destructiveHint"])
        self.assertFalse(generate_tool["annotations"]["idempotentHint"])
        self.assertFalse(atlas_tool["annotations"]["readOnlyHint"])
        self.assertFalse(atlas_tool["annotations"]["destructiveHint"])
        self.assertTrue(atlas_tool["annotations"]["idempotentHint"])

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

    def test_registration_accepts_unused_trailing_idat_bytes(self):
        png = self._generate_real_png()
        payload = png.read_bytes()
        offset = len(PNG_SIGNATURE)
        idat_data = bytearray()
        while offset < len(payload):
            length = struct.unpack(">I", payload[offset:offset + 4])[0]
            kind = payload[offset + 4:offset + 8]
            data = payload[offset + 8:offset + 8 + length]
            offset += 12 + length
            if kind == b"IDAT":
                idat_data.extend(data)
        self._replace_png_idat(png, bytes(idat_data) + b"\x00\x00\x00")
        response = self._register(identifier="trailing_bytes")
        result = response["result"]["structuredContent"]
        self.assertFalse(response["result"]["isError"], result)
        self.assertEqual(result["status"], "registered")

    def test_registration_rejects_crc_valid_invalid_idat_stream(self):
        png = self._generate_real_png()
        self._replace_png_idat(png, b"not-a-zlib-stream")
        response = self._register()
        result = response["result"]["structuredContent"]
        self.assertTrue(response["result"]["isError"], result)
        self.assertEqual(result["error"]["code"], "INVALID_PNG")
        self.assertFalse((self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "terrain_texture.json").exists())

    def test_registration_rejects_crc_valid_wrong_scanline_length(self):
        png = self._generate_real_png()
        self._replace_png_idat(png, zlib.compress(b"\x00"))
        response = self._register()
        result = response["result"]["structuredContent"]
        self.assertTrue(response["result"]["isError"], result)
        self.assertEqual(result["error"]["code"], "INVALID_PNG")

    def test_registration_rejects_invalid_png_scanline_filter(self):
        png = self._generate_real_png()
        payload = png.read_bytes()
        width, height = struct.unpack(">II", payload[16:24])
        bit_depth, color_type, _compression, _filter, interlace = payload[24:29]
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
        self.assertEqual(interlace, 0, "bundled test generator should emit non-interlaced PNGs")
        row_size = (width * channels * bit_depth + 7) // 8
        invalid_scanlines = b"".join(b"\x05" + (b"\x00" * row_size) for _ in range(height))
        self._replace_png_idat(png, zlib.compress(invalid_scanlines))
        response = self._register()
        result = response["result"]["structuredContent"]
        self.assertTrue(response["result"]["isError"], result)
        self.assertEqual(result["error"]["code"], "INVALID_PNG")

    def test_registration_accepts_adam7_interlaced_png(self):
        width = height = 5
        pass_specs = (
            (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8),
            (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
        )
        filtered = bytearray()
        for x_start, y_start, x_step, y_step in pass_specs:
            pass_width = 0 if width <= x_start else (width - x_start + x_step - 1) // x_step
            pass_height = 0 if height <= y_start else (height - y_start + y_step - 1) // y_step
            if not pass_width or not pass_height:
                continue
            row_size = pass_width * 4
            for _ in range(pass_height):
                filtered.extend(b"\x00" + (b"\x00" * row_size))

        png = bytearray(PNG_SIGNATURE)

        def append_chunk(kind, data):
            png.extend(struct.pack(">I", len(data)))
            png.extend(kind)
            png.extend(data)
            png.extend(struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

        append_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 1))
        append_chunk(b"IDAT", zlib.compress(bytes(filtered)))
        append_chunk(b"IEND", b"")

        relative_path = f"resource_packs/{self.project_name}_RP/textures/blocks/adam7.png"
        (self.project / relative_path).write_bytes(png)
        response = self._register(identifier="adam7", texture_path=relative_path)
        result = response["result"]["structuredContent"]
        self.assertFalse(response["result"]["isError"], result)
        self.assertEqual(result["status"], "registered")
        self.assertEqual((result["width"], result["height"]), (width, height))

    def test_register_block_texture_creates_atlas_and_preserves_existing_entries(self):
        self._generate_real_png()
        atlas_path = self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "terrain_texture.json"
        original = {
            "resource_pack_name": "Keep Existing Name",
            "texture_name": "atlas.terrain",
            "padding": 8,
            "num_mip_levels": 4,
            "texture_data": {"existing_block": {"textures": "textures/blocks/existing_block"}},
        }
        atlas_path.write_text(json.dumps(original), encoding="utf-8")
        response = self._register()
        result = response["result"]["structuredContent"]
        self.assertFalse(response["result"]["isError"], result)
        self.assertEqual(result["status"], "registered")
        self.assertEqual(result["atlas_path"], f"resource_packs/{self.project_name}_RP/textures/terrain_texture.json")
        self.assertEqual(result["texture_reference"], "textures/blocks/ruby_ore")
        self.assertEqual((result["width"], result["height"]), (8, 8))
        saved = json.loads(atlas_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["resource_pack_name"], "Keep Existing Name")
        self.assertEqual(saved["texture_data"]["existing_block"], original["texture_data"]["existing_block"])
        self.assertEqual(saved["texture_data"]["ruby_ore"], {"textures": "textures/blocks/ruby_ore"})
        before = atlas_path.read_bytes()
        repeat = self._register()
        self.assertEqual(repeat["result"]["structuredContent"]["status"], "already_registered")
        self.assertEqual(atlas_path.read_bytes(), before)

    def test_register_item_texture_creates_item_atlas(self):
        item_path = f"resource_packs/{self.project_name}_RP/textures/items/ruby_gem.png"
        self._generate_real_png(item_path)
        response = self._register(texture_type="items", identifier="ruby_gem", texture_path=item_path)
        result = response["result"]["structuredContent"]
        self.assertFalse(response["result"]["isError"], result)
        self.assertEqual(result["status"], "registered")
        atlas = self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "item_texture.json"
        data = json.loads(atlas.read_text(encoding="utf-8"))
        self.assertEqual(data["texture_name"], "atlas.items")
        self.assertEqual(data["texture_data"]["ruby_gem"], {"textures": "textures/items/ruby_gem"})

    def test_registration_refuses_identifier_conflicts_without_overwriting_atlas(self):
        first = self._generate_real_png()
        second_rel = f"resource_packs/{self.project_name}_RP/textures/blocks/ruby_ore_alt.png"
        self._generate_real_png(second_rel)
        self.assertEqual(self._register()["result"]["structuredContent"]["status"], "registered")
        atlas = self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "terrain_texture.json"
        before = atlas.read_bytes()
        response = self._register(texture_path=second_rel)
        result = response["result"]["structuredContent"]
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(result["error"]["code"], "IDENTIFIER_CONFLICT")
        self.assertEqual(atlas.read_bytes(), before)
        self.assertTrue(first.is_file())

    def test_registration_rejects_wrong_paths_missing_files_and_bad_atlas(self):
        invalid_paths = [
            f"resource_packs/{self.project_name}_RP/textures/items/wrong_folder.png",
            f"resource_packs/{self.project_name}_RP/textures/blocks/../escape.png",
            "/tmp/ruby_ore.png",
        ]
        for path in invalid_paths:
            with self.subTest(path=path):
                result = self._register(texture_path=path)["result"]["structuredContent"]
                self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
        missing = self._register(texture_path=f"resource_packs/{self.project_name}_RP/textures/blocks/missing.png")["result"]["structuredContent"]
        self.assertEqual(missing["error"]["code"], "TEXTURE_UNAVAILABLE")
        self._generate_real_png()
        atlas = self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "terrain_texture.json"
        atlas.write_text("not-json", encoding="utf-8")
        malformed = self._register()["result"]["structuredContent"]
        self.assertEqual(malformed["error"]["code"], "INVALID_ATLAS")
        self.assertEqual(atlas.read_text(encoding="utf-8"), "not-json")

    def test_registration_rejects_corrupt_png_and_symlinked_texture_parent(self):
        bad = self.project / self.output_rel
        bad.write_bytes(b"not a png" * 10)
        corrupt = self._register()["result"]["structuredContent"]
        self.assertEqual(corrupt["error"]["code"], "INVALID_PNG")
        bad.unlink()
        outside = self.workspace / "outside-textures"
        outside.mkdir()
        linked = self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "blocks" / "linked"
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks are unavailable in this environment: {exc}")
        linked_file = linked / "escape.png"
        linked_file.write_bytes(b"not a png")
        path = f"resource_packs/{self.project_name}_RP/textures/blocks/linked/escape.png"
        result = self._register(texture_path=path)["result"]["structuredContent"]
        self.assertEqual(result["error"]["code"], "UNSAFE_TEXTURE_PATH")
        self.assertFalse((self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "terrain_texture.json").exists())

    def test_unknown_tool_and_unknown_method_return_protocol_errors(self):
        unknown_tool = texture_mcp.handle_message({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"something_else","arguments":{}}})
        unknown_method = texture_mcp.handle_message({"jsonrpc":"2.0","id":2,"method":"not/a/method"})
        self.assertEqual(unknown_tool["error"]["code"], -32602)
        self.assertEqual(unknown_method["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
