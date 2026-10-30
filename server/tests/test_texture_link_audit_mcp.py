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
import texture_link_audit_mcp as audit_mcp


def png_bytes(width: int = 16, height: int = 16, *, idat_payload: bytes | None = None) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    rows = b"".join(b"\x00" + bytes([96, 128, 160, 255]) * width for _ in range(height))
    compressed = zlib.compress(rows) if idat_payload is None else idat_payload
    return audit_mcp.PNG_SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


class TextureLinkAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.project_name = "ruby-addon"
        self.project = self.workspace / self.project_name
        self.bp = self.project / "behavior_packs" / f"{self.project_name}_BP"
        self.rp = self.project / "resource_packs" / f"{self.project_name}_RP"
        (self.bp / "blocks").mkdir(parents=True)
        (self.bp / "items").mkdir(parents=True)
        (self.rp / "textures" / "blocks").mkdir(parents=True)
        (self.rp / "textures" / "items").mkdir(parents=True)
        for pack in (self.bp, self.rp):
            (pack / "manifest.json").write_text(json.dumps({"format_version": 2, "header": {"uuid": "00000000-0000-4000-8000-000000000001"}}), encoding="utf-8")
        (self.rp / "textures" / "blocks" / "ruby_ore.png").write_bytes(png_bytes())
        (self.rp / "textures" / "items" / "ruby_gem.png").write_bytes(png_bytes(32, 32))
        self.terrain = {
            "resource_pack_name": "ruby-addon",
            "texture_name": "atlas.terrain",
            "texture_data": {"ruby_ore": {"textures": "textures/blocks/ruby_ore"}},
        }
        self.item_atlas = {
            "resource_pack_name": "ruby-addon",
            "texture_name": "atlas.items",
            "texture_data": {"ruby_gem": {"textures": "textures/items/ruby_gem"}},
        }
        (self.rp / "textures" / "terrain_texture.json").write_text(json.dumps(self.terrain), encoding="utf-8")
        (self.rp / "textures" / "item_texture.json").write_text(json.dumps(self.item_atlas), encoding="utf-8")
        block = {
            "format_version": "1.26.30",
            "minecraft:block": {
                "description": {"identifier": "ruby:addon_ore"},
                "components": {
                    "minecraft:geometry": "minecraft:geometry.full_block",
                    "minecraft:material_instances": {"*": {"texture": "ruby_ore", "render_method": "opaque"}},
                },
            },
        }
        item = {
            "format_version": "1.26.30",
            "minecraft:item": {
                "description": {"identifier": "ruby:gem"},
                "components": {"minecraft:icon": {"textures": {"default": "ruby_gem"}}},
            },
        }
        (self.bp / "blocks" / "ruby_ore.block.json").write_text(json.dumps(block), encoding="utf-8")
        (self.bp / "items" / "ruby_gem.json").write_text(json.dumps(item), encoding="utf-8")
        env_patch = patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(self.workspace)})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def _call(self, arguments=None):
        args = {"project_directory": self.project_name}
        if arguments:
            args.update(arguments)
        return audit_mcp.handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "audit_texture_links", "arguments": args},
        })

    def _payload(self, arguments=None):
        return self._call(arguments)["result"]["structuredContent"]

    def test_registers_read_only_tool_with_closed_schema(self):
        listed = audit_mcp.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = listed["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["audit_texture_links"])
        schema = tools[0]["inputSchema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertTrue(tools[0]["annotations"]["readOnlyHint"])
        self.assertTrue(tools[0]["annotations"]["idempotentHint"])

    def test_healthy_block_and_item_chain_completes(self):
        result = self._payload()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["summary"]["errors"], 0)
        self.assertEqual(result["summary"]["block_texture_references"], 1)
        self.assertEqual(result["summary"]["item_texture_references"], 1)
        self.assertEqual(result["summary"]["terrain_atlas_entries"], 1)
        self.assertEqual(result["summary"]["item_atlas_entries"], 1)
        self.assertTrue(result["summary"]["analysis_complete"])
        self.assertEqual(result["summary"]["unique_png_files_inspected"], 2)
        self.assertEqual(result["runtime_status"], "NOT RUN")
        self.assertTrue(any(x["code"] == "TEXTURE_LINK_OK" for x in result["findings"]))

    def test_detects_missing_block_atlas_key(self):
        block_path = self.bp / "blocks" / "ruby_ore.block.json"
        block = json.loads(block_path.read_text(encoding="utf-8"))
        block["minecraft:block"]["components"]["minecraft:material_instances"]["*"]["texture"] = "missing_key"
        block_path.write_text(json.dumps(block), encoding="utf-8")
        result = self._payload()
        self.assertEqual(result["status"], "issues_found")
        self.assertTrue(any(x["code"] == "MISSING_ATLAS_KEY" and "missing_key" in x["message"] for x in result["findings"]))

    def test_detects_missing_item_atlas_key_with_legacy_string_icon(self):
        item_path = self.bp / "items" / "ruby_gem.json"
        item = json.loads(item_path.read_text(encoding="utf-8"))
        item["minecraft:item"]["components"]["minecraft:icon"] = "unknown_icon"
        item_path.write_text(json.dumps(item), encoding="utf-8")
        result = self._payload()
        self.assertTrue(any(x["code"] == "MISSING_ATLAS_KEY" and "unknown_icon" in x["message"] for x in result["findings"]))

    def test_detects_missing_png_referenced_by_atlas(self):
        self.terrain["texture_data"]["ruby_ore"]["textures"] = "textures/blocks/not_there"
        (self.rp / "textures" / "terrain_texture.json").write_text(json.dumps(self.terrain), encoding="utf-8")
        result = self._payload()
        self.assertTrue(any(x["code"] == "BROKEN_ATLAS_TEXTURE" and "not_there" in x["message"] for x in result["findings"]))

    def test_detects_corrupt_png_crc(self):
        path = self.rp / "textures" / "blocks" / "ruby_ore.png"
        payload = bytearray(path.read_bytes())
        offset = len(audit_mcp.PNG_SIGNATURE)
        while offset < len(payload):
            length = struct.unpack(">I", payload[offset:offset + 4])[0]
            kind = bytes(payload[offset + 4:offset + 8])
            if kind == b"IDAT" and length:
                payload[offset + 8] ^= 0x01  # leave the stored CRC unchanged
                break
            offset += length + 12
        path.write_bytes(payload)
        result = self._payload()
        self.assertTrue(any(x["code"] == "BROKEN_ATLAS_TEXTURE" and "CRC" in x["message"] for x in result["findings"]))

    def test_detects_valid_crc_with_corrupt_png_image_stream(self):
        path = self.rp / "textures" / "blocks" / "ruby_ore.png"
        path.write_bytes(png_bytes(idat_payload=b"not a zlib stream"))
        result = self._payload()
        finding = next(x for x in result["findings"] if x["code"] == "BROKEN_ATLAS_TEXTURE" and "ruby_ore" in x["message"])
        self.assertIn("compression stream", finding["message"])
        self.assertEqual(result["status"], "issues_found")

    def test_detects_duplicate_json_keys_in_atlas(self):
        atlas = self.rp / "textures" / "terrain_texture.json"
        atlas.write_text('{"texture_name":"atlas.terrain","texture_data":{},"texture_data":{}}', encoding="utf-8")
        result = self._payload()
        self.assertTrue(any(x["code"] == "INVALID_ATLAS_JSON" and "duplicate" in x["message"] for x in result["findings"]))

    def test_detects_duplicate_json_keys_in_definition(self):
        path = self.bp / "blocks" / "ruby_ore.block.json"
        path.write_text('{"minecraft:block":{"components":{},"components":{}}}', encoding="utf-8")
        result = self._payload()
        self.assertTrue(any(x["code"] == "INVALID_DEFINITION_JSON" and "duplicate" in x["message"] for x in result["findings"]))

    def test_rejects_atlas_path_traversal(self):
        self.terrain["texture_data"]["ruby_ore"]["textures"] = "textures/blocks/../../outside"
        (self.rp / "textures" / "terrain_texture.json").write_text(json.dumps(self.terrain), encoding="utf-8")
        result = self._payload()
        self.assertTrue(any(x["code"] == "BROKEN_ATLAS_TEXTURE" and "traversal" in x["message"] for x in result["findings"]))

    def test_reports_unused_atlas_entries_as_warning(self):
        self.terrain["texture_data"]["unused_texture"] = {"textures": "textures/blocks/ruby_ore"}
        (self.rp / "textures" / "terrain_texture.json").write_text(json.dumps(self.terrain), encoding="utf-8")
        result = self._payload()
        self.assertTrue(any(x["code"] == "UNUSED_ATLAS_ENTRY" and "unused_texture" in x["message"] for x in result["findings"]))

    def test_reuses_png_validation_for_multiple_atlas_keys(self):
        self.terrain["texture_data"]["ruby_ore_alias"] = {"textures": "textures/blocks/ruby_ore"}
        (self.rp / "textures" / "terrain_texture.json").write_text(json.dumps(self.terrain), encoding="utf-8")
        result = self._payload()
        self.assertEqual(result["summary"]["unique_png_files_inspected"], 2)
        self.assertEqual(result["summary"]["png_bytes_inspected"], sum(
            (self.rp / "textures" / category / name).stat().st_size
            for category, name in (("blocks", "ruby_ore.png"), ("items", "ruby_gem.png"))
        ))

    def test_reports_incomplete_analysis_when_png_budget_is_exhausted(self):
        with patch.object(audit_mcp, "MAX_TOTAL_PNG_BYTES", 1):
            result = self._payload()
        self.assertFalse(result["summary"]["analysis_complete"])
        self.assertTrue(any(x["code"] == "ATLAS_KEY_NOT_VALIDATED" for x in result["findings"]))

    def test_reports_incomplete_analysis_when_atlas_entry_limit_is_exceeded(self):
        self.terrain["texture_data"]["zzz_extra"] = {"textures": "textures/blocks/ruby_ore"}
        (self.rp / "textures" / "terrain_texture.json").write_text(json.dumps(self.terrain), encoding="utf-8")
        with patch.object(audit_mcp, "MAX_ATLAS_ENTRIES", 1):
            result = self._payload()
        self.assertFalse(result["summary"]["analysis_complete"])
        self.assertTrue(any(x["code"] == "ATLAS_ENTRY_SCAN_LIMIT" for x in result["findings"]))

    def test_rejects_symlinked_project(self):
        linked = self.workspace / "linked-addon"
        try:
            linked.symlink_to(self.project, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        result = self._payload({"project_directory": "linked-addon"})
        self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")

    def test_refuses_path_like_project_directory_and_extra_arguments(self):
        path_result = self._payload({"project_directory": "../outside"})
        extra_result = self._payload({"unexpected": True})
        self.assertEqual(path_result["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(extra_result["error"]["code"], "INVALID_ARGUMENT")

    def test_missing_atlas_is_reported_without_mutation(self):
        atlas = self.rp / "textures" / "terrain_texture.json"
        before = atlas.read_bytes()
        atlas.unlink()
        result = self._payload()
        self.assertTrue(any(x["code"] == "ATLAS_MISSING" for x in result["findings"]))
        self.assertFalse(atlas.exists())
        self.assertEqual(before, json.dumps(self.terrain).encode("utf-8"))

    def test_refuses_symlinked_resource_pack_textures_directory(self):
        textures = self.rp / "textures"
        outside = self.workspace / "outside-textures"
        outside.mkdir()
        backup = self.rp / "textures-original"
        textures.rename(backup)
        try:
            textures.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            backup.rename(textures)
            self.skipTest(f"symlinks unavailable: {exc}")
        result = self._payload()
        self.assertTrue(any(x["code"] == "UNSAFE_TEXTURES_DIRECTORY" for x in result["findings"]))
        self.assertFalse(any(x["code"] == "TEXTURE_LINK_OK" for x in result["findings"]))

    def test_invalid_json_shape_is_reported(self):
        atlas = self.rp / "textures" / "item_texture.json"
        atlas.write_text(json.dumps({"texture_name": "wrong", "texture_data": {}}), encoding="utf-8")
        result = self._payload()
        self.assertTrue(any(x["code"] == "INVALID_ATLAS_SHAPE" and "atlas.items" in x["message"] for x in result["findings"]))

    def test_jsonrpc_notifications_and_unknown_tool(self):
        notification = audit_mcp.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        unknown = audit_mcp.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "not_a_tool", "arguments": {}}})
        self.assertIsNone(notification)
        self.assertEqual(unknown["error"]["code"], -32602)


if __name__ == "__main__":
    unittest.main()
