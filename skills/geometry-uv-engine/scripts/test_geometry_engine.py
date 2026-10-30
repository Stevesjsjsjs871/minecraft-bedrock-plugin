from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import geometry_engine as engine
from geometry_engine import GeometryError, analyze_file, analyze_geometry


def doc(cubes, *, identifier="geometry.test", width=64, height=64, bone_extra=None, extra_geometries=None):
    description = {"identifier": identifier}
    if width is not None:
        description["texture_width"] = width
    if height is not None:
        description["texture_height"] = height
    bone = {"name": "root", "cubes": cubes}
    if bone_extra:
        bone.update(bone_extra)
    geometries = [{"description": description, "bones": [bone]}]
    if extra_geometries:
        geometries.extend(extra_geometries)
    return {"format_version": "1.21.0", "minecraft:geometry": geometries}


def classic_cube(uv=(0, 0), size=(4, 6, 2), origin=(0, 0, 0)):
    return {"origin": list(origin), "size": list(size), "uv": list(uv)}


class GeometryEngineTests(unittest.TestCase):
    def test_classic_box_layout(self):
        result = analyze_geometry(doc([classic_cube((1, 2))]))
        region = result["regions"][0]
        self.assertEqual((region["width"], region["height"]), (12, 8))
        self.assertEqual(result["summary"]["status"], "PASS")

    def test_per_face_default_extents(self):
        uv = {face: {"uv": [0, 0]} for face in ("north", "south", "east", "west", "up", "down")}
        result = analyze_geometry(doc([{"origin": [0, 0, 0], "size": [4, 6, 2], "uv": uv}]))
        dimensions = {item["selector"]["face"]: (item["width"], item["height"]) for item in result["regions"]}
        self.assertEqual(dimensions["north"], (4, 6))
        self.assertEqual(dimensions["east"], (2, 6))
        self.assertEqual(dimensions["up"], (4, 2))

    def test_rotation_swaps_bounds(self):
        uv = {"north": {"uv": [0, 0], "uv_size": [4, 6], "uv_rotation": 90}}
        result = analyze_geometry(doc([{"origin": [0, 0, 0], "size": [4, 6, 2], "uv": uv}]))
        self.assertEqual((result["regions"][0]["width"], result["regions"][0]["height"]), (6, 4))

    def test_negative_uv_size_is_normalized_for_occupied_bounds(self):
        uv = {"north": {"uv": [8, 8], "uv_size": [-4, -6]}}
        result = analyze_geometry(doc([{"origin": [0, 0, 0], "size": [4, 6, 2], "uv": uv}]))
        self.assertEqual((result["regions"][0]["width"], result["regions"][0]["height"]), (4, 6))

    def test_out_of_bounds(self):
        result = analyze_geometry(doc([classic_cube((60, 60))]))
        self.assertEqual(result["summary"]["status"], "FAIL")
        self.assertEqual(result["summary"]["out_of_bounds"], 1)

    def test_overlap_is_warning(self):
        cubes = [classic_cube((0, 0)), classic_cube((1, 1), origin=(8, 0, 0))]
        result = analyze_geometry(doc(cubes))
        self.assertGreater(result["summary"]["overlaps"], 0)
        self.assertEqual(result["summary"]["status"], "WARN")

    def test_touching_rectangles_do_not_overlap(self):
        cubes = [classic_cube((0, 0)), classic_cube((12, 0), origin=(8, 0, 0))]
        result = analyze_geometry(doc(cubes))
        self.assertEqual(result["summary"]["overlaps"], 0)

    def test_geometry_selection_required(self):
        first = doc([])["minecraft:geometry"][0]
        second = json.loads(json.dumps(first))
        second["description"]["identifier"] = "geometry.second"
        with self.assertRaisesRegex(GeometryError, "multiple geometries"):
            analyze_geometry({"minecraft:geometry": [first, second]})

    def test_geometry_identifier_selects_exact_entry(self):
        second = {"description": {"identifier": "geometry.second", "texture_width": 64, "texture_height": 64}, "bones": []}
        result = analyze_geometry(doc([], extra_geometries=[second]), geometry_identifier="geometry.second")
        self.assertEqual(result["geometry_identifier"], "geometry.second")

    def test_duplicate_geometry_identifier_is_rejected(self):
        first = doc([])["minecraft:geometry"][0]
        second = json.loads(json.dumps(first))
        with self.assertRaisesRegex(GeometryError, "ambiguous"):
            analyze_geometry({"minecraft:geometry": [first, second]}, geometry_identifier="geometry.test")

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.geo.json"
            path.write_text('{"minecraft:geometry":[],"minecraft:geometry":[]}', encoding="utf-8")
            with self.assertRaisesRegex(GeometryError, "duplicate JSON key"):
                analyze_file(path)

    def test_nonfinite_json_constant_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nan.geo.json"
            path.write_text('{"format_version":"1.21.0","minecraft:geometry":[{"description":{"identifier":"geometry.nan","texture_width":64,"texture_height":64},"bones":[{"name":"root","cubes":[{"origin":[0,0,0],"size":[NaN,1,1],"uv":[0,0]}]}]}]}', encoding="utf-8")
            with self.assertRaisesRegex(GeometryError, "non-finite JSON constant"):
                analyze_file(path)

    def test_nonfinite_geometry_number_rejected(self):
        with self.assertRaisesRegex(GeometryError, "finite number"):
            analyze_geometry(doc([classic_cube(size=(float("nan"), 1, 1))]))

    def test_zero_cube_dimension_rejected(self):
        with self.assertRaisesRegex(GeometryError, "dimensions must be positive"):
            analyze_geometry(doc([classic_cube(size=(0, 1, 1))]))

    def test_texture_canvas_must_use_integers(self):
        with self.assertRaisesRegex(GeometryError, "must be an integer"):
            analyze_geometry(doc([classic_cube()], width=64.0))

    def test_boolean_texture_canvas_rejected(self):
        with self.assertRaisesRegex(GeometryError, "must be an integer"):
            analyze_geometry(doc([classic_cube()], width=True))

    def test_missing_texture_canvas_is_warn_not_assumed(self):
        result = analyze_geometry(doc([classic_cube()], width=None, height=None))
        self.assertEqual(result["summary"]["status"], "WARN")
        self.assertFalse(result["summary"]["bounds_checked"])
        self.assertIsNone(result["regions"][0]["out_of_bounds"])

    def test_incomplete_texture_canvas_is_warn(self):
        result = analyze_geometry(doc([classic_cube()], width=64, height=None))
        self.assertIn("INCOMPLETE_TEXTURE_CANVAS", {item["code"] for item in result["findings"]})
        self.assertFalse(result["summary"]["bounds_checked"])

    def test_bone_level_poly_mesh_is_reported(self):
        result = analyze_geometry(doc([], bone_extra={"poly_mesh": {"positions": []}}))
        self.assertIn("UNSUPPORTED_MESH_UV", {item["code"] for item in result["findings"]})
        self.assertEqual(result["summary"]["status"], "WARN")

    def test_bone_level_texture_meshes_are_reported(self):
        result = analyze_geometry(doc([], bone_extra={"texture_meshes": []}))
        self.assertIn("UNSUPPORTED_MESH_UV", {item["code"] for item in result["findings"]})

    def test_float_uv_rotation_is_rejected(self):
        uv = {"north": {"uv": [0, 0], "uv_rotation": 90.0}}
        with self.assertRaisesRegex(GeometryError, "must be an integer"):
            analyze_geometry(doc([{"origin": [0, 0, 0], "size": [4, 6, 2], "uv": uv}]))

    def test_boolean_uv_rotation_is_rejected(self):
        uv = {"north": {"uv": [0, 0], "uv_rotation": True}}
        with self.assertRaisesRegex(GeometryError, "must be an integer"):
            analyze_geometry(doc([{"origin": [0, 0, 0], "size": [4, 6, 2], "uv": uv}]))

    def test_unknown_face_is_warning(self):
        uv = {"north": {"uv": [0, 0]}, "front": {"uv": [0, 0]}}
        result = analyze_geometry(doc([{"origin": [0, 0, 0], "size": [4, 6, 2], "uv": uv}]))
        self.assertIn("UNKNOWN_UV_FACE", {item["code"] for item in result["findings"]})
        self.assertEqual(result["summary"]["status"], "WARN")

    def test_overlap_comparison_budget_is_reported(self):
        cubes = [classic_cube((0, 0)), classic_cube((0, 0), origin=(8, 0, 0)), classic_cube((0, 0), origin=(16, 0, 0))]
        with patch.object(engine, "MAX_OVERLAP_COMPARISONS", 1):
            result = analyze_geometry(doc(cubes))
        self.assertFalse(result["summary"]["overlap_analysis_complete"])
        self.assertIn("OVERLAP_ANALYSIS_TRUNCATED", {item["code"] for item in result["findings"]})

    def test_region_limit_fails_closed(self):
        cubes = [classic_cube((0, 0)), classic_cube((20, 0), origin=(8, 0, 0))]
        with patch.object(engine, "MAX_REGIONS", 1):
            with self.assertRaisesRegex(GeometryError, "region count exceeds"):
                analyze_geometry(doc(cubes))

    def test_file_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.geo.json"
            path.write_text(" " * 64, encoding="utf-8")
            with patch.object(engine, "MAX_JSON_BYTES", 32):
                with self.assertRaisesRegex(GeometryError, "safety limit"):
                    analyze_file(path)

    def test_symlink_geometry_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.geo.json"
            target.write_text(json.dumps(doc([classic_cube()])), encoding="utf-8")
            link = root / "link.geo.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            with self.assertRaisesRegex(GeometryError, "non-symlink"):
                analyze_file(link)

    def test_report_is_new_file_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            geometry = root / "model.geo.json"
            geometry.write_text(json.dumps(doc([classic_cube()])), encoding="utf-8")
            report = root / "report.json"
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(engine.main([str(geometry), "--report", str(report)]), 0)
            before = report.read_bytes()
            output = StringIO()
            with redirect_stdout(output):
                code = engine.main([str(geometry), "--report", str(report)])
            self.assertEqual(code, 2)
            self.assertEqual(report.read_bytes(), before)
            self.assertIn("refusing to overwrite", json.loads(output.getvalue())["error"]["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
