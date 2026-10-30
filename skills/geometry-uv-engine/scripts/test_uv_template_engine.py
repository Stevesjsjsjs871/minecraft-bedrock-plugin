from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from uv_template_engine import (
    MAX_OUTPUT_PIXELS, TemplateError, encode_png, extract_regions,
    render_template, validate_png_bytes, write_new_png,
)


def geometry(uv, *, width=64, height=64, bone_extra=None, cube_extra=None):
    description = {"identifier": "geometry.test"}
    if width is not None:
        description["texture_width"] = width
    if height is not None:
        description["texture_height"] = height
    cube = {"origin": [0, 0, 0], "size": [4, 6, 2], "uv": uv}
    if cube_extra:
        cube.update(cube_extra)
    bone = {"name": "root", "cubes": [cube]}
    if bone_extra:
        bone.update(bone_extra)
    return {
        "format_version": "1.21.0",
        "minecraft:geometry": [{"description": description, "bones": [bone]}],
    }


class UVTemplateTests(unittest.TestCase):
    def test_classic_uv_expands_six_faces(self):
        report, regions = extract_regions(geometry([0, 0]))
        self.assertEqual(len(regions), 6)
        self.assertEqual({r["face"] for r in regions},
                         {"north", "south", "east", "west", "up", "down"})
        self.assertEqual(report["render_canvas_source"], "geometry")

    def test_classic_net_face_rectangles(self):
        _, regions = extract_regions(geometry([0, 0]))
        by_face = {r["face"]: r for r in regions}
        self.assertEqual(
            (by_face["north"]["u"], by_face["north"]["v"],
             by_face["north"]["width"], by_face["north"]["height"]),
            (2.0, 2.0, 4.0, 6.0),
        )
        self.assertEqual(
            (by_face["up"]["u"], by_face["up"]["v"],
             by_face["up"]["width"], by_face["up"]["height"]),
            (2.0, 0.0, 4.0, 2.0),
        )

    def test_per_face_default_extents_and_rotation(self):
        uv = {
            "north": {"uv": [3, 4]},
            "east": {"uv": [10, 10], "uv_size": [2, 6], "uv_rotation": 90},
        }
        _, regions = extract_regions(geometry(uv))
        by_face = {r["face"]: r for r in regions}
        self.assertEqual((by_face["north"]["width"], by_face["north"]["height"]), (4.0, 6.0))
        self.assertEqual((by_face["east"]["width"], by_face["east"]["height"]), (6.0, 2.0))

    def test_negative_uv_size_is_normalized_and_flagged(self):
        report, regions = extract_regions(
            geometry({"north": {"uv": [8, 9], "uv_size": [-4, 6]}})
        )
        region = regions[0]
        self.assertEqual((region["u"], region["v"], region["width"], region["height"]),
                         (4.0, 9.0, 4.0, 6.0))
        self.assertTrue(region["flip_x"])
        self.assertIn("NEGATIVE_UV_SIZE_REVIEW", report["template_review_flags"])

    def test_missing_canvas_requires_override(self):
        with self.assertRaisesRegex(TemplateError, "supply --canvas"):
            extract_regions(geometry([0, 0], width=None, height=None))

    def test_explicit_canvas_override_is_recorded(self):
        report, regions = extract_regions(
            geometry([0, 0], width=None, height=None), canvas_override=(64, 32)
        )
        self.assertEqual(report["render_canvas"], {"width": 64, "height": 32})
        self.assertEqual(report["render_canvas_source"], "user_override")
        self.assertIn("CANVAS_OVERRIDE_USED", report["template_review_flags"])
        self.assertTrue(regions)

    def test_canvas_override_must_match_declared_dimensions(self):
        with self.assertRaisesRegex(TemplateError, "conflicts"):
            extract_regions(geometry([0, 0]), canvas_override=(128, 64))

    def test_mesh_geometry_fails_closed(self):
        with self.assertRaisesRegex(TemplateError, "complete UV guide is unavailable"):
            extract_regions(geometry([0, 0], bone_extra={"poly_mesh": {"positions": []}}))

    def test_mirror_is_reported_for_review(self):
        report, regions = extract_regions(geometry([0, 0], cube_extra={"mirror": True}))
        self.assertTrue(all(r["mirrored"] for r in regions))
        self.assertIn("MIRRORED_FACE_REVIEW", report["template_review_flags"])

    def test_invalid_mirror_type_is_rejected(self):
        with self.assertRaisesRegex(TemplateError, "mirror must be a boolean"):
            extract_regions(geometry([0, 0], cube_extra={"mirror": "yes"}))

    def test_template_png_signature_dimensions_and_validation(self):
        report, regions = extract_regions(geometry([0, 0]))
        png, meta = render_template(report, regions, pixel_scale=2, margin=1)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (130, 130))
        self.assertEqual(validate_png_bytes(png)["color_type"], "RGBA8")
        self.assertTrue(meta["png_validated"])

    def test_max_pixels_enforced(self):
        report, regions = extract_regions(geometry([0, 0]))
        with self.assertRaises(TemplateError):
            render_template(report, regions, max_pixels=10)

    def test_hard_pixel_cap_cannot_be_raised(self):
        report, regions = extract_regions(geometry([0, 0]))
        with self.assertRaisesRegex(TemplateError, "between 1 and"):
            render_template(report, regions, max_pixels=MAX_OUTPUT_PIXELS + 1)

    def test_invalid_scale_rejected(self):
        report, regions = extract_regions(geometry([0, 0]))
        with self.assertRaises(TemplateError):
            render_template(report, regions, pixel_scale=0)

    def test_png_encoder_rejects_wrong_buffer_size(self):
        with self.assertRaisesRegex(TemplateError, "buffer length"):
            encode_png(2, 2, b"\x00" * 8)

    def test_png_validator_rejects_crc_corruption(self):
        report, regions = extract_regions(geometry([0, 0]))
        png, _ = render_template(report, regions, pixel_scale=1)
        corrupted = bytearray(png)
        corrupted[29] ^= 0x01
        with self.assertRaisesRegex(TemplateError, "CRC mismatch"):
            validate_png_bytes(corrupted)

    def test_png_validator_rejects_trailing_bytes(self):
        report, regions = extract_regions(geometry([0, 0]))
        png, _ = render_template(report, regions, pixel_scale=1)
        with self.assertRaisesRegex(TemplateError, "after PNG IEND"):
            validate_png_bytes(png + b"extra")

    def test_extreme_uv_coordinates_are_clipped(self):
        report, regions = extract_regions(
            geometry({"north": {"uv": [1e100, 1e100], "uv_size": [4, 6]}})
        )
        png, meta = render_template(report, regions, pixel_scale=1)
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertEqual(meta["out_of_bounds"], 1)
        self.assertEqual(meta["render_status"], "WARN")

    def test_zero_regions_rejected(self):
        doc = geometry([0, 0])
        doc["minecraft:geometry"][0]["bones"][0]["cubes"] = []
        with self.assertRaisesRegex(TemplateError, "no supported cube UV"):
            extract_regions(doc)

    def test_input_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.geo.json"
            target.write_text(json.dumps(geometry([0, 0])), encoding="utf-8")
            link = root / "link.geo.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            from uv_template_engine import _read_geometry
            with self.assertRaisesRegex(TemplateError, "non-symlink"):
                _read_geometry(link)

    def test_output_is_exclusive_and_sha256_verified(self):
        report, regions = extract_regions(geometry([0, 0]))
        png, _ = render_template(report, regions, pixel_scale=1)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "guide.png"
            written, digest = write_new_png(output, png)
            self.assertEqual(written.read_bytes(), png)
            self.assertEqual(hashlib.sha256(written.read_bytes()).hexdigest(), digest)
            before = written.read_bytes()
            with self.assertRaisesRegex(TemplateError, "overwrite"):
                write_new_png(output, png)
            self.assertEqual(written.read_bytes(), before)

    def test_dangling_output_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            link = root / "guide.png"
            try:
                link.symlink_to(root / "missing.png")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            from uv_template_engine import _safe_output_path
            with self.assertRaisesRegex(TemplateError, "symlink"):
                _safe_output_path(link)

    def test_missing_output_parent_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing" / "guide.png"
            from uv_template_engine import _safe_output_path
            with self.assertRaisesRegex(TemplateError, "must already exist"):
                _safe_output_path(output)
            self.assertFalse(output.parent.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
