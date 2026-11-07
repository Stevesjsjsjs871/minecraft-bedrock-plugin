#!/usr/bin/env python3
"""Bounded, dependency-free PNG structural validator for Bedrock assets.

This is a structural validator, not a renderer or proof of Minecraft runtime
compatibility. It validates chunk ordering/CRCs and the exact IHDR-derived
scanline stream while bounding compressed expansion and image dimensions.
"""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
_DEPTHS = {
    0: {1, 2, 4, 8, 16},
    2: {8, 16},
    3: {1, 2, 4, 8},
    4: {8, 16},
    6: {8, 16},
}
_ADAM7 = (
    (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8),
    (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
)


class PNGValidationError(ValueError):
    """PNG input is malformed, unsupported, truncated, or exceeds limits."""


def _positive_int(name: str, value: int, minimum: int = 1) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def inspect_png(
    data: bytes,
    *,
    max_bytes: int = 64 * 1024 * 1024,
    max_dimension: int = 4096,
    max_pixels: int = 16_777_216,
    max_chunks: int = 4096,
) -> dict:
    """Validate PNG bytes and return metadata without decoding pixel colors."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("PNG input must be bytes or bytearray")
    _positive_int("max_bytes", max_bytes, 45)
    _positive_int("max_dimension", max_dimension)
    _positive_int("max_pixels", max_pixels)
    _positive_int("max_chunks", max_chunks)
    data = bytes(data)
    if len(data) < 45 or len(data) > max_bytes:
        raise PNGValidationError(f"file size must be between 45 and {max_bytes} bytes")
    if not data.startswith(_SIGNATURE):
        raise PNGValidationError("invalid PNG signature")

    pos = 8
    ihdr = None
    idats: list[bytes] = []
    idat_started = False
    idat_ended = False
    seen_plte = False
    seen_trns = False
    seen_iend = False
    palette_entries = None
    chunks: list[str] = []

    while pos < len(data):
        if len(chunks) >= max_chunks:
            raise PNGValidationError(f"PNG exceeds the {max_chunks}-chunk limit")
        if pos + 12 > len(data):
            raise PNGValidationError("truncated PNG chunk header")
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        end = pos + 12 + size
        if end > len(data):
            raise PNGValidationError(f"truncated {kind!r} chunk")
        if any(not (65 <= c <= 90 or 97 <= c <= 122) for c in kind):
            raise PNGValidationError("PNG chunk type contains non-letter bytes")
        if kind[2] & 0x20:
            raise PNGValidationError("PNG chunk uses a lowercase reserved third character")
        payload = data[pos + 8:pos + 8 + size]
        crc = struct.unpack(">I", data[pos + 8 + size:end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise PNGValidationError(f"CRC mismatch in {kind.decode('ascii', 'replace')} chunk")
        chunks.append(kind.decode("ascii"))

        if ihdr is None:
            if kind != b"IHDR" or size != 13:
                raise PNGValidationError("IHDR must be the first 13-byte chunk")
            width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", payload)
            if not width or not height or width > max_dimension or height > max_dimension or width * height > max_pixels:
                raise PNGValidationError("PNG dimensions exceed configured safety limits")
            if color not in _DEPTHS or depth not in _DEPTHS[color]:
                raise PNGValidationError("invalid bit-depth/color-type combination")
            if comp != 0 or filt != 0 or interlace not in (0, 1):
                raise PNGValidationError("invalid PNG compression, filter or interlace method")
            ihdr = (width, height, depth, color, interlace)
        elif kind == b"IHDR":
            raise PNGValidationError("duplicate IHDR chunk")

        if kind == b"PLTE":
            if seen_plte or seen_trns or idat_started or size < 3 or size > 768 or size % 3:
                raise PNGValidationError("invalid, duplicated or misplaced PLTE chunk")
            if ihdr[3] in (0, 4):
                raise PNGValidationError("grayscale PNG must not contain PLTE")
            palette_entries = size // 3
            if ihdr[3] == 3 and palette_entries > (1 << ihdr[2]):
                raise PNGValidationError("palette has more entries than indexed bit depth allows")
            seen_plte = True
        elif kind == b"tRNS":
            color = ihdr[3]
            if seen_trns or idat_started or color in (4, 6):
                raise PNGValidationError("invalid, duplicated or misplaced tRNS chunk")
            if color == 0 and size != 2:
                raise PNGValidationError("grayscale tRNS must contain two bytes")
            if color == 2 and size != 6:
                raise PNGValidationError("truecolor tRNS must contain six bytes")
            if color == 3 and (not seen_plte or palette_entries is None or not 1 <= size <= palette_entries):
                raise PNGValidationError("indexed tRNS must follow PLTE and fit its palette")
            seen_trns = True

        if kind == b"IDAT":
            if idat_ended:
                raise PNGValidationError("IDAT chunks must be consecutive")
            if ihdr[3] == 3 and not seen_plte:
                raise PNGValidationError("indexed PNG requires PLTE before IDAT")
            idat_started = True
            idats.append(payload)
        elif idat_started:
            idat_ended = True

        if kind == b"IEND":
            if size != 0 or not idat_started or end != len(data):
                raise PNGValidationError("IEND must be empty, follow IDAT and terminate the file")
            seen_iend = True
            pos = end
            break
        if kind[0] & 0x20 == 0 and kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
            raise PNGValidationError(f"unknown critical PNG chunk {kind.decode('ascii')}")
        pos = end

    if ihdr is None or not idats or not seen_iend:
        raise PNGValidationError("PNG must contain IHDR, IDAT and IEND")

    width, height, depth, color, interlace = ihdr
    bits_per_pixel = _CHANNELS[color] * depth
    passes = ((0, 0, 1, 1),) if interlace == 0 else _ADAM7
    row_shapes: list[tuple[int, int]] = []
    expected = 0
    for x0, y0, dx, dy in passes:
        pw = (width - x0 + dx - 1) // dx if width > x0 else 0
        ph = (height - y0 + dy - 1) // dy if height > y0 else 0
        if pw and ph:
            row_bytes = (pw * bits_per_pixel + 7) // 8
            row_shapes.append((row_bytes, ph))
            expected += (row_bytes + 1) * ph
    if expected < 1:
        raise PNGValidationError("PNG scanline stream is empty")

    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(b"".join(idats), expected + 1)
        if len(raw) > expected or decoder.unconsumed_tail:
            raise PNGValidationError("IDAT expands beyond the IHDR-declared scanline size")
        raw += decoder.flush(expected + 1 - len(raw))
    except zlib.error as exc:
        raise PNGValidationError(f"invalid IDAT compression stream: {exc}") from exc
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise PNGValidationError("IDAT does not decode to the exact IHDR-declared scanline size")

    cursor = 0
    for row_bytes, rows in row_shapes:
        for _ in range(rows):
            if raw[cursor] > 4:
                raise PNGValidationError("unknown PNG scanline filter")
            cursor += row_bytes + 1
    if cursor != len(raw):
        raise PNGValidationError("PNG scanline layout does not match IHDR")

    return {
        "valid": True, "width": width, "height": height, "bit_depth": depth,
        "color_type": color, "interlaced": bool(interlace), "file_bytes": len(data),
        "decoded_bytes": len(raw), "chunks": chunks,
    }


def validate_file(
    path: str | Path,
    *,
    max_bytes: int = 64 * 1024 * 1024,
    max_dimension: int = 4096,
    max_pixels: int = 16_777_216,
    max_chunks: int = 4096,
) -> dict:
    """Validate a regular, non-symlink PNG and detect size changes while reading."""
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise PNGValidationError("PNG path must be a regular non-symlink file")
    try:
        size = p.stat().st_size
        if size < 45 or size > max_bytes:
            raise PNGValidationError(f"file size must be between 45 and {max_bytes} bytes")
        payload = p.read_bytes()
    except OSError as exc:
        raise PNGValidationError(f"PNG file could not be read: {exc}") from exc
    if len(payload) != size:
        raise PNGValidationError("PNG file changed while it was being read")
    return inspect_png(
        payload, max_bytes=max_bytes, max_dimension=max_dimension,
        max_pixels=max_pixels, max_chunks=max_chunks,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png")
    parser.add_argument("--max-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--max-dimension", type=int, default=4096)
    parser.add_argument("--max-pixels", type=int, default=16_777_216)
    parser.add_argument("--max-chunks", type=int, default=4096)
    args = parser.parse_args(argv)
    try:
        result = validate_file(
            args.png, max_bytes=args.max_bytes, max_dimension=args.max_dimension,
            max_pixels=args.max_pixels, max_chunks=args.max_chunks,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
