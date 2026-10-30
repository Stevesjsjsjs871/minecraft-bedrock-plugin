#!/usr/bin/env python3
"""Generate a labeled PNG UV template and overlap report from Bedrock geometry.

This is an authoring aid, not a renderer. It writes a separate template image and
never edits the source geometry or the entity's actual texture.
"""
from __future__ import annotations

import json
import math
import os
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
try:
    SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

PROJECT_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_TEXTURE_DIMENSION = 4096
MAX_OUTPUT_PIXELS = 8_388_608
MAX_REGIONS = 6000
MAX_OVERLAP_COMPARISONS = 250_000
MAX_REPORTED_OVERLAPS = 2000
MAX_UV_VALUE = 1_000_000.0
FACES = {"north", "south", "east", "west", "up", "down"}

# Fixed, direction-oriented palette. Overlap intersections use a separate alert color.
FACE_COLORS: dict[str, tuple[int, int, int, int]] = {
    "north": (70, 160, 225, 105),
    "south": (225, 135, 65, 105),
    "east": (90, 190, 130, 105),
    "west": (190, 115, 205, 105),
    "up": (225, 205, 85, 105),
    "down": (105, 145, 205, 105),
    "box": (140, 150, 165, 70),
}

FONT: dict[str, tuple[str, ...]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("111", "010", "010", "010", "010", "010", "111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ":": ("000", "010", "010", "000", "010", "010", "000"),
    " ": ("000", "000", "000", "000", "000", "000", "000"),
}


class DuplicateJsonKey(ValueError):
    pass


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKey(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _tool() -> dict[str, Any]:
    return {
        "name": "generate_geometry_uv_template",
        "description": (
            "Generate a labeled PNG UV atlas template from one Bedrock .geo.json geometry. Supports classic box UV "
            "nets and per-face UV rectangles, detects possible overlapping islands, clips drawing to the canvas, "
            "and marks fractional coordinates/out-of-bounds regions. Saves a separate PNG under the Resource Pack "
            "textures/uv_templates directory; does not edit geometry or the actual entity texture. Overlap may be "
            "intentional texture reuse and is reported as a warning, not an automatic error. Static authoring aid; "
            "Minecraft runtime/rendering remain NOT RUN."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
                "geometry_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "output_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "geometry_identifier": {"type": "string", "minLength": 1, "maxLength": 128},
                "pixel_scale": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4},
                "include_labels": {"type": "boolean", "default": True},
                "include_grid": {"type": "boolean", "default": True}
            },
            "required": ["project_directory", "geometry_path", "output_path"],
            "additionalProperties": False
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
    }


TOOLS = [_tool()]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def _validate_relpath(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{label} must be a non-empty relative POSIX path")
    if "\\" in value or "\x00" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"{label} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must not contain empty, dot or parent-traversal segments")
    return value


def _validate_args(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("arguments must be a JSON object")
    allowed = {"project_directory", "geometry_path", "output_path", "geometry_identifier", "pixel_scale", "include_labels", "include_grid"}
    extra = set(raw) - allowed
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    required = {"project_directory", "geometry_path", "output_path"}
    missing = required - set(raw)
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    project = raw["project_directory"]
    if not isinstance(project, str) or not PROJECT_RE.fullmatch(project) or "--" in project:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    geometry_path = _validate_relpath(raw["geometry_path"], "geometry_path")
    geometry_parts = geometry_path.split("/")
    if len(geometry_parts) < 5 or geometry_parts[:4] != ["resource_packs", f"{project}_RP", "models", "entity"] or not geometry_path.endswith(".json"):
        raise ValueError(f"geometry_path must be a JSON file under resource_packs/{project}_RP/models/entity/")
    output_path = _validate_relpath(raw["output_path"], "output_path")
    output_parts = output_path.split("/")
    if len(output_parts) < 5 or output_parts[:4] != ["resource_packs", f"{project}_RP", "textures", "uv_templates"] or not output_path.endswith(".png"):
        raise ValueError(f"output_path must be a PNG under resource_packs/{project}_RP/textures/uv_templates/")
    identifier = raw.get("geometry_identifier")
    if identifier is not None and (not isinstance(identifier, str) or not identifier or len(identifier) > 128):
        raise ValueError("geometry_identifier must be a non-empty string up to 128 characters")
    scale = raw.get("pixel_scale", 4)
    if isinstance(scale, bool) or not isinstance(scale, int) or not 1 <= scale <= 8:
        raise ValueError("pixel_scale must be an integer from 1 to 8")
    labels = raw.get("include_labels", True)
    grid = raw.get("include_grid", True)
    if not isinstance(labels, bool) or not isinstance(grid, bool):
        raise ValueError("include_labels and include_grid must be booleans")
    return {
        "project_directory": project,
        "geometry_path": geometry_path,
        "output_path": output_path,
        "geometry_identifier": identifier,
        "pixel_scale": scale,
        "include_labels": labels,
        "include_grid": grid,
    }


def _workspace_root() -> Path:
    raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    base = Path(raw).expanduser() if raw else Path.cwd()
    resolved = base.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("configured workspace must be a directory")
    return resolved


def _resolve_roots(project_name: str) -> tuple[Path, Path]:
    workspace = _workspace_root()
    candidate = workspace / project_name
    if candidate.is_symlink():
        raise ValueError("project_directory must not be a symlink")
    project = candidate.resolve(strict=True)
    if project.parent != workspace or not project.is_dir():
        raise ValueError("project_directory must be a real directory directly under workspace")
    rp_container = project / "resource_packs"
    rp_root = rp_container / f"{project_name}_RP"
    for path in (rp_container, rp_root):
        if path.is_symlink():
            raise ValueError("Resource Pack path contains a symlink")
    rp_container_real = rp_container.resolve(strict=True)
    rp_root_real = rp_root.resolve(strict=True)
    rp_container_real.relative_to(project)
    rp_root_real.relative_to(rp_container_real)
    if not rp_container_real.is_dir() or not rp_root_real.is_dir():
        raise ValueError("Resource Pack path is missing or not a directory")
    manifest = rp_root_real / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("Resource Pack manifest.json is missing or unsafe")
    return project, rp_root_real


def _safe_file(root: Path, relative: str, label: str) -> Path:
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} contains a symlink")
    resolved = current.resolve(strict=True)
    resolved.relative_to(root)
    if not resolved.is_file():
        raise ValueError(f"{label} is not a regular file")
    return resolved


def _read_geometry(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("geometry JSON exceeds the 2 MiB safety limit")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateJsonKey) as exc:
        raise ValueError(f"geometry JSON is invalid: {exc}") from exc


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _pair(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, list) or len(value) != 2 or not all(_num(v) and abs(float(v)) <= MAX_UV_VALUE for v in value):
        return None
    return float(value[0]), float(value[1])


def _size3(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, list) or len(value) != 3 or not all(_num(v) and abs(float(v)) <= MAX_UV_VALUE for v in value):
        return None
    return float(value[0]), float(value[1]), float(value[2])


def _rect(uv: tuple[float, float], size: tuple[float, float]) -> tuple[float, float, float, float]:
    x0, y0 = uv
    x1, y1 = x0 + size[0], y0 + size[1]
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _append_region(regions: list[dict[str, Any]], *, geometry_id: str, bone: str, bone_index: int,
                   cube_index: int, face: str, bounds: tuple[float, float, float, float],
                   mapping: str, rotation: int = 0) -> None:
    if len(regions) >= MAX_REGIONS:
        return
    left, top, right, bottom = bounds
    if right <= left or bottom <= top:
        return
    regions.append({
        "geometry_identifier": geometry_id,
        "bone": bone,
        "bone_index": bone_index,
        "cube_index": cube_index,
        "face": face,
        "mapping": mapping,
        "bounds": [left, top, right, bottom],
        "uv_rotation": rotation,
    })


def _classic_regions(cube: dict[str, Any], *, geometry_id: str, bone: str, bone_index: int,
                     cube_index: int, regions: list[dict[str, Any]], findings: list[dict[str, Any]]) -> None:
    uv = _pair(cube.get("uv"))
    size = _size3(cube.get("size"))
    if uv is None or size is None or any(part < 0 for part in size):
        findings.append({"severity": "warning", "code": "UNMAPPED_CLASSIC_CUBE", "bone": bone, "cube_index": cube_index,
                         "message": "Classic box UV requires a finite [u,v] origin and non-negative size[3]."})
        return
    u, v = uv
    x, y, z = size
    # Bedrock's classic box-UV net: UP and DOWN in the top band; side strip below.
    # DOWN has its V direction reversed in the engine; its occupied rectangle is still this positive area.
    placements = {
        "up": (u + z, v, x, z),
        "down": (u + z + x, v, x, z),
        "west": (u, v + z, z, y),
        "north": (u + z, v + z, x, y),
        "east": (u + z + x, v + z, z, y),
        "south": (u + 2 * z + x, v + z, x, y),
    }
    for face, (left, top, width, height) in placements.items():
        _append_region(regions, geometry_id=geometry_id, bone=bone, bone_index=bone_index,
                       cube_index=cube_index, face=face,
                       bounds=(left, top, left + width, top + height), mapping="classic_box_uv")


def _per_face_regions(cube: dict[str, Any], *, geometry_id: str, bone: str, bone_index: int,
                      cube_index: int, regions: list[dict[str, Any]], findings: list[dict[str, Any]]) -> None:
    uv_map = cube.get("uv")
    if not isinstance(uv_map, dict):
        findings.append({"severity": "warning", "code": "INVALID_PER_FACE_UV", "bone": bone, "cube_index": cube_index,
                         "message": "Per-face UV map must be an object."})
        return
    size = _size3(cube.get("size"))
    face_axes = {"north": (0, 1), "south": (0, 1), "east": (2, 1), "west": (2, 1), "up": (0, 2), "down": (0, 2)}
    for face, data in uv_map.items():
        if face not in FACES:
            findings.append({"severity": "warning", "code": "UNKNOWN_UV_FACE", "bone": bone,
                             "cube_index": cube_index, "face": face, "message": "Unknown per-face UV key; skipped."})
            continue
        if not isinstance(data, dict):
            findings.append({"severity": "warning", "code": "INVALID_UV_FACE_ENTRY", "bone": bone,
                             "cube_index": cube_index, "face": face, "message": "Face UV entry must be an object."})
            continue
        uv = _pair(data.get("uv"))
        uv_size = _pair(data.get("uv_size"))
        if uv is None:
            findings.append({"severity": "warning", "code": "INVALID_UV_ORIGIN", "bone": bone,
                             "cube_index": cube_index, "face": face, "message": "Face uv must be two finite numbers."})
            continue
        if uv_size is None:
            if size is None:
                findings.append({"severity": "warning", "code": "UNKNOWN_FACE_SIZE", "bone": bone,
                                 "cube_index": cube_index, "face": face, "message": "uv_size is omitted and cube size is invalid."})
                continue
            axes = face_axes[face]
            uv_size = (size[axes[0]], size[axes[1]])
        rotation = data.get("uv_rotation", 0)
        if isinstance(rotation, bool) or not isinstance(rotation, int) or rotation not in {0, 90, 180, 270}:
            findings.append({"severity": "warning", "code": "INVALID_UV_ROTATION", "bone": bone,
                             "cube_index": cube_index, "face": face, "message": "uv_rotation must be 0, 90, 180 or 270."})
            continue
        adjusted_size = (uv_size[1], uv_size[0]) if rotation in {90, 270} else uv_size
        bounds = _rect(uv, adjusted_size)
        _append_region(regions, geometry_id=geometry_id, bone=bone, bone_index=bone_index,
                       cube_index=cube_index, face=face, bounds=bounds,
                       mapping="per_face_uv", rotation=rotation)
        if uv_size[0] < 0 or uv_size[1] < 0:
            findings.append({"severity": "info", "code": "UV_AXIS_FLIP", "bone": bone,
                             "cube_index": cube_index, "face": face,
                             "message": "Negative uv_size flips face sampling; the template shows the occupied rectangle."})


def _extract_regions(geometry: dict[str, Any], geometry_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    regions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    bones = geometry.get("bones")
    if not isinstance(bones, list):
        raise ValueError("selected geometry must contain a bones array")
    cube_count = 0
    for bone_index, bone in enumerate(bones):
        if not isinstance(bone, dict):
            findings.append({"severity": "warning", "code": "INVALID_BONE", "bone_index": bone_index,
                             "message": "Non-object bone entry was skipped."})
            continue
        bone_name = bone.get("name") if isinstance(bone.get("name"), str) else f"bone_{bone_index}"
        cubes = bone.get("cubes", [])
        if not isinstance(cubes, list):
            findings.append({"severity": "warning", "code": "INVALID_CUBES", "bone": bone_name,
                             "message": "Bone cubes field is not an array."})
            continue
        for cube_index, cube in enumerate(cubes):
            cube_count += 1
            if not isinstance(cube, dict):
                findings.append({"severity": "warning", "code": "INVALID_CUBE", "bone": bone_name,
                                 "cube_index": cube_index, "message": "Non-object cube entry was skipped."})
                continue
            uv = cube.get("uv")
            if isinstance(uv, list):
                _classic_regions(cube, geometry_id=geometry_id, bone=bone_name, bone_index=bone_index,
                                 cube_index=cube_index, regions=regions, findings=findings)
            elif isinstance(uv, dict):
                _per_face_regions(cube, geometry_id=geometry_id, bone=bone_name, bone_index=bone_index,
                                  cube_index=cube_index, regions=regions, findings=findings)
            else:
                findings.append({"severity": "warning", "code": "MISSING_CUBE_UV", "bone": bone_name,
                                 "cube_index": cube_index, "message": "Cube has no supported UV mapping."})
            for unsupported in ("poly_mesh", "texture_meshes"):
                if unsupported in bone:
                    findings.append({"severity": "warning", "code": "UNSUPPORTED_MESH_UV_SCOPE", "bone": bone_name,
                                     "resource": unsupported, "message": f"{unsupported} UVs are not represented in this cube template."})
    if len(regions) >= MAX_REGIONS:
        findings.append({"severity": "warning", "code": "REGION_LIMIT", "message": f"UV template hit the {MAX_REGIONS}-region safety limit."})
    return regions, findings, cube_count


def _overlaps(regions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, bool]:
    ordered = sorted(enumerate(regions), key=lambda item: (item[1]["bounds"][0], item[1]["bounds"][1]))
    active: list[tuple[int, dict[str, Any]]] = []
    results: list[dict[str, Any]] = []
    comparisons = 0
    complete = True
    total_found = 0
    for index, region in ordered:
        left, top, right, bottom = region["bounds"]
        active = [(old_i, old) for old_i, old in active if old["bounds"][2] > left]
        for old_i, old in active:
            comparisons += 1
            if comparisons > MAX_OVERLAP_COMPARISONS:
                complete = False
                break
            oleft, otop, oright, obottom = old["bounds"]
            iy = min(bottom, obottom) - max(top, otop)
            ix = min(right, oright) - max(left, oleft)
            if ix > 0 and iy > 0:
                total_found += 1
                if len(results) < MAX_REPORTED_OVERLAPS:
                    results.append({
                        "region_a": old_i,
                        "region_b": index,
                        "a": {"bone": old["bone"], "cube_index": old["cube_index"], "face": old["face"]},
                        "b": {"bone": region["bone"], "cube_index": region["cube_index"], "face": region["face"]},
                        "intersection": [max(left, oleft), max(top, otop), min(right, oright), min(bottom, obottom)],
                        "area": round(ix * iy, 4),
                    })
        if not complete:
            break
        active.append((index, region))
    return results, total_found, complete


def _blend(dst: bytearray, index: int, color: tuple[int, int, int, int]) -> None:
    sr, sg, sb, sa = color
    dr, dg, db, da = dst[index:index + 4]
    inv = 255 - sa
    dst[index] = (sr * sa + dr * inv) // 255
    dst[index + 1] = (sg * sa + dg * inv) // 255
    dst[index + 2] = (sb * sa + db * inv) // 255
    dst[index + 3] = min(255, sa + (da * inv) // 255)


def _pixel(image: bytearray, width: int, height: int, x: int, y: int,
           color: tuple[int, int, int, int]) -> None:
    if 0 <= x < width and 0 <= y < height:
        _blend(image, (y * width + x) * 4, color)


def _line(image: bytearray, width: int, height: int, x0: int, y0: int, x1: int, y1: int,
          color: tuple[int, int, int, int]) -> None:
    if x0 == x1:
        for y in range(max(0, min(y0, y1)), min(height - 1, max(y0, y1)) + 1):
            _pixel(image, width, height, x0, y, color)
    elif y0 == y1:
        for x in range(max(0, min(x0, x1)), min(width - 1, max(x0, x1)) + 1):
            _pixel(image, width, height, x, y0, color)


def _draw_text(image: bytearray, width: int, height: int, x: int, y: int, text: str,
               scale: int, color: tuple[int, int, int, int], max_width: int, max_height: int) -> None:
    text = text.upper()
    cell_width = 6 * scale
    available = max(0, min(len(text), max_width // cell_width))
    if available <= 0 or 7 * scale > max_height:
        return
    text = text[:available]
    total_width = len(text) * cell_width - scale
    start_x = x + max(0, (max_width - total_width) // 2)
    start_y = y + max(0, (max_height - 7 * scale) // 2)
    for char_index, char in enumerate(text):
        glyph = FONT.get(char, FONT["-"])
        gx = start_x + char_index * cell_width
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    px0, py0 = gx + col * scale, start_y + row * scale
                    for dy in range(scale):
                        for dx in range(scale):
                            _pixel(image, width, height, px0 + dx, py0 + dy, color)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _encode_png(width: int, height: int, pixels: bytearray) -> bytes:
    if len(pixels) != width * height * 4:
        raise ValueError("internal PNG buffer size mismatch")
    raw = b"".join(b"\x00" + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b"")


def _render_template(canvas_width: int, canvas_height: int, regions: list[dict[str, Any]], overlaps: list[dict[str, Any]],
                     *, scale: int, labels: bool, grid: bool) -> bytes:
    width, height = canvas_width * scale, canvas_height * scale
    if width > 8192 or height > 8192 or width * height > MAX_OUTPUT_PIXELS:
        raise ValueError(f"scaled atlas is too large: {width}x{height}; reduce pixel_scale")
    pixels = bytearray(width * height * 4)
    # Transparent neutral canvas; the grid remains visible but does not become part of the entity texture.
    for y in range(height):
        row_alpha = 22 if (y // scale) % 2 == 0 else 12
        start = y * width * 4
        for x in range(width):
            i = start + x * 4
            pixels[i:i + 4] = bytes((65, 72, 82, row_alpha))
    if grid:
        minor = (125, 135, 145, 72)
        major = (180, 190, 200, 115)
        for gx in range(canvas_width + 1):
            x = gx * scale
            _line(pixels, width, height, x, 0, x, height - 1, major if gx % 8 == 0 else minor)
        for gy in range(canvas_height + 1):
            y = gy * scale
            _line(pixels, width, height, 0, y, width - 1, y, major if gy % 8 == 0 else minor)
    for region in regions:
        left, top, right, bottom = region["bounds"]
        x0 = max(0, min(width, round(left * scale)))
        y0 = max(0, min(height, round(top * scale)))
        x1 = max(0, min(width, round(right * scale)))
        y1 = max(0, min(height, round(bottom * scale)))
        if x1 <= x0 or y1 <= y0:
            continue
        fill = FACE_COLORS[region["face"]]
        for y in range(y0, y1):
            for x in range(x0, x1):
                _pixel(pixels, width, height, x, y, fill)
        border = (245, 245, 245, 225)
        _line(pixels, width, height, x0, y0, x1 - 1, y0, border)
        _line(pixels, width, height, x0, y1 - 1, x1 - 1, y1 - 1, border)
        _line(pixels, width, height, x0, y0, x0, y1 - 1, border)
        _line(pixels, width, height, x1 - 1, y0, x1 - 1, y1 - 1, border)
        if labels:
            label = region["face"][0].upper()
            _draw_text(pixels, width, height, x0, y0, label, scale, (255, 255, 255, 245), x1 - x0, y1 - y0)
    # Overlay actual intersection rectangles; intentional reuse is flagged but not silently hidden.
    for overlap in overlaps:
        left, top, right, bottom = overlap["intersection"]
        x0 = max(0, min(width, round(left * scale)))
        y0 = max(0, min(height, round(top * scale)))
        x1 = max(0, min(width, round(right * scale)))
        y1 = max(0, min(height, round(bottom * scale)))
        for y in range(y0, y1):
            for x in range(x0, x1):
                if (x + y) % max(2, 2 * scale) < scale:
                    _pixel(pixels, width, height, x, y, (255, 35, 145, 135))
    return _encode_png(width, height, pixels)


def _write_new_file(path: Path, payload: bytes) -> None:
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


def generate_geometry_uv_template(raw_args: Any) -> dict[str, Any]:
    args = _validate_args(raw_args)
    project, rp_root = _resolve_roots(args["project_directory"])
    geometry_relative = "/".join(args["geometry_path"].split("/")[2:])
    geometry_file = _safe_file(rp_root, geometry_relative, "geometry_path")
    root = _read_geometry(geometry_file)
    geometries = root.get("minecraft:geometry") if isinstance(root, dict) else None
    if not isinstance(geometries, list) or not geometries:
        raise ValueError("geometry JSON must contain a non-empty minecraft:geometry array")
    identifier = args["geometry_identifier"]
    candidates: list[dict[str, Any]] = []
    for entry in geometries:
        if not isinstance(entry, dict):
            continue
        desc = entry.get("description")
        geometry_id = desc.get("identifier") if isinstance(desc, dict) else None
        if identifier is None or geometry_id == identifier:
            candidates.append(entry)
    if not candidates:
        raise ValueError(f"no geometry matched identifier {identifier!r}")
    if identifier is None and len(candidates) != 1:
        raise ValueError("geometry JSON contains multiple geometries; supply geometry_identifier to select one")
    geometry = candidates[0]
    description = geometry.get("description")
    if not isinstance(description, dict):
        raise ValueError("selected geometry has no description object")
    geometry_id = description.get("identifier") if isinstance(description.get("identifier"), str) else "<unnamed-geometry>"
    width, height = description.get("texture_width"), description.get("texture_height")
    if isinstance(width, bool) or not isinstance(width, int) or isinstance(height, bool) or not isinstance(height, int):
        raise ValueError("selected geometry must declare integer texture_width and texture_height")
    if not (1 <= width <= MAX_TEXTURE_DIMENSION and 1 <= height <= MAX_TEXTURE_DIMENSION):
        raise ValueError(f"texture canvas must be between 1 and {MAX_TEXTURE_DIMENSION} texels per dimension")

    regions, findings, cube_count = _extract_regions(geometry, geometry_id)
    if not regions:
        raise ValueError("selected geometry contains no supported cube UV regions")
    overlaps, overlap_count, overlap_complete = _overlaps(regions)
    for region in regions:
        l, t, r, b = region["bounds"]
        if l < 0 or t < 0 or r > width or b > height:
            findings.append({"severity": "error", "code": "UV_OUT_OF_BOUNDS", "bone": region["bone"],
                             "cube_index": region["cube_index"], "face": region["face"],
                             "bounds": [l, t, r, b], "message": f"UV region exceeds declared {width}x{height} canvas."})
        if any(abs(value - round(value)) > 1e-6 for value in (l, t, r, b)):
            findings.append({"severity": "info", "code": "FRACTIONAL_UV_COORDINATES", "bone": region["bone"],
                             "cube_index": region["cube_index"], "face": region["face"],
                             "message": "UV boundary is fractional; the template rasterizes it at the selected pixel scale."})
    if overlap_count:
        findings.append({"severity": "warning", "code": "UV_REGION_OVERLAP", "count": overlap_count,
                         "message": "UV regions share texels. This may be intentional mirroring or texture reuse; inspect the intersections."})
    if not overlap_complete:
        findings.append({"severity": "warning", "code": "OVERLAP_ANALYSIS_TRUNCATED",
                         "message": f"Overlap comparison safety limit ({MAX_OVERLAP_COMPARISONS}) was reached."})

    scale = args["pixel_scale"]
    png_bytes = _render_template(width, height, regions, overlaps, scale=scale,
                                 labels=args["include_labels"], grid=args["include_grid"])

    output_relative = "/".join(args["output_path"].split("/")[2:])
    textures_root = rp_root / "textures"
    uv_dir = textures_root / "uv_templates"
    if textures_root.is_symlink() or not textures_root.is_dir():
        raise ValueError("Resource Pack textures directory is missing or unsafe")
    if uv_dir.exists() and uv_dir.is_symlink():
        raise ValueError("textures/uv_templates must not be a symlink")
    if not uv_dir.exists():
        uv_dir.mkdir(mode=0o700)
    uv_dir_real = uv_dir.resolve(strict=True)
    uv_dir_real.relative_to(textures_root.resolve(strict=True))
    output = _safe_new_destination(rp_root, output_relative)
    _write_new_file(output, png_bytes)
    import hashlib
    digest = hashlib.sha256(png_bytes).hexdigest()
    return {
        "status": "success",
        "geometry": {"identifier": geometry_id, "path": args["geometry_path"], "texture_size": [width, height],
                     "bone_count": len(geometry.get("bones", [])), "cube_count": cube_count},
        "template": {"path": args["output_path"], "width": width * scale, "height": height * scale,
                     "pixel_scale": scale, "bytes": len(png_bytes), "sha256": digest},
        "uv_analysis": {"regions": len(regions), "detected_overlap_pairs": overlap_count, "reported_overlap_pairs": len(overlaps),
                        "overlap_analysis_complete": overlap_complete,
                        "region_map": [{"index": index, "bone": region["bone"], "bone_index": region["bone_index"],
                                        "cube_index": region["cube_index"], "face": region["face"],
                                        "bounds": region["bounds"], "mapping": region["mapping"],
                                        "uv_rotation": region["uv_rotation"]}
                                       for index, region in enumerate(regions[:300])],
                        "region_map_truncated": len(regions) > 300,
                        "out_of_bounds_regions": sum(1 for f in findings if f.get("code") == "UV_OUT_OF_BOUNDS"),
                        "fractional_regions": sum(1 for f in findings if f.get("code") == "FRACTIONAL_UV_COORDINATES"),
                        "findings": findings[:250]},
        "scope_note": "PNG is a separate transparent UV guide, not a painted texture and not automatically bound to the entity. Overlap may be intentional reuse. Geometry/texture files were not modified. Minecraft runtime and visual rendering: NOT RUN.",
    }


def _safe_new_destination(rp_root: Path, relative: str) -> Path:
    current = rp_root
    parts = relative.split("/")
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("output directory path contains a symlink")
        if not current.exists() or not current.is_dir():
            raise ValueError("output parent directory is missing or not a directory")
    destination = current / parts[-1]
    if destination.exists() or destination.is_symlink():
        raise ValueError("output file already exists; refusing to overwrite it")
    return destination


def _tool_result(request_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
        "structuredContent": payload,
        "isError": payload.get("status") == "error",
    }}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid JSON-RPC request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {})
    if not isinstance(method, str) or not isinstance(params, dict):
        return _jsonrpc_error(request_id, -32600, "Invalid method or params")
    if "id" not in message:
        return None
    if method == "initialize":
        requested = params.get("protocolVersion", "2024-11-05")
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": requested, "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-geometry-uv-template", "version": SERVER_VERSION},
            "instructions": "Use generate_geometry_uv_template with one geometry file and a separate PNG output path under textures/uv_templates. It never alters the source model or entity texture."
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or name not in TOOL_BY_NAME:
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = generate_geometry_uv_template(arguments)
        except (ValueError, OSError) as exc:
            payload = _error("UV_TEMPLATE_FAILED", str(exc))
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
