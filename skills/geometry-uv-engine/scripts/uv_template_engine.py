#!/usr/bin/env python3
"""Render a bounded, transparent Bedrock cube-UV guide without editing source assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import struct
import zlib
from pathlib import Path

from geometry_engine import (
    FACE_AXES, FACES, GeometryError, MAX_CANVAS_DIMENSION, MAX_JSON_BYTES,
    MAX_REGIONS, _pairs_no_duplicates, _reject_nonfinite_constant, analyze_geometry,
)

MAX_OUTPUT_PIXELS = 4_194_304
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_LABEL_CHARS = 24


class TemplateError(ValueError):
    """Raised when a UV guide cannot be generated safely or completely."""


def _classic_faces(size):
    x, y, z = size
    return {
        "west": (0, z, z, y), "north": (z, z, x, y),
        "east": (z + x, z, z, y), "south": (2 * z + x, z, x, y),
        "up": (z, 0, x, z), "down": (z + x, 0, x, z),
    }


def _read_geometry(path):
    source = Path(path).expanduser()
    try:
        before = source.lstat()
    except OSError as exc:
        raise TemplateError(f"geometry file cannot be inspected: {exc}") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise TemplateError("geometry input must be a regular non-symlink file")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(source, flags)
    except OSError as exc:
        raise TemplateError(f"geometry file cannot be opened safely: {exc}") from exc
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise TemplateError("geometry input must be a regular file")
        if before.st_ino and opened.st_ino and (
            before.st_dev != opened.st_dev or before.st_ino != opened.st_ino
        ):
            raise TemplateError("geometry input changed while it was being opened")
        if opened.st_size > MAX_JSON_BYTES:
            raise TemplateError(f"geometry JSON exceeds the {MAX_JSON_BYTES}-byte safety limit")
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            payload = stream.read(MAX_JSON_BYTES + 1)
        if len(payload) > MAX_JSON_BYTES or len(payload) != opened.st_size:
            raise TemplateError("geometry file changed or exceeded its size limit while being read")
    finally:
        if fd >= 0:
            os.close(fd)

    try:
        data = json.loads(
            payload.decode("utf-8-sig"),
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_nonfinite_constant,
        )
    except UnicodeDecodeError as exc:
        raise TemplateError("geometry JSON must be UTF-8 encoded") from exc
    except (json.JSONDecodeError, GeometryError, RecursionError) as exc:
        raise TemplateError(f"invalid geometry JSON: {exc}") from exc
    return data


def _validate_canvas(canvas):
    if not isinstance(canvas, (list, tuple)) or len(canvas) != 2:
        raise TemplateError("canvas must contain width and height")
    width, height = canvas
    for label, value in (("canvas width", width), ("canvas height", height)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TemplateError(f"{label} must be an integer")
        if not 1 <= value <= MAX_CANVAS_DIMENSION:
            raise TemplateError(
                f"{label} must be between 1 and {MAX_CANVAS_DIMENSION} (an analyzer safety limit)"
            )
    return int(width), int(height)


def extract_regions(data, geometry_identifier=None, *, canvas_override=None):
    """Validate geometry and expand supported classic/per-face cube UVs into rectangles."""
    try:
        report = analyze_geometry(data, geometry_identifier=geometry_identifier)
    except GeometryError as exc:
        raise TemplateError(str(exc)) from exc

    declared = report.get("texture_canvas")
    if declared is None:
        if canvas_override is None:
            raise TemplateError(
                "texture canvas dimensions are unknown; supply --canvas WIDTH HEIGHT "
                "or declare texture_width and texture_height"
            )
        canvas = _validate_canvas(canvas_override)
        canvas_source = "user_override"
    else:
        canvas = _validate_canvas((declared.get("width"), declared.get("height")))
        if canvas_override is not None and _validate_canvas(canvas_override) != canvas:
            raise TemplateError("canvas override conflicts with geometry texture dimensions")
        canvas_source = "geometry"

    geometry = data["minecraft:geometry"][report["geometry_index"]]
    regions = []
    review_flags = set()
    for bone in geometry.get("bones", []):
        unsupported = [key for key in ("poly_mesh", "texture_meshes") if key in bone]
        if unsupported:
            raise TemplateError(
                "complete UV guide is unavailable for mesh geometry on bone "
                f"{bone.get('name', '<unnamed>')!r}: {', '.join(unsupported)}"
            )
        bone_name = bone["name"]
        bone_mirror = bone.get("mirror", False)
        if not isinstance(bone_mirror, bool):
            raise TemplateError(f"bone {bone_name!r}.mirror must be a boolean")

        for cube_index, cube in enumerate(bone.get("cubes", [])):
            cube_mirror = cube.get("mirror", bone_mirror)
            if not isinstance(cube_mirror, bool):
                raise TemplateError(f"bone {bone_name!r} cube {cube_index}.mirror must be a boolean")
            if cube_mirror:
                review_flags.add("MIRRORED_FACE_REVIEW")
            size = tuple(float(value) for value in cube["size"])
            uv = cube["uv"]
            selector = {"bone": bone_name, "cube_index": cube_index}

            if isinstance(uv, list):
                u, v = (float(value) for value in uv)
                for face, (du, dv, face_width, face_height) in _classic_faces(size).items():
                    left, top = u + du, v + dv
                    regions.append({
                        **selector, "face": face, "u": left, "v": top,
                        "width": face_width, "height": face_height,
                        "flip_x": False, "flip_y": False, "uv_rotation": 0,
                        "mirrored": cube_mirror,
                        "out_of_bounds": (
                            left < 0 or top < 0
                            or left + face_width > canvas[0]
                            or top + face_height > canvas[1]
                        ),
                    })
            elif isinstance(uv, dict):
                for face, face_data in uv.items():
                    if face not in FACES:
                        continue
                    u, v = (float(value) for value in face_data["uv"])
                    axis = FACE_AXES[face]
                    default_size = (size[axis[0]], size[axis[1]])
                    raw_size = face_data.get("uv_size", default_size)
                    signed_width, signed_height = float(raw_size[0]), float(raw_size[1])
                    rotation = face_data.get("uv_rotation", 0)
                    flip_x, flip_y = signed_width < 0, signed_height < 0
                    left = u + min(0.0, signed_width)
                    top = v + min(0.0, signed_height)
                    face_width, face_height = abs(signed_width), abs(signed_height)
                    if rotation in (90, 270):
                        face_width, face_height = face_height, face_width
                    if flip_x or flip_y:
                        review_flags.add("NEGATIVE_UV_SIZE_REVIEW")
                    regions.append({
                        **selector, "face": face, "u": left, "v": top,
                        "width": face_width, "height": face_height,
                        "flip_x": flip_x, "flip_y": flip_y,
                        "uv_rotation": rotation, "mirrored": cube_mirror,
                        "out_of_bounds": (
                            left < 0 or top < 0
                            or left + face_width > canvas[0]
                            or top + face_height > canvas[1]
                        ),
                    })
            else:
                raise TemplateError(
                    f"bone {bone_name!r} cube {cube_index} has unsupported UV data"
                )
            if len(regions) > MAX_REGIONS:
                raise TemplateError(f"UV region count exceeds the {MAX_REGIONS}-region safety limit")

    if not regions:
        raise TemplateError("selected geometry contains no supported cube UV regions")

    for finding in report.get("findings", []):
        if finding.get("severity") in ("WARN", "FAIL"):
            review_flags.add(finding.get("code", "GEOMETRY_REVIEW"))
    if canvas_source == "user_override":
        review_flags.add("CANVAS_OVERRIDE_USED")

    report = dict(report)
    report["render_canvas"] = {"width": canvas[0], "height": canvas[1]}
    report["render_canvas_source"] = canvas_source
    report["render_bounds_checked"] = True
    report["template_review_flags"] = sorted(review_flags)
    return report, regions


def _chunk(kind, payload):
    return (
        struct.pack(">I", len(payload)) + kind + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def validate_png_bytes(payload, *, max_pixels=MAX_OUTPUT_PIXELS):
    """Validate the exact RGBA8 PNG subset emitted by this renderer."""
    if not isinstance(payload, (bytes, bytearray)) or len(payload) > MAX_OUTPUT_BYTES:
        raise TemplateError("PNG payload is invalid or exceeds the byte safety limit")
    data = bytes(payload)
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise TemplateError("invalid PNG signature")
    chunks, offset = [], 8
    while offset < len(data):
        if offset + 12 > len(data):
            raise TemplateError("truncated PNG chunk header")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        end = offset + 12 + length
        if end > len(data):
            raise TemplateError("truncated PNG chunk payload")
        kind = data[offset + 4:offset + 8]
        chunk_data = data[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length:end])[0]
        if zlib.crc32(kind + chunk_data) & 0xFFFFFFFF != expected_crc:
            raise TemplateError(f"PNG CRC mismatch in {kind!r} chunk")
        chunks.append((kind, chunk_data))
        offset = end
        if kind == b"IEND":
            break
    if offset != len(data):
        raise TemplateError("unexpected data after PNG IEND")
    if [kind for kind, _ in chunks] != [b"IHDR", b"IDAT", b"IEND"]:
        raise TemplateError("PNG must contain exactly IHDR, IDAT and IEND chunks")
    if len(chunks[0][1]) != 13 or chunks[2][1]:
        raise TemplateError("invalid PNG IHDR or IEND payload")

    width, height, depth, color, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", chunks[0][1]
    )
    if width < 1 or height < 1 or width * height > max_pixels:
        raise TemplateError("PNG dimensions exceed the pixel safety limit")
    if (depth, color, compression, filtering, interlace) != (8, 6, 0, 0, 0):
        raise TemplateError("PNG must use non-interlaced 8-bit RGBA encoding")

    if isinstance(max_pixels, bool) or not isinstance(max_pixels, int):
        raise TemplateError("PNG max_pixels must be an integer")
    if not 1 <= max_pixels <= MAX_OUTPUT_PIXELS:
        raise TemplateError(f"PNG max_pixels must be between 1 and {MAX_OUTPUT_PIXELS}")
    expected = height * (width * 4 + 1)
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(chunks[1][1], expected + 1)
    except zlib.error as exc:
        raise TemplateError(f"invalid PNG compressed data: {exc}") from exc
    if (
        len(raw) > expected or decoder.unconsumed_tail
        or len(raw) != expected or not decoder.eof or decoder.unused_data
    ):
        raise TemplateError("PNG decompressed length or stream termination is invalid")
    stride = width * 4 + 1
    for row in range(height):
        if raw[row * stride] > 4:
            raise TemplateError(f"invalid PNG filter type on row {row}")
    return {"width": width, "height": height, "color_type": "RGBA8"}


def encode_png(width, height, pixels, *, max_pixels=MAX_OUTPUT_PIXELS):
    if isinstance(width, bool) or not isinstance(width, int) or width < 1:
        raise TemplateError("PNG width must be a positive integer")
    if isinstance(height, bool) or not isinstance(height, int) or height < 1:
        raise TemplateError("PNG height must be a positive integer")
    if isinstance(max_pixels, bool) or not isinstance(max_pixels, int):
        raise TemplateError("max_pixels must be an integer")
    if not 1 <= max_pixels <= MAX_OUTPUT_PIXELS:
        raise TemplateError(f"max_pixels must be between 1 and {MAX_OUTPUT_PIXELS}")
    if width * height > max_pixels:
        raise TemplateError("PNG dimensions exceed the pixel safety limit")
    if not isinstance(pixels, (bytes, bytearray)) or len(pixels) != width * height * 4:
        raise TemplateError("RGBA pixel buffer length does not match PNG dimensions")

    raw = bytearray()
    stride = width * 4
    for row in range(height):
        raw.append(0)
        start = row * stride
        raw.extend(pixels[start:start + stride])
    compressed = zlib.compress(bytes(raw), level=6)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    result = (
        b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")
    )
    if len(result) > MAX_OUTPUT_BYTES:
        raise TemplateError("encoded PNG exceeds the byte safety limit")
    validate_png_bytes(result, max_pixels=max_pixels)
    return result


_FONT = {
    "A":"010101111101101", "B":"110101110101110", "C":"011100100100011",
    "D":"110101101101110", "E":"111100110100111", "F":"111100110100100",
    "G":"011100101101011", "H":"101101111101101", "I":"111010010010111",
    "J":"001001001101010", "K":"101101110101101", "L":"100100100100111",
    "M":"101111111101101", "N":"101111111111101", "O":"010101101101010",
    "P":"110101110100100", "Q":"010101101111011", "R":"110101110101101",
    "S":"011100010001110", "T":"111010010010010", "U":"101101101101111",
    "V":"101101101101010", "W":"101101111111101", "X":"101101010101101",
    "Y":"101101010010010", "Z":"111001010100111", "0":"111101101101111",
    "1":"010110010010111", "2":"110001010100111", "3":"110001010001110",
    "4":"101101111001001", "5":"111100110001110", "6":"011100110101010",
    "7":"111001010010010", "8":"010101010101010", "9":"010101011001110",
    "-":"000000111000000", "_":"000000000000111", " ":"000000000000000",
}


def _set_pixel(pixels, width, height, x, y, color):
    if 0 <= x < width and 0 <= y < height:
        offset = (y * width + x) * 4
        pixels[offset:offset + 4] = bytes(color)


def _clip_line(x0, y0, x1, y1, width, height):
    """Liang-Barsky clipping bounds raster work to the output canvas."""
    dx, dy = x1 - x0, y1 - y0
    if not math.isfinite(dx) or not math.isfinite(dy):
        return None
    lower, upper = 0.0, 1.0
    for p, q in (
        (-dx, x0), (dx, width - 1 - x0),
        (-dy, y0), (dy, height - 1 - y0),
    ):
        if p == 0:
            if q < 0:
                return None
            continue
        ratio = q / p
        if p < 0:
            if ratio > upper:
                return None
            lower = max(lower, ratio)
        else:
            if ratio < lower:
                return None
            upper = min(upper, ratio)
    if lower > upper:
        return None
    points = (
        (x0 + lower * dx, y0 + lower * dy),
        (x0 + upper * dx, y0 + upper * dy),
    )
    if not all(math.isfinite(value) for point in points for value in point):
        return None
    (left, top), (right, bottom) = points
    return (
        max(0, min(width - 1, round(left))),
        max(0, min(height - 1, round(top))),
        max(0, min(width - 1, round(right))),
        max(0, min(height - 1, round(bottom))),
    )


def _line(pixels, width, height, x0, y0, x1, y1, color):
    clipped = _clip_line(x0, y0, x1, y1, width, height)
    if clipped is None:
        return
    x0, y0, x1, y1 = clipped
    dx, sx = abs(x1 - x0), (1 if x0 < x1 else -1)
    dy, sy = -abs(y1 - y0), (1 if y0 < y1 else -1)
    error = dx + dy
    while True:
        _set_pixel(pixels, width, height, x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += sx
        if doubled <= dx:
            error += dx
            y0 += sy


def _text(pixels, width, height, x, y, label, color, scale):
    cursor = x
    for char in label[:MAX_LABEL_CHARS].upper():
        glyph = _FONT.get(char, _FONT[" "])
        for index, enabled in enumerate(glyph):
            if enabled == "1":
                gx, gy = index % 3, index // 3
                for sy in range(scale):
                    for sx in range(scale):
                        _set_pixel(
                            pixels, width, height,
                            cursor + gx * scale + sx, y + gy * scale + sy, color,
                        )
        cursor += 4 * scale


def _draw_region(pixels, width, height, margin, scale, label_scale, region):
    x0 = margin + region["u"] * scale
    y0 = margin + region["v"] * scale
    x1 = margin + (region["u"] + region["width"]) * scale
    y1 = margin + (region["v"] + region["height"]) * scale
    if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
        raise TemplateError("UV coordinates exceed the renderable numeric range")
    color = (255, 70, 185, 255) if region["out_of_bounds"] else (225, 230, 238, 255)
    _line(pixels, width, height, x0, y0, x1, y0, color)
    _line(pixels, width, height, x1, y0, x1, y1, color)
    _line(pixels, width, height, x1, y1, x0, y1, color)
    _line(pixels, width, height, x0, y1, x0, y0, color)

    if region["out_of_bounds"]:
        if max(x0, x1) >= 0 and min(x0, x1) <= width - 1:
            if max(y0, y1) >= 0 and min(y0, y1) <= height - 1:
                left = max(0, math.ceil(min(x0, x1)))
                right = min(width - 1, math.floor(max(x0, x1)))
                top = max(0, math.ceil(min(y0, y1)))
                bottom = min(height - 1, math.floor(max(y0, y1)))
                step = max(4, scale * 2)
                for yy in range(top, bottom + 1, step):
                    for xx in range(left, right + 1, step):
                        _set_pixel(pixels, width, height, xx, yy, color)

    label = f"{region['bone'][:8]} {region['cube_index']} {region['face'][:2]}"
    label_x = max(0, min(width - 1, round(max(0, min(width - 1, x0 + 1)))))
    label_y = max(0, min(height - 1, round(max(0, min(height - 1, y0 + 1)))))
    _text(pixels, width, height, label_x, label_y, label, (238, 243, 250, 255), label_scale)


def render_template(
    report, regions, *, pixel_scale=4, label_scale=1, margin=2,
    max_pixels=MAX_OUTPUT_PIXELS,
):
    for label, value, low, high in (
        ("pixel_scale", pixel_scale, 1, 8),
        ("label_scale", label_scale, 1, 2),
        ("margin", margin, 0, 64),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise TemplateError(f"{label} must be an integer from {low} to {high}")
    if isinstance(max_pixels, bool) or not isinstance(max_pixels, int):
        raise TemplateError("max_pixels must be an integer")
    if not 1 <= max_pixels <= MAX_OUTPUT_PIXELS:
        raise TemplateError(f"max_pixels must be between 1 and {MAX_OUTPUT_PIXELS}")
    canvas = report.get("render_canvas") or report.get("texture_canvas")
    if not isinstance(canvas, dict):
        raise TemplateError("render canvas is missing; supply an explicit canvas override")
    canvas_width, canvas_height = _validate_canvas((canvas.get("width"), canvas.get("height")))
    if not isinstance(regions, list) or not regions or len(regions) > MAX_REGIONS:
        raise TemplateError(f"regions must contain 1 to {MAX_REGIONS} supported UV rectangles")

    width = canvas_width * pixel_scale + margin * 2
    height = canvas_height * pixel_scale + margin * 2
    total_pixels = width * height
    if total_pixels > max_pixels or total_pixels > MAX_OUTPUT_PIXELS:
        raise TemplateError(
            f"output canvas exceeds pixel budget ({width}x{height}, {total_pixels} pixels)"
        )

    pixels = bytearray(total_pixels * 4)
    grid = (70, 80, 92, 90)
    for y in range(margin, margin + canvas_height * pixel_scale):
        for x in range(margin, margin + canvas_width * pixel_scale):
            if (x - margin) % pixel_scale == 0 or (y - margin) % pixel_scale == 0:
                _set_pixel(pixels, width, height, x, y, grid)
    for region in regions:
        _draw_region(pixels, width, height, margin, pixel_scale, label_scale, region)

    png = encode_png(width, height, pixels, max_pixels=max_pixels)
    info = validate_png_bytes(png, max_pixels=max_pixels)
    out_of_bounds = sum(1 for region in regions if region["out_of_bounds"])
    flags = set(report.get("template_review_flags", []))
    if out_of_bounds:
        flags.add("UV_OUT_OF_BOUNDS")
    if report.get("summary", {}).get("overlaps", 0):
        flags.add("UV_OVERLAP_REVIEW")
    render_status = "WARN" if flags else "PASS"
    return png, {
        "width": info["width"], "height": info["height"],
        "texture_width": canvas_width, "texture_height": canvas_height,
        "canvas_source": report.get("render_canvas_source", "geometry"),
        "pixel_scale": pixel_scale, "regions": len(regions),
        "out_of_bounds": out_of_bounds,
        "geometry_status": report.get("summary", {}).get("status", "UNKNOWN"),
        "render_status": render_status, "review_flags": sorted(flags),
        "png_validated": True, "pixel_budget": max_pixels,
    }


def _safe_output_path(path):
    target = Path(path).expanduser()
    if not target.name or target.name in {".", ".."}:
        raise TemplateError("output path must name a file")
    try:
        parent = target.parent.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise TemplateError(f"output parent directory must already exist: {exc}") from exc
    if not parent.is_dir():
        raise TemplateError("output parent must be an existing directory")
    destination = parent / target.name
    if target.is_symlink() or destination.is_symlink():
        raise TemplateError("refusing to write through an output symlink")
    if target.exists() or destination.exists():
        raise TemplateError("refusing to overwrite an existing output file")
    return destination


def write_new_png(path, payload):
    validate_png_bytes(payload)
    destination = _safe_output_path(path)
    digest = hashlib.sha256(payload).hexdigest()
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(destination, flags, 0o600)
    except FileExistsError as exc:
        raise TemplateError("output file appeared during creation; refusing to overwrite it") from exc
    except OSError as exc:
        raise TemplateError(f"output file cannot be created safely: {exc}") from exc
    created = os.fstat(fd)
    try:
        with os.fdopen(fd, "r+b") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            written = stream.read(MAX_OUTPUT_BYTES + 1)
        if written != payload:
            raise TemplateError("written PNG bytes differ from generated payload")
        validate_png_bytes(written)
        if hashlib.sha256(written).hexdigest() != digest:
            raise TemplateError("on-disk PNG SHA-256 does not match generated bytes")
    except Exception:
        try:
            current = destination.lstat()
            if current.st_dev == created.st_dev and current.st_ino == created.st_ino:
                destination.unlink()
        except OSError:
            pass
        raise
    return destination, digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geometry", help="Path to one Bedrock .geo.json file")
    parser.add_argument("output", help="New PNG path; existing files and symlinks are refused")
    parser.add_argument("--geometry-identifier", help="Exact description.identifier when needed")
    parser.add_argument("--canvas", nargs=2, type=int, metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--pixel-scale", type=int, default=4)
    parser.add_argument("--label-scale", type=int, default=1)
    parser.add_argument("--margin", type=int, default=2)
    parser.add_argument("--max-pixels", type=int, default=MAX_OUTPUT_PIXELS)
    args = parser.parse_args(argv)
    try:
        data = _read_geometry(args.geometry)
        report, regions = extract_regions(
            data, args.geometry_identifier, canvas_override=args.canvas
        )
        png, meta = render_template(
            report, regions, pixel_scale=args.pixel_scale,
            label_scale=args.label_scale, margin=args.margin,
            max_pixels=args.max_pixels,
        )
        destination, digest = write_new_png(args.output, png)
    except (OSError, GeometryError, TemplateError, ValueError, OverflowError) as exc:
        print(json.dumps({
            "status": "FAIL",
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps({
        "status": meta["render_status"], "output": str(destination),
        "sha256": digest, **meta,
    }, ensure_ascii=False, indent=2))
    if meta["geometry_status"] == "FAIL" or meta["render_status"] == "WARN":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
