from __future__ import annotations

import json
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import geometry_uv_template_mcp as mod


def make_project(root: Path, geometry: dict, *, geometry_file_text: str | None = None) -> tuple[Path, Path]:
    project = root / "uv-test"
    rp = project / "resource_packs" / "uv-test_RP"
    model_dir = rp / "models" / "entity"
    texture_dir = rp / "textures"
    model_dir.mkdir(parents=True)
    texture_dir.mkdir(parents=True)
    (rp / "manifest.json").write_text(json.dumps({"header": {"name": "RP"}, "modules": []}), encoding="utf-8")
    model_file = model_dir / "test.geo.json"
    if geometry_file_text is None:
        model_file.write_text(json.dumps(geometry), encoding="utf-8")
    else:
        model_file.write_text(geometry_file_text, encoding="utf-8")
    return project, model_file


def png_chunks(payload: bytes) -> tuple[int, int, bytes]:
    assert payload.startswith(mod.PNG_SIGNATURE)
    offset = len(mod.PNG_SIGNATURE)
    idat = bytearray()
    width = height = 0
    saw_end = False
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        data = payload[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", payload[offset + 8 + length:offset + 12 + length])[0]
        assert zlib.crc32(kind + data) & 0xFFFFFFFF == crc
        if kind == b"IHDR":
            width, height, depth, color, *_ = struct.unpack(">IIBBBBB", data)
            assert (depth, color) == (8, 6)
        elif kind == b"IDAT":
            idat.extend(data)
        elif kind == b"IEND":
            saw_end = True
            break
        offset += 12 + length
    assert saw_end
    return width, height, zlib.decompress(idat)


def classic_geometry() -> dict:
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": "geometry.test", "texture_width": 16, "texture_height": 16},
            "bones": [{"name": "body", "cubes": [{"origin": [0, 0, 0], "size": [4, 6, 2], "uv": [1, 2]}]}]
        }]
    }


class GeometryUvTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_workspace = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
        os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = str(self.root)

    def tearDown(self) -> None:
        if self.old_workspace is None:
            os.environ.pop("MINECRAFT_BEDROCK_WORKSPACE", None)
        else:
            os.environ["MINECRAFT_BEDROCK_WORKSPACE"] = self.old_workspace
        self.temp.cleanup()

    def args(self, *, output="resource_packs/uv-test_RP/textures/uv_templates/guide.png", **extra):
        return {
            "project_directory": "uv-test",
            "geometry_path": "resource_packs/uv-test_RP/models/entity/test.geo.json",
            "output_path": output,
            **extra,
        }

    def test_classic_box_creates_six_correct_regions(self):
        _, model_file = make_project(self.root, classic_geometry())
        root = mod._read_geometry(model_file)
        regions, findings, cube_count = mod._extract_regions(root["minecraft:geometry"][0], "geometry.test")
        self.assertEqual(cube_count, 1)
        self.assertEqual(len(regions), 6)
        by_face = {r["face"]: r["bounds"] for r in regions}
        self.assertEqual(by_face["up"], [3.0, 2.0, 7.0, 4.0])
        self.assertEqual(by_face["down"], [7.0, 2.0, 11.0, 4.0])
        self.assertEqual(by_face["west"], [1.0, 4.0, 3.0, 10.0])
        self.assertEqual(by_face["north"], [3.0, 4.0, 7.0, 10.0])
        self.assertEqual(by_face["east"], [7.0, 4.0, 9.0, 10.0])
        self.assertEqual(by_face["south"], [9.0, 4.0, 13.0, 10.0])
        self.assertFalse(findings)
        overlaps, count, complete = mod._overlaps(regions)
        self.assertEqual((overlaps, count, complete), ([], 0, True))

    def test_per_face_negative_sizes_and_rotation_use_normalized_bounds(self):
        geometry = {
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.test", "texture_width": 32, "texture_height": 32},
                "bones": [{"name": "head", "cubes": [{"size": [4, 5, 6], "uv": {
                    "north": {"uv": [2, 3], "uv_size": [4, 5]},
                    "up": {"uv": [12, 12], "uv_size": [-4, -6]},
                    "east": {"uv": [20, 4], "uv_size": [6, 5], "uv_rotation": 90}
                }}]}]
            }]
        }
        root = geometry["minecraft:geometry"][0]
        regions, findings, _ = mod._extract_regions(root, "geometry.test")
        by_face = {r["face"]: r["bounds"] for r in regions}
        self.assertEqual(by_face["north"], [2.0, 3.0, 6.0, 8.0])
        self.assertEqual(by_face["up"], [8.0, 6.0, 12.0, 12.0])
        self.assertEqual(by_face["east"], [20.0, 4.0, 25.0, 10.0])
        self.assertTrue(any(f["code"] == "UV_AXIS_FLIP" for f in findings))

    def test_overlap_detected_with_intersection_area(self):
        regions = [
            {"bone": "a", "cube_index": 0, "face": "north", "bounds": [0, 0, 4, 4]},
            {"bone": "b", "cube_index": 1, "face": "south", "bounds": [2, 1, 6, 5]},
        ]
        records, count, complete = mod._overlaps(regions)
        self.assertTrue(complete)
        self.assertEqual(count, 1)
        self.assertEqual(records[0]["intersection"], [2, 1, 4, 4])
        self.assertEqual(records[0]["area"], 6)

    def test_touching_rectangles_do_not_overlap(self):
        regions = [
            {"bone": "a", "cube_index": 0, "face": "north", "bounds": [0, 0, 2, 2]},
            {"bone": "b", "cube_index": 1, "face": "north", "bounds": [2, 0, 4, 2]},
        ]
        self.assertEqual(mod._overlaps(regions), ([], 0, True))

    def test_generates_valid_png_and_does_not_modify_geometry(self):
        project, model_file = make_project(self.root, classic_geometry())
        original = model_file.read_bytes()
        result = mod.generate_geometry_uv_template(self.args(pixel_scale=3))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["template"]["width"], 48)
        self.assertEqual(result["template"]["height"], 48)
        self.assertEqual(result["uv_analysis"]["regions"], 6)
        output = project / "resource_packs/uv-test_RP/textures/uv_templates/guide.png"
        width, height, scanlines = png_chunks(output.read_bytes())
        self.assertEqual((width, height), (48, 48))
        self.assertEqual(len(scanlines), height * (width * 4 + 1))
        self.assertEqual(model_file.read_bytes(), original)

    def test_template_reports_bounds_and_fractional_coords(self):
        geometry = {
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.test", "texture_width": 8, "texture_height": 8},
                "bones": [{"name": "arm", "cubes": [{"size": [2, 2, 1], "uv": [7.5, 0]}]}]
            }]
        }
        make_project(self.root, geometry)
        result = mod.generate_geometry_uv_template(self.args())
        codes = {finding["code"] for finding in result["uv_analysis"]["findings"]}
        self.assertIn("UV_OUT_OF_BOUNDS", codes)
        self.assertIn("FRACTIONAL_UV_COORDINATES", codes)

    def test_ambiguous_multi_geometry_requires_identifier(self):
        geometry = classic_geometry()
        geometry["minecraft:geometry"].append({
            "description": {"identifier": "geometry.other", "texture_width": 16, "texture_height": 16},
            "bones": [{"name": "root", "cubes": [{"size": [1, 1, 1], "uv": [0, 0]}]}]
        })
        make_project(self.root, geometry)
        with self.assertRaisesRegex(ValueError, "multiple geometries"):
            mod.generate_geometry_uv_template(self.args())
        result = mod.generate_geometry_uv_template(self.args(geometry_identifier="geometry.other", output="resource_packs/uv-test_RP/textures/uv_templates/other.png"))
        self.assertEqual(result["geometry"]["identifier"], "geometry.other")

    def test_existing_output_is_never_overwritten(self):
        project, _ = make_project(self.root, classic_geometry())
        out_dir = project / "resource_packs/uv-test_RP/textures/uv_templates"
        out_dir.mkdir()
        output = out_dir / "guide.png"
        output.write_bytes(b"KEEP")
        with self.assertRaisesRegex(ValueError, "already exists"):
            mod.generate_geometry_uv_template(self.args())
        self.assertEqual(output.read_bytes(), b"KEEP")

    def test_rejects_path_traversal(self):
        with self.assertRaisesRegex(ValueError, "parent-traversal"):
            mod._validate_args(self.args(output="resource_packs/uv-test_RP/textures/uv_templates/../bad.png"))

    def test_duplicate_json_keys_are_rejected(self):
        duplicate = '{"minecraft:geometry":[],"minecraft:geometry":[]}'
        _, model_file = make_project(self.root, {}, geometry_file_text=duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
            mod._read_geometry(model_file)

    def test_output_pixel_budget_is_enforced(self):
        _, _ = make_project(self.root, {
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.test", "texture_width": 1024, "texture_height": 1024},
                "bones": [{"name": "root", "cubes": [{"size": [1, 1, 1], "uv": [0, 0]}]}]
            }]
        })
        with self.assertRaisesRegex(ValueError, "scaled atlas is too large"):
            mod.generate_geometry_uv_template(self.args(pixel_scale=4))

    def test_tool_schema_and_mcp_handshake(self):
        tool = mod.TOOLS[0]
        self.assertEqual(tool["name"], "generate_geometry_uv_template")
        self.assertEqual(tool["annotations"]["readOnlyHint"], False)
        response = mod.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["result"]["serverInfo"]["name"], "minecraft-bedrock-geometry-uv-template")
        listed = mod.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(listed["result"]["tools"][0]["name"], "generate_geometry_uv_template")

    def test_missing_template_folder_created_safely(self):
        project, _ = make_project(self.root, classic_geometry())
        output = project / "resource_packs/uv-test_RP/textures/uv_templates/guide.png"
        self.assertFalse(output.parent.exists())
        mod.generate_geometry_uv_template(self.args())
        self.assertTrue(output.is_file())

    def test_uv_alias_filter_and_canvas_requirement(self):
        geometry = {
            "minecraft:geometry": [
                {"description": {"identifier": "geometry.other", "texture_width": 16, "texture_height": 16}, "bones": []},
                {"description": {"identifier": "geometry.test", "texture_width": 16, "texture_height": 16}, "bones": [{"name": "root", "cubes": [{"size": [2, 2, 2], "uv": [0, 0]}]}]}
            ]
        }
        make_project(self.root, geometry)
        result = mod.generate_geometry_uv_template(self.args(geometry_identifier="geometry.test"))
        self.assertEqual(result["geometry"]["identifier"], "geometry.test")


    def test_mojang_goat_sample_box_uv_regression(self):
        geometry = {
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.goat", "texture_width": 64, "texture_height": 64},
                "bones": [{"name": "left_back_leg", "cubes": [{"origin": [1, 0, 4], "size": [3, 6, 3], "uv": [36, 29]}]}]
            }]
        }
        regions, findings, _ = mod._extract_regions(geometry["minecraft:geometry"][0], "geometry.goat")
        self.assertEqual(len(regions), 6)
        self.assertFalse(findings)
        self.assertTrue(all(r["bounds"][0] >= 0 and r["bounds"][1] >= 0 and r["bounds"][2] <= 64 and r["bounds"][3] <= 64 for r in regions))

    def test_symlinked_template_directory_is_rejected(self):
        project, _ = make_project(self.root, classic_geometry())
        rp = project / "resource_packs/uv-test_RP"
        outside = self.root / "outside"
        outside.mkdir()
        (rp / "textures/uv_templates").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            mod.generate_geometry_uv_template(self.args())
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_geometry_is_rejected(self):
        project, model_file = make_project(self.root, classic_geometry())
        model_file.unlink()
        target = self.root / "outside.geo.json"
        target.write_text(json.dumps(classic_geometry()), encoding="utf-8")
        model_file.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "contains a symlink"):
            mod.generate_geometry_uv_template(self.args())

    def test_extreme_uv_values_are_not_rendered(self):
        geometry = {
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.test", "texture_width": 16, "texture_height": 16},
                "bones": [{"name": "root", "cubes": [{"size": [1, 1, 1], "uv": [1e100, 0]}]}]
            }]
        }
        make_project(self.root, geometry)
        with self.assertRaisesRegex(ValueError, "no supported cube UV regions"):
            mod.generate_geometry_uv_template(self.args())


    def test_end_to_end_overlap_is_warning_and_included_in_region_map(self):
        geometry = {
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.test", "texture_width": 16, "texture_height": 16},
                "bones": [{"name": "head", "cubes": [{"size": [2, 2, 2], "uv": {
                    "north": {"uv": [1, 1], "uv_size": [2, 2]},
                    "south": {"uv": [1, 1], "uv_size": [2, 2]}
                }}]}]
            }]
        }
        make_project(self.root, geometry)
        result = mod.generate_geometry_uv_template(self.args())
        analysis = result["uv_analysis"]
        self.assertEqual(analysis["regions"], 2)
        self.assertEqual(analysis["detected_overlap_pairs"], 1)
        self.assertIn("UV_REGION_OVERLAP", {f["code"] for f in analysis["findings"]})
        self.assertEqual([r["face"] for r in analysis["region_map"]], ["north", "south"])


if __name__ == "__main__":
    unittest.main()
