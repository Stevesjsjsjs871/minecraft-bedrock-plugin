from __future__ import annotations
import struct, zlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import reference_transfer as transfer_module

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

    def test_png_chunk_count_limit(self):
        data = encode_rgba_png(1, 1, bytes((1, 2, 3, 255)))
        # Add many valid ancillary chunks before IEND; total bytes remain well below the file cap.
        chunk = struct.pack(">I", 0) + b"tEXt" + struct.pack(">I", zlib.crc32(b"tEXt") & 0xffffffff)
        payload = data[:-12] + chunk * (transfer_module.MAX_PNG_CHUNKS + 1) + data[-12:]
        with self.assertRaisesRegex(TransferError, "chunk limit"):
            decode_png_rgba(payload)


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

    def test_duplicate_target_layering_requires_explicit_opt_in(self):
        req = base_request()
        req["mappings"].append(dict(req["mappings"][0]))
        req["allow_uv_overlap"] = True
        result = transfer(req, workspace=self.workspace)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["transfer"]["duplicate_region_selections"], 1)
        self.assertTrue(any(w["code"] == "ORDERED_MAPPING_LAYERS" for w in result["transfer"]["warnings"]))

    def test_geometry_uv_overlap_requires_opt_in(self):
        geo_path = self.rp / "models/entity/test.geo.json"
        geometry = json.loads(geo_path.read_text())
        geometry["minecraft:geometry"][0]["bones"].append({"name": "overlay", "cubes": [{"origin": [0, 0, 0], "size": [1, 1, 1], "uv": [0, 0]}]})
        geo_path.write_text(json.dumps(geometry))
        with self.assertRaisesRegex(TransferError, "UV overlap"):
            transfer(base_request(), workspace=self.workspace)

    def test_base_texture_dimensions_must_match_geometry(self):
        geo_path = self.rp / "models/entity/test.geo.json"
        geometry = make_geometry(texture=(4, 4))
        geo_path.write_text(json.dumps(geometry))
        with self.assertRaisesRegex(TransferError, "geometry requires"):
            transfer(base_request(), workspace=self.workspace)
        self.assertFalse((self.rp / "textures/entity/result.png").exists())

    def test_geometry_uv_out_of_bounds_refuses_output(self):
        geo_path = self.rp / "models/entity/test.geo.json"
        geo_path.write_text(json.dumps(make_geometry(uv=(3, 1))))
        with self.assertRaisesRegex(TransferError, "exceed declared"):
            transfer(base_request(), workspace=self.workspace)
        self.assertFalse((self.rp / "textures/entity/result.png").exists())

    def test_reference_and_base_paths_must_be_distinct_from_output(self):
        req = base_request()
        req["output_path"] = req["base_texture_path"]
        with self.assertRaisesRegex(TransferError, "must be distinct"):
            validate_request(req)

    def test_base_texture_path_must_be_in_entity_texture_directory(self):
        req = base_request()
        req["base_texture_path"] = req["reference_image_path"]
        with self.assertRaisesRegex(TransferError, "inside RP textures/entity"):
            validate_request(req)

    def test_invalid_sampling_type_is_rejected(self):
        req = base_request()
        req["mappings"][0]["sampling"] = []
        with self.assertRaisesRegex(TransferError, "sampling"):
            validate_request(req)

    def test_invalid_selector_value_type_is_rejected(self):
        req = base_request()
        req["mappings"][0]["selector"]["face"] = ["north"]
        with self.assertRaisesRegex(TransferError, "selector face"):
            validate_request(req)

    def test_boolean_opacity_and_rotation_are_rejected(self):
        req = base_request()
        req["mappings"][0]["opacity"] = True
        with self.assertRaisesRegex(TransferError, "opacity"):
            validate_request(req)
        req = base_request()
        req["mappings"][0]["rotation"] = True
        with self.assertRaisesRegex(TransferError, "rotation"):
            validate_request(req)

    def test_non_boolean_flip_is_rejected(self):
        req = base_request()
        req["mappings"][0]["flip_x"] = 1
        with self.assertRaisesRegex(TransferError, "flip_x/flip_y"):
            validate_request(req)

    def test_symlinked_reference_base_and_geometry_are_rejected(self):
        outside = self.workspace / "outside.png"
        outside.write_bytes((self.rp / "textures/references/source.png").read_bytes())
        ref_link = self.rp / "textures/references/linked.png"
        ref_link.symlink_to(outside)
        req = base_request()
        req["reference_image_path"] = "resource_packs/demo_RP/textures/references/linked.png"
        with self.assertRaisesRegex(TransferError, "symlink"):
            transfer(req, workspace=self.workspace)

        base_link = self.rp / "textures/entity/linked-base.png"
        base_link.symlink_to(self.rp / "textures/entity/base.png")
        req = base_request()
        req["base_texture_path"] = "resource_packs/demo_RP/textures/entity/linked-base.png"
        with self.assertRaisesRegex(TransferError, "symlink"):
            transfer(req, workspace=self.workspace)

        geo_link = self.rp / "models/entity/linked.geo.json"
        geo_link.symlink_to(self.rp / "models/entity/test.geo.json")
        req = base_request()
        req["geometry_path"] = "resource_packs/demo_RP/models/entity/linked.geo.json"
        with self.assertRaisesRegex(TransferError, "symlink"):
            transfer(req, workspace=self.workspace)

    def test_bilinear_alpha_interpolation_avoids_rgb_halo(self):
        # Transparent blue must not contaminate an opaque red sample's RGB.
        source = bytes((255, 0, 0, 255, 0, 0, 255, 0))
        sampled = transfer_module._bilinear(source, 2, {"x": 0, "y": 0, "width": 2, "height": 1}, 0.5, 0.5)
        self.assertGreater(sampled[0], 245)
        self.assertEqual(sampled[2], 0)
        self.assertEqual(sampled[3], 128)

    def test_overlap_scan_budget_fails_closed_without_opt_in(self):
        req = base_request()
        # Force an over-budget region inventory without constructing a huge model.
        region = {"bone": "body", "cube_index": 0, "face": "north", "bounds": (0, 0, 1, 1), "mapping": "test", "uv_rotation": 0}
        regions = [dict(region, cube_index=i) for i in range(710)]
        with patch.object(transfer_module, "extract_face_regions", return_value=(regions, 710, [])):
            with self.assertRaisesRegex(TransferError, "overlap found or overlap analysis hit its budget"):
                transfer(req, workspace=self.workspace)


if __name__ == "__main__":
    unittest.main(verbosity=2)
