#!/usr/bin/env python3
"""Geometry-aware, deterministic Bedrock texture painter.

The painter applies bounded pixel operations to the exact UV rectangles extracted
from a Bedrock geometry file. It never edits source geometry or a source texture;
all output is a new PNG in the selected Resource Pack textures directory.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import geometry_uv_template_mcp as uv  # shared parser/UV-region implementation
from png_validation import PngValidationError, validate_png_bytes

ROOT = Path(__file__).resolve().parents[1]
try:
    SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

PROJECT_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
COLOR_RE = re.compile(r"#?[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?")
FACES = {"north", "south", "east", "west", "up", "down"}
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PNG_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 16_777_216
MAX_OPERATIONS = 128
MAX_PAINT_PIXELS = 16_777_216
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _tool() -> dict[str, Any]:
    selector = {
        "type": "object",
        "properties": {
            "bone": {"type": "string", "minLength": 1, "maxLength": 64},
            "cube_index": {"type": "integer", "minimum": 0, "maximum": 255},
            "face": {"type": "string", "enum": sorted(FACES)},
        },
        "minProperties": 1,
        "additionalProperties": False,
    }
    operation = {
        "type": "object",
        "properties": {
            "selector": selector,
            "mode": {"type": "string", "enum": ["fill", "border", "checker", "stripes", "gradient", "noise"]},
            "color": {"type": "string", "pattern": r"^#?[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"},
            "secondary_color": {"type": "string", "pattern": r"^#?[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"},
            "opacity": {"type": "integer", "minimum": 0, "maximum": 255, "default": 255},
            "blend_mode": {"type": "string", "enum": ["over", "replace"], "default": "over"},
            "border_width": {"type": "integer", "minimum": 1, "maximum": 32, "default": 1},
            "cell_size": {"type": "integer", "minimum": 1, "maximum": 128, "default": 2},
            "axis": {"type": "string", "enum": ["x", "y"], "default": "x"},
            "seed": {"type": "integer", "minimum": -2147483648, "maximum": 2147483647, "default": 1},
        },
        "required": ["selector", "mode", "color"],
        "additionalProperties": False,
    }
    return {
        "name": "paint_geometry_texture",
        "description": (
            "Create a new Bedrock entity texture by painting deterministic pixel operations into UV regions "
            "extracted from the selected .geo.json geometry. Supports fill, border, checker, stripes, gradient "
            "and seeded noise, filtered by bone/cube/face. Can start from a validated source PNG or a transparent/" 
            "solid canvas. Preserves unpainted source pixels and alpha, requires the canvas dimensions to match "
            "geometry texture_width/texture_height, refuses out-of-bounds UV regions and never overwrites files. "
            "This is structured pixel painting, not AI image synthesis or a 3D renderer. Minecraft runtime remains NOT RUN."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
                "geometry_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "output_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "geometry_identifier": {"type": "string", "minLength": 1, "maxLength": 128},
                "source_texture_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "background_color": {"type": "string", "pattern": r"^#?[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"},
                "operations": {"type": "array", "minItems": 1, "maxItems": MAX_OPERATIONS, "items": operation},
                "allow_uv_overlap": {"type": "boolean", "default": False},
            },
            "required": ["project_directory", "geometry_path", "output_path", "operations"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    }


TOOLS = [_tool()]
TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        result["error"]["details"] = details
    return result


def _safe_relative(value: Any, label: str, *, minimum_parts: int = 4) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{label} must be a relative POSIX path of at most 512 characters")
    if "\\" in value or "\x00" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"{label} must be a safe relative POSIX path")
    parts = value.split("/")
    if len(parts) < minimum_parts or any(p in {"", ".", ".."} for p in parts):
        raise ValueError(f"{label} contains an empty, dot, traversal or incomplete path segment")
    return value


def _parse_color(value: Any, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, str) or not COLOR_RE.fullmatch(value):
        raise ValueError(f"{label} must be #RRGGBB or #RRGGBBAA")
    raw = value.lstrip("#")
    if len(raw) == 6:
        raw += "FF"
    return tuple(bytes.fromhex(raw))  # type: ignore[return-value]


def _validate_args(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("arguments must be a JSON object")
    allowed = {"project_directory", "geometry_path", "output_path", "geometry_identifier", "source_texture_path", "background_color", "operations", "allow_uv_overlap"}
    extra = set(raw) - allowed
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    required = {"project_directory", "geometry_path", "output_path", "operations"}
    missing = required - set(raw)
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")

    project = raw["project_directory"]
    if not isinstance(project, str) or not PROJECT_RE.fullmatch(project) or "--" in project:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    geometry_path = _safe_relative(raw["geometry_path"], "geometry_path", minimum_parts=5)
    expected_geo = ["resource_packs", f"{project}_RP", "models", "entity"]
    gp = geometry_path.split("/")
    if gp[:4] != expected_geo or not geometry_path.endswith(".json"):
        raise ValueError(f"geometry_path must be a .json file under resource_packs/{project}_RP/models/entity/")
    output_path = _safe_relative(raw["output_path"], "output_path", minimum_parts=5)
    op = output_path.split("/")
    if op[:4] != ["resource_packs", f"{project}_RP", "textures", "entity"] or len(op) < 5 or not output_path.endswith(".png"):
        raise ValueError(f"output_path must be a PNG inside resource_packs/{project}_RP/textures/entity/")
    source = raw.get("source_texture_path")
    if source is not None:
        source = _safe_relative(source, "source_texture_path", minimum_parts=5)
        sp = source.split("/")
        if sp[:4] != ["resource_packs", f"{project}_RP", "textures", "entity"] or len(sp) < 5 or not source.endswith(".png"):
            raise ValueError(f"source_texture_path must be a PNG inside resource_packs/{project}_RP/textures/entity/")
        if source == output_path:
            raise ValueError("source_texture_path and output_path must be different files")
    geometry_id = raw.get("geometry_identifier")
    if geometry_id is not None and (not isinstance(geometry_id, str) or not geometry_id or len(geometry_id) > 128):
        raise ValueError("geometry_identifier must be a non-empty string up to 128 characters")
    background = raw.get("background_color")
    if background is not None:
        _parse_color(background, "background_color")
    overlap = raw.get("allow_uv_overlap", False)
    if not isinstance(overlap, bool):
        raise ValueError("allow_uv_overlap must be a boolean")
    operations_raw = raw["operations"]
    if not isinstance(operations_raw, list) or not 1 <= len(operations_raw) <= MAX_OPERATIONS:
        raise ValueError(f"operations must contain 1 to {MAX_OPERATIONS} entries")
    operations: list[dict[str, Any]] = []
    for index, entry in enumerate(operations_raw):
        label = f"operations[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{label} must be an object")
        op_allowed = {"selector", "mode", "color", "secondary_color", "opacity", "blend_mode", "border_width", "cell_size", "axis", "seed"}
        op_extra = set(entry) - op_allowed
        if op_extra:
            raise ValueError(f"{label} has unexpected field(s): {', '.join(sorted(op_extra))}")
        selector = entry.get("selector")
        if not isinstance(selector, dict) or not selector or set(selector) - {"bone", "cube_index", "face"}:
            raise ValueError(f"{label}.selector must select at least one of bone, cube_index or face")
        if "bone" in selector and (not isinstance(selector["bone"], str) or not selector["bone"] or len(selector["bone"]) > 64):
            raise ValueError(f"{label}.selector.bone must be a non-empty bone name")
        if "cube_index" in selector and (isinstance(selector["cube_index"], bool) or not isinstance(selector["cube_index"], int) or not 0 <= selector["cube_index"] <= 255):
            raise ValueError(f"{label}.selector.cube_index must be an integer from 0 to 255")
        if "face" in selector and (not isinstance(selector["face"], str) or selector["face"] not in FACES):
            raise ValueError(f"{label}.selector.face must be one of {sorted(FACES)}")
        mode = entry.get("mode")
        if not isinstance(mode, str) or mode not in {"fill", "border", "checker", "stripes", "gradient", "noise"}:
            raise ValueError(f"{label}.mode is unsupported")
        color = _parse_color(entry.get("color"), f"{label}.color")
        secondary_raw = entry.get("secondary_color")
        secondary = _parse_color(secondary_raw, f"{label}.secondary_color") if secondary_raw is not None else None
        if mode in {"checker", "stripes", "gradient", "noise"} and secondary is None:
            raise ValueError(f"{label}.secondary_color is required for {mode}")
        opacity = entry.get("opacity", 255)
        if isinstance(opacity, bool) or not isinstance(opacity, int) or not 0 <= opacity <= 255:
            raise ValueError(f"{label}.opacity must be an integer from 0 to 255")
        blend = entry.get("blend_mode", "over")
        if not isinstance(blend, str) or blend not in {"over", "replace"}:
            raise ValueError(f"{label}.blend_mode must be over or replace")
        border_width = entry.get("border_width", 1)
        cell_size = entry.get("cell_size", 2)
        seed = entry.get("seed", 1)
        for key, value, lo, hi in (("border_width", border_width, 1, 32), ("cell_size", cell_size, 1, 128)):
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise ValueError(f"{label}.{key} must be an integer from {lo} to {hi}")
        if isinstance(seed, bool) or not isinstance(seed, int) or not -2147483648 <= seed <= 2147483647:
            raise ValueError(f"{label}.seed must be a signed 32-bit integer")
        axis = entry.get("axis", "x")
        if not isinstance(axis, str) or axis not in {"x", "y"}:
            raise ValueError(f"{label}.axis must be x or y")
        operations.append({
            "selector": dict(selector), "mode": mode, "color": color, "secondary_color": secondary,
            "opacity": opacity, "blend_mode": blend, "border_width": border_width,
            "cell_size": cell_size, "seed": seed, "axis": axis,
        })
    return {"project_directory": project, "geometry_path": geometry_path, "output_path": output_path,
            "geometry_identifier": geometry_id, "source_texture_path": source, "background_color": background,
            "operations": operations, "allow_uv_overlap": overlap}


def _workspace_root() -> Path:
    raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    base = Path(raw).expanduser() if raw else Path.cwd()
    try:
        root = base.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"configured workspace does not exist: {base}") from exc
    if not root.is_dir():
        raise ValueError("configured workspace must be a directory")
    return root


def _resolve_project(project_name: str) -> tuple[Path, Path, Path]:
    workspace = _workspace_root()
    candidate = workspace / project_name
    if candidate.is_symlink():
        raise ValueError("project directory must not be a symlink")
    try:
        project = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"project directory is unavailable: {project_name}") from exc
    if project.parent != workspace or not project.is_dir():
        raise ValueError("project must be one existing directory directly under the configured workspace")
    container = project / "resource_packs"
    rp = container / f"{project_name}_RP"
    for item in (container, rp):
        if item.is_symlink():
            raise ValueError(f"unsafe symlink in Resource Pack path: {item.name}")
    try:
        croot = container.resolve(strict=True)
        rp_root = rp.resolve(strict=True)
        croot.relative_to(project)
        rp_root.relative_to(croot)
    except (OSError, ValueError) as exc:
        raise ValueError("expected Resource Pack directories are missing or outside the project") from exc
    if not croot.is_dir() or not rp_root.is_dir():
        raise ValueError("expected Resource Pack directories must be directories")
    manifest = rp_root / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("Resource Pack manifest.json is missing or unsafe")
    return workspace, project, rp_root


def _resolve_file(root: Path, relative: str, label: str) -> Path:
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} contains a symlink")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} is missing or resolves outside the Resource Pack") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} is not a regular file")
    return resolved


def _new_destination(root: Path, relative: str) -> Path:
    parts = relative.split("/")
    current = root
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("output path contains a symlink")
        if not current.exists():
            raise ValueError(f"output parent directory does not exist: {'/'.join(parts[:-1])}")
        if not current.is_dir():
            raise ValueError("output parent segment is not a directory")
        current.resolve(strict=True).relative_to(root)
    destination = current / parts[-1]
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"output already exists: {relative}")
    destination.parent.resolve(strict=True).relative_to(root)
    return destination


def _png_chunks(payload: bytes) -> list[tuple[bytes, bytes]]:
    chunks: list[tuple[bytes, bytes]] = []
    offset = len(PNG_SIGNATURE)
    while offset + 12 <= len(payload):
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(payload):
            raise ValueError("PNG has a truncated chunk")
        chunks.append((kind, payload[offset + 8:offset + 8 + length]))
        offset = end
        if kind == b"IEND":
            break
    return chunks


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def _decode_png_rgba(payload: bytes) -> tuple[int, int, bytearray]:
    """Decode validated, non-interlaced, 8-bit PNGs into RGBA8 without third-party deps."""
    validate_png_bytes(payload, max_bytes=MAX_PNG_BYTES, max_dimension=MAX_DIMENSION, max_pixels=MAX_PIXELS)
    chunks = _png_chunks(payload)
    ihdr = next(data for kind, data in chunks if kind == b"IHDR")
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", ihdr)
    if bit_depth != 8 or interlace != 0:
        raise ValueError("painting source PNG must use 8-bit channels and non-interlaced scanlines; convert it to standard RGBA/RGB PNG first")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    if color_type not in {0, 2, 3, 4, 6}:
        raise ValueError("source PNG uses an unsupported color type")
    palette = b""
    transparency = b""
    idat = bytearray()
    for kind, data in chunks:
        if kind == b"PLTE":
            palette = data
        elif kind == b"tRNS":
            transparency = data
        elif kind == b"IDAT":
            idat.extend(data)
    row_bytes = width * channels
    expected = (row_bytes + 1) * height
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(bytes(idat), expected + 1)
        if len(raw) > expected or decoder.unconsumed_tail:
            raise ValueError("source PNG expands beyond its declared scanline size")
        raw += decoder.flush(expected + 1 - len(raw))
    except zlib.error as exc:
        raise ValueError(f"source PNG compression stream is invalid: {exc}") from exc
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("source PNG does not decode to its exact scanline size")
    bpp = channels
    decoded = bytearray(row_bytes * height)
    cursor = 0
    for y in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor:cursor + row_bytes])
        cursor += row_bytes
        prev_start = (y - 1) * row_bytes
        for x in range(row_bytes):
            left = row[x - bpp] if x >= bpp else 0
            above = decoded[prev_start + x] if y else 0
            upper_left = decoded[prev_start + x - bpp] if y and x >= bpp else 0
            if filter_type == 1:
                row[x] = (row[x] + left) & 255
            elif filter_type == 2:
                row[x] = (row[x] + above) & 255
            elif filter_type == 3:
                row[x] = (row[x] + ((left + above) // 2)) & 255
            elif filter_type == 4:
                row[x] = (row[x] + _paeth(left, above, upper_left)) & 255
            elif filter_type != 0:
                raise ValueError(f"source PNG uses unsupported scanline filter {filter_type}")
        decoded[y * row_bytes:(y + 1) * row_bytes] = row

    rgba = bytearray(width * height * 4)
    out = 0
    if color_type == 6:
        return width, height, decoded
    for pixel in range(width * height):
        base = pixel * channels
        if color_type == 0:
            gray = decoded[base]
            r = g = b = gray
            a = 0 if transparency and gray == int.from_bytes(transparency[:2], "big") else 255
        elif color_type == 2:
            r, g, b = decoded[base:base + 3]
            a = 0 if len(transparency) >= 6 and (r, g, b) == tuple(int.from_bytes(transparency[i:i + 2], "big") for i in (0, 2, 4)) else 255
        elif color_type == 3:
            index = decoded[base]
            if index * 3 + 2 >= len(palette):
                raise ValueError("source PNG palette index exceeds PLTE entries")
            r, g, b = palette[index * 3:index * 3 + 3]
            a = transparency[index] if index < len(transparency) else 255
        elif color_type == 4:
            r = g = b = decoded[base]
            a = decoded[base + 1]
        else:
            raise ValueError("source PNG uses an unsupported color type")
        rgba[out:out + 4] = bytes((r, g, b, a))
        out += 4
    return width, height, rgba


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def _encode_png(width: int, height: int, rgba: bytearray) -> bytes:
    if len(rgba) != width * height * 4:
        raise ValueError("RGBA canvas length does not match its dimensions")
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y * stride:(y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _png_chunk(b"IEND", b"")


def _blend(dst: bytearray, offset: int, src: tuple[int, int, int, int], blend_mode: str) -> None:
    sr, sg, sb, sa = src
    if blend_mode == "replace":
        dst[offset:offset + 4] = bytes(src)
        return
    if sa <= 0:
        return
    dr, dg, db, da = dst[offset:offset + 4]
    out_a = sa + (da * (255 - sa) + 127) // 255
    if out_a <= 0:
        dst[offset:offset + 4] = b"\x00\x00\x00\x00"
        return
    # Straight-alpha source-over, with integer rounding.
    for channel, sc, dc in ((0, sr, dr), (1, sg, dg), (2, sb, db)):
        premul = sc * sa + (dc * da * (255 - sa) + 127) // 255
        dst[offset + channel] = max(0, min(255, (premul + out_a // 2) // out_a))
    dst[offset + 3] = out_a


def _mix(a: tuple[int, int, int, int], b: tuple[int, int, int, int], amount: float) -> tuple[int, int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(round(x * (1.0 - amount) + y * amount) for x, y in zip(a, b))  # type: ignore[return-value]


def _matches(region: dict[str, Any], selector: dict[str, Any]) -> bool:
    return (("bone" not in selector or region["bone"] == selector["bone"])
            and ("cube_index" not in selector or region["cube_index"] == selector["cube_index"])
            and ("face" not in selector or region["face"] == selector["face"]))


def _operation_color(op: dict[str, Any], local_x: int, local_y: int, region_w: int, region_h: int) -> tuple[int, int, int, int] | None:
    mode = op["mode"]
    primary = op["color"]
    secondary = op["secondary_color"]
    use_primary = True
    if mode == "border":
        bw = op["border_width"]
        if local_x >= bw and local_y >= bw and local_x < region_w - bw and local_y < region_h - bw:
            if secondary is None:
                return None
            primary = secondary
    elif mode == "checker":
        use_primary = ((local_x // op["cell_size"] + local_y // op["cell_size"]) % 2) == 0
    elif mode == "stripes":
        coord = local_x if op["axis"] == "x" else local_y
        use_primary = (coord // op["cell_size"]) % 2 == 0
    elif mode == "gradient":
        extent = max(1, (region_w if op["axis"] == "x" else region_h) - 1)
        pos = local_x if op["axis"] == "x" else local_y
        return _mix(primary, secondary, pos / extent)
    elif mode == "noise":
        # Stable integer hash: reproducible across Python versions/platforms.
        n = (local_x * 0x45D9F3B + local_y * 0x119DE1F3 + (op["seed"] & 0xFFFFFFFF)) & 0xFFFFFFFF
        n = ((n ^ (n >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
        n = (n ^ (n >> 16)) & 0xFFFFFFFF
        use_primary = (n & 1) == 0
    if not use_primary:
        primary = secondary
    assert primary is not None
    return primary


def _region_pixel_bounds(region: dict[str, Any], canvas_width: int, canvas_height: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = region["bounds"]
    x0 = max(0, math.ceil(left - 0.5))
    y0 = max(0, math.ceil(top - 0.5))
    x1 = min(canvas_width, math.ceil(right - 0.5))
    y1 = min(canvas_height, math.ceil(bottom - 0.5))
    return x0, y0, x1, y1


def _paint_region(canvas: bytearray, canvas_width: int, canvas_height: int,
                  region: dict[str, Any], op: dict[str, Any]) -> int:
    x0, y0, x1, y1 = _region_pixel_bounds(region, canvas_width, canvas_height)
    rw, rh = max(0, x1 - x0), max(0, y1 - y0)
    changed = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            color = _operation_color(op, x - x0, y - y0, rw, rh)
            if color is None:
                continue
            rgba = (color[0], color[1], color[2], (color[3] * op["opacity"] + 127) // 255)
            offset = (y * canvas_width + x) * 4
            before = bytes(canvas[offset:offset + 4])
            _blend(canvas, offset, rgba, op["blend_mode"])
            if before != canvas[offset:offset + 4]:
                changed += 1
    return changed


def _write_new(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def paint_geometry_texture(raw_args: Any) -> dict[str, Any]:
    args = _validate_args(raw_args)
    _, project, rp_root = _resolve_project(args["project_directory"])
    geometry_rel = "/".join(args["geometry_path"].split("/")[2:])
    geometry_file = _resolve_file(rp_root, geometry_rel, "geometry_path")
    geom_root = uv._read_geometry(geometry_file)
    geometries = geom_root.get("minecraft:geometry") if isinstance(geom_root, dict) else None
    if not isinstance(geometries, list) or not geometries:
        raise ValueError("geometry JSON must contain a non-empty minecraft:geometry array")
    candidates: list[dict[str, Any]] = []
    for entry in geometries:
        if not isinstance(entry, dict):
            continue
        desc = entry.get("description")
        gid = desc.get("identifier") if isinstance(desc, dict) else None
        if args["geometry_identifier"] is None or gid == args["geometry_identifier"]:
            candidates.append(entry)
    if not candidates:
        raise ValueError(f"no geometry matched identifier {args['geometry_identifier']!r}")
    if len(candidates) != 1:
        if args["geometry_identifier"] is None:
            raise ValueError("geometry file has multiple geometries; supply geometry_identifier explicitly")
        raise ValueError("geometry_identifier is duplicated; selection would be ambiguous")
    geometry = candidates[0]
    desc = geometry.get("description")
    if not isinstance(desc, dict):
        raise ValueError("selected geometry has no description object")
    geometry_id = desc.get("identifier") if isinstance(desc.get("identifier"), str) else "<unnamed-geometry>"
    width, height = desc.get("texture_width"), desc.get("texture_height")
    if isinstance(width, bool) or not isinstance(width, int) or isinstance(height, bool) or not isinstance(height, int):
        raise ValueError("selected geometry must declare integer texture_width and texture_height")
    if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION) or width * height > MAX_PIXELS:
        raise ValueError("geometry texture canvas is outside safe dimension/pixel limits")

    regions, extraction_findings, cube_count = uv._extract_regions(geometry, geometry_id)
    if not regions:
        raise ValueError("selected geometry contains no supported UV regions")
    overlaps, overlap_count, overlap_complete = uv._overlaps(regions)
    out_of_bounds = [r for r in regions if r["bounds"][0] < 0 or r["bounds"][1] < 0 or r["bounds"][2] > width or r["bounds"][3] > height]
    if out_of_bounds:
        return _error("UV_OUT_OF_BOUNDS", "painting refused because one or more UV regions exceed the geometry texture canvas", {
            "texture_size": [width, height],
            "out_of_bounds_regions": [{"bone": r["bone"], "cube_index": r["cube_index"], "face": r["face"], "bounds": r["bounds"]} for r in out_of_bounds[:100]],
            "count": len(out_of_bounds),
        })
    if overlap_count and not args["allow_uv_overlap"]:
        return _error("UV_OVERLAP_REVIEW_REQUIRED", "UV regions overlap; set allow_uv_overlap=true only when texture reuse is intentional", {
            "overlap_pairs": overlap_count,
            "examples": overlaps[:25],
        })

    if args["source_texture_path"]:
        src_rel = "/".join(args["source_texture_path"].split("/")[2:])
        source_file = _resolve_file(rp_root, src_rel, "source_texture_path")
        out_rel = "/".join(args["output_path"].split("/")[2:])
        # Compare resolved paths too, to catch alternate relative spellings.
        out_candidate = rp_root.joinpath(*out_rel.split("/"))
        try:
            if source_file.resolve(strict=True) == out_candidate.resolve(strict=False):
                raise ValueError("source_texture_path and output_path resolve to the same file")
        except OSError:
            pass
        source_size = source_file.stat().st_size
        if source_size < 45 or source_size > MAX_PNG_BYTES:
            raise ValueError("source PNG must be between 45 bytes and the 16 MiB safety limit")
        with source_file.open("rb") as handle:
            source_payload = handle.read(MAX_PNG_BYTES + 1)
        if len(source_payload) > MAX_PNG_BYTES:
            raise ValueError("source PNG grew beyond the 16 MiB safety limit while it was being read")
        if len(source_payload) != source_size:
            raise ValueError("source PNG changed while it was being read")
        sw, sh, canvas = _decode_png_rgba(source_payload)
        if (sw, sh) != (width, height):
            return _error("TEXTURE_DIMENSION_MISMATCH", "source texture dimensions do not match geometry texture_width/texture_height", {
                "geometry_size": [width, height], "source_texture_size": [sw, sh], "source_path": args["source_texture_path"],
            })
    else:
        if args["background_color"] is None:
            canvas = bytearray(width * height * 4)
        else:
            bg = _parse_color(args["background_color"], "background_color")
            canvas = bytearray(bytes(bg) * (width * height))

    output_relative = "/".join(args["output_path"].split("/")[2:])
    destination = _new_destination(rp_root, output_relative)
    operation_results: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = list(extraction_findings[:100])
    planned_operations: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    estimated_writes = 0
    for index, op in enumerate(args["operations"]):
        selected = [r for r in regions if _matches(r, op["selector"])]
        if not selected:
            return _error("SELECTOR_MATCHED_NO_UV", f"operations[{index}] selector matched no UV regions", {"selector": op["selector"]})
        for region in selected:
            x0, y0, x1, y1 = _region_pixel_bounds(region, width, height)
            estimated_writes += max(0, x1 - x0) * max(0, y1 - y0)
        if estimated_writes > MAX_PAINT_PIXELS:
            return _error("PAINT_BUDGET_EXCEEDED", "planned UV painting exceeds the total texel-operation safety budget", {
                "estimated_texel_writes": estimated_writes, "maximum_texel_writes": MAX_PAINT_PIXELS,
                "suggestion": "Reduce the number/area of selected UV regions or split the work into separate textures."
            })
        planned_operations.append((op, selected))
    for index, (op, selected) in enumerate(planned_operations):
        texel_writes = 0
        for region in selected:
            texel_writes += _paint_region(canvas, width, height, region, op)
        operation_results.append({"index": index, "mode": op["mode"], "selector": op["selector"],
                                  "matched_regions": len(selected), "texel_writes": texel_writes})
    if overlap_count:
        warnings.append({"code": "UV_REGION_OVERLAP_ALLOWED", "count": overlap_count,
                         "message": "Overlapping UV regions may share texels; later operations can overwrite earlier paint on shared coordinates."})
    if not overlap_complete:
        warnings.append({"code": "OVERLAP_ANALYSIS_INCOMPLETE", "message": "UV overlap comparison reached its safety budget."})

    png = _encode_png(width, height, canvas)
    if len(png) > MAX_PNG_BYTES:
        raise ValueError("painted PNG exceeds the 16 MiB output limit")
    out_w, out_h = validate_png_bytes(png, max_bytes=MAX_PNG_BYTES, max_dimension=MAX_DIMENSION, max_pixels=MAX_PIXELS)
    _write_new(destination, png)
    digest = hashlib.sha256(png).hexdigest()
    return {
        "status": "success",
        "geometry": {"identifier": geometry_id, "path": args["geometry_path"], "texture_size": [width, height],
                     "bone_count": len(geometry.get("bones", [])), "cube_count": cube_count, "uv_region_count": len(regions)},
        "texture": {"path": args["output_path"], "width": out_w, "height": out_h, "format": "PNG RGBA8",
                    "bytes": len(png), "sha256": digest, "source_texture": args["source_texture_path"]},
        "painting": {"operation_count": len(operation_results), "operations": operation_results,
                     "painted_texel_writes_total": sum(item["texel_writes"] for item in operation_results),
                     "uv_overlap_pairs": overlap_count, "overlap_analysis_complete": overlap_complete,
                     "warnings": warnings},
        "scope_note": "Creates a new deterministic 2D texture by editing UV rectangles from the selected geometry. Unpainted pixels and alpha are retained when a source PNG is supplied. Pattern coordinates are texture-space coordinates; UV face sampling orientation, actual rendering, material effects, and runtime behavior are not simulated. This is not AI image synthesis or a 3D preview. Minecraft runtime: NOT RUN.",
    }


def _tool_result(request_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
        "structuredContent": payload, "isError": payload.get("status") == "error",
    }}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid JSON-RPC request")
    method, request_id = message.get("method"), message.get("id")
    params = message.get("params", {})
    if not isinstance(method, str) or not isinstance(params, dict):
        return _jsonrpc_error(request_id, -32600, "Invalid method or params")
    if "id" not in message:
        return None
    if method == "initialize":
        requested = params.get("protocolVersion", "2024-11-05")
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": requested, "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-texture-painter", "version": SERVER_VERSION},
            "instructions": "Use paint_geometry_texture with a selected geometry and explicit bone/cube/face paint operations. It creates a new PNG and does not modify source textures or geometry. For a source texture, dimensions must exactly match geometry. Minecraft runtime remains NOT RUN."
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if not isinstance(name, str) or name not in TOOL_BY_NAME:
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = paint_geometry_texture(args)
        except FileExistsError as exc:
            payload = _error("OUTPUT_EXISTS", str(exc))
        except (ValueError, PngValidationError) as exc:
            payload = _error("INVALID_INPUT", str(exc))
        except OSError as exc:
            payload = _error("IO_ERROR", f"safe texture operation failed: {exc}")
        except Exception as exc:
            payload = _error("INTERNAL_ERROR", f"unexpected {type(exc).__name__}: {exc}")
        return _tool_result(request_id, payload)
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle_message(json.loads(line))
        except json.JSONDecodeError:
            response = _jsonrpc_error(None, -32700, "Parse error")
        except Exception as exc:
            response = _jsonrpc_error(None, -32603, f"Internal error: {type(exc).__name__}")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
