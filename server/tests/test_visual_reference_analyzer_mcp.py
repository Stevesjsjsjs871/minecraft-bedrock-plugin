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

# The published base package supplies the full validator; this overlay-only
# test process injects a small bounded PNG structure shim. The painter's PNG
# decoder below still independently checks IDAT decompression and scanlines.
validation = types.ModuleType("png_validation")
if not hasattr(validation, "PngValidationError"):
    class PngValidationError(ValueError):
        pass
    validation.PngValidationError = PngValidationError
if not hasattr(validation, "validate_png_bytes"):
    def validate_png_bytes(payload, *, max_bytes=16 * 1024 * 1024, max_dimension=4096, max_pixels=16_777_216):
        if len(payload) < 45 or len(payload) > max_bytes or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise validation.PngValidationError("invalid PNG signature or size")
        offset, chunks = 8, []
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
        if offset != len(payload):
            raise validation.PngValidationError("PNG trailing bytes")
        ihdr = chunks[0][1]
        width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", ihdr)
        if depth != 8 or color != 6 or comp != 0 or filt != 0 or interlace != 0:
            raise validation.PngValidationError("test shim accepts only RGBA8 non-interlaced PNG")
        if not (1 <= width <= max_dimension and 1 <= height <= max_dimension and width * height <= max_pixels):
            raise validation.PngValidationError("PNG dimensions over limit")
        if not any(kind == b"IDAT" for kind, _ in chunks) or chunks[-1][0] != b"IEND":
            raise validation.PngValidationError("required PNG chunks missing")
        return width, height
    validation.validate_png_bytes = validate_png_bytes
SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

with patch.dict(sys.modules, {"png_validation": validation}):
    import texture_painting_mcp as painter
    import visual_reference_analyzer_mcp as analyzer


class VisualReferenceAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        self.envpatch = patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(self.workspace)})
        self.envpatch.start()
        self.project = self.workspace / "forest-addon"
        self.rp = self.project / "resource_packs" / "forest-addon_RP"
        self.ref_dir = self.rp / "textures" / "references"
        self.geo_dir = self.rp / "models" / "entity"
        self.ref_dir.mkdir(parents=True)
        self.geo_dir.mkdir(parents=True)
        (self.rp / "manifest.json").write_text(json.dumps({"header": {}, "modules": []}), encoding="utf-8")
        self.ref_path = "resource_packs/forest-addon_RP/textures/references/guide.png"
        self.geo_path = "resource_packs/forest-addon_RP/models/entity/test.geo.json"
        geo = {
            "format_version": "1.12.0",
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.test", "texture_width": 16, "texture_height": 16},
                "bones": [{"name": "body", "pivot": [0, 0, 0], "cubes": [
                    {"origin": [-2, 0, -2], "size": [4, 4, 4], "uv": [0, 0]}
                ]}]
            }]
        }
        (self.geo_dir / "test.geo.json").write_text(json.dumps(geo), encoding="utf-8")
        self.rgba = bytearray(8 * 8 * 4)
        # Transparent canvas with red 2x2 and blue 2x2 components.
        for y in range(1, 3):
            for x in range(1, 3):
                i = (y * 8 + x) * 4
                self.rgba[i:i + 4] = bytes((240, 20, 20, 255))
        for y in range(5, 7):
            for x in range(5, 7):
                i = (y * 8 + x) * 4
                self.rgba[i:i + 4] = bytes((20, 40, 240, 255))
        self.write_reference()

    def tearDown(self):
        self.envpatch.stop()
        self.tmp.cleanup()

    def write_reference(self):
        payload = painter._encode_png(8, 8, self.rgba)
        (self.ref_dir / "guide.png").write_bytes(payload)

    def args(self, **extra):
        base = {"project_directory": "forest-addon", "reference_image_path": self.ref_path}
        base.update(extra)
        return base

    def test_color_components_extract_two_regions(self):
        result = analyzer.analyze_visual_reference(self.args(segmentation_mode="color_components", color_bucket_size=16, min_region_area=2))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["segmentation"]["connected_component_count_after_min_area"], 2)
        self.assertEqual(result["regions"][0]["pixel_area"], 4)
        self.assertEqual(result["regions"][0]["source_rect"], {"x": 1, "y": 1, "width": 2, "height": 2})
        self.assertEqual(result["regions"][1]["average_color"], "#1428F0")

    def test_alpha_components_separate_disconnected_shapes(self):
        result = analyzer.analyze_visual_reference(self.args(segmentation_mode="alpha_components", min_region_area=1))
        self.assertEqual(result["segmentation"]["connected_component_count_after_min_area"], 2)

    def test_color_components_merge_runs_across_rows(self):
        image = bytearray(5 * 4 * 4)
        for y in range(1, 4):
            for x in range(1, 4):
                i = (y * 5 + x) * 4
                image[i:i + 4] = bytes((120, 120, 120, 255))
        result, stats = analyzer._segment(5, 4, image, mode="color_components", alpha_threshold=8,
                                          bucket=16, min_area=1, max_regions=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pixel_area"], 9)
        self.assertEqual(result[0]["centroid"], [2.0, 2.0])

    def test_diagonal_pixels_are_distinct_four_connected_components(self):
        image = bytearray(2 * 2 * 4)
        image[0:4] = bytes((255, 0, 0, 255))
        image[(1 * 2 + 1) * 4:(1 * 2 + 1) * 4 + 4] = bytes((255, 0, 0, 255))
        regions, _ = analyzer._segment(2, 2, image, mode="color_components", alpha_threshold=8,
                                       bucket=16, min_area=1, max_regions=10)
        self.assertEqual(len(regions), 2)

    def test_alpha_threshold_filters_low_alpha(self):
        image = bytearray(2 * 4)
        image[0:4] = bytes((200, 10, 10, 7))
        image[4:8] = bytes((200, 10, 10, 8))
        regions, _ = analyzer._segment(2, 1, image, mode="alpha_components", alpha_threshold=8,
                                       bucket=16, min_area=1, max_regions=10)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["pixel_area"], 1)

    def test_min_area_discards_small_islands(self):
        with self.assertRaisesRegex(ValueError, "no visible connected regions"):
            analyzer.analyze_visual_reference(self.args(min_region_area=5))

    def test_max_regions_truncates_results(self):
        result = analyzer.analyze_visual_reference(self.args(min_region_area=1, max_regions=1))
        self.assertTrue(result["segmentation"]["truncated"])
        self.assertEqual(len(result["regions"]), 1)

    def test_returns_edge_contact_and_coverage(self):
        result = analyzer.analyze_visual_reference(self.args(min_region_area=1))
        red = next(r for r in result["regions"] if r["average_color"] == "#F01414")
        self.assertFalse(any(red["edge_contact"].values()))
        self.assertEqual(red["coverage"], 0.0625)

    def test_geometry_candidates_are_geometric_only(self):
        result = analyzer.analyze_visual_reference(self.args(geometry_path=self.geo_path, geometry_identifier="geometry.test", min_region_area=1))
        self.assertEqual(result["geometry"]["uv_face_regions"], 6)
        self.assertEqual(len(result["geometric_candidates"]), 6)
        self.assertIn("no semantic recognition", result["geometric_candidates"][0]["matching_basis"])

    def test_ambiguous_geometry_requires_identifier(self):
        geo_file = self.geo_dir / "test.geo.json"
        data = json.loads(geo_file.read_text())
        data["minecraft:geometry"].append(data["minecraft:geometry"][0])
        geo_file.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "multiple geometry"):
            analyzer.analyze_visual_reference(self.args(geometry_path=self.geo_path, min_region_area=1))

    def test_duplicate_json_keys_rejected_in_geometry(self):
        (self.geo_dir / "test.geo.json").write_text('{"minecraft:geometry":[],"minecraft:geometry":[]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
            analyzer.analyze_visual_reference(self.args(geometry_path=self.geo_path, min_region_area=1))

    def test_path_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError, "traversal"):
            analyzer._validate_args(self.args(reference_image_path="resource_packs/forest-addon_RP/textures/../outside.png"))

    def test_wrong_pack_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be a PNG under"):
            analyzer._validate_args(self.args(reference_image_path="resource_packs/another_RP/textures/a.png"))

    def test_geometry_without_identifier_requires_single_entry(self):
        args = self.args(geometry_path=self.geo_path, min_region_area=1)
        result = analyzer.analyze_visual_reference(args)
        self.assertEqual(result["geometry"]["identifier"], "geometry.test")

    def test_missing_reference_file_rejected(self):
        (self.ref_dir / "guide.png").unlink()
        with self.assertRaises(OSError):
            analyzer.analyze_visual_reference(self.args())

    def test_analysis_is_read_only(self):
        before = sorted(str(p.relative_to(self.project)) for p in self.project.rglob("*"))
        analyzer.analyze_visual_reference(self.args(geometry_path=self.geo_path, min_region_area=1))
        after = sorted(str(p.relative_to(self.project)) for p in self.project.rglob("*"))
        self.assertEqual(before, after)

    def test_schema_and_mcp_protocol(self):
        try:
            import jsonschema
            jsonschema.Draft202012Validator.check_schema(analyzer.TOOLS[0]["inputSchema"])
        except ImportError:
            pass
        response = analyzer.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(response["result"]["tools"][0]["name"], "analyze_visual_reference")

    def test_bool_not_accepted_as_integer_threshold(self):
        with self.assertRaisesRegex(ValueError, "alpha_threshold"):
            analyzer._validate_args(self.args(alpha_threshold=True))

    def test_region_run_budget_is_enforced(self):
        image = bytearray(12 * 12 * 4)
        for y in range(12):
            for x in range(12):
                i = (y * 12 + x) * 4
                image[i:i + 4] = bytes(((x % 2) * 255, (y % 2) * 255, 0, 255))
        with patch.object(analyzer, "MAX_RUNS", 5):
            with self.assertRaisesRegex(ValueError, "complexity budget"):
                analyzer._segment(12, 12, image, mode="color_components", alpha_threshold=8,
                                  bucket=4, min_area=1, max_regions=20)

    def test_candidate_score_stays_bounded(self):
        fake_uv = [{"bone": "body", "cube_index": 0, "face": "north", "bounds": [0, 0, 4, 2]}]
        fake_source = [{"region_id": "region_001", "source_rect": {"x": 0, "y": 0, "width": 8, "height": 4},
                        "pixel_area": 32}]
        match = analyzer._candidate_matches(fake_uv, fake_source, 16, 16, 16, 16)[0]["candidates"][0]
        self.assertGreaterEqual(match["score"], 0)
        self.assertLessEqual(match["score"], 1)

    def test_alpha_mode_ignores_color_variation_inside_connected_subject(self):
        image = bytearray(3 * 3 * 4)
        for y in range(3):
            for x in range(3):
                i = (y * 3 + x) * 4
                image[i:i + 4] = bytes((x * 80, y * 80, 90, 255))
        regions, _ = analyzer._segment(3, 3, image, mode="alpha_components", alpha_threshold=8,
                                       bucket=16, min_area=1, max_regions=10)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["pixel_area"], 9)

    def test_small_color_bucket_splits_more_regions_than_large_bucket(self):
        image = bytearray(2 * 2 * 4)
        colors = [(10, 10, 10, 255), (20, 20, 20, 255), (10, 10, 10, 255), (20, 20, 20, 255)]
        for index, color in enumerate(colors):
            image[index * 4:index * 4 + 4] = bytes(color)
        small, _ = analyzer._segment(2, 2, image, mode="color_components", alpha_threshold=8,
                                    bucket=4, min_area=1, max_regions=10)
        large, _ = analyzer._segment(2, 2, image, mode="color_components", alpha_threshold=8,
                                    bucket=64, min_area=1, max_regions=10)
        self.assertGreaterEqual(len(small), len(large))

    def test_corrupt_png_rejected_by_decoder(self):
        payload = bytearray((self.ref_dir / "guide.png").read_bytes())
        payload[-5] ^= 0xFF
        (self.ref_dir / "guide.png").write_bytes(payload)
        with self.assertRaises(ValueError):
            analyzer.analyze_visual_reference(self.args())

    def test_symlink_reference_rejected(self):
        linked = self.ref_dir / "linked.png"
        linked.symlink_to(self.ref_dir / "guide.png")
        with self.assertRaises(ValueError):
            analyzer.analyze_visual_reference(self.args(reference_image_path="resource_packs/forest-addon_RP/textures/references/linked.png"))


if __name__ == "__main__":
    unittest.main()
