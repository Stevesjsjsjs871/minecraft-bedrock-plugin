from __future__ import annotations
import json
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from texture_painter import PaintError, _decode_png_rgba, _encode_png, paint, validate_request


def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def make_png(width=1, height=1, color=6, depth=8, interlace=0, filter_type=0, palette=b"\x00\x00\x00", transparency=b""):
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    row_bytes = (width * channels * depth + 7) // 8
    raw = b"".join(bytes([filter_type]) + bytes(row_bytes) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, interlace)
    parts = [b"\x89PNG\r\n\x1a\n", chunk(b"IHDR", ihdr)]
    if color == 3:
        parts.append(chunk(b"PLTE", palette))
    if transparency:
        parts.append(chunk(b"tRNS", transparency))
    parts.extend((chunk(b"IDAT", zlib.compress(raw)), chunk(b"IEND", b"")))
    return b"".join(parts)


def geometry(texture=(16, 16), uv=(0, 0), identifier="geometry.guardian"):
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": identifier, "texture_width": texture[0], "texture_height": texture[1]},
        "bones": [{"name": "body", "pivot": [0, 0, 0], "cubes": [{"origin": [-2, 0, -2], "size": [4, 4, 4], "uv": list(uv)}]}],
    }]}


def request(output="resource_packs/forest-addon_RP/textures/entity/painted.png", **extra):
    value = {
        "project_directory": "forest-addon",
        "geometry_path": "resource_packs/forest-addon_RP/models/entity/guardian.geo.json",
        "output_path": output,
        "source_texture_path": "resource_packs/forest-addon_RP/textures/entity/base.png",
        "operations": [{"selector": {"bone": "body", "face": "north"}, "mode": "fill", "color": "#FF0000"}],
    }
    value.update(extra)
    return value


class TexturePainterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.project = self.workspace / "forest-addon"
        self.rp = self.project / "resource_packs" / "forest-addon_RP"
        self.geo_dir = self.rp / "models" / "entity"
        self.tex_dir = self.rp / "textures" / "entity"
        self.geo_dir.mkdir(parents=True)
        self.tex_dir.mkdir(parents=True)
        (self.rp / "manifest.json").write_text(json.dumps({"header": {}, "modules": []}), encoding="utf-8")
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(geometry()), encoding="utf-8")
        base = bytes((10, 20, 30, 128)) * (16 * 16)
        (self.tex_dir / "base.png").write_bytes(_encode_png(16, 16, bytearray(base)))

    def tearDown(self):
        self.temp.cleanup()

    def run_paint(self, req=None):
        return paint(req or request(), workspace=self.workspace)

    def decode_output(self, name="painted.png"):
        return _decode_png_rgba((self.tex_dir / name).read_bytes())

    def test_fill_targets_selected_face_and_preserves_unpainted_alpha(self):
        result = self.run_paint()
        self.assertEqual(result["status"], "PASS")
        w, h, pixels = self.decode_output()
        self.assertEqual((w, h), (16, 16))
        self.assertEqual(tuple(pixels[(4 * w + 4) * 4:(4 * w + 4) * 4 + 4]), (255, 0, 0, 255))
        self.assertEqual(tuple(pixels[:4]), (10, 20, 30, 128))

    def test_zero_opacity_preserves_source_alpha(self):
        req = request(operations=[{"selector": {"bone": "body", "face": "north"}, "mode": "fill", "color": "#FFFFFF", "opacity": 0}])
        self.run_paint(req)
        _, _, pixels = self.decode_output()
        self.assertEqual(tuple(pixels[(4 * 16 + 4) * 4:(4 * 16 + 4) * 4 + 4]), (10, 20, 30, 128))

    def test_transparent_canvas_without_source(self):
        req = request(source_texture_path=None, operations=[{"selector": {"face": "north"}, "mode": "fill", "color": "#00FF00"}])
        self.run_paint(req)
        _, _, pixels = self.decode_output()
        self.assertEqual(tuple(pixels[(4 * 16 + 4) * 4:(4 * 16 + 4) * 4 + 4]), (0, 255, 0, 255))
        self.assertEqual(tuple(pixels[:4]), (0, 0, 0, 0))

    def test_background_color(self):
        req = request(source_texture_path=None, background_color="#11223380", operations=[{"selector": {"face": "north"}, "mode": "fill", "color": "#FFFFFF", "opacity": 0}])
        self.run_paint(req)
        _, _, pixels = self.decode_output()
        self.assertEqual(tuple(pixels[:4]), (17, 34, 51, 128))

    def test_background_and_source_are_mutually_exclusive(self):
        with self.assertRaisesRegex(PaintError, "cannot be combined"):
            validate_request(request(background_color="#112233"))

    def test_checker_uses_secondary_color(self):
        req = request(source_texture_path=None, operations=[{"selector": {"face": "north"}, "mode": "checker", "color": "#FF0000", "secondary_color": "#0000FF", "cell_size": 1, "blend_mode": "replace"}])
        self.run_paint(req)
        w, _, pixels = self.decode_output()
        self.assertEqual(tuple(pixels[(4 * w + 4) * 4:(4 * w + 4) * 4 + 4]), (255, 0, 0, 255))
        self.assertEqual(tuple(pixels[(4 * w + 5) * 4:(4 * w + 5) * 4 + 4]), (0, 0, 255, 255))

    def test_gradient_interpolates_both_ends(self):
        req = request(source_texture_path=None, operations=[{"selector": {"face": "north"}, "mode": "gradient", "color": "#000000", "secondary_color": "#FFFFFF", "axis": "x", "blend_mode": "replace"}])
        self.run_paint(req)
        w, _, pixels = self.decode_output()
        left = tuple(pixels[(4 * w + 4) * 4:(4 * w + 4) * 4 + 3])
        right = tuple(pixels[(4 * w + 7) * 4:(4 * w + 7) * 4 + 3])
        self.assertEqual(left, (0, 0, 0)); self.assertEqual(right, (255, 255, 255))

    def test_border_keeps_interior_from_source_when_no_secondary(self):
        req = request(operations=[{"selector": {"face": "north"}, "mode": "border", "color": "#FFAA00", "border_width": 1}])
        self.run_paint(req)
        w, _, pixels = self.decode_output()
        self.assertEqual(tuple(pixels[(4 * w + 4) * 4:(4 * w + 4) * 4 + 4]), (255, 170, 0, 255))
        self.assertEqual(tuple(pixels[(5 * w + 5) * 4:(5 * w + 5) * 4 + 4]), (10, 20, 30, 128))

    def test_noise_is_deterministic(self):
        base = request(source_texture_path=None, operations=[{"selector": {"face": "north"}, "mode": "noise", "color": "#111111", "secondary_color": "#EEEEEE", "seed": 42}])
        first = self.run_paint(base)
        second_req = dict(base, output_path="resource_packs/forest-addon_RP/textures/entity/second.png")
        second = self.run_paint(second_req)
        self.assertEqual(first["output"]["sha256"], second["output"]["sha256"])

    def test_uv_overlap_requires_explicit_opt_in(self):
        doc = json.loads((self.geo_dir / "guardian.geo.json").read_text())
        doc["minecraft:geometry"][0]["bones"].append({"name": "overlay", "pivot": [0, 0, 0], "cubes": [{"origin": [0,0,0], "size": [4,4,4], "uv": [0,0]}]})
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(doc))
        with self.assertRaisesRegex(PaintError, "UV overlap"):
            self.run_paint()

    def test_uv_overlap_can_be_allowed_and_reported(self):
        doc = json.loads((self.geo_dir / "guardian.geo.json").read_text())
        doc["minecraft:geometry"][0]["bones"].append({"name": "overlay", "pivot": [0,0,0], "cubes": [{"origin": [0,0,0], "size": [4,4,4], "uv": [0,0]}]})
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(doc))
        result = self.run_paint(request(allow_uv_overlap=True))
        self.assertGreater(result["painting"]["uv_overlap_pairs"], 0)

    def test_uv_out_of_bounds_refuses_to_write(self):
        doc = geometry(uv=(15, 15))
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(doc))
        with self.assertRaisesRegex(PaintError, "exceed declared"):
            self.run_paint()
        self.assertFalse((self.tex_dir / "painted.png").exists())

    def test_source_dimensions_must_match_geometry(self):
        (self.tex_dir / "base.png").write_bytes(_encode_png(8, 8, bytearray(bytes((0,0,0,255))*64)))
        with self.assertRaisesRegex(PaintError, "requires 16x16"):
            self.run_paint()

    def test_existing_output_is_never_overwritten(self):
        target = self.tex_dir / "painted.png"; target.write_bytes(b"preserve me")
        with self.assertRaises(FileExistsError): self.run_paint()
        self.assertEqual(target.read_bytes(), b"preserve me")

    def test_invalid_selector_does_not_create_file(self):
        req = request(operations=[{"selector": {"bone": "missing"}, "mode": "fill", "color": "#FFFFFF"}])
        with self.assertRaisesRegex(PaintError, "matched no"):
            self.run_paint(req)
        self.assertFalse((self.tex_dir / "painted.png").exists())

    def test_same_source_and_output_is_rejected(self):
        req = request(output="resource_packs/forest-addon_RP/textures/entity/base.png")
        with self.assertRaisesRegex(PaintError, "different files"):
            validate_request(req)

    def test_per_face_uv_is_painted(self):
        doc = geometry()
        cube = doc["minecraft:geometry"][0]["bones"][0]["cubes"][0]
        cube["uv"] = {"north": {"uv": [4, 4], "uv_size": [4, 4]}, "south": {"uv": [8, 4], "uv_size": [4, 4]}}
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(doc))
        req = request(operations=[{"selector": {"bone": "body", "face": "north"}, "mode": "fill", "color": "#AA0000", "blend_mode": "replace"}])
        self.run_paint(req)
        w, _, pixels = self.decode_output()
        self.assertEqual(tuple(pixels[(4 * w + 4) * 4:(4 * w + 4) * 4 + 4]), (170,0,0,255))
        self.assertEqual(tuple(pixels[(4 * w + 8) * 4:(4 * w + 8) * 4 + 4]), (10,20,30,128))

    def test_duplicate_geometry_identifier_is_rejected(self):
        doc = geometry(); doc["minecraft:geometry"].append(doc["minecraft:geometry"][0])
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(doc))
        with self.assertRaisesRegex(PaintError, "missing or ambiguous"):
            self.run_paint()

    def test_path_traversal_is_rejected(self):
        req = request(); req["geometry_path"] = "resource_packs/forest-addon_RP/models/entity/../../escape.json"
        with self.assertRaises(PaintError): validate_request(req)

    def test_invalid_enum_and_boolean_values_are_rejected(self):
        for patch in ({"mode": "paint"}, {"mode": "fill", "opacity": True}, {"mode": "fill", "axis": "z"}, {"mode": "fill", "blend_mode": "multiply"}):
            op = {"selector": {"face": "north"}, "mode": "fill", "color": "#FFFFFF"}; op.update(patch)
            with self.subTest(patch=patch), self.assertRaises(PaintError): validate_request(request(operations=[op]))

    def test_png_decoder_supports_rgb_gray_palette_and_gray_alpha(self):
        self.assertEqual(_decode_png_rgba(make_png(color=2))[2][:4], bytearray((0,0,0,255)))
        self.assertEqual(_decode_png_rgba(make_png(color=0))[2][:4], bytearray((0,0,0,255)))
        self.assertEqual(_decode_png_rgba(make_png(color=3, palette=b"\x11\x22\x33"))[2][:4], bytearray((17,34,51,255)))
        self.assertEqual(_decode_png_rgba(make_png(color=4))[2][:4], bytearray((0,0,0,0)))

    def test_png_decoder_rejects_interlace_and_16_bit(self):
        with self.assertRaises(PaintError): _decode_png_rgba(make_png(interlace=1))
        with self.assertRaises(PaintError): _decode_png_rgba(make_png(depth=16))

    def test_png_decoder_supports_all_scanline_filters(self):
        for filter_type in range(5):
            with self.subTest(filter_type=filter_type):
                self.assertEqual(_decode_png_rgba(make_png(filter_type=filter_type))[2], bytearray((0,0,0,0)))

    def test_symlinked_source_texture_is_rejected(self):
        link = self.tex_dir / "linked.png"
        try: link.symlink_to(self.tex_dir / "base.png")
        except (OSError, NotImplementedError): self.skipTest("symlinks unavailable")
        req = request(source_texture_path="resource_packs/forest-addon_RP/textures/entity/linked.png")
        with self.assertRaisesRegex(PaintError, "symlink"):
            self.run_paint(req)

    def test_symlinked_geometry_is_rejected(self):
        source = self.geo_dir / "guardian.geo.json"; link = self.geo_dir / "linked.geo.json"
        link.symlink_to(source)
        req = request(geometry_path="resource_packs/forest-addon_RP/models/entity/linked.geo.json")
        with self.assertRaisesRegex(PaintError, "symlink"):
            self.run_paint(req)

    def test_texel_budget_is_checked_before_painting(self):
        doc = {"minecraft:geometry": [{"description": {"identifier": "geometry.guardian", "texture_width": 2048, "texture_height": 2048}, "bones": [{"name": "body", "cubes": [{"size": [1,1,1], "uv": {face: {"uv": [0,0], "uv_size": [2048,2048]} for face in ("north","south","east","west","up")}}]}]}]}
        (self.geo_dir / "guardian.geo.json").write_text(json.dumps(doc))
        req = request(source_texture_path=None, allow_uv_overlap=True, operations=[{"selector": {"bone": "body"}, "mode": "fill", "color": "#FFFFFF"}])
        with self.assertRaisesRegex(PaintError, "texel-write budget"):
            self.run_paint(req)
        self.assertFalse((self.tex_dir / "painted.png").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
