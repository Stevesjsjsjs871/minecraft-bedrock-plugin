#!/usr/bin/env python3
"""Explicit reference-image to Bedrock geometry-UV transfer MCP server.

This tool does not infer a 3D projection from a portrait or create AI artwork.
It maps caller-selected source-image rectangles onto caller-selected geometry UV
regions, preserving source alpha and optionally compositing over a base texture.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import geometry_uv_template_mcp as uv
import texture_painting_mcp as painter
from png_validation import PngValidationError, validate_png_bytes

ROOT = Path(__file__).resolve().parents[1]
try:
    SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

PROJECT_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
MAX_MAPPINGS = 256
MAX_SAMPLE_WRITES = 16_777_216
MAX_REFERENCE_BYTES = 16 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
FACES = {"north", "south", "east", "west", "up", "down"}


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
    mapping = {
        "type": "object",
        "properties": {
            "selector": selector,
            "source_rect": {
                "type": "object", "additionalProperties": False,
                "required": ["x", "y", "width", "height"],
                "properties": {
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                    "width": {"type": "integer", "minimum": 1},
                    "height": {"type": "integer", "minimum": 1},
                },
            },
            "rotation": {"type": "integer", "enum": [0, 90, 180, 270], "default": 0},
            "flip_x": {"type": "boolean", "default": False},
            "flip_y": {"type": "boolean", "default": False},
            "sampling": {"type": "string", "enum": ["nearest", "bilinear"], "default": "nearest"},
            "opacity": {"type": "integer", "minimum": 0, "maximum": 255, "default": 255},
            "blend_mode": {"type": "string", "enum": ["over", "replace"], "default": "over"},
        },
        "required": ["selector", "source_rect"],
        "additionalProperties": False,
    }
    return {
        "name": "map_reference_texture_to_uv",
        "description": (
            "Transfer explicitly selected rectangular regions from a reference PNG onto exact Bedrock geometry UV "
            "face rectangles. Each mapping selects a bone/cube/face and supplies a source-image crop, optional 90-degree "
            "rotation, flips, nearest/bilinear sampling, opacity and alpha-over/replace blend. Can preserve an existing "
            "base texture or start transparent. The reference PNG must be inside the project's RP textures tree; the "
            "output is a new PNG with exact geometry texture dimensions. Does not infer 3D projection from a portrait, "
            "generate AI artwork, simulate engine face sampling, or overwrite source files. Minecraft runtime NOT RUN."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
                "geometry_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "output_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "reference_image_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "geometry_identifier": {"type": "string", "minLength": 1, "maxLength": 128},
                "base_texture_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "background_color": {"type": "string", "pattern": r"^#?[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"},
                "mappings": {"type": "array", "minItems": 1, "maxItems": MAX_MAPPINGS, "items": mapping},
                "allow_uv_overlap": {"type": "boolean", "default": False},
            },
            "required": ["project_directory", "geometry_path", "output_path", "reference_image_path", "mappings"],
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


def _path(value: Any, label: str, project: str, *, kind: str) -> str:
    value = painter._safe_relative(value, label, minimum_parts=4)
    parts = value.split("/")
    if parts[:3] != ["resource_packs", f"{project}_RP", "textures"] or not value.endswith(".png"):
        raise ValueError(f"{label} must be a PNG under resource_packs/{project}_RP/textures/")
    if kind == "output":
        if len(parts) < 5 or parts[3] != "entity":
            raise ValueError(f"output_path must be inside resource_packs/{project}_RP/textures/entity/")
    elif kind == "base":
        if len(parts) < 5 or parts[3] != "entity":
            raise ValueError(f"base_texture_path must be inside resource_packs/{project}_RP/textures/entity/")
    return value


def _validate_args(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("arguments must be a JSON object")
    allowed = {"project_directory", "geometry_path", "output_path", "reference_image_path", "geometry_identifier", "base_texture_path", "background_color", "mappings", "allow_uv_overlap"}
    extra = set(raw) - allowed
    required = {"project_directory", "geometry_path", "output_path", "reference_image_path", "mappings"}
    missing = required - set(raw)
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    project = raw["project_directory"]
    if not isinstance(project, str) or not PROJECT_RE.fullmatch(project) or "--" in project:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    geometry_path = painter._safe_relative(raw["geometry_path"], "geometry_path", minimum_parts=5)
    if geometry_path.split("/")[:4] != ["resource_packs", f"{project}_RP", "models", "entity"] or not geometry_path.endswith(".json"):
        raise ValueError(f"geometry_path must be a .json file under resource_packs/{project}_RP/models/entity/")
    output_path = _path(raw["output_path"], "output_path", project, kind="output")
    reference_path = _path(raw["reference_image_path"], "reference_image_path", project, kind="reference")
    base_path = raw.get("base_texture_path")
    if base_path is not None:
        base_path = _path(base_path, "base_texture_path", project, kind="base")
    if reference_path == output_path or base_path == output_path:
        raise ValueError("output_path must be different from reference_image_path and base_texture_path")
    if reference_path == base_path and base_path is not None:
        raise ValueError("reference_image_path and base_texture_path must be different files")
    identifier = raw.get("geometry_identifier")
    if identifier is not None and (not isinstance(identifier, str) or not identifier or len(identifier) > 128):
        raise ValueError("geometry_identifier must be a non-empty string up to 128 characters")
    background = raw.get("background_color")
    if background is not None:
        painter._parse_color(background, "background_color")
    if base_path is not None and background is not None:
        raise ValueError("background_color cannot be combined with base_texture_path")
    overlap = raw.get("allow_uv_overlap", False)
    if not isinstance(overlap, bool):
        raise ValueError("allow_uv_overlap must be a boolean")
    raw_mappings = raw["mappings"]
    if not isinstance(raw_mappings, list) or not 1 <= len(raw_mappings) <= MAX_MAPPINGS:
        raise ValueError(f"mappings must contain 1 to {MAX_MAPPINGS} entries")
    mappings = []
    for index, entry in enumerate(raw_mappings):
        label = f"mappings[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{label} must be an object")
        extra_map = set(entry) - {"selector", "source_rect", "rotation", "flip_x", "flip_y", "sampling", "opacity", "blend_mode"}
        if extra_map:
            raise ValueError(f"{label} has unexpected field(s): {', '.join(sorted(extra_map))}")
        selector = entry.get("selector")
        if not isinstance(selector, dict) or not selector or set(selector) - {"bone", "cube_index", "face"}:
            raise ValueError(f"{label}.selector must select at least one of bone, cube_index or face")
        if "bone" in selector and (not isinstance(selector["bone"], str) or not selector["bone"] or len(selector["bone"]) > 64):
            raise ValueError(f"{label}.selector.bone must be a non-empty bone name")
        if "cube_index" in selector and (isinstance(selector["cube_index"], bool) or not isinstance(selector["cube_index"], int) or not 0 <= selector["cube_index"] <= 255):
            raise ValueError(f"{label}.selector.cube_index must be an integer from 0 to 255")
        if "face" in selector and (not isinstance(selector["face"], str) or selector["face"] not in FACES):
            raise ValueError(f"{label}.selector.face must be one of {sorted(FACES)}")
        rect = entry.get("source_rect")
        if not isinstance(rect, dict) or set(rect) != {"x", "y", "width", "height"}:
            raise ValueError(f"{label}.source_rect must contain exactly x, y, width and height")
        for key in ("x", "y", "width", "height"):
            val = rect[key]
            if isinstance(val, bool) or not isinstance(val, int) or val < (1 if key in {"width", "height"} else 0):
                raise ValueError(f"{label}.source_rect.{key} has an invalid integer value")
        rotation = entry.get("rotation", 0)
        if isinstance(rotation, bool) or not isinstance(rotation, int) or rotation not in {0, 90, 180, 270}:
            raise ValueError(f"{label}.rotation must be 0, 90, 180 or 270")
        flip_x, flip_y = entry.get("flip_x", False), entry.get("flip_y", False)
        if not isinstance(flip_x, bool) or not isinstance(flip_y, bool):
            raise ValueError(f"{label}.flip_x and flip_y must be booleans")
        sampling = entry.get("sampling", "nearest")
        if not isinstance(sampling, str) or sampling not in {"nearest", "bilinear"}:
            raise ValueError(f"{label}.sampling must be nearest or bilinear")
        opacity = entry.get("opacity", 255)
        if isinstance(opacity, bool) or not isinstance(opacity, int) or not 0 <= opacity <= 255:
            raise ValueError(f"{label}.opacity must be an integer from 0 to 255")
        blend_mode = entry.get("blend_mode", "over")
        if not isinstance(blend_mode, str) or blend_mode not in {"over", "replace"}:
            raise ValueError(f"{label}.blend_mode must be over or replace")
        mappings.append({"selector": dict(selector), "source_rect": dict(rect), "rotation": rotation,
                         "flip_x": flip_x, "flip_y": flip_y, "sampling": sampling,
                         "opacity": opacity, "blend_mode": blend_mode})
    return {"project_directory": project, "geometry_path": geometry_path, "output_path": output_path,
            "reference_image_path": reference_path, "geometry_identifier": identifier,
            "base_texture_path": base_path, "background_color": background,
            "mappings": mappings, "allow_uv_overlap": overlap}


def _matches(region: dict[str, Any], selector: dict[str, Any]) -> bool:
    return (("bone" not in selector or region["bone"] == selector["bone"])
            and ("cube_index" not in selector or region["cube_index"] == selector["cube_index"])
            and ("face" not in selector or region["face"] == selector["face"]))


def _sample_nearest(src: bytearray, sw: int, sh: int, rect: dict[str, int], u: float, v: float) -> tuple[int, int, int, int]:
    sx = rect["x"] + min(rect["width"] - 1, max(0, int(math.floor(u * rect["width"]))))
    sy = rect["y"] + min(rect["height"] - 1, max(0, int(math.floor(v * rect["height"]))))
    i = (sy * sw + sx) * 4
    return tuple(src[i:i + 4])  # type: ignore[return-value]


def _sample_bilinear(src: bytearray, sw: int, rect: dict[str, int], u: float, v: float) -> tuple[int, int, int, int]:
    # Coordinates are centered on source texel centers; interpolate in premultiplied-alpha space.
    fx = rect["x"] + u * rect["width"] - 0.5
    fy = rect["y"] + v * rect["height"] - 0.5
    x0, y0 = math.floor(fx), math.floor(fy)
    x1, y1 = x0 + 1, y0 + 1
    tx, ty = fx - x0, fy - y0
    x0 = min(rect["x"] + rect["width"] - 1, max(rect["x"], x0))
    x1 = min(rect["x"] + rect["width"] - 1, max(rect["x"], x1))
    y0 = min(rect["y"] + rect["height"] - 1, max(rect["y"], y0))
    y1 = min(rect["y"] + rect["height"] - 1, max(rect["y"], y1))
    samples = [
        (src[(y0 * sw + x0) * 4:(y0 * sw + x0) * 4 + 4], (1 - tx) * (1 - ty)),
        (src[(y0 * sw + x1) * 4:(y0 * sw + x1) * 4 + 4], tx * (1 - ty)),
        (src[(y1 * sw + x0) * 4:(y1 * sw + x0) * 4 + 4], (1 - tx) * ty),
        (src[(y1 * sw + x1) * 4:(y1 * sw + x1) * 4 + 4], tx * ty),
    ]
    alpha = sum(pixel[3] * weight for pixel, weight in samples)
    if alpha <= 0:
        return (0, 0, 0, 0)
    channels = []
    for channel in range(3):
        premul = sum(pixel[channel] * pixel[3] * weight for pixel, weight in samples)
        channels.append(max(0, min(255, round(premul / alpha))))
    return (channels[0], channels[1], channels[2], max(0, min(255, round(alpha))))


def _transform_uv(u: float, v: float, mapping: dict[str, Any]) -> tuple[float, float]:
    rotation = mapping["rotation"]
    if rotation == 90:
        u, v = v, 1.0 - u
    elif rotation == 180:
        u, v = 1.0 - u, 1.0 - v
    elif rotation == 270:
        u, v = 1.0 - v, u
    if mapping["flip_x"]:
        u = 1.0 - u
    if mapping["flip_y"]:
        v = 1.0 - v
    return min(1.0, max(0.0, u)), min(1.0, max(0.0, v))


def _apply_mapping(canvas: bytearray, cw: int, region: dict[str, Any], source: bytearray, sw: int, sh: int,
                   mapping: dict[str, Any]) -> int:
    x0, y0, x1, y1 = painter._region_pixel_bounds(region, cw, len(canvas) // (cw * 4))
    tw, th = x1 - x0, y1 - y0
    if tw <= 0 or th <= 0:
        return 0
    rect = mapping["source_rect"]
    changed = 0
    for dy in range(th):
        for dx in range(tw):
            u = (dx + 0.5) / tw
            v = (dy + 0.5) / th
            u, v = _transform_uv(u, v, mapping)
            if mapping["sampling"] == "bilinear":
                pixel = _sample_bilinear(source, sw, rect, u, v)
            else:
                pixel = _sample_nearest(source, sw, sh, rect, u, v)
            opacity = mapping["opacity"]
            pixel = (pixel[0], pixel[1], pixel[2], (pixel[3] * opacity + 127) // 255)
            offset = ((y0 + dy) * cw + x0 + dx) * 4
            before = bytes(canvas[offset:offset + 4])
            painter._blend(canvas, offset, pixel, mapping["blend_mode"])
            if before != canvas[offset:offset + 4]:
                changed += 1
    return changed


def _load_png(path: Path) -> tuple[int, int, bytearray, bytes]:
    size = path.stat().st_size
    if size < 45 or size > MAX_REFERENCE_BYTES:
        raise ValueError(f"PNG size must be between 45 bytes and {MAX_REFERENCE_BYTES} bytes")
    payload = path.read_bytes()
    if len(payload) != size:
        raise ValueError("PNG changed while it was being read")
    width, height, pixels = painter._decode_png_rgba(payload)
    return width, height, pixels, payload


def map_reference_texture_to_uv(raw_args: Any) -> dict[str, Any]:
    args = _validate_args(raw_args)
    _, project, rp_root = painter._resolve_project(args["project_directory"])
    geo_rel = "/".join(args["geometry_path"].split("/")[2:])
    geo_file = painter._resolve_file(rp_root, geo_rel, "geometry_path")
    geometry_root = uv._read_geometry(geo_file)
    geometries = geometry_root.get("minecraft:geometry") if isinstance(geometry_root, dict) else None
    if not isinstance(geometries, list) or not geometries:
        raise ValueError("geometry JSON must contain a non-empty minecraft:geometry array")
    candidates = []
    for entry in geometries:
        if not isinstance(entry, dict):
            continue
        desc = entry.get("description")
        gid = desc.get("identifier") if isinstance(desc, dict) else None
        if args["geometry_identifier"] is None or gid == args["geometry_identifier"]:
            candidates.append(entry)
    if len(candidates) != 1:
        if not candidates:
            raise ValueError(f"no geometry matched identifier {args['geometry_identifier']!r}")
        raise ValueError("geometry_identifier is required when a file contains multiple/duplicate geometries")
    geometry = candidates[0]
    desc = geometry.get("description")
    if not isinstance(desc, dict):
        raise ValueError("selected geometry has no description object")
    geometry_id = desc.get("identifier") if isinstance(desc.get("identifier"), str) else "<unnamed-geometry>"
    width, height = desc.get("texture_width"), desc.get("texture_height")
    if isinstance(width, bool) or not isinstance(width, int) or isinstance(height, bool) or not isinstance(height, int):
        raise ValueError("geometry must declare integer texture_width and texture_height")
    if not (1 <= width <= 4096 and 1 <= height <= 4096) or width * height > 16_777_216:
        raise ValueError("geometry texture canvas exceeds configured safety limits")
    regions, extraction_findings, cube_count = uv._extract_regions(geometry, geometry_id)
    if not regions:
        raise ValueError("selected geometry contains no supported UV regions")
    overlaps, overlap_count, overlap_complete = uv._overlaps(regions)
    out_of_bounds = [r for r in regions if r["bounds"][0] < 0 or r["bounds"][1] < 0 or r["bounds"][2] > width or r["bounds"][3] > height]
    if out_of_bounds:
        return _error("UV_OUT_OF_BOUNDS", "reference transfer refused because UV regions exceed the geometry texture canvas", {
            "texture_size": [width, height], "count": len(out_of_bounds),
            "regions": [{"bone": r["bone"], "cube_index": r["cube_index"], "face": r["face"], "bounds": r["bounds"]} for r in out_of_bounds[:100]],
        })
    if overlap_count and not args["allow_uv_overlap"]:
        return _error("UV_OVERLAP_REVIEW_REQUIRED", "UV regions overlap; enable allow_uv_overlap only when shared texels are intentional", {
            "overlap_pairs": overlap_count, "examples": overlaps[:25],
        })
    if not overlap_complete and not args["allow_uv_overlap"]:
        return _error("UV_OVERLAP_ANALYSIS_INCOMPLETE", "UV overlap analysis reached its safety budget; refusing a potentially ambiguous transfer unless overlap is explicitly accepted", {
            "overlap_pairs_found": overlap_count,
        })

    reference_rel = "/".join(args["reference_image_path"].split("/")[2:])
    reference_file = painter._resolve_file(rp_root, reference_rel, "reference_image_path")
    src_w, src_h, source, reference_payload = _load_png(reference_file)
    for index, mapping in enumerate(args["mappings"]):
        rect = mapping["source_rect"]
        if rect["x"] + rect["width"] > src_w or rect["y"] + rect["height"] > src_h:
            return _error("SOURCE_RECT_OUT_OF_BOUNDS", f"mappings[{index}].source_rect exceeds the reference image", {
                "reference_size": [src_w, src_h], "source_rect": rect,
            })

    output_rel = "/".join(args["output_path"].split("/")[2:])
    destination = painter._new_destination(rp_root, output_rel)
    if args["base_texture_path"]:
        base_rel = "/".join(args["base_texture_path"].split("/")[2:])
        base_file = painter._resolve_file(rp_root, base_rel, "base_texture_path")
        base_w, base_h, canvas, _base_payload = _load_png(base_file)
        if (base_w, base_h) != (width, height):
            return _error("BASE_TEXTURE_DIMENSION_MISMATCH", "base texture size must match geometry texture dimensions", {
                "geometry_size": [width, height], "base_texture_size": [base_w, base_h],
            })
    elif args["background_color"] is not None:
        bg = painter._parse_color(args["background_color"], "background_color")
        canvas = bytearray(bytes(bg) * (width * height))
    else:
        canvas = bytearray(width * height * 4)

    plan: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    duplicate_target_count = 0
    target_seen: dict[tuple[str, int, str], int] = {}
    estimated_writes = 0
    for index, mapping in enumerate(args["mappings"]):
        selected = [r for r in regions if _matches(r, mapping["selector"])]
        if not selected:
            return _error("SELECTOR_MATCHED_NO_UV", f"mappings[{index}] selector matched no UV region", {"selector": mapping["selector"]})
        for region in selected:
            key = (region["bone"], region["cube_index"], region["face"])
            target_seen[key] = target_seen.get(key, 0) + 1
            if target_seen[key] > 1:
                duplicate_target_count += 1
            x0, y0, x1, y1 = painter._region_pixel_bounds(region, width, height)
            estimated_writes += max(0, x1 - x0) * max(0, y1 - y0)
            if estimated_writes > MAX_SAMPLE_WRITES:
                return _error("TRANSFER_BUDGET_EXCEEDED", "planned texture transfer exceeds the texel-operation safety budget", {
                    "estimated_texel_writes": estimated_writes, "maximum_texel_writes": MAX_SAMPLE_WRITES,
                })
            plan.append((index, mapping, region))
    if duplicate_target_count and not args["allow_uv_overlap"]:
        return _error("TARGET_MAPPED_MORE_THAN_ONCE", "one or more UV regions are selected by multiple mappings; set allow_uv_overlap=true to apply intentional ordered layers", {
            "duplicate_region_selections": duplicate_target_count,
        })

    results = []
    for index, mapping, region in plan:
        changed = _apply_mapping(canvas, width, region, source, src_w, src_h, mapping)
        results.append({"mapping_index": index, "selector": mapping["selector"],
                        "target": {"bone": region["bone"], "bone_index": region["bone_index"], "cube_index": region["cube_index"],
                                   "face": region["face"], "bounds": region["bounds"],
                                   "uv_mapping": region["mapping"], "geometry_uv_rotation": region["uv_rotation"]},
                        "source_rect": mapping["source_rect"], "sampling": mapping["sampling"],
                        "rotation": mapping["rotation"], "flip_x": mapping["flip_x"], "flip_y": mapping["flip_y"],
                        "blend_mode": mapping["blend_mode"], "opacity": mapping["opacity"], "changed_texels": changed})
    png = painter._encode_png(width, height, canvas)
    out_w, out_h = validate_png_bytes(png, max_bytes=MAX_REFERENCE_BYTES, max_dimension=4096, max_pixels=16_777_216)
    painter._write_new(destination, png)
    warnings = list(extraction_findings[:100])
    if overlap_count:
        warnings.append({"code": "UV_REGION_OVERLAP_ALLOWED", "count": overlap_count,
                         "message": "Geometry UV regions overlap; later mapping operations may write shared texels."})
    if duplicate_target_count:
        warnings.append({"code": "ORDERED_MAPPING_LAYERS", "count": duplicate_target_count,
                         "message": "Some UV regions were selected more than once; mapping order determines the final pixels."})
    if not overlap_complete:
        warnings.append({"code": "OVERLAP_ANALYSIS_INCOMPLETE", "message": "UV overlap analysis stopped at its safety limit."})
    digest = hashlib.sha256(png).hexdigest()
    source_digest = hashlib.sha256(reference_payload).hexdigest()
    return {
        "status": "success",
        "geometry": {"identifier": geometry_id, "path": args["geometry_path"], "texture_size": [width, height],
                     "bone_count": len(geometry.get("bones", [])), "cube_count": cube_count, "uv_region_count": len(regions)},
        "reference": {"path": args["reference_image_path"], "size": [src_w, src_h], "sha256": source_digest},
        "texture": {"path": args["output_path"], "size": [out_w, out_h], "format": "PNG RGBA8",
                    "bytes": len(png), "sha256": digest, "base_texture": args["base_texture_path"]},
        "transfer": {"mapping_count": len(args["mappings"]), "target_region_count": len(plan),
                     "estimated_texel_writes": estimated_writes, "changed_texels": sum(r["changed_texels"] for r in results),
                     "uv_overlap_pairs": overlap_count, "overlap_analysis_complete": overlap_complete,
                     "mapping_results": results, "warnings": warnings},
        "scope_note": "Maps explicit source-image rectangles onto exact 2D geometry UV rectangles; preserves source alpha and optional base texture outside mapped regions. Mapping orientation is texture-space only and does not emulate Bedrock 3D face sampling, normals, materials, mipmaps or seam bleed. It does not infer correspondence from a portrait or generate AI art. Minecraft runtime: NOT RUN.",
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
            "serverInfo": {"name": "minecraft-bedrock-reference-texture-transfer", "version": SERVER_VERSION},
            "instructions": "Use map_reference_texture_to_uv with an existing reference PNG, a selected geometry and explicit source-rectangle to bone/cube/face mappings. It writes a new PNG; it does not infer 3D projection or generate artwork. Minecraft runtime remains NOT RUN."
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or name not in TOOL_BY_NAME:
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = map_reference_texture_to_uv(params.get("arguments", {}))
        except FileExistsError as exc:
            payload = _error("OUTPUT_EXISTS", str(exc))
        except (ValueError, PngValidationError) as exc:
            payload = _error("INVALID_INPUT", str(exc))
        except OSError as exc:
            payload = _error("IO_ERROR", f"safe reference transfer failed: {exc}")
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
