import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from generate_texture import PNG_SIGNATURE, STYLES, encode_rgba_png, generate_rgba, write_texture


def parse_png(data):
    assert data.startswith(PNG_SIGNATURE)
    offset = len(PNG_SIGNATURE)
    chunks = []
    while offset < len(data):
        if offset + 8 > len(data):
            raise AssertionError("truncated chunk header")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 8 + length
        if end + 4 > len(data):
            raise AssertionError("truncated chunk data")
        payload = data[offset + 8:end]
        crc = struct.unpack(">I", data[end:end + 4])[0]
        assert zlib.crc32(kind + payload) & 0xffffffff == crc
        chunks.append((kind, payload))
        offset = end + 4
        if kind == b"IEND":
            break
    assert offset == len(data), "trailing bytes after IEND"
    return chunks


class TextureGeneratorTests(unittest.TestCase):
    def test_encodes_real_rgba_png_with_valid_chunks(self):
        raw = bytes([255, 0, 0, 255] * 4)
        chunks = parse_png(encode_rgba_png(2, 2, raw))
        self.assertEqual([c[0] for c in chunks], [b"IHDR", b"IDAT", b"IEND"])
        self.assertEqual(struct.unpack(">IIBBBBB", chunks[0][1]), (2, 2, 8, 6, 0, 0, 0))
        self.assertEqual(zlib.decompress(chunks[1][1]), b"\x00" + raw[:8] + b"\x00" + raw[8:])

    def test_seed_makes_pixel_noise_and_veins_deterministic(self):
        for style in ("pixel_noise", "ore_veins", "stone_noise", "wood_grain", "brick"):
            self.assertEqual(generate_rgba(32, 32, style=style, seed=42), generate_rgba(32, 32, style=style, seed=42))
            self.assertNotEqual(generate_rgba(32, 32, style=style, seed=42), generate_rgba(32, 32, style=style, seed=43))

    def test_all_styles_have_correct_rgba_size(self):
        self.assertEqual(len(STYLES), 10)
        for style in STYLES:
            with self.subTest(style=style):
                self.assertEqual(len(generate_rgba(8, 4, style=style)), 8 * 4 * 4)

    def test_gradient_endpoints_match_requested_colors(self):
        raw = generate_rgba(3, 2, style="horizontal_gradient", base_color="#000000", accent_color="#FFFFFF")
        self.assertEqual(tuple(raw[0:3]), (0, 0, 0))
        self.assertEqual(tuple(raw[(2 * 4):(2 * 4 + 3)]), (255, 255, 255))

    def test_transparency_is_preserved_for_every_style(self):
        for style in STYLES:
            raw = generate_rgba(3, 3, style=style, alpha=0)
            self.assertEqual(raw[3::4], bytes([0] * 9))

    def test_rejects_invalid_dimensions_and_color(self):
        for args in ({"width": 0}, {"width": 1025}, {"width": True}, {"width": 4096, "height": 4096}, {"base_color": "red"}, {"base_color": "+00000"}, {"accent_color": None}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                generate_rgba(**args)

    def test_rejects_unknown_style_and_invalid_alpha_or_seed(self):
        for args in ({"style": "ai_magic"}, {"alpha": 256}, {"alpha": True}, {"seed": True}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                generate_rgba(**args)

    def test_writes_png_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "texture.png"
            result = write_texture(path, width=16, height=16, style="brick")
            self.assertEqual(result["status"], "created")
            self.assertTrue(path.read_bytes().startswith(PNG_SIGNATURE))
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_texture(path, width=16, height=16)
            self.assertEqual(path.read_bytes(), original)

    def test_atomic_write_and_explicit_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "texture.png"
            write_texture(path, style="solid", base_color="#112233")
            first = path.read_bytes()
            write_texture(path, style="solid", base_color="#445566", force=True)
            self.assertNotEqual(path.read_bytes(), first)
            self.assertEqual(list(Path(tmp).glob("*.tmp-*")), [])

    def test_refuses_symlink_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.png"
            target.write_bytes(b"keep")
            link = root / "link.png"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this host")
            with self.assertRaises(ValueError):
                write_texture(link)
            self.assertEqual(target.read_bytes(), b"keep")

    def test_requires_png_suffix_and_existing_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                write_texture(Path(tmp) / "texture.json")
            with self.assertRaises(ValueError):
                write_texture(Path(tmp) / "missing" / "texture.png")

    def test_cli_writes_machine_readable_json_and_reports_errors(self):
        script = Path(__file__).with_name("generate_texture.py")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "cli.png"
            ok = subprocess.run([sys.executable, str(script), str(output), "--style", "ore_veins", "--seed", "7"], capture_output=True, text=True, check=False)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            payload = json.loads(ok.stdout)
            self.assertEqual(payload["status"], "created")
            self.assertTrue(output.is_file())
            err = subprocess.run([sys.executable, str(script), str(Path(tmp) / "bad.png"), "--width", "0"], capture_output=True, text=True, check=False)
            self.assertEqual(err.returncode, 2)
            self.assertEqual(json.loads(err.stderr)["status"], "error")


if __name__ == "__main__":
    unittest.main()
