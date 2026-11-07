import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from png_engine import inspect_png, validate_file, PNGValidationError


def chunk(kind, payload):
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)


def make_png(width=2, height=2, color=6, depth=8, filter_type=0, palette=True, ancillary=False):
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    row_bytes = (width * channels * depth + 7) // 8
    raw = b''.join(bytes([filter_type]) + bytes(row_bytes) for _ in range(height))
    ihdr = struct.pack('>IIBBBBB', width, height, depth, color, 0, 0, 0)
    parts = [b'\x89PNG\r\n\x1a\n', chunk(b'IHDR', ihdr)]
    if color == 3 and palette:
        parts.append(chunk(b'PLTE', b'\x00\x00\x00'))
    if ancillary:
        parts.append(chunk(b'tEXt', b'key\x00value'))
    parts.extend((chunk(b'IDAT', zlib.compress(raw)), chunk(b'IEND', b'')))
    return b''.join(parts)


class TestPNGEngine(unittest.TestCase):
    def test_valid_rgba(self):
        result = inspect_png(make_png())
        self.assertTrue(result['valid'])
        self.assertEqual((result['width'], result['height']), (2, 2))

    def test_valid_rgb_and_ancillary_chunk(self):
        self.assertIn('tEXt', inspect_png(make_png(color=2, ancillary=True))['chunks'])

    def test_indexed_requires_palette(self):
        with self.assertRaises(PNGValidationError):
            inspect_png(make_png(color=3, palette=False))

    def test_bad_signature_and_truncation(self):
        for payload in (b'not png', make_png()[:20]):
            with self.subTest(length=len(payload)), self.assertRaises(PNGValidationError):
                inspect_png(payload)

    def test_bad_crc(self):
        payload = bytearray(make_png())
        payload[29] ^= 1
        with self.assertRaises(PNGValidationError):
            inspect_png(payload)

    def test_trailing_bytes(self):
        with self.assertRaises(PNGValidationError):
            inspect_png(make_png() + b'x')

    def test_zero_dimensions(self):
        with self.assertRaises(PNGValidationError):
            inspect_png(make_png(width=0))

    def test_dimension_and_pixel_limits(self):
        with self.assertRaises(PNGValidationError):
            inspect_png(make_png(width=3), max_dimension=2)
        with self.assertRaises(PNGValidationError):
            inspect_png(make_png(width=3, height=2), max_pixels=5)

    def test_invalid_scanline_filter(self):
        with self.assertRaises(PNGValidationError):
            inspect_png(make_png(filter_type=5))

    def test_file_size_limit_and_invalid_limits(self):
        with self.assertRaises(PNGValidationError):
            inspect_png(make_png(), max_bytes=45)
        for kwargs in ({'max_bytes': True}, {'max_dimension': 0}, {'max_pixels': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                inspect_png(make_png(), **kwargs)

    def test_adam7_scanline_mismatch(self):
        # Valid IHDR metadata with non-interlaced scanlines must not pass as Adam7.
        payload = make_png()
        ihdr = struct.pack('>IIBBBBB', 2, 2, 8, 6, 0, 0, 1)
        payload = payload[:8] + chunk(b'IHDR', ihdr) + payload[8 + 25:]
        with self.assertRaises(PNGValidationError):
            inspect_png(payload)

    def test_unknown_critical_chunk(self):
        payload = make_png()
        ihdr_end = 8 + 25
        payload = payload[:ihdr_end] + chunk(b'ABCD', b'') + payload[ihdr_end:]
        with self.assertRaises(PNGValidationError):
            inspect_png(payload)

    def test_chunk_count_limit_is_enforced(self):
        with self.assertRaisesRegex(PNGValidationError, "chunk limit"):
            inspect_png(make_png(), max_chunks=2)

    def test_validate_file_forwards_chunk_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'texture.png'
            path.write_bytes(make_png())
            with self.assertRaisesRegex(PNGValidationError, "chunk limit"):
                validate_file(path, max_chunks=2)

    def test_max_chunks_rejects_boolean_and_zero(self):
        for value in (True, 0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                inspect_png(make_png(), max_chunks=value)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target.png'
            target.write_bytes(make_png())
            link = root / 'link.png'
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('symlinks are unavailable in this environment')
            with self.assertRaises(PNGValidationError):
                validate_file(link)

    def test_regular_file_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'texture.png'
            path.write_bytes(make_png())
            self.assertTrue(validate_file(path)['valid'])

    def test_non_file_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PNGValidationError):
                validate_file(directory)


if __name__ == '__main__':
    unittest.main()
