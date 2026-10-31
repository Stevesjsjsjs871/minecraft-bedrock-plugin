from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from reference_transfer import (
    TransferError, decode_png_rgba, encode_rgba_png, extract_face_regions,
    transfer, validate_request,
)


def make_geometry(*, uv=(0, 0), texture=(4, 2)):
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": "geometry.test", "texture_width": texture[0], "texture_height": texture[1]},
            "bones": [{"name": "body", "cubes": [{"origin": [0, 0, 0], "size": [1, 1, 1], "uv": list(uv)}]}],
        }],
    }


def base_request(output="resource_packs/demo_RP/textures/entity/result.png"):
    return {
        "project_directory": "demo",
        "geometry_path": "resource_packs/demo_RP/models/entity/test.geo.json",
        "geometry_identifier": "geometry.test",
        "reference_image_path": "resource_packs/demo_RP/textures/references/source.png",
        "base_texture_path": "resource_packs/demo_RP/textures/entity/base.png",
        "output_path": output,
        "mappings": [{
            "selector": {"bone": "body", "cube_index": 0, "face": "north"},
            "source_rect": {"x": 0, "y": 0, "width": 1, "height": 1},
            "sampling": "nearest", "blend_mode": "replace",
        }],
    }


class GeometryRegionTests(unittest.TestCase):
    def test_classic_uv_expands_to_six_exact_face_regions(self):
        geometry = make_geometry()["minecraft:geometry"][0]
        regions, cubes, findings = extract_face_regions(geometry)
        self.assertEqual(cubes, 1)
        self.assertEqual(findings, [])
        self.assertEqual({r["face"] for r in regions}, {"north", "south", "east", "west", "up", "down"})
        north = next(r for r in regions if r["face"] == "north")
        self.assertEqual(north["bounds"], (1.0, 1.0, 2.0, 2.0))

    def test_per_face_uv_rotation_and_signed_size(self):
        geometry = {
            "bones": [{"name": "body", "cubes": [{"size": [2, 3, 1], "uv": {
                "north": {"uv": [6, 4], "uv_size": [-3, 2], "uv_rotation": 90}
            }}]}]
        }
        regions, _, findings = extract_face_regions(geometry)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["bounds"], (6.0, 1.0, 8.0, 4.0))
        self.assertIn("UV_AXIS_FLIP", {f["code"] for f in findings})

    def test_bad_geometry_size_rejected(self):
        with self.assertRaises(TransferError):
            extract_face_regions({"bones": [{"name": "body", "cubes": [{"size": [1, -1, 1], "uv": [0, 0]}]}]})


class PngCodecTests(unittest.TestCase):
    def test_rgba_round_trip(self):
        pixels = bytes((10, 20, 30, 255, 200, 100, 50, 64))
        data = encode_rgba_png(2, 1, pixels)
        self.assertEqual(decode_png_rgba(data), (2, 1, pixels))

    def test_crc_corruption_rejected(self):
        data = bytearray(encode_rgba_png(1, 1, bytes((1, 2, 3, 255))))
        data[29] ^= 0x01
        with self.assertRaisesRegex(TransferError, "CRC"):
            decode_png_rgba(bytes(data))

    def test_wrong_rgba_buffer_rejected(self):
        with self.assertRaises(TransferError):
            encode_rgba_png(1, 1, b"\x00")


class RequestValidationTests(unittest.TestCase):
    def test_rejects_parent_traversal(self):
        req = base_request()
        req["reference_image_path"] = "resource_packs/demo_RP/textures/../../escape.png"
        with self.assertRaises(TransferError):
            validate_request(req)

    def test_rejects_boolean_as_integer_source_coordinate(self):
        req = base_request()
        req["mappings"][0]["source_rect"]["x"] = True
        with self.assertRaises(TransferError):
            validate_request(req)

    def test_rejects_unknown_fields(self):
        req = base_request()
        req["run_shell"] = True
        with self.assertRaises(TransferError):
            validate_request(req)

    def test_rejects_output_collision_with_source(self):
        req = base_request()
        req["output_path"] = req["reference_image_path"]
        with self.assertRaises(TransferError):
            validate_request(req)


class EndToEndTransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        self.project = self.workspace / "demo"
        self.rp = self.project / "resource_packs" / "demo_RP"
        (self.rp / "models/entity").mkdir(parents=True)
        (self.rp / "textures/references").mkdir(parents=True)
        (self.rp / "textures/entity").mkdir(parents=True)
        (self.rp / "manifest.json").write_text("{}", encoding="utf-8")
        (self.rp / "models/entity/test.geo.json").write_text(json.dumps(make_geometry()), encoding="utf-8")
        (self.rp / "textures/references/source.png").write_bytes(encode_rgba_png(1, 1, bytes((255, 0, 0, 255))))
        base = bytes((0, 255, 0, 255)) * 8
        (self.rp / "textures/entity/base.png").write_bytes(encode_rgba_png(4, 2, base))

    def tearDown(self):
        self.tmp.cleanup()

    def test_transfers_exact_face_and_preserves_unmapped_base_pixels(self):
        result = transfer(base_request(), workspace=self.workspace)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["transfer"]["changed_texels"], 1)
        output = self.project / "resource_packs/demo_RP/textures/entity/result.png"
        w, h, rgba = decode_png_rgba(output.read_bytes())
        self.assertEqual((w, h), (4, 2))
        self.assertEqual(tuple(rgba[(1 * w + 1) * 4:(1 * w + 1) * 4 + 4]), (255, 0, 0, 255))
        self.assertEqual(tuple(rgba[:4]), (0, 255, 0, 255))

    def test_refuses_to_overwrite_existing_output(self):
        (self.rp / "textures/entity/result.png").write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            transfer(base_request(), workspace=self.workspace)
        self.assertEqual((self.rp / "textures/entity/result.png").read_bytes(), b"existing")

    def test_rejects_reference_crop_out_of_bounds(self):
        req = base_request()
        req["mappings"][0]["source_rect"] = {"x": 1, "y": 0, "width": 1, "height": 1}
        with self.assertRaisesRegex(TransferError, "source_rect"):
            transfer(req, workspace=self.workspace)

    def test_duplicate_target_requires_explicit_approval(self):
        req = base_request()
        req["mappings"].append(dict(req["mappings"][0]))
        with self.assertRaisesRegex(TransferError, "selected more than once"):
            transfer(req, workspace=self.workspace)

    def test_missing_selector_is_rejected_without_creating_output(self):
        req = base_request()
        req["mappings"][0]["selector"]["bone"] = "not-a-bone"
        with self.assertRaisesRegex(TransferError, "matched no"):
            transfer(req, workspace=self.workspace)
        self.assertFalse((self.rp / "textures/entity/result.png").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
