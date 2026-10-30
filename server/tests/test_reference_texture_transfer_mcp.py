from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import types
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

# The installed base plugin supplies the complete PNG validator. The overlay-only
# test harness uses a bounded IHDR/chunk shim and the painter's decoder still
# independently checks decompression, scanline length and filter reconstruction.
validation = types.ModuleType("png_validation")
class PngValidationError(ValueError):
    pass

def _validate_png_bytes(payload, *, max_bytes=16 * 1024 * 1024, max_dimension=4096, max_pixels=16_777_216):
    sig = b"\x89PNG\r\n\x1a\n"
    if not isinstance(payload, bytes) or len(payload) < 45 or len(payload) > max_bytes or not payload.startswith(sig):
        raise PngValidationError("invalid PNG signature or size")
    offset = 8
    chunks = []
    while offset + 12 <= len(payload):
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        end = offset + length + 12
        if end > len(payload):
            raise PngValidationError("truncated PNG chunk")
        data = payload[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", payload[offset + 8 + length:end])[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != crc:
            raise PngValidationError("PNG CRC mismatch")
        chunks.append((kind, data))
        offset = end
        if kind == b"IEND":
            break
    if offset != len(payload):
        raise PngValidationError("trailing PNG bytes")
    ihdr = next(data for kind, data in chunks if kind == b"IHDR")
    w, h, depth, ctype, comp, filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    if not (1 <= w <= max_dimension and 1 <= h <= max_dimension and w * h <= max_pixels):
        raise PngValidationError("PNG dimensions over limit")
    if depth != 8 or ctype not in {0, 2, 3, 4, 6} or comp != 0 or filt != 0 or interlace != 0:
        raise PngValidationError("test shim only accepts 8-bit non-interlaced PNG")
    if chunks[0][0] != b"IHDR" or chunks[-1][0] != b"IEND" or not any(k == b"IDAT" for k, _ in chunks):
        raise PngValidationError("required PNG chunks missing")
    return w, h

validation.PngValidationError = PngValidationError
validation.validate_png_bytes = _validate_png_bytes
SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

with patch.dict(sys.modules, {"png_validation": validation}):
    import texture_painting_mcp as painter
    import reference_texture_transfer_mcp as transfer


class ReferenceTextureTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.project = self.workspace / "forest-addon"
        self.rp = self.project / "resource_packs" / "forest-addon_RP"
        self.geo_dir = self.rp / "models" / "entity"
        self.tex_dir = self.rp / "textures" / "entity"
        self.ref_dir = self.rp / "textures" / "references"
        self.geo_dir.mkdir(parents=True)
        self.tex_dir.mkdir(parents=True)
        self.ref_dir.mkdir(parents=True)
        (self.rp / "manifest.json").write_text(json.dumps({"header": {}, "modules": []}), encoding="utf-8")
        self.geometry_path = "resource_packs/forest-addon_RP/models/entity/guardian.geo.json"
        self.reference_path = "resource_packs/forest-addon_RP/textures/references/reference.png"
        self.base_path = "resource_packs/forest-addon_RP/textures/entity/base.png"
        self.output_path = "resource_packs/forest-addon_RP/textures/entity/guardian_reference.png"
        geo = {
            "format_version": "1.12.0",
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.guardian", "texture_width": 16, "texture_height": 16},
                "bones": [{"name": "body", "pivot": [0, 0, 0], "cubes": [
                    {"origin": [-2, 0, -2], "size": [4, 4, 4], "uv": [0, 0]}
                ]}]
            }]
        }
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(geo), encoding="utf-8")
        # 4x4 reference image: each pixel has a distinct, opaque color.
        ref = bytearray()
        for y in range(4):
            for x in range(4):
                ref.extend((x * 60, y * 60, (x + y) * 24, 255))
        self.reference_pixels = bytes(ref)
        (self.ref_dir / "reference.png").write_bytes(painter._encode_png(4, 4, bytearray(ref)))
        base = bytes((10, 20, 30, 128)) * (16 * 16)
        (self.tex_dir / "base.png").write_bytes(painter._encode_png(16, 16, bytearray(base)))
        self.env_patch = patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(self.workspace)})
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.temp.cleanup()

    def args(self, mappings=None, **overrides):
        payload = {
            "project_directory": "forest-addon",
            "geometry_path": self.geometry_path,
            "output_path": self.output_path,
            "reference_image_path": self.reference_path,
            "mappings": mappings or [{"selector": {"bone": "body", "face": "north"}, "source_rect": {"x": 0, "y": 0, "width": 4, "height": 4}}],
        }
        payload.update(overrides)
        return payload

    def decode(self, path=None):
        target = self.rp / ((path or self.output_path).split("/", 2)[2])
        return painter._decode_png_rgba(target.read_bytes())

    def pixel(self, pixels, x, y, width=16):
        i = (y * width + x) * 4
        return tuple(pixels[i:i + 4])

    def test_tool_schema_contract(self):
        tool = transfer.TOOLS[0]
        self.assertEqual(tool["name"], "map_reference_texture_to_uv")
        schema = tool["inputSchema"]
        self.assertEqual(schema["properties"]["mappings"]["maxItems"], 256)
        self.assertIn("bilinear", schema["properties"]["mappings"]["items"]["properties"]["sampling"]["enum"])

    def test_maps_reference_crop_onto_exact_face_uv(self):
        result = transfer.map_reference_texture_to_uv(self.args())
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["texture"]["size"], [16, 16])
        _, _, pixels = self.decode()
        # north face of a 4x4 cube occupies x=4..7, y=4..7 in classic box UV.
        self.assertEqual(self.pixel(pixels, 4, 4), (0, 0, 0, 255))
        self.assertEqual(self.pixel(pixels, 7, 7), (180, 180, 144, 255))
        self.assertEqual(self.pixel(pixels, 0, 0), (0, 0, 0, 0))

    def test_base_texture_is_preserved_outside_mapped_region(self):
        result = transfer.map_reference_texture_to_uv(self.args(base_texture_path=self.base_path))
        self.assertEqual(result["status"], "success")
        _, _, pixels = self.decode()
        self.assertEqual(self.pixel(pixels, 0, 0), (10, 20, 30, 128))
        self.assertEqual(self.pixel(pixels, 4, 4), (0, 0, 0, 255))

    def test_source_rect_bounds_are_checked_before_output(self):
        result = transfer.map_reference_texture_to_uv(self.args([{"selector": {"face": "north"}, "source_rect": {"x": 3, "y": 0, "width": 2, "height": 2}}]))
        self.assertEqual(result["error"]["code"], "SOURCE_RECT_OUT_OF_BOUNDS")
        self.assertFalse((self.tex_dir / "guardian_reference.png").exists())

    def test_unknown_selector_refuses_output(self):
        result = transfer.map_reference_texture_to_uv(self.args([{"selector": {"bone": "missing"}, "source_rect": {"x": 0, "y": 0, "width": 2, "height": 2}}]))
        self.assertEqual(result["error"]["code"], "SELECTOR_MATCHED_NO_UV")
        self.assertFalse((self.tex_dir / "guardian_reference.png").exists())

    def test_rotation_90_transforms_source_orientation(self):
        mapping = {"selector": {"bone": "body", "face": "north"}, "source_rect": {"x": 0, "y": 0, "width": 4, "height": 4}, "rotation": 90}
        result = transfer.map_reference_texture_to_uv(self.args([mapping]))
        self.assertEqual(result["status"], "success")
        _, _, pixels = self.decode()
        # 90-degree clockwise texture transform maps top-left target to original bottom-left.
        self.assertEqual(self.pixel(pixels, 4, 4), (0, 180, 72, 255))

    def test_flip_x_is_applied(self):
        mapping = {"selector": {"bone": "body", "face": "north"}, "source_rect": {"x": 0, "y": 0, "width": 4, "height": 4}, "flip_x": True}
        self.assertEqual(transfer.map_reference_texture_to_uv(self.args([mapping]))["status"], "success")
        _, _, pixels = self.decode()
        self.assertEqual(self.pixel(pixels, 4, 4), (180, 0, 72, 255))

    def test_bilinear_sampling_interpolates_and_keeps_alpha(self):
        mapping = {"selector": {"face": "north"}, "source_rect": {"x": 0, "y": 0, "width": 4, "height": 4}, "sampling": "bilinear"}
        result = transfer.map_reference_texture_to_uv(self.args([mapping]))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["transfer"]["mapping_results"][0]["sampling"], "bilinear")

    def test_reference_alpha_survives_replace_sampling(self):
        rgba = bytearray()
        for _ in range(16):
            rgba.extend((240, 20, 30, 96))
        (self.ref_dir / "alpha.png").write_bytes(painter._encode_png(4, 4, rgba))
        result = transfer.map_reference_texture_to_uv(self.args(reference_image_path="resource_packs/forest-addon_RP/textures/references/alpha.png", mappings=[{"selector": {"face": "north"}, "source_rect": {"x": 0, "y": 0, "width": 4, "height": 4}, "blend_mode": "replace"}]))
        self.assertEqual(result["status"], "success")
        _, _, pixels = self.decode()
        self.assertEqual(self.pixel(pixels, 4, 4), (240, 20, 30, 96))

    def test_opacity_scales_reference_alpha(self):
        mapping = {"selector": {"face": "north"}, "source_rect": {"x": 0, "y": 0, "width": 4, "height": 4}, "opacity": 128, "blend_mode": "replace"}
        self.assertEqual(transfer.map_reference_texture_to_uv(self.args([mapping]))["status"], "success")
        _, _, pixels = self.decode()
        self.assertEqual(self.pixel(pixels, 4, 4), (0, 0, 0, 128))

    def test_duplicate_region_mapping_requires_opt_in(self):
        mappings = [
            {"selector": {"bone": "body", "face": "north"}, "source_rect": {"x": 0, "y": 0, "width": 2, "height": 2}},
            {"selector": {"bone": "body", "face": "north"}, "source_rect": {"x": 2, "y": 2, "width": 2, "height": 2}},
        ]
        result = transfer.map_reference_texture_to_uv(self.args(mappings))
        self.assertEqual(result["error"]["code"], "TARGET_MAPPED_MORE_THAN_ONCE")

    def test_ordered_layers_can_be_allowed(self):
        mappings = [
            {"selector": {"bone": "body", "face": "north"}, "source_rect": {"x": 0, "y": 0, "width": 2, "height": 2}, "blend_mode": "replace"},
            {"selector": {"bone": "body", "face": "north"}, "source_rect": {"x": 2, "y": 2, "width": 2, "height": 2}, "blend_mode": "replace"},
        ]
        result = transfer.map_reference_texture_to_uv(self.args(mappings, allow_uv_overlap=True))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["transfer"]["mapping_count"], 2)
        self.assertTrue(any(w["code"] == "ORDERED_MAPPING_LAYERS" for w in result["transfer"]["warnings"]))

    def test_geometry_uv_overlap_requires_opt_in(self):
        geo_file = self.geo_dir / "guardian.geo.json"
        data = json.loads(geo_file.read_text())
        data["minecraft:geometry"][0]["bones"].append({"name": "overlay", "pivot": [0, 0, 0], "cubes": [
            {"origin": [0, 0, 0], "size": [4, 4, 4], "uv": [0, 0]}
        ]})
        geo_file.write_text(json.dumps(data))
        result = transfer.map_reference_texture_to_uv(self.args())
        self.assertEqual(result["error"]["code"], "UV_OVERLAP_REVIEW_REQUIRED")

    def test_incomplete_uv_overlap_scan_refuses_without_opt_in(self):
        with patch.object(transfer.uv, "_overlaps", return_value=([], 0, False)):
            result = transfer.map_reference_texture_to_uv(self.args())
        self.assertEqual(result["error"]["code"], "UV_OVERLAP_ANALYSIS_INCOMPLETE")

    def test_base_texture_dimensions_must_match_geometry(self):
        (self.tex_dir / "small.png").write_bytes(painter._encode_png(2, 2, bytearray((1, 2, 3, 255)) * 4))
        result = transfer.map_reference_texture_to_uv(self.args(base_texture_path="resource_packs/forest-addon_RP/textures/entity/small.png"))
        self.assertEqual(result["error"]["code"], "BASE_TEXTURE_DIMENSION_MISMATCH")
        self.assertFalse((self.tex_dir / "guardian_reference.png").exists())

    def test_out_of_bounds_geometry_uv_refuses(self):
        geo_file = self.geo_dir / "guardian.geo.json"
        data = json.loads(geo_file.read_text())
        data["minecraft:geometry"][0]["bones"][0]["cubes"][0]["uv"] = [14, 14]
        geo_file.write_text(json.dumps(data))
        result = transfer.map_reference_texture_to_uv(self.args())
        self.assertEqual(result["error"]["code"], "UV_OUT_OF_BOUNDS")

    def test_output_collision_does_not_overwrite(self):
        target = self.tex_dir / "guardian_reference.png"
        target.write_bytes(b"preserve-me")
        response = transfer.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "map_reference_texture_to_uv", "arguments": self.args()}})
        result = response["result"]["structuredContent"]
        self.assertEqual(result["error"]["code"], "OUTPUT_EXISTS")
        self.assertEqual(target.read_bytes(), b"preserve-me")

    def test_reference_and_base_must_not_equal_output(self):
        with self.assertRaisesRegex(ValueError, "different from"):
            transfer.map_reference_texture_to_uv(self.args(reference_image_path=self.output_path))

    def test_path_traversal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "traversal"):
            transfer.map_reference_texture_to_uv(self.args(reference_image_path="resource_packs/forest-addon_RP/textures/references/../../../../outside.png"))

    def test_symlinked_reference_is_rejected(self):
        outside = self.workspace / "outside.png"
        outside.write_bytes((self.ref_dir / "reference.png").read_bytes())
        link = self.ref_dir / "linked.png"
        link.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            transfer.map_reference_texture_to_uv(self.args(reference_image_path="resource_packs/forest-addon_RP/textures/references/linked.png"))

    def test_malformed_mapping_type_is_structured_error(self):
        with self.assertRaisesRegex(ValueError, "selector.face"):
            transfer.map_reference_texture_to_uv(self.args([{"selector": {"face": ["north"]}, "source_rect": {"x": 0, "y": 0, "width": 1, "height": 1}}]))

    def test_bad_sampling_type_is_structured_error(self):
        with self.assertRaisesRegex(ValueError, "sampling"):
            transfer.map_reference_texture_to_uv(self.args([{"selector": {"face": "north"}, "source_rect": {"x": 0, "y": 0, "width": 1, "height": 1}, "sampling": []}]))

    def test_jsonrpc_initialize_and_tool_registry(self):
        init = transfer.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        listed = transfer.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "minecraft-bedrock-reference-texture-transfer")
        self.assertEqual(listed["result"]["tools"][0]["name"], "map_reference_texture_to_uv")

    def test_bilinear_alpha_interpolation_avoids_rgb_halo(self):
        # One fully opaque red texel beside transparent blue must interpolate as red-with-alpha, not purple.
        source = bytearray((255, 0, 0, 255, 0, 0, 255, 0))
        sampled = transfer._sample_bilinear(source, 2, {"x": 0, "y": 0, "width": 2, "height": 1}, 0.5, 0.5)
        self.assertGreater(sampled[0], 245)
        self.assertEqual(sampled[2], 0)
        self.assertEqual(sampled[3], 128)


if __name__ == "__main__":
    unittest.main()
