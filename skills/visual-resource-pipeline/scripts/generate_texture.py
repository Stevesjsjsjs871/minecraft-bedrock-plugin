#!/usr/bin/env python3
"""Deterministic, dependency-free pixel-art PNG generator for Minecraft Bedrock.

This is a procedural starter generator, not an AI image model. It creates valid
RGBA PNGs, uses a local seed for repeatability, and never overwrites a destination
unless --force is explicitly supplied.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Iterable

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_DIMENSION = 1024
MAX_PIXELS = 1_048_576
STYLES = (
    "pixel_noise", "checker", "stripes", "solid", "vertical_gradient",
    "horizontal_gradient", "brick", "stone_noise", "ore_veins", "wood_grain",
)
_COLOR_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def encode_rgba_png(width: int, height: int, rgba: bytes) -> bytes:
    """Encode RGBA pixels into a standards-compliant PNG using only stdlib."""
    if (not isinstance(width, int) or isinstance(width, bool)
            or not isinstance(height, int) or isinstance(height, bool)):
        raise ValueError("width and height must be integers")
    if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValueError(f"dimensions must be between 1 and {MAX_DIMENSION}")
    if width * height > MAX_PIXELS:
        raise ValueError(f"image cannot exceed {MAX_PIXELS} pixels")
    if not isinstance(rgba, (bytes, bytearray, memoryview)) or len(rgba) != width * height * 4:
        raise ValueError("RGBA buffer length does not match image dimensions")
    stride = width * 4
    scanlines = b"".join(b"\x00" + rgba[y * stride:(y + 1) * stride] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (PNG_SIGNATURE + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(scanlines, 9))
            + _chunk(b"IEND", b""))


def _hex_rgb(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not _COLOR_RE.fullmatch(value):
        raise ValueError("colors must be six-digit RGB hex values such as #AABBCC")
    value = value.removeprefix("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _blend(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = min(1.0, max(0.0, amount))
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b))


def _shade(color: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
    return tuple(min(255, max(0, channel + delta)) for channel in color)


def generate_rgba(
    width: int = 16,
    height: int = 16,
    *,
    style: str = "pixel_noise",
    base_color: str = "#777777",
    accent_color: str = "#A0A0A0",
    seed: int = 1,
    alpha: int = 255,
) -> bytes:
    """Generate a deterministic procedural pixel-art texture as raw RGBA bytes."""
    if style not in STYLES:
        raise ValueError(f"style must be one of: {', '.join(STYLES)}")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if not isinstance(alpha, int) or isinstance(alpha, bool) or not 0 <= alpha <= 255:
        raise ValueError("alpha must be an integer between 0 and 255")
    if (not isinstance(width, int) or isinstance(width, bool)
            or not isinstance(height, int) or isinstance(height, bool)):
        raise ValueError("width and height must be integers")
    if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
        raise ValueError(f"dimensions must be within 1..{MAX_DIMENSION} and at most {MAX_PIXELS} pixels")

    base = _hex_rgb(base_color)
    accent = _hex_rgb(accent_color)
    rng = random.Random(seed)
    pixels = bytearray(width * height * 4)

    # Ore uses connected short random walks rather than isolated noise points.
    ore_mask: set[tuple[int, int]] = set()
    if style == "ore_veins":
        seed_count = max(1, width * height // 96)
        steps = max(3, min(14, (width + height) // 4))
        for _ in range(seed_count):
            x, y = rng.randrange(width), rng.randrange(height)
            for _step in range(steps):
                ore_mask.add((x, y))
                x = min(width - 1, max(0, x + rng.choice((-1, 0, 1))))
                y = min(height - 1, max(0, y + rng.choice((-1, 0, 1))))

    # Precompute a staggered brick/mortar pattern at any supported dimension.
    cell_w = max(3, width // 4)
    cell_h = max(2, height // 4)
    mortar = max(1, min(2, cell_w // 5, cell_h // 3))

    for y in range(height):
        for x in range(width):
            color = base
            if style == "solid":
                color = base
            elif style == "checker":
                color = accent if ((x + y) // 2) % 2 else base
            elif style == "stripes":
                color = accent if (x // max(1, width // 4)) % 2 else base
            elif style == "vertical_gradient":
                color = _blend(base, accent, y / max(1, height - 1))
            elif style == "horizontal_gradient":
                color = _blend(base, accent, x / max(1, width - 1))
            elif style == "brick":
                row = y // cell_h
                offset = (cell_w // 2) if row % 2 else 0
                local_x = (x + offset) % cell_w
                if y % cell_h < mortar or local_x < mortar:
                    color = accent
                elif rng.randrange(20) == 0:
                    color = _shade(base, rng.choice((-12, -7, 6)))
            elif style == "stone_noise":
                roll = rng.randrange(16)
                if roll == 0:
                    color = accent
                elif roll <= 2:
                    color = _shade(base, -18)
                elif roll == 3:
                    color = _shade(base, 12)
            elif style == "ore_veins":
                if (x, y) in ore_mask:
                    color = accent
                elif rng.randrange(24) == 0:
                    color = _shade(base, -12)
            elif style == "wood_grain":
                # Slightly jittered vertical grain with occasional dark knots.
                grain_x = x + ((y // max(1, height // 8)) % 3 - 1)
                if grain_x % max(2, width // 5) == 0:
                    color = accent
                elif rng.randrange(18) == 0:
                    color = _shade(base, -14)
            else:  # pixel_noise
                roll = rng.randrange(10)
                if roll < 2:
                    color = accent
                elif roll == 2:
                    color = _shade(base, -24)
                elif roll == 3:
                    color = _shade(base, 18)

            offset = (y * width + x) * 4
            pixels[offset:offset + 4] = bytes((*color, alpha))
    return bytes(pixels)


def write_texture(
    output: str | Path,
    *,
    width: int = 16,
    height: int = 16,
    style: str = "pixel_noise",
    base_color: str = "#777777",
    accent_color: str = "#A0A0A0",
    seed: int = 1,
    alpha: int = 255,
    force: bool = False,
) -> dict:
    """Atomically write a PNG and return machine-readable metadata."""
    destination = Path(output)
    if destination.suffix.lower() != ".png":
        raise ValueError("output path must end with .png")
    if destination.is_symlink():
        raise ValueError("refusing to write through a symlink")
    rgba = generate_rgba(width, height, style=style, base_color=base_color,
                         accent_color=accent_color, seed=seed, alpha=alpha)
    payload = encode_rgba_png(width, height, rgba)
    try:
        parent = destination.parent.resolve(strict=True)
    except OSError as exc:
        raise ValueError("output parent directory must already exist") from exc
    if not parent.is_dir():
        raise ValueError("output parent directory must already exist")
    destination = parent / destination.name
    if destination.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {destination}")
    if destination.exists() and not destination.is_file():
        raise ValueError("destination must be a regular file when --force is used")
    temp_path = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{destination.name}.tmp-", dir=str(parent))
        temp_path = Path(name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if force:
            os.replace(temp_path, destination)
        else:
            # Atomic install that fails if another process creates destination.
            os.link(temp_path, destination)
            temp_path.unlink()
        temp_path = None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
    return {
        "status": "created",
        "path": str(destination),
        "format": "PNG",
        "width": width,
        "height": height,
        "color_type": "RGBA",
        "style": style,
        "seed": seed,
        "bytes_written": len(payload),
        "runtime_status": "NOT RUN",
        "generator_status": "PROCEDURAL_STARTER",
        "note": "Procedural PNG generated by deterministic local algorithms; no AI image synthesis or in-game validation is implied.",
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="Destination .png file")
    parser.add_argument("--width", type=int, default=16)
    parser.add_argument("--height", type=int, default=16)
    parser.add_argument("--style", choices=STYLES, default="pixel_noise")
    parser.add_argument("--base", default="#777777", help="Base RGB color in hex")
    parser.add_argument("--accent", default="#A0A0A0", help="Accent RGB color in hex")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--alpha", type=int, default=255)
    parser.add_argument("--force", action="store_true", help="Allow replacing an existing destination")
    args = parser.parse_args(argv)
    try:
        result = write_texture(args.output, width=args.width, height=args.height,
                               style=args.style, base_color=args.base,
                               accent_color=args.accent, seed=args.seed,
                               alpha=args.alpha, force=args.force)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
