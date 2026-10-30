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

# The released base package already supplies server/png_validation.py. The
# isolated overlay test environment injects a tiny IHDR reader so this new
# auditor can be tested without copying or forking that shared validator.
png_stub = types.ModuleType("png_validation")

class PngValidationError(ValueError):
    pass

def validate_png_file(path, **_limits):
    data = path.read_bytes()
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
        raise PngValidationError("invalid PNG signature or IHDR")
    width, height = struct.unpack(">II", data[16:24])
    if width < 1 or height < 1:
        raise PngValidationError("invalid PNG dimensions")
    return width, height

png_stub.PngValidationError = PngValidationError
png_stub.validate_png_file = validate_png_file
with patch.dict(sys.modules, {"png_validation": png_stub}):
    import geometry_uv_audit_mcp as auditor


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def make_png(width: int, height: int) -> bytes:
    raw = b"".join(b"\x00" + b"\x22\x44\x66\xff" * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


class GeometryUvAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        self.project = self.workspace / "forest-addon"
        self.rp = self.project / "resource_packs" / "forest-addon_RP"
        self.models = self.rp / "models" / "entity"
        self.textures = self.rp / "textures" / "entity"
        self.models.mkdir(parents=True)
        self.textures.mkdir(parents=True)
        (self.rp / "manifest.json").write_text(json.dumps({"header": {}, "modules": []}), encoding="utf-8")
        self.geometry_path = self.models / "guardian.geo.json"
        self.texture_path = self.textures / "guardian.png"
        self.texture_path.write_bytes(make_png(64, 64))
        self.env = patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(self.workspace)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def write_geometry(self, payload: dict) -> None:
        self.geometry_path.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def geometry(*, width: int = 64, height: int = 64, cubes: list | None = None) -> dict:
        return {
            "format_version": "1.21.0",
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.guardian", "texture_width": width, "texture_height": height},
                "bones": [{"name": "body", "pivot": [0, 0, 0], "cubes": cubes if cubes is not None else [{"origin": [-4, 0, -2], "size": [8, 12, 4], "uv": [0, 0]}]}],
            }],
        }

    def run_audit(self, **extra):
        args = {"project_directory": "forest-addon", **extra}
        return auditor.audit_geometry_uvs(args)

    def test_classic_box_uv_in_bounds(self):
        self.write_geometry(self.geometry(cubes=[{"origin": [0, 0, 0], "size": [8, 12, 4], "uv": [0, 0]}]))
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["uv_mappings_checked"], 1)
        self.assertEqual(result["summary"]["faces_checked"], 6)
        self.assertEqual(result["findings"], [])

    def test_classic_box_uv_out_of_bounds(self):
        self.write_geometry(self.geometry(cubes=[{"origin": [0, 0, 0], "size": [8, 12, 4], "uv": [48, 0]}]))
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertEqual(result["status"], "issues_found")
        self.assertIn("UV_OUT_OF_BOUNDS", [item["code"] for item in result["findings"]])

    def test_per_face_uv_defaults_to_cube_face_dimensions(self):
        cube = {"origin": [0, 0, 0], "size": [8, 12, 4], "uv": {"north": {"uv": [0, 0]}, "up": {"uv": [16, 0]}}}
        self.write_geometry(self.geometry(cubes=[cube]))
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["uv_mappings_checked"], 2)
        self.assertEqual(result["summary"]["faces_checked"], 2)
        recs = result["files"][0]["geometry"][0]
        self.assertEqual(recs["uv_mappings_checked"], 2)

    def test_per_face_rotation_swaps_bounds_dimensions(self):
        cube = {"origin": [0, 0, 0], "size": [8, 12, 4], "uv": {"north": {"uv": [60, 0], "uv_size": [2, 8], "uv_rotation": 90}}}
        self.write_geometry(self.geometry(cubes=[cube]))
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertIn("UV_OUT_OF_BOUNDS", [item["code"] for item in result["findings"]])

    def test_invalid_rotation_is_error_and_incomplete(self):
        cube = {"origin": [0, 0, 0], "size": [8, 12, 4], "uv": {"north": {"uv": [0, 0], "uv_rotation": 45}}}
        self.write_geometry(self.geometry(cubes=[cube]))
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertIn("INVALID_UV_ROTATION", [item["code"] for item in result["findings"]])
        self.assertFalse(result["summary"]["analysis_complete"])

    def test_explicit_png_validated_and_used_as_canvas_fallback(self):
        payload = self.geometry(cubes=[{"origin": [0, 0, 0], "size": [8, 12, 4], "uv": [0, 0]}])
        del payload["minecraft:geometry"][0]["description"]["texture_width"]
        del payload["minecraft:geometry"][0]["description"]["texture_height"]
        self.write_geometry(payload)
        result = self.run_audit(
            geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json",
            texture_path="resource_packs/forest-addon_RP/textures/entity/guardian.png",
        )
        self.assertEqual(result["texture"]["status"], "valid_png")
        self.assertEqual(result["files"][0]["geometry"][0]["texture_size_used"], [64, 64])
        self.assertTrue(result["summary"]["analysis_complete"])

    def test_declared_and_actual_png_dimension_mismatch_is_warning(self):
        self.texture_path.write_bytes(make_png(32, 32))
        self.write_geometry(self.geometry())
        result = self.run_audit(
            geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json",
            texture_path="resource_packs/forest-addon_RP/textures/entity/guardian.png",
        )
        self.assertIn("TEXTURE_CANVAS_DIMENSION_MISMATCH", [item["code"] for item in result["findings"]])
        self.assertEqual(result["status"], "ok")

    def test_actual_png_can_cause_additional_bounds_error(self):
        self.texture_path.write_bytes(make_png(16, 16))
        self.write_geometry(self.geometry(cubes=[{"origin": [0, 0, 0], "size": [8, 12, 4], "uv": [0, 0]}]))
        result = self.run_audit(
            geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json",
            texture_path="resource_packs/forest-addon_RP/textures/entity/guardian.png",
        )
        codes = [item["code"] for item in result["findings"]]
        self.assertIn("TEXTURE_CANVAS_DIMENSION_MISMATCH", codes)
        self.assertIn("UV_OUTSIDE_ACTUAL_TEXTURE", codes)

    def test_missing_canvas_without_png_is_incomplete(self):
        payload = self.geometry()
        del payload["minecraft:geometry"][0]["description"]["texture_width"]
        del payload["minecraft:geometry"][0]["description"]["texture_height"]
        self.write_geometry(payload)
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertIn("TEXTURE_CANVAS_UNKNOWN", [item["code"] for item in result["findings"]])
        self.assertFalse(result["summary"]["analysis_complete"])

    def test_recursive_scan(self):
        self.write_geometry(self.geometry())
        result = self.run_audit()
        self.assertEqual(result["summary"]["geometry_files_scanned"], 1)
        self.assertEqual(result["summary"]["cubes_scanned"], 1)

    def test_duplicate_json_keys_rejected(self):
        self.geometry_path.write_text('{"minecraft:geometry":[],"minecraft:geometry":[]}', encoding="utf-8")
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertIn("INVALID_GEOMETRY_JSON", [item["code"] for item in result["findings"]])
        self.assertFalse(result["summary"]["analysis_complete"])

    def test_poly_mesh_reported_as_outside_scope(self):
        geometry = self.geometry()
        geometry["minecraft:geometry"][0]["bones"][0]["poly_mesh"] = {"positions": [], "normals": [], "uvs": [], "polys": []}
        self.write_geometry(geometry)
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertIn("UNSUPPORTED_MESH_UV_SCOPE", [item["code"] for item in result["findings"]])
        self.assertFalse(result["summary"]["analysis_complete"])

    def test_path_constraints(self):
        with self.assertRaises(ValueError):
            auditor._validate_args({"project_directory": "forest-addon", "texture_path": "resource_packs/forest-addon_RP/textures/entity/a.png"})
        with self.assertRaises(ValueError):
            auditor._validate_args({"project_directory": "forest-addon", "geometry_path": "../../outside.json"})

    def test_symlink_geometry_is_rejected(self):
        target = self.models / "real.geo.json"
        target.write_text(json.dumps(self.geometry()), encoding="utf-8")
        link = self.models / "linked.geo.json"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available on this platform")
        with self.assertRaises(ValueError):
            auditor._safe_resolve(self.rp, "models/entity/linked.geo.json", label="geometry_path")


    def test_invalid_explicit_png_is_reported_and_marks_partial(self):
        payload = self.geometry()
        self.write_geometry(payload)
        self.texture_path.write_bytes(b"not a png")
        result = self.run_audit(
            geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json",
            texture_path="resource_packs/forest-addon_RP/textures/entity/guardian.png",
        )
        self.assertIn("INVALID_TEXTURE_PNG", [item["code"] for item in result["findings"]])
        self.assertFalse(result["summary"]["analysis_complete"])

    def test_unknown_face_is_rejected(self):
        cube = {"origin": [0, 0, 0], "size": [8, 12, 4], "uv": {"front": {"uv": [0, 0]}}}
        self.write_geometry(self.geometry(cubes=[cube]))
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertIn("UNKNOWN_UV_FACE", [item["code"] for item in result["findings"]])
        self.assertFalse(result["summary"]["analysis_complete"])

    def test_audit_is_read_only(self):
        self.write_geometry(self.geometry())
        before_geometry = self.geometry_path.read_bytes()
        before_texture = self.texture_path.read_bytes()
        self.run_audit(
            geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json",
            texture_path="resource_packs/forest-addon_RP/textures/entity/guardian.png",
        )
        self.assertEqual(self.geometry_path.read_bytes(), before_geometry)
        self.assertEqual(self.texture_path.read_bytes(), before_texture)

    def test_mcp_initialize_and_tools_list(self):
        init = auditor.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "minecraft-bedrock-geometry-uv-auditor")
        listed = auditor.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual([tool["name"] for tool in listed["result"]["tools"]], ["audit_geometry_uvs"])

    def test_goat_sample_classic_uvs_fit_declared_canvas(self):
        # Version-matched sample geometry is reproduced here as a compact fixture.
        bones = [
            {"name": "leg", "pivot": [0, 0, 0], "cubes": [{"origin": [1, 0, 4], "size": [3, 6, 3], "uv": [36, 29]}]},
            {"name": "body", "pivot": [0, 0, 0], "cubes": [
                {"origin": [-4, 6, -7], "size": [9, 11, 16], "uv": [1, 1]},
                {"origin": [-5, 4, -8], "size": [11, 14, 11], "uv": [0, 28]},
            ]},
            {"name": "head", "pivot": [0, 0, 0], "cubes": [
                {"origin": [-2, 15, -16], "size": [5, 7, 10], "uv": [34, 46]},
                {"origin": [3, 19, -10], "size": [3, 2, 1], "uv": [2, 61]},
                {"origin": [-5, 19, -10], "size": [3, 2, 1], "uv": [2, 61]},
                {"origin": [0.5, 6, -14], "size": [0, 7, 5], "uv": [23, 52]},
            ]},
            {"name": "right_horn", "pivot": [0, 0, 0], "cubes": [{"origin": [-1.99, 19, -10], "size": [2, 7, 2], "uv": [12, 55]}]},
        ]
        self.write_geometry({"format_version": "1.21.0", "minecraft:geometry": [{"description": {"identifier": "geometry.goat", "texture_width": 64, "texture_height": 64}, "bones": bones}]})
        result = self.run_audit(geometry_path="resource_packs/forest-addon_RP/models/entity/guardian.geo.json")
        self.assertEqual(result["summary"]["errors"], 0)
        self.assertEqual(result["summary"]["faces_checked"], 6 * sum(len(bone["cubes"]) for bone in bones))


if __name__ == "__main__":
    unittest.main()
