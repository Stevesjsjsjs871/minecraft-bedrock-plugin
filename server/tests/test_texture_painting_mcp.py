from __future__ import annotations

import json
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
import sys
import types

# The production package already contains its shared PNG validator. The isolated
# overlay suite may have injected the UV-audit IHDR-only shim before this module;
# extend that test-local shim without affecting the production implementation.
validation = sys.modules.get("png_validation") or types.ModuleType("png_validation")
if not hasattr(validation, "PngValidationError"):
    class PngValidationError(ValueError):
        pass
    validation.PngValidationError = PngValidationError
if not hasattr(validation, "validate_png_bytes"):
    def validate_png_bytes(payload, *, max_bytes=16 * 1024 * 1024, max_dimension=4096, max_pixels=16_777_216):
        if not payload.startswith(b"\x89PNG\r\n\x1a\n") or len(payload) > max_bytes:
            raise validation.PngValidationError("invalid PNG signature or size")
        offset = 8
        chunks = []
        while offset + 12 <= len(payload):
            length = struct.unpack(">I", payload[offset:offset + 4])[0]
            kind = payload[offset + 4:offset + 8]
            end = offset + length + 12
            if end > len(payload):
                raise validation.PngValidationError("truncated PNG")
            data = payload[offset + 8:offset + 8 + length]
            crc = struct.unpack(">I", payload[offset + 8 + length:end])[0]
            if zlib.crc32(kind + data) & 0xFFFFFFFF != crc:
                raise validation.PngValidationError("PNG CRC mismatch")
            chunks.append((kind, data))
            offset = end
            if kind == b"IEND":
                break
        ihdr = next(data for kind, data in chunks if kind == b"IHDR")
        w, h, depth, ctype, comp, filt, interlace = struct.unpack(">IIBBBBB", ihdr)
        if not (1 <= w <= max_dimension and 1 <= h <= max_dimension and w * h <= max_pixels):
            raise validation.PngValidationError("PNG dimensions over limit")
        if depth not in {1, 2, 4, 8, 16} or ctype not in {0, 2, 3, 4, 6} or interlace not in {0, 1}:
            raise validation.PngValidationError("invalid PNG IHDR")
        return w, h
    validation.validate_png_bytes = validate_png_bytes
if not hasattr(validation, "validate_png_file"):
    validation.validate_png_file = lambda path, **kwargs: validation.validate_png_bytes(path.read_bytes(), **kwargs)
sys.modules["png_validation"] = validation

import texture_painting_mcp as painter


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def simple_png(width: int, height: int, color_type: int, raw_pixels: bytes, *, palette: bytes = b"", transparency: bytes = b"") -> bytes:
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    raw = bytearray()
    stride = width * channels
    for y in range(height):
        raw.append(0)
        raw.extend(raw_pixels[y * stride:(y + 1) * stride])
    chunks = [png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))]
    if palette:
        chunks.append(png_chunk(b"PLTE", palette))
    if transparency:
        chunks.append(png_chunk(b"tRNS", transparency))
    chunks += [png_chunk(b"IDAT", zlib.compress(bytes(raw))), png_chunk(b"IEND", b"")]
    return painter.PNG_SIGNATURE + b"".join(chunks)


class TexturePaintingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.project = self.workspace / "forest-addon"
        self.rp = self.project / "resource_packs" / "forest-addon_RP"
        self.geo_dir = self.rp / "models" / "entity"
        self.tex_dir = self.rp / "textures" / "entity"
        self.geo_dir.mkdir(parents=True)
        self.tex_dir.mkdir(parents=True)
        (self.rp / "manifest.json").write_text(json.dumps({"header": {}, "modules": []}), encoding="utf-8")
        self.geometry_path = "resource_packs/forest-addon_RP/models/entity/guardian.geo.json"
        self.source_path = "resource_packs/forest-addon_RP/textures/entity/base.png"
        self.output_path = "resource_packs/forest-addon_RP/textures/entity/guardian_painted.png"
        geometry = {
            "format_version": "1.12.0",
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.guardian", "texture_width": 16, "texture_height": 16},
                "bones": [{"name": "body", "pivot": [0, 0, 0], "cubes": [
                    {"origin": [-2, 0, -2], "size": [4, 4, 4], "uv": [0, 0]}
                ]}]
            }]
        }
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(geometry), encoding="utf-8")
        base = bytes((10, 20, 30, 128)) * (16 * 16)
        (self.tex_dir / "base.png").write_bytes(painter._encode_png(16, 16, bytearray(base)))
        self.patch = patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(self.workspace)})
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.temp.cleanup()

    def args(self, operations=None, **overrides):
        payload = {
            "project_directory": "forest-addon",
            "geometry_path": self.geometry_path,
            "output_path": self.output_path,
            "source_texture_path": self.source_path,
            "operations": operations or [{"selector": {"bone": "body", "face": "north"}, "mode": "fill", "color": "#FF0000"}],
        }
        payload.update(overrides)
        return payload

    def decode_output(self, path: str | None = None):
        target = self.rp / (path or self.output_path.split("/", 2)[2])
        return painter._decode_png_rgba(target.read_bytes())

    def test_schema_and_tool_contract(self):
        schema = painter.TOOLS[0]["inputSchema"]
        self.assertEqual(painter.TOOLS[0]["name"], "paint_geometry_texture")
        self.assertEqual(schema["properties"]["operations"]["maxItems"], 128)
        self.assertTrue(schema["properties"]["operations"]["items"]["properties"]["selector"]["minProperties"])

    def test_fill_targets_selected_face_and_preserves_unpainted_alpha(self):
        result = painter.paint_geometry_texture(self.args())
        self.assertEqual(result["status"], "success")
        w, h, pixels = self.decode_output()
        self.assertEqual((w, h), (16, 16))
        self.assertEqual(tuple(pixels[(4 * w + 4) * 4:(4 * w + 4) * 4 + 4]), (255, 0, 0, 255))
        self.assertEqual(tuple(pixels[(0 * w + 0) * 4:(0 * w + 0) * 4 + 4]), (10, 20, 30, 128))

    def test_source_alpha_is_preserved_for_zero_opacity(self):
        args = self.args([{ "selector": {"bone": "body", "face": "north"}, "mode": "fill", "color": "#FFFFFF", "opacity": 0 }])
        result = painter.paint_geometry_texture(args)
        self.assertEqual(result["status"], "success")
        _, _, pixels = self.decode_output()
        self.assertEqual(tuple(pixels[4 * (4 * 16 + 4):4 * (4 * 16 + 4) + 4]), (10, 20, 30, 128))

    def test_transparent_canvas_when_no_source_is_given(self):
        args = self.args(source_texture_path=None, operations=[{"selector": {"face": "north"}, "mode": "fill", "color": "#00FF00"}])
        result = painter.paint_geometry_texture(args)
        self.assertEqual(result["status"], "success")
        _, _, pixels = self.decode_output()
        self.assertEqual(tuple(pixels[4 * (4 * 16 + 4):4 * (4 * 16 + 4) + 4]), (0, 255, 0, 255))
        self.assertEqual(tuple(pixels[:4]), (0, 0, 0, 0))

    def test_background_color(self):
        args = self.args(source_texture_path=None, background_color="#11223380", operations=[{"selector": {"face": "north"}, "mode": "fill", "color": "#FFFFFF", "opacity": 0}])
        result = painter.paint_geometry_texture(args)
        self.assertEqual(result["status"], "success")
        _, _, pixels = self.decode_output()
        self.assertEqual(tuple(pixels[:4]), (17, 34, 51, 128))

    def test_checker_pattern_uses_secondary_color(self):
        args = self.args([{"selector": {"face": "north"}, "mode": "checker", "color": "#FF0000", "secondary_color": "#0000FF", "cell_size": 1, "blend_mode": "replace"}], source_texture_path=None)
        self.assertEqual(painter.paint_geometry_texture(args)["status"], "success")
        w, _, px = self.decode_output()
        self.assertEqual(tuple(px[4 * (4 * w + 4):4 * (4 * w + 4) + 4]), (255, 0, 0, 255))
        self.assertEqual(tuple(px[4 * (4 * w + 5):4 * (4 * w + 5) + 4]), (0, 0, 255, 255))

    def test_gradient_interpolates_both_ends(self):
        args = self.args([{"selector": {"face": "north"}, "mode": "gradient", "color": "#000000", "secondary_color": "#FFFFFF", "axis": "x", "blend_mode": "replace"}], source_texture_path=None)
        self.assertEqual(painter.paint_geometry_texture(args)["status"], "success")
        w, _, px = self.decode_output()
        left = tuple(px[4 * (4 * w + 4):4 * (4 * w + 4) + 3])
        right = tuple(px[4 * (4 * w + 7):4 * (4 * w + 7) + 3])
        self.assertEqual(left, (0, 0, 0))
        self.assertEqual(right, (255, 255, 255))

    def test_border_keeps_interior_from_source_when_no_secondary(self):
        args = self.args([{"selector": {"face": "north"}, "mode": "border", "color": "#FFAA00", "border_width": 1}], source_texture_path=self.source_path)
        self.assertEqual(painter.paint_geometry_texture(args)["status"], "success")
        w, _, px = self.decode_output()
        corner = tuple(px[4 * (4 * w + 4):4 * (4 * w + 4) + 4])
        inner = tuple(px[4 * (5 * w + 5):4 * (5 * w + 5) + 4])
        self.assertEqual(corner, (255, 170, 0, 255))
        self.assertEqual(inner, (10, 20, 30, 128))

    def test_noise_is_deterministic(self):
        one = self.args([{"selector": {"face": "north"}, "mode": "noise", "color": "#111111", "secondary_color": "#EEEEEE", "seed": 42}], output_path="resource_packs/forest-addon_RP/textures/entity/one.png", source_texture_path=None)
        two = dict(one, output_path="resource_packs/forest-addon_RP/textures/entity/two.png")
        a = painter.paint_geometry_texture(one)
        b = painter.paint_geometry_texture(two)
        self.assertEqual(a["texture"]["sha256"], b["texture"]["sha256"])

    def test_uv_overlap_requires_explicit_opt_in(self):
        geometry_file = self.geo_dir / "guardian.geo.json"
        data = json.loads(geometry_file.read_text())
        data["minecraft:geometry"][0]["bones"].append({"name": "overlay", "pivot": [0, 0, 0], "cubes": [
            {"origin": [0, 0, 0], "size": [4, 4, 4], "uv": [0, 0]}
        ]})
        geometry_file.write_text(json.dumps(data))
        result = painter.paint_geometry_texture(self.args())
        self.assertEqual(result["error"]["code"], "UV_OVERLAP_REVIEW_REQUIRED")

    def test_uv_overlap_can_be_allowed_and_reported(self):
        geometry_file = self.geo_dir / "guardian.geo.json"
        data = json.loads(geometry_file.read_text())
        data["minecraft:geometry"][0]["bones"].append({"name": "overlay", "pivot": [0, 0, 0], "cubes": [
            {"origin": [0, 0, 0], "size": [4, 4, 4], "uv": [0, 0]}
        ]})
        geometry_file.write_text(json.dumps(data))
        result = painter.paint_geometry_texture(self.args(allow_uv_overlap=True))
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["painting"]["uv_overlap_pairs"], 0)

    def test_uv_out_of_bounds_refuses_to_write(self):
        data = json.loads((self.geo_dir / "guardian.geo.json").read_text())
        data["minecraft:geometry"][0]["bones"][0]["cubes"][0]["uv"] = [15, 15]
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(data))
        result = painter.paint_geometry_texture(self.args())
        self.assertEqual(result["error"]["code"], "UV_OUT_OF_BOUNDS")
        self.assertFalse((self.tex_dir / "guardian_painted.png").exists())

    def test_source_dimensions_must_match_geometry(self):
        (self.tex_dir / "base.png").write_bytes(painter._encode_png(8, 8, bytearray(bytes((0, 0, 0, 255)) * 64)))
        result = painter.paint_geometry_texture(self.args())
        self.assertEqual(result["error"]["code"], "TEXTURE_DIMENSION_MISMATCH")

    def test_existing_output_is_never_overwritten(self):
        target = self.tex_dir / "guardian_painted.png"
        target.write_bytes(b"preserve me")
        with self.assertRaises(FileExistsError):
            painter.paint_geometry_texture(self.args())
        self.assertEqual(target.read_bytes(), b"preserve me")

    def test_invalid_selector_does_not_create_file(self):
        args = self.args([{"selector": {"bone": "missing"}, "mode": "fill", "color": "#FFFFFF"}])
        result = painter.paint_geometry_texture(args)
        self.assertEqual(result["error"]["code"], "SELECTOR_MATCHED_NO_UV")
        self.assertFalse((self.tex_dir / "guardian_painted.png").exists())

    def test_same_source_and_output_is_rejected(self):
        args = self.args(output_path=self.source_path)
        with self.assertRaises(ValueError):
            painter._validate_args(args)

    def test_per_face_uv_is_painted(self):
        data = json.loads((self.geo_dir / "guardian.geo.json").read_text())
        data["minecraft:geometry"][0]["bones"][0]["cubes"][0]["uv"] = {
            "north": {"uv": [1, 1], "uv_size": [4, 4]},
            "south": {"uv": [8, 1], "uv_size": [4, 4]}
        }
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(data))
        args = self.args([{"selector": {"face": "north"}, "mode": "fill", "color": "#123456", "blend_mode": "replace"}], source_texture_path=None)
        self.assertEqual(painter.paint_geometry_texture(args)["status"], "success")
        w, _, px = self.decode_output()
        self.assertEqual(tuple(px[4 * (1 * w + 1):4 * (1 * w + 1) + 4]), (18, 52, 86, 255))

    def test_png_decoder_supports_rgb(self):
        raw = bytes((20, 40, 60)) * 4
        w, h, rgba = painter._decode_png_rgba(simple_png(2, 2, 2, raw))
        self.assertEqual((w, h), (2, 2))
        self.assertEqual(tuple(rgba[:4]), (20, 40, 60, 255))

    def test_png_decoder_supports_gray_and_palette(self):
        _, _, gray = painter._decode_png_rgba(simple_png(1, 1, 0, bytes((90,))))
        self.assertEqual(tuple(gray), (90, 90, 90, 255))
        pal = simple_png(2, 1, 3, bytes((0, 1)), palette=bytes((255, 0, 0, 0, 255, 0)), transparency=bytes((255, 80)))
        _, _, rgba = painter._decode_png_rgba(pal)
        self.assertEqual(tuple(rgba[:4]), (255, 0, 0, 255))
        self.assertEqual(tuple(rgba[4:8]), (0, 255, 0, 80))

    def test_png_decoder_supports_gray_alpha(self):
        _, _, rgba = painter._decode_png_rgba(simple_png(1, 1, 4, bytes((70, 33))))
        self.assertEqual(tuple(rgba), (70, 70, 70, 33))

    def test_png_decoder_rejects_interlace_and_16_bit(self):
        for bit_depth, interlace in ((16, 0), (8, 1)):
            raw = b"\x00" + bytes((0, 0, 0, 255))
            payload = painter.PNG_SIGNATURE + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, bit_depth, 6, 0, 0, interlace)) + png_chunk(b"IDAT", zlib.compress(raw)) + png_chunk(b"IEND", b"")
            with self.assertRaises(ValueError):
                painter._decode_png_rgba(payload)

    def test_path_traversal_is_rejected(self):
        args = self.args(output_path="resource_packs/forest-addon_RP/textures/../../bad.png")
        with self.assertRaises(ValueError):
            painter._validate_args(args)


    def test_partial_opacity_composites_over_source_alpha(self):
        args = self.args([{ "selector": {"face": "north"}, "mode": "fill", "color": "#FF0000", "opacity": 128, "blend_mode": "over" }])
        self.assertEqual(painter.paint_geometry_texture(args)["status"], "success")
        w, _, px = self.decode_output()
        result = tuple(px[4 * (4 * w + 4):4 * (4 * w + 4) + 4])
        self.assertEqual(result[3], 192)
        self.assertGreater(result[0], result[1])

    def test_invalid_enum_types_return_validation_error(self):
        for op in (
            {"selector": {"face": ["north"]}, "mode": "fill", "color": "#FFFFFF"},
            {"selector": {"face": "north"}, "mode": ["fill"], "color": "#FFFFFF"},
            {"selector": {"face": "north"}, "mode": "stripes", "color": "#FFFFFF", "secondary_color": "#000000", "axis": ["x"]},
        ):
            with self.assertRaises(ValueError):
                painter._validate_args(self.args([op]))

    def test_duplicate_geometry_identifier_is_rejected(self):
        geometry_file = self.geo_dir / "guardian.geo.json"
        data = json.loads(geometry_file.read_text())
        data["minecraft:geometry"].append(data["minecraft:geometry"][0])
        geometry_file.write_text(json.dumps(data))
        args = self.args(geometry_identifier="geometry.guardian")
        with self.assertRaisesRegex(ValueError, "duplicated"):
            painter.paint_geometry_texture(args)

    def test_symlinked_source_texture_is_rejected(self):
        alias = self.tex_dir / "alias.png"
        alias.symlink_to(self.tex_dir / "base.png")
        args = self.args(source_texture_path="resource_packs/forest-addon_RP/textures/entity/alias.png")
        with self.assertRaisesRegex(ValueError, "symlink"):
            painter.paint_geometry_texture(args)

    def test_source_decoder_supports_all_png_scanline_filters(self):
        # Five RGB rows exercise PNG filter types 0, 1, 2, 3 and 4.
        source_rows = [bytes((10 + y, 20 + y, 30 + y, 40 + y, 50 + y, 60 + y)) for y in range(5)]
        filtered = bytearray()
        reconstructed_rows = []
        bpp = 3
        for y, row in enumerate(source_rows):
            ftype = y
            prev = reconstructed_rows[y - 1] if y else bytes(len(row))
            encoded = bytearray()
            for x, value in enumerate(row):
                left = row[x - bpp] if x >= bpp else 0
                above = prev[x]
                upper = prev[x - bpp] if x >= bpp else 0
                if ftype == 0:
                    predictor = 0
                elif ftype == 1:
                    predictor = left
                elif ftype == 2:
                    predictor = above
                elif ftype == 3:
                    predictor = (left + above) // 2
                else:
                    predictor = painter._paeth(left, above, upper)
                encoded.append((value - predictor) & 255)
            filtered.append(ftype)
            filtered.extend(encoded)
            reconstructed_rows.append(row)
        payload = painter.PNG_SIGNATURE + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 5, 8, 2, 0, 0, 0)) + png_chunk(b"IDAT", zlib.compress(bytes(filtered))) + png_chunk(b"IEND", b"")
        w, h, rgba = painter._decode_png_rgba(payload)
        self.assertEqual((w, h), (2, 5))
        self.assertEqual(tuple(rgba[:4]), (10, 20, 30, 255))
        self.assertEqual(tuple(rgba[(4 * w) * 4:(4 * w) * 4 + 4]), (14, 24, 34, 255))


    def test_total_texel_operation_budget_is_enforced_before_painting(self):
        geometry = {
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.big", "texture_width": 2048, "texture_height": 2048},
                "bones": [{"name": "body", "pivot": [0, 0, 0], "cubes": [{
                    "origin": [0, 0, 0], "size": [1, 1, 1],
                    "uv": {"north": {"uv": [0, 0], "uv_size": [2048, 2048]}}
                }]}]
            }]
        }
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(geometry))
        operations = [{"selector": {"face": "north"}, "mode": "fill", "color": "#FFFFFF"} for _ in range(5)]
        result = painter.paint_geometry_texture(self.args(operations, source_texture_path=None))
        self.assertEqual(result["error"]["code"], "PAINT_BUDGET_EXCEEDED")
        self.assertFalse((self.tex_dir / "guardian_painted.png").exists())

    def test_mcp_handshake_and_tool_listing(self):
        init = painter.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        listing = painter.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "minecraft-bedrock-texture-painter")
        self.assertEqual(listing["result"]["tools"][0]["name"], "paint_geometry_texture")


if __name__ == "__main__":
    unittest.main()
