from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(SERVER_DIR))
import png_validation
from png_validation import PngValidationError, validate_png_bytes, validate_png_file

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def make_png(
    *,
    width: int = 2,
    height: int = 2,
    bit_depth: int = 8,
    color_type: int = 6,
    interlace: int = 0,
    scanlines: bytes | None = None,
    idat: bytes | None = None,
    before_idat: tuple[tuple[bytes, bytes], ...] = (),
    between_idat: tuple[tuple[bytes, bytes], ...] = (),
) -> bytes:
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    if scanlines is None:
        row_bytes = (width * channels * bit_depth + 7) // 8
        scanlines = b"".join(b"\x00" + bytes(row_bytes) for _ in range(height))
    if idat is None:
        idat = zlib.compress(scanlines)
    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, interlace)
    data = PNG_SIGNATURE + chunk(b"IHDR", ihdr)
    for kind, payload in before_idat:
        data += chunk(kind, payload)
    data += chunk(b"IDAT", idat[: max(1, len(idat) // 2)])
    for kind, payload in between_idat:
        data += chunk(kind, payload)
    if len(idat) > 1:
        data += chunk(b"IDAT", idat[max(1, len(idat) // 2):])
    data += chunk(b"IEND", b"")
    return data


class PngValidationTests(unittest.TestCase):
    def test_valid_rgba_png_returns_dimensions(self):
        self.assertEqual(validate_png_bytes(make_png(width=3, height=5)), (3, 5))

    def test_rejects_valid_crc_with_invalid_zlib_stream(self):
        with self.assertRaisesRegex(PngValidationError, "compression stream"):
            validate_png_bytes(make_png(idat=b"not a zlib stream"))

    def test_rejects_wrong_decompressed_scanline_size(self):
        with self.assertRaisesRegex(PngValidationError, "exact scanline size"):
            validate_png_bytes(make_png(scanlines=b"\x00" + b"\x00" * 3))

    def test_rejects_unknown_scanline_filter(self):
        with self.assertRaisesRegex(PngValidationError, "unknown filter"):
            validate_png_bytes(make_png(scanlines=b"\x05" + b"\x00" * 8 + b"\x00" + b"\x00" * 8))

    def test_rejects_chunk_crc_mismatch(self):
        payload = bytearray(make_png())
        payload[-5] ^= 1
        with self.assertRaisesRegex(PngValidationError, "checksum"):
            validate_png_bytes(bytes(payload))

    def test_rejects_nonconsecutive_idat_chunks(self):
        with self.assertRaisesRegex(PngValidationError, "must be consecutive"):
            validate_png_bytes(make_png(between_idat=((b"tEXt", b"x"),)))

    def test_rejects_unknown_critical_chunk(self):
        payload = PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        payload += chunk(b"ABCD", b"x") + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00")) + chunk(b"IEND", b"")
        with self.assertRaisesRegex(PngValidationError, "unknown critical chunk"):
            validate_png_bytes(payload)

    def test_supports_indexed_png_with_palette_and_transparency(self):
        scanlines = b"\x00\x00\x01"
        payload = make_png(
            width=2,
            height=1,
            bit_depth=8,
            color_type=3,
            scanlines=scanlines,
            before_idat=((b"PLTE", b"\xff\x00\x00\x00\xff\x00"), (b"tRNS", b"\xff\x80")),
        )
        self.assertEqual(validate_png_bytes(payload), (2, 1))

    def test_rejects_palette_missing_for_indexed_png(self):
        payload = make_png(width=2, height=1, color_type=3, scanlines=b"\x00\x00\x01")
        with self.assertRaisesRegex(PngValidationError, "must contain PLTE"):
            validate_png_bytes(payload)

    def test_supports_adam7_interlace(self):
        # A 1x1 RGBA image occupies only the first Adam7 pass.
        self.assertEqual(validate_png_bytes(make_png(width=1, height=1, interlace=1, scanlines=b"\x00\x00\x00\x00\x00")), (1, 1))

    def test_rejects_decompression_expansion_beyond_ihdr(self):
        compressed = zlib.compress(b"\x00" * 100_000)
        with self.assertRaisesRegex(PngValidationError, "expands beyond"):
            validate_png_bytes(make_png(width=1, height=1, idat=compressed))

    def test_enforces_dimension_and_byte_limits(self):
        with self.assertRaisesRegex(PngValidationError, "dimensions"):
            validate_png_bytes(make_png(width=3, height=2), max_dimension=2)
        payload = make_png()
        with self.assertRaisesRegex(PngValidationError, "size"):
            validate_png_bytes(payload, max_bytes=len(payload) - 1)

    def test_rejects_invalid_ihdr_combinations(self):
        payload = PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 4, 6, 0, 0, 0))
        payload += chunk(b"IDAT", zlib.compress(b"\x00" * 3)) + chunk(b"IEND", b"")
        with self.assertRaisesRegex(PngValidationError, "illegal bit-depth"):
            validate_png_bytes(payload)

    def test_validates_regular_file_and_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "image.png"
            image.write_bytes(make_png(width=4, height=3))
            self.assertEqual(validate_png_file(image), (4, 3))
            link = root / "link.png"
            try:
                link.symlink_to(image)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(PngValidationError, "non-symlink"):
                validate_png_file(link)


if __name__ == "__main__":
    unittest.main()


class PngValidationImportIsolationTests(unittest.TestCase):
    def test_import_resolves_to_repository_validator_not_test_stub(self):
        self.assertEqual(
            Path(png_validation.__file__).resolve(),
            (SERVER_DIR / "png_validation.py").resolve(),
        )
