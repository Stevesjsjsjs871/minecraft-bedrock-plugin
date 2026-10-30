#!/usr/bin/env python3
"""Bounded, dependency-free PNG validation shared by Bedrock resource tooling.

Validates chunk structure/CRCs and the decompressed scanline stream. It does not
render pixels or prove Minecraft compatibility; it only verifies that a PNG is
structurally and internally consistent.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PngValidationError(ValueError):
    """PNG input is malformed, unsupported, truncated, or exceeds safety limits."""


def validate_png_bytes(
    payload: bytes,
    *,
    max_bytes: int = 16 * 1024 * 1024,
    max_dimension: int = 4096,
    max_pixels: int = 16_777_216,
) -> tuple[int, int]:
    """Validate a PNG fully and return (width, height).

    Supports the five PNG color types, legal bit depths, palette transparency,
    split/consecutive IDAT chunks, optional ancillary chunks and Adam7 interlace.
    The decompressor is bounded by the exact IHDR-derived scanline size plus one
    byte to prevent compressed data from causing unbounded expansion.
    """
    if not isinstance(payload, bytes):
        raise PngValidationError("PNG payload must be bytes")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 45:
        raise ValueError("max_bytes must be an integer >= 45")
    if not isinstance(max_dimension, int) or isinstance(max_dimension, bool) or max_dimension < 1:
        raise ValueError("max_dimension must be a positive integer")
    if not isinstance(max_pixels, int) or isinstance(max_pixels, bool) or max_pixels < 1:
        raise ValueError("max_pixels must be a positive integer")
    if len(payload) < 45 or len(payload) > max_bytes:
        raise PngValidationError(f"PNG size must be between 45 bytes and {max_bytes} bytes")
    if not payload.startswith(PNG_SIGNATURE):
        raise PngValidationError("file does not have a PNG signature")

    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    legal_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = 0
    seen_ihdr = seen_plte = seen_trns = seen_idat = seen_iend = False
    idat_finished = False
    palette_entries: int | None = None
    idat_parts: list[bytes] = []
    chunk_count = 0
    max_chunks = 4096

    while offset < len(payload):
        chunk_count += 1
        if chunk_count > max_chunks:
            raise PngValidationError(f"PNG exceeds the {max_chunks}-chunk structural limit")
        if len(payload) - offset < 12:
            raise PngValidationError("PNG contains a truncated chunk header")
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(payload):
            raise PngValidationError("PNG contains a truncated chunk body")
        if any(not (65 <= byte <= 90 or 97 <= byte <= 122) for byte in kind):
            raise PngValidationError("PNG chunk type contains non-letter bytes")
        if kind[2] & 0x20:
            raise PngValidationError("PNG chunk uses a lowercase reserved third type character")

        data = payload[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + length:end])[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != expected_crc:
            label = kind.decode("ascii", "replace")
            raise PngValidationError(f"PNG {label} chunk CRC checksum failed")

        if not seen_ihdr:
            if kind != b"IHDR" or length != 13:
                raise PngValidationError("PNG must begin with a 13-byte IHDR chunk")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", data)
            if width < 1 or height < 1 or width > max_dimension or height > max_dimension or width * height > max_pixels:
                raise PngValidationError("PNG dimensions are outside the configured safety limits")
            if color_type not in legal_depths or bit_depth not in legal_depths[color_type]:
                raise PngValidationError("PNG IHDR uses an illegal bit-depth/color-type combination")
            if compression != 0 or filter_method != 0 or interlace not in {0, 1}:
                raise PngValidationError("PNG IHDR uses an unsupported compression, filter or interlace method")
            seen_ihdr = True
        elif kind == b"IHDR":
            raise PngValidationError("PNG contains a duplicate IHDR chunk")

        if kind == b"PLTE":
            if seen_plte or seen_trns or seen_idat or length < 3 or length > 768 or length % 3:
                raise PngValidationError("PNG PLTE chunk is duplicated, misplaced or has an invalid palette length")
            if color_type in {0, 4}:
                raise PngValidationError("PNG grayscale color types must not contain a PLTE chunk")
            palette_entries = length // 3
            if color_type == 3 and palette_entries > (1 << bit_depth):
                raise PngValidationError("PNG indexed palette contains more entries than its bit depth allows")
            seen_plte = True
        elif kind == b"tRNS":
            if seen_trns or seen_idat or color_type in {4, 6}:
                raise PngValidationError("PNG tRNS chunk is duplicated, misplaced or invalid for its color type")
            if color_type == 0 and length != 2:
                raise PngValidationError("grayscale PNG tRNS must contain exactly two bytes")
            if color_type == 2 and length != 6:
                raise PngValidationError("truecolor PNG tRNS must contain exactly six bytes")
            if color_type == 3 and (not seen_plte or palette_entries is None or length < 1 or length > palette_entries):
                raise PngValidationError("indexed PNG tRNS must follow PLTE and not exceed its palette")
            seen_trns = True
        elif kind == b"IDAT":
            if idat_finished:
                raise PngValidationError("PNG IDAT chunks must be consecutive")
            if color_type == 3 and not seen_plte:
                raise PngValidationError("indexed PNG must contain PLTE before IDAT")
            seen_idat = True
            idat_parts.append(data)
        else:
            if seen_idat:
                idat_finished = True
            if kind == b"IEND":
                if length != 0 or not seen_idat or end != len(payload):
                    raise PngValidationError("PNG IEND must be empty, follow IDAT and terminate the file")
                seen_iend = True
                offset = end
                break
            # PLTE, IDAT and IEND are the only critical chunks besides IHDR.
            if kind[0] & 0x20 == 0 and kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
                raise PngValidationError(f"PNG contains an unknown critical chunk {kind.decode('ascii')}")

        offset = end

    if not (seen_ihdr and seen_idat and seen_iend):
        raise PngValidationError("PNG must contain IHDR, IDAT and IEND chunks")

    bits_per_pixel = channels_by_type[color_type] * bit_depth
    if interlace == 0:
        passes = ((0, 0, 1, 1),)
    else:
        passes = (
            (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8),
            (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
        )
    pass_rows: list[tuple[int, int]] = []
    expected_size = 0
    for x_start, y_start, x_step, y_step in passes:
        pass_width = (width - x_start + x_step - 1) // x_step if width > x_start else 0
        pass_height = (height - y_start + y_step - 1) // y_step if height > y_start else 0
        if pass_width and pass_height:
            row_bytes = (pass_width * bits_per_pixel + 7) // 8
            pass_rows.append((row_bytes, pass_height))
            expected_size += (row_bytes + 1) * pass_height
    if expected_size < 1:
        raise PngValidationError("PNG IHDR produces an empty scanline stream")

    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(b"".join(idat_parts), expected_size + 1)
        if len(decoded) > expected_size or decompressor.unconsumed_tail:
            raise PngValidationError("PNG IDAT expands beyond the scanline size declared by IHDR")
        decoded += decompressor.flush(expected_size + 1 - len(decoded))
    except zlib.error as exc:
        raise PngValidationError(f"PNG IDAT compression stream is invalid: {exc}") from exc
    if len(decoded) != expected_size or not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail:
        raise PngValidationError("PNG IDAT data does not decode to the exact scanline size declared by IHDR")

    cursor = 0
    for row_bytes, rows in pass_rows:
        stride = row_bytes + 1
        for _ in range(rows):
            if decoded[cursor] > 4:
                raise PngValidationError("PNG scanline uses an unknown filter method")
            cursor += stride
    if cursor != len(decoded):
        raise PngValidationError("PNG scanline layout is inconsistent with IHDR")
    return width, height


def validate_png_file(
    path: Path,
    *,
    max_bytes: int = 16 * 1024 * 1024,
    max_dimension: int = 4096,
    max_pixels: int = 16_777_216,
) -> tuple[int, int]:
    """Read and validate a regular PNG file without following a symlink."""
    if path.is_symlink() or not path.is_file():
        raise PngValidationError("referenced PNG is missing or is not a regular non-symlink file")
    try:
        size = path.stat().st_size
        if size < 45 or size > max_bytes:
            raise PngValidationError(f"PNG size must be between 45 bytes and {max_bytes} bytes")
        payload = path.read_bytes()
    except OSError as exc:
        raise PngValidationError(f"PNG file could not be read: {exc}") from exc
    if len(payload) != size:
        raise PngValidationError("PNG file changed while it was being read")
    return validate_png_bytes(
        payload,
        max_bytes=max_bytes,
        max_dimension=max_dimension,
        max_pixels=max_pixels,
    )
