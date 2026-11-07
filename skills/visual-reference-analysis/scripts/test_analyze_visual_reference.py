from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("analyze_visual_reference.py")
spec = importlib.util.spec_from_file_location("analyze_visual_reference", SCRIPT)
assert spec and spec.loader
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)

# The utility imports the same bounded decoder used by the texture painter.
import texture_painter


class SegmentTests(unittest.TestCase):
    def test_alpha_mode_merges_adjacent_different_colors_and_reports_centroid(self):
        rgba = bytearray(4 * 3 * 2)
        rgba[(0 * 3 + 0) * 4:(0 * 3 + 0) * 4 + 4] = bytes((255, 0, 0, 255))
        rgba[(0 * 3 + 1) * 4:(0 * 3 + 1) * 4 + 4] = bytes((0, 0, 255, 255))
        regions, stats = analyzer.segment_rgba(3, 2, rgba, mode="alpha_components", min_region_area=1)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["pixel_area"], 2)
        self.assertEqual(regions[0]["source_rect"], {"x": 0, "y": 0, "width": 2, "height": 1})
        self.assertEqual(regions[0]["centroid"], [0.5, 0.0])
        self.assertEqual(regions[0]["average_color"], "#800080")
        self.assertEqual(stats["run_count"], 1)

    def test_color_mode_uses_quantized_buckets(self):
        rgba = bytearray()
        for color in ((16, 16, 16, 255), (31, 31, 31, 255), (32, 32, 32, 255)):
            rgba.extend(color)
        regions, _ = analyzer.segment_rgba(3, 1, rgba, mode="color_components", color_bucket_size=16, min_region_area=1)
        self.assertEqual(len(regions), 2)
        self.assertEqual([item["pixel_area"] for item in regions], [2, 1])

    def test_diagonal_pixels_are_separate_four_connected_components(self):
        rgba = bytearray(3 * 3 * 4)
        rgba[(0 * 3 + 0) * 4:(0 * 3 + 0) * 4 + 4] = bytes((200, 10, 10, 255))
        rgba[(1 * 3 + 1) * 4:(1 * 3 + 1) * 4 + 4] = bytes((200, 10, 10, 255))
        regions, _ = analyzer.segment_rgba(3, 3, rgba, mode="alpha_components", min_region_area=1)
        self.assertEqual(len(regions), 2)

    def test_min_area_and_max_regions_are_reported(self):
        rgba = bytearray(5 * 2 * 4)
        for x in (0, 2, 4):
            rgba[x * 4:x * 4 + 4] = bytes((x + 10, 0, 0, 255))
        regions, stats = analyzer.segment_rgba(5, 2, rgba, mode="alpha_components", min_region_area=1, max_regions=2)
        self.assertEqual(len(regions), 2)
        self.assertTrue(stats["truncated"])
        self.assertEqual(stats["connected_component_count_after_min_area"], 3)

    def test_run_budget_rejects_pathological_segmentation(self):
        rgba = bytearray()
        for row in range(2):
            for col in range(2):
                rgba.extend((255, 0, 0, 255) if (row + col) % 2 == 0 else (0, 0, 255, 255))
        with self.assertRaisesRegex(analyzer.ReferenceAnalysisError, "run complexity budget"):
            analyzer.segment_rgba(2, 2, rgba, mode="color_components", color_bucket_size=4, max_runs=3)

    def test_candidate_ranking_is_deterministic_and_explains_basis(self):
        components = [
            {"region_id": "region_001", "pixel_area": 8, "source_rect": {"x": 0, "y": 0, "width": 4, "height": 2}},
            {"region_id": "region_002", "pixel_area": 8, "source_rect": {"x": 0, "y": 2, "width": 2, "height": 4}},
        ]
        uv_regions = [{"bone": "body", "cube_index": 0, "face": "north", "u": 0, "v": 0, "width": 4, "height": 2}]
        result = analyzer.candidate_matches(uv_regions, components, 8, 8, 16, 16)
        self.assertEqual(result[0]["candidates"][0]["region_id"], "region_001")
        self.assertIn("no semantic recognition", result[0]["matching_basis"])


class ProjectWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "forest-addon"
        rp = self.project / "resource_packs" / "forest-addon_RP"
        (rp / "textures" / "references").mkdir(parents=True)
        (rp / "models" / "entity").mkdir(parents=True)
        (rp / "manifest.json").write_text('{"format_version":2}', encoding="utf-8")
        pixels = bytearray()
        for y in range(8):
            for x in range(8):
                if x < 2 and y < 2:
                    pixels.extend((240, 20, 20, 255))
                elif x >= 5 and y < 2:
                    pixels.extend((20, 20, 240, 255))
                else:
                    pixels.extend((0, 0, 0, 0))
        image = texture_painter._encode_png(8, 8, pixels)
        (rp / "textures" / "references" / "concept.png").write_bytes(image)
        geometry = {
            "format_version": "1.12.0",
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.test", "texture_width": 16, "texture_height": 16},
                "bones": [{"name": "body", "cubes": [{"origin": [0, 0, 0], "size": [2, 2, 2], "uv": [0, 0]}]},],
            }],
        }
        (rp / "models" / "entity" / "test.geo.json").write_text(json.dumps(geometry), encoding="utf-8")
        self.ref = "resource_packs/forest-addon_RP/textures/references/concept.png"
        self.geo = "resource_packs/forest-addon_RP/models/entity/test.geo.json"

    def test_full_workflow_returns_regions_and_geometry_hints_read_only(self):
        before = (self.project / "resource_packs" / "forest-addon_RP" / "textures" / "references" / "concept.png").read_bytes()
        result = analyzer.analyze_reference(self.project, self.ref, min_region_area=1, geometry_path=self.geo, geometry_identifier="geometry.test")
        after = (self.project / "resource_packs" / "forest-addon_RP" / "textures" / "references" / "concept.png").read_bytes()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["reference"]["sha256"], __import__("hashlib").sha256(before).hexdigest())
        self.assertEqual(result["geometry"]["identifier"], "geometry.test")
        self.assertEqual(len(result["geometric_candidates"]), 6)
        self.assertTrue(result["regions"])
        self.assertEqual(before, after)
        self.assertIn("Minecraft runtime/rendering: NOT RUN", result["scope_note"])

    def test_alpha_mode_reports_single_silhouette_warning(self):
        rp = self.project / "resource_packs" / "forest-addon_RP"
        pixels = bytearray()
        for _ in range(8 * 8):
            pixels.extend((80, 120, 160, 255))
        (rp / "textures" / "references" / "concept.png").write_bytes(texture_painter._encode_png(8, 8, pixels))
        result = analyzer.analyze_reference(self.project, self.ref, segmentation_mode="alpha_components", min_region_area=1)
        self.assertEqual(len(result["regions"]), 1)
        self.assertIn("SINGLE_ALPHA_SILHOUETTE", {item["code"] for item in result["warnings"]})

    def test_path_traversal_and_wrong_tree_are_rejected(self):
        with self.assertRaisesRegex(analyzer.ReferenceAnalysisError, "traversal"):
            analyzer.analyze_reference(self.project, "resource_packs/forest-addon_RP/textures/../../manifest.json")
        with self.assertRaisesRegex(analyzer.ReferenceAnalysisError, "must be PNG under"):
            analyzer.analyze_reference(self.project, "resource_packs/other_RP/textures/ref.png")

    def test_geometry_identifier_requires_geometry_path(self):
        with self.assertRaisesRegex(analyzer.ReferenceAnalysisError, "requires geometry_path"):
            analyzer.analyze_reference(self.project, self.ref, geometry_identifier="geometry.test")

    def test_duplicate_geometry_json_keys_are_rejected(self):
        geo_path = self.project / self.geo
        geo_path.write_text('{"minecraft:geometry":[],"minecraft:geometry":[]}', encoding="utf-8")
        with self.assertRaisesRegex(analyzer.ReferenceAnalysisError, "duplicate JSON key"):
            analyzer.analyze_reference(self.project, self.ref, min_region_area=1, geometry_path=self.geo)

    def test_reference_symlink_is_rejected(self):
        ref_path = self.project / self.ref
        original = ref_path.with_suffix(".real.png")
        ref_path.rename(original)
        try:
            ref_path.symlink_to(original)
        except (OSError, NotImplementedError):
            original.rename(ref_path)
            self.skipTest("symlinks are unavailable in this environment")
        with self.assertRaisesRegex(analyzer.ReferenceAnalysisError, "symlink"):
            analyzer.analyze_reference(self.project, self.ref)

    def test_png_is_not_written_or_modified_by_analysis(self):
        ref_path = self.project / self.ref
        original = ref_path.read_bytes()
        analyzer.analyze_reference(self.project, self.ref, min_region_area=1)
        self.assertEqual(ref_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
