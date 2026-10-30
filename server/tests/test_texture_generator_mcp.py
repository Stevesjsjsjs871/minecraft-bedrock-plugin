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
            "import struct, zlib\n"
            "PNG_SIGNATURE = b'\\x89PNG\\r\\n\\x1a\\n'\n"
            "def chunk(kind, data):\n"
            "    body = kind + data\n"
            "    return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)\n"
            "def write_texture(output, *, width=16, height=16, style='pixel_noise', base_color='#777777', accent_color='#A0A0A0', seed=1, alpha=255, force=False):\n"
            "    path = Path(output)\n"
            "    if path.exists() and not force: raise FileExistsError(path)\n"
            "    rgb = bytes.fromhex(base_color.removeprefix('#'))\n"
            "    pixel = rgb + bytes([alpha])\n"
            "    rgba = pixel * (width * height)\n"
            "    stride = width * 4\n"
            "    scanlines = b''.join(b'\\x00' + rgba[y * stride:(y + 1) * stride] for y in range(height))\n"
            "    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)\n"
            "    payload = PNG_SIGNATURE + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b'')\n"
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
        lock_path = atlas_path.with_name(f".{atlas_path.name}.mbe.lock")
        self.assertFalse(lock_path.exists(), "atlas lock must be released after a successful write")
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
        self.assertFalse(atlas.with_name(f".{atlas.name}.mbe.lock").exists())

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

    @staticmethod
    def _png_chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    @classmethod
    def _png_from_chunks(cls, chunks):
        return PNG_SIGNATURE + b"".join(cls._png_chunk(kind, data) for kind, data in chunks)

    @staticmethod
    def _extract_png_chunks(png):
        chunks = []
        offset = len(PNG_SIGNATURE)
        while offset < len(png):
            length = struct.unpack(">I", png[offset:offset + 4])[0]
            kind = png[offset + 4:offset + 8]
            data = png[offset + 8:offset + 8 + length]
            chunks.append((kind, data))
            offset += length + 12
        return chunks

    def _assert_png_rejected(self, png_bytes):
        path = self.workspace / "invalid.png"
        path.write_bytes(png_bytes)
        with self.assertRaises(texture_mcp.AtlasToolError) as caught:
            texture_mcp._read_valid_png(path)
        self.assertEqual(caught.exception.code, "INVALID_PNG")

    def test_png_validator_rejects_invalid_ihdr_metadata(self):
        valid_path = self._generate_real_png()
        chunks = self._extract_png_chunks(valid_path.read_bytes())
        ihdr = bytearray(chunks[0][1])
        for index, value in ((8, 3), (10, 1), (11, 1), (12, 2)):
            mutated = bytearray(ihdr)
            mutated[index] = value
            self._assert_png_rejected(self._png_from_chunks([(b"IHDR", bytes(mutated)), *chunks[1:]]))

    def test_png_validator_rejects_corrupt_idat_even_with_a_valid_crc(self):
        valid_path = self._generate_real_png()
        chunks = self._extract_png_chunks(valid_path.read_bytes())
        replaced = [(kind, b"not-zlib-data" if kind == b"IDAT" else data) for kind, data in chunks]
        self._assert_png_rejected(self._png_from_chunks(replaced))

    def test_png_validator_rejects_invalid_scanline_filter_and_extra_stream_data(self):
        valid_path = self._generate_real_png(width=4, height=2)
        chunks = self._extract_png_chunks(valid_path.read_bytes())
        ihdr = chunks[0][1]
        # RGBA: each row has a one-byte filter marker plus 4 * 4 pixel bytes.
        invalid_filter = zlib.compress(b"\x05" + bytes(16) + b"\x00" + bytes(16))
        self._assert_png_rejected(self._png_from_chunks([(b"IHDR", ihdr), (b"IDAT", invalid_filter), (b"IEND", b"")]))
        normal_idat = next(data for kind, data in chunks if kind == b"IDAT")
        self._assert_png_rejected(self._png_from_chunks([(b"IHDR", ihdr), (b"IDAT", normal_idat + b"trailing"), (b"IEND", b"")]))

    def test_png_validator_rejects_unknown_critical_and_nonconsecutive_idat(self):
        valid_path = self._generate_real_png()
        chunks = self._extract_png_chunks(valid_path.read_bytes())
        unknown_critical = [chunks[0], (b"ABCD", b"x"), *chunks[1:]]
        self._assert_png_rejected(self._png_from_chunks(unknown_critical))
        idat = next(data for kind, data in chunks if kind == b"IDAT")
        midpoint = max(1, len(idat) // 2)
        nonconsecutive = [chunks[0], (b"IDAT", idat[:midpoint]), (b"tEXt", b"k\x00v"), (b"IDAT", idat[midpoint:]), (b"IEND", b"")]
        self._assert_png_rejected(self._png_from_chunks(nonconsecutive))

    def test_png_validator_rejects_idat_expansion_beyond_declared_dimensions(self):
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
        oversized_scanlines = zlib.compress(b"\x00" + bytes(64 * 1024))
        png = self._png_from_chunks([(b"IHDR", ihdr), (b"IDAT", oversized_scanlines), (b"IEND", b"")])
        self._assert_png_rejected(png)

    def test_png_validator_rejects_misordered_palette_and_empty_indexed_transparency(self):
        valid_path = self._generate_real_png()
        chunks = self._extract_png_chunks(valid_path.read_bytes())
        ihdr = struct.pack(">IIBBBBB", 2, 1, 1, 3, 0, 0, 0)
        palette = bytes((0, 0, 0, 255, 0, 0))
        image_data = zlib.compress(b"\x00\x40")
        self._assert_png_rejected(self._png_from_chunks([
            (b"IHDR", ihdr), (b"IDAT", image_data), (b"PLTE", palette), (b"IEND", b"")
        ]))
        self._assert_png_rejected(self._png_from_chunks([
            (b"IHDR", ihdr), (b"PLTE", palette), (b"tRNS", b""), (b"IDAT", image_data), (b"IEND", b"")
        ]))

    def test_png_validator_accepts_indexed_png_with_palette(self):
        ihdr = struct.pack(">IIBBBBB", 2, 1, 1, 3, 0, 0, 0)
        palette = bytes((0, 0, 0, 255, 0, 0))
        image_data = zlib.compress(b"\x00\x40")  # filter 0, two 1-bit palette indices
        png = self._png_from_chunks([(b"IHDR", ihdr), (b"PLTE", palette), (b"IDAT", image_data), (b"IEND", b"")])
        path = self.workspace / "indexed.png"
        path.write_bytes(png)
        self.assertEqual(texture_mcp._read_valid_png(path), (2, 1))

    def test_png_validator_accepts_adam7_interlaced_rgba_png(self):
        width = height = 8
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 1)
        passes = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))
        rows = bytearray()
        for x0, y0, dx, dy in passes:
            pw = (width - x0 + dx - 1) // dx if width > x0 else 0
            ph = (height - y0 + dy - 1) // dy if height > y0 else 0
            for _ in range(ph):
                rows.extend(b"\x00" + bytes(pw * 4))
        png = self._png_from_chunks([(b"IHDR", ihdr), (b"IDAT", zlib.compress(bytes(rows))), (b"IEND", b"")])
        path = self.workspace / "adam7.png"
        path.write_bytes(png)
        self.assertEqual(texture_mcp._read_valid_png(path), (8, 8))

    def test_registration_refuses_active_atlas_lock_and_releases_own_lock_on_conflict(self):
        self._generate_real_png()
        atlas = self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "terrain_texture.json"
        lock = atlas.with_name(f".{atlas.name}.mbe.lock")
        lock.write_text("active writer", encoding="utf-8")
        busy = self._register()["result"]["structuredContent"]
        self.assertEqual(busy["error"]["code"], "ATLAS_BUSY")
        self.assertFalse(atlas.exists())
        lock.unlink()
        atlas.write_text(json.dumps({"texture_name": "atlas.terrain", "texture_data": {"ruby_ore": {"textures": "elsewhere"}}}), encoding="utf-8")
        conflict = self._register()["result"]["structuredContent"]
        self.assertEqual(conflict["error"]["code"], "IDENTIFIER_CONFLICT")
        self.assertFalse(lock.exists(), "atlas lock must be released after a failed registration")

    def test_registration_rejects_duplicate_json_keys_without_mutation(self):
        self._generate_real_png()
        atlas = self.project / "resource_packs" / f"{self.project_name}_RP" / "textures" / "terrain_texture.json"
        original = b'{"texture_name":"atlas.terrain","texture_data":{},"texture_data":{"keep":{"textures":"textures/blocks/keep"}}}'
        atlas.write_bytes(original)
        result = self._register()["result"]["structuredContent"]
        self.assertEqual(result["error"]["code"], "INVALID_ATLAS")
        self.assertEqual(atlas.read_bytes(), original)

    def test_unknown_tool_and_unknown_method_return_protocol_errors(self):
        unknown_tool = texture_mcp.handle_message({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"something_else","arguments":{}}})
        unknown_method = texture_mcp.handle_message({"jsonrpc":"2.0","id":2,"method":"not/a/method"})
        self.assertEqual(unknown_tool["error"]["code"], -32602)
        self.assertEqual(unknown_method["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
