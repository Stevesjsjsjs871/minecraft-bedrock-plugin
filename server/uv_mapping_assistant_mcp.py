#!/usr/bin/env python3
"""Prepare explicit, geometry-aware UV-to-reference transfer plans for Bedrock entities.

The assistant inventories every supported cube-face UV region, expands caller-provided
source-rectangle assignments into exact selectors, and emits a validated request that
can be passed to map_reference_texture_to_uv. It never modifies project files.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import geometry_uv_template_mcp as uv
import reference_texture_transfer_mcp as transfer
import texture_painting_mcp as painter

ROOT = Path(__file__).resolve().parents[1]
try:
    SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

MAX_ASSIGNMENTS = 256
MAX_REGIONS = uv.MAX_REGIONS
FACES = {"north", "south", "east", "west", "up", "down"}


def _tool() -> dict[str, Any]:
    return {
        "name": "build_uv_mapping_plan",
        "description": (
            "Read-only UV Mapping Assistant for Minecraft Bedrock entities. Inventories all supported cube-face UV regions "
            "from one .geo.json geometry, calculates exact pixel bounds and normalized coordinates, detects overlaps, "
            "and expands explicit source-sheet rectangle assignments into exact bone/cube/face selectors. When a reference "
            "PNG is supplied, validates it and checks every source rectangle. Returns a transfer_request compatible with "
            "map_reference_texture_to_uv; the caller can pass that request to the transfer tool. It does not infer semantic "
            "correspondence from character art, unwrap meshes, render 3D faces, or modify files. Static planning only; "
            "Minecraft runtime/rendering remain NOT RUN."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
                "geometry_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "geometry_identifier": {"type": "string", "minLength": 1, "maxLength": 128},
                "reference_image_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "output_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "base_texture_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "background_color": {"type": "string", "minLength": 6, "maxLength": 7},
                "source_assignments": {
                    "type": "array", "minItems": 1, "maxItems": MAX_ASSIGNMENTS,
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["selector", "source_rect"],
                        "properties": {
                            "selector": {
                                "type": "object", "minProperties": 1, "additionalProperties": False,
                                "properties": {
                                    "bone": {"type": "string", "minLength": 1, "maxLength": 64},
                                    "cube_index": {"type": "integer", "minimum": 0, "maximum": 255},
                                    "face": {"type": "string", "enum": sorted(FACES)},
                                },
                            },
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
                    },
                },
                "allow_uv_overlap": {"type": "boolean", "default": False},
                "allow_layered_assignments": {"type": "boolean", "default": False},
                "require_full_coverage": {"type": "boolean", "default": False},
            },
            "required": ["project_directory", "geometry_path", "geometry_identifier", "reference_image_path", "output_path", "source_assignments"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    }


TOOLS = [_tool()]
TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        result["error"]["details"] = details
    return result


def _validate_rel_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{label} must be a non-empty relative POSIX path")
    if "\\" in value or "\x00" in value or value.startswith("/") or (len(value) >= 2 and value[1] == ":"):
        raise ValueError(f"{label} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise ValueError(f"{label} must not contain empty, dot or parent-traversal segments")
    return value


def _validate_args(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("arguments must be a JSON object")
    schema = TOOLS[0]["inputSchema"]
    allowed = set(schema["properties"])
    extra = set(raw) - allowed
    missing = set(schema["required"]) - set(raw)
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")

    project = raw["project_directory"]
    if not isinstance(project, str) or not painter.PROJECT_RE.fullmatch(project) or "--" in project:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    geometry_path = _validate_rel_path(raw["geometry_path"], "geometry_path")
    gp = geometry_path.split("/")
    if len(gp) < 5 or gp[:4] != ["resource_packs", f"{project}_RP", "models", "entity"] or not geometry_path.endswith(".json"):
        raise ValueError(f"geometry_path must be inside resource_packs/{project}_RP/models/entity/")
    reference_path = _validate_rel_path(raw["reference_image_path"], "reference_image_path")
    rp = reference_path.split("/")
    if len(rp) < 5 or rp[:3] != ["resource_packs", f"{project}_RP", "textures"] or not reference_path.endswith(".png"):
        raise ValueError(f"reference_image_path must be a PNG under resource_packs/{project}_RP/textures/")
    output_path = _validate_rel_path(raw["output_path"], "output_path")
    op = output_path.split("/")
    if len(op) < 5 or op[:4] != ["resource_packs", f"{project}_RP", "textures", "entity"] or not output_path.endswith(".png"):
        raise ValueError(f"output_path must be a PNG under resource_packs/{project}_RP/textures/entity/")
    if output_path in {reference_path, geometry_path}:
        raise ValueError("output_path must be distinct from the geometry and source reference")

    gid = raw["geometry_identifier"]
    if not isinstance(gid, str) or not gid or len(gid) > 128:
        raise ValueError("geometry_identifier must be a non-empty string up to 128 characters")
    base = raw.get("base_texture_path")
    if base is not None:
        base = _validate_rel_path(base, "base_texture_path")
        bp = base.split("/")
        if len(bp) < 5 or bp[:4] != ["resource_packs", f"{project}_RP", "textures", "entity"] or not base.endswith(".png"):
            raise ValueError(f"base_texture_path must be a PNG under resource_packs/{project}_RP/textures/entity/")
        if base in {output_path, reference_path}:
            raise ValueError("base_texture_path must be distinct from output and reference images")
    background = raw.get("background_color")
    if background is not None:
        painter._parse_color(background, "background_color")
        if base is not None:
            raise ValueError("background_color cannot be combined with base_texture_path")

    flags = {}
    for key in ("allow_uv_overlap", "allow_layered_assignments", "require_full_coverage"):
        value = raw.get(key, False)
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a boolean")
        flags[key] = value
    assignments = raw["source_assignments"]
    if not isinstance(assignments, list) or not 1 <= len(assignments) <= MAX_ASSIGNMENTS:
        raise ValueError(f"source_assignments must contain 1 to {MAX_ASSIGNMENTS} entries")
    normalized: list[dict[str, Any]] = []
    for i, item in enumerate(assignments):
        label = f"source_assignments[{i}]"
        if not isinstance(item, dict) or set(item) - {"selector", "source_rect", "rotation", "flip_x", "flip_y", "sampling", "opacity", "blend_mode"}:
            raise ValueError(f"{label} contains invalid fields")
        selector = item.get("selector")
        if not isinstance(selector, dict) or not selector or set(selector) - {"bone", "cube_index", "face"}:
            raise ValueError(f"{label}.selector must specify one or more of bone, cube_index and face")
        if "bone" in selector and (not isinstance(selector["bone"], str) or not selector["bone"] or len(selector["bone"]) > 64):
            raise ValueError(f"{label}.selector.bone is invalid")
        if "cube_index" in selector and (isinstance(selector["cube_index"], bool) or not isinstance(selector["cube_index"], int) or not 0 <= selector["cube_index"] <= 255):
            raise ValueError(f"{label}.selector.cube_index is invalid")
        if "face" in selector and (not isinstance(selector["face"], str) or selector["face"] not in FACES):
            raise ValueError(f"{label}.selector.face must be a Bedrock cube face")
        rect = item.get("source_rect")
        if not isinstance(rect, dict) or set(rect) != {"x", "y", "width", "height"}:
            raise ValueError(f"{label}.source_rect must contain x, y, width and height")
        for k in ("x", "y", "width", "height"):
            val = rect[k]
            if isinstance(val, bool) or not isinstance(val, int) or val < (1 if k in {"width", "height"} else 0):
                raise ValueError(f"{label}.source_rect.{k} is invalid")
        rotation = item.get("rotation", 0)
        if isinstance(rotation, bool) or not isinstance(rotation, int) or rotation not in {0, 90, 180, 270}:
            raise ValueError(f"{label}.rotation must be 0, 90, 180 or 270")
        flip_x, flip_y = item.get("flip_x", False), item.get("flip_y", False)
        if not isinstance(flip_x, bool) or not isinstance(flip_y, bool):
            raise ValueError(f"{label}.flip_x/flip_y must be booleans")
        sampling = item.get("sampling", "nearest")
        if not isinstance(sampling, str) or sampling not in {"nearest", "bilinear"}:
            raise ValueError(f"{label}.sampling must be nearest or bilinear")
        opacity = item.get("opacity", 255)
        if isinstance(opacity, bool) or not isinstance(opacity, int) or not 0 <= opacity <= 255:
            raise ValueError(f"{label}.opacity must be an integer from 0 to 255")
        blend = item.get("blend_mode", "over")
        if not isinstance(blend, str) or blend not in {"over", "replace"}:
            raise ValueError(f"{label}.blend_mode must be over or replace")
        normalized.append({"selector": dict(selector), "source_rect": dict(rect), "rotation": rotation,
                           "flip_x": flip_x, "flip_y": flip_y, "sampling": sampling,
                           "opacity": opacity, "blend_mode": blend})
    if base and background is not None:
        raise ValueError("background_color cannot be combined with base_texture_path")
    return {"project_directory": project, "geometry_path": geometry_path, "geometry_identifier": gid,
            "reference_image_path": reference_path, "output_path": output_path,
            "base_texture_path": base, "background_color": background,
            "source_assignments": normalized, **flags}


def _match(region: dict[str, Any], selector: dict[str, Any]) -> bool:
    target = region["selector"]
    return (("bone" not in selector or target["bone"] == selector["bone"])
            and ("cube_index" not in selector or target["cube_index"] == selector["cube_index"])
            and ("face" not in selector or target["face"] == selector["face"]))


def build_uv_mapping_plan(raw_args: Any) -> dict[str, Any]:
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
        if isinstance(desc, dict) and desc.get("identifier") == args["geometry_identifier"]:
            candidates.append(entry)
    if len(candidates) != 1:
        raise ValueError("geometry_identifier must match exactly one geometry in the file")
    geometry = candidates[0]
    desc = geometry.get("description")
    width, height = desc.get("texture_width"), desc.get("texture_height")
    if isinstance(width, bool) or not isinstance(width, int) or isinstance(height, bool) or not isinstance(height, int):
        raise ValueError("selected geometry must declare integer texture_width and texture_height")
    if not (1 <= width <= 4096 and 1 <= height <= 4096) or width * height > 16_777_216:
        raise ValueError("geometry texture canvas exceeds safety limits")

    reference_rel = "/".join(args["reference_image_path"].split("/")[2:])
    reference_file = painter._resolve_file(rp_root, reference_rel, "reference_image_path")
    source_width, source_height, _source_pixels, source_payload = transfer._load_png(reference_file)
    base_size = None
    if args["base_texture_path"]:
        base_rel = "/".join(args["base_texture_path"].split("/")[2:])
        base_file = painter._resolve_file(rp_root, base_rel, "base_texture_path")
        base_width, base_height, _pixels, _payload = transfer._load_png(base_file)
        base_size = [base_width, base_height]
        if base_size != [width, height]:
            return _error("BASE_TEXTURE_DIMENSION_MISMATCH", "base texture must match the geometry canvas", {
                "geometry_size": [width, height], "base_texture_size": base_size,
            })

    regions, extraction_findings, cube_count = uv._extract_regions(geometry, args["geometry_identifier"])
    if not regions:
        raise ValueError("selected geometry contains no supported cube-face UV regions")
    if len(regions) > MAX_REGIONS:
        raise ValueError("geometry exceeds the UV region safety limit")
    overlaps, overlap_count, overlap_complete = uv._overlaps(regions)
    out_of_bounds = []
    normalized_regions = []
    for region_index, region in enumerate(regions):
        left, top, right, bottom = region["bounds"]
        if left < 0 or top < 0 or right > width or bottom > height:
            out_of_bounds.append({"region_index": region_index, "bone": region["bone"], "cube_index": region["cube_index"],
                                  "face": region["face"], "bounds": region["bounds"]})
        record = {
            "region_id": f"r{region_index:04d}",
            "selector": {"bone": region["bone"], "cube_index": region["cube_index"], "face": region["face"]},
            "bone_index": region["bone_index"],
            "mapping": region["mapping"],
            "uv_bounds": [left, top, right, bottom],
            "uv_size": [right - left, bottom - top],
            "normalized_bounds": [round(left / width, 6), round(top / height, 6), round(right / width, 6), round(bottom / height, 6)],
            "pixel_rect": {"x": math.floor(left), "y": math.floor(top),
                           "width": max(0, math.ceil(right) - math.floor(left)),
                           "height": max(0, math.ceil(bottom) - math.floor(top))},
            "pixel_coverage": max(0, math.ceil(right) - math.floor(left)) * max(0, math.ceil(bottom) - math.floor(top)),
            "uv_rotation": region.get("uv_rotation", 0),
            "in_bounds": left >= 0 and top >= 0 and right <= width and bottom <= height,
        }
        normalized_regions.append(record)
    if out_of_bounds:
        return _error("UV_OUT_OF_BOUNDS", "mapping plan cannot be transfer-ready while UV regions exceed the texture canvas", {
            "texture_size": [width, height], "regions": out_of_bounds[:100], "count": len(out_of_bounds),
        })

    resolved_mappings = []
    assignment_results = []
    selected_counts: dict[str, int] = {}
    for assignment_index, assignment in enumerate(args["source_assignments"]):
        selector = assignment["selector"]
        matches = [r for r in normalized_regions if _match(r, selector)]
        if not matches:
            return _error("SELECTOR_MATCHED_NO_UV", f"source_assignments[{assignment_index}] selector matched no UV region", {
                "selector": selector,
            })
        rect = assignment["source_rect"]
        if rect["x"] + rect["width"] > source_width or rect["y"] + rect["height"] > source_height:
            return _error("SOURCE_RECT_OUT_OF_BOUNDS", f"source_assignments[{assignment_index}] source_rect exceeds the reference image", {
                "reference_size": [source_width, source_height], "source_rect": rect,
            })
        expanded = []
        for region in matches:
            rid = region["region_id"]
            selected_counts[rid] = selected_counts.get(rid, 0) + 1
            mapping = {
                "selector": dict(region["selector"]),
                "source_rect": dict(rect),
                "rotation": assignment["rotation"],
                "flip_x": assignment["flip_x"],
                "flip_y": assignment["flip_y"],
                "sampling": assignment["sampling"],
                "opacity": assignment["opacity"],
                "blend_mode": assignment["blend_mode"],
            }
            resolved_mappings.append(mapping)
            expanded.append(rid)
        assignment_results.append({"assignment_index": assignment_index, "input_selector": selector,
                                   "matched_region_ids": expanded, "expanded_region_count": len(matches),
                                   "source_rect": rect})
        if len(resolved_mappings) > MAX_ASSIGNMENTS:
            return _error("MAPPING_LIMIT_EXCEEDED", f"expanded transfer plan exceeds {MAX_ASSIGNMENTS} mappings", {
                "expanded_mappings": len(resolved_mappings),
            })

    duplicate_targets = [rid for rid, count in selected_counts.items() if count > 1]
    covered = set(selected_counts)
    missing = [r for r in normalized_regions if r["region_id"] not in covered]
    if duplicate_targets and not args["allow_layered_assignments"]:
        return _error("DUPLICATE_TARGET_ASSIGNMENT", "multiple source assignments select the same UV region; enable allow_layered_assignments only for intentional ordered overlays", {
            "region_ids": duplicate_targets[:100], "count": len(duplicate_targets),
        })
    if duplicate_targets and args["allow_layered_assignments"] and not args["allow_uv_overlap"]:
        return _error("UV_OVERLAP_ACCEPTANCE_REQUIRED", "the downstream transfer tool uses one allow_uv_overlap switch for both shared UVs and ordered target layers; set allow_uv_overlap=true to accept intentional layering", {
            "region_ids": duplicate_targets[:100], "count": len(duplicate_targets),
        })
    if overlap_count and not args["allow_uv_overlap"]:
        overlap_transfer_blocked = True
    else:
        overlap_transfer_blocked = not overlap_complete and not args["allow_uv_overlap"]
    full_coverage_ok = not missing or not args["require_full_coverage"]
    mapping_request = {
        "project_directory": args["project_directory"],
        "geometry_path": args["geometry_path"],
        "geometry_identifier": args["geometry_identifier"],
        "reference_image_path": args["reference_image_path"],
        "output_path": args["output_path"],
        "mappings": resolved_mappings,
        "allow_uv_overlap": args["allow_uv_overlap"],
    }
    if args["base_texture_path"]:
        mapping_request["base_texture_path"] = args["base_texture_path"]
    if args["background_color"]:
        mapping_request["background_color"] = args["background_color"]
    # Validate compatibility with the existing transfer tool schema before returning it.
    transfer._validate_args(mapping_request)
    output_rel = "/".join(args["output_path"].split("/")[2:])
    painter._new_destination(rp_root, output_rel)

    can_execute = full_coverage_ok and not overlap_transfer_blocked
    if not can_execute:
        status = "needs_review"
    elif missing:
        status = "partial"
    else:
        status = "ready"
    warnings = list(extraction_findings[:100])
    if overlap_count:
        warnings.append({"code": "UV_REGION_OVERLAP", "count": overlap_count,
                         "message": "UV regions share texels. This may be intentional; transfer requires explicit allow_uv_overlap."})
    if not overlap_complete:
        warnings.append({"code": "UV_OVERLAP_ANALYSIS_INCOMPLETE", "message": "Overlap comparison reached the configured safety budget."})
    if missing:
        warnings.append({"code": "INCOMPLETE_UV_COVERAGE", "count": len(missing),
                         "region_ids": [r["region_id"] for r in missing[:100]],
                         "message": "Some geometry faces have no source assignment."})
    if duplicate_targets:
        warnings.append({"code": "ORDERED_LAYERED_ASSIGNMENTS", "count": len(duplicate_targets),
                         "message": "Multiple assignments target the same UV region; input order determines final pixels."})
    if source_width < 1 or source_height < 1:
        raise ValueError("reference PNG dimensions are invalid")

    return {
        "status": "success",
        "plan_status": status,
        "can_execute_transfer": can_execute,
        "geometry": {"path": args["geometry_path"], "identifier": args["geometry_identifier"],
                     "texture_size": [width, height], "bone_count": len(geometry.get("bones", [])),
                     "cube_count": cube_count, "uv_region_count": len(normalized_regions)},
        "reference": {"path": args["reference_image_path"], "size": [source_width, source_height],
                      "sha256": hashlib.sha256(source_payload).hexdigest()},
        "base_texture": {"path": args["base_texture_path"], "size": base_size} if base_size else None,
        "inventory": normalized_regions,
        "assignments": assignment_results,
        "coverage": {"mapped_regions": len(covered), "unmapped_regions": len(missing),
                     "total_regions": len(normalized_regions), "complete": not missing,
                     "unmapped_region_ids": [r["region_id"] for r in missing[:250]]},
        "overlap": {"pair_count": overlap_count, "analysis_complete": overlap_complete,
                    "pairs": overlaps[:100], "accepted": args["allow_uv_overlap"]},
        "transfer_request": mapping_request if can_execute else None,
        "draft_transfer_request": mapping_request if not can_execute else None,
        "warnings": warnings,
        "scope_note": "This tool resolves explicit user-authored source rectangles into exact geometry face selectors. It does not infer which portrait/image pixels depict a particular body part. The transfer_request is schema-validated for map_reference_texture_to_uv. This tool is read-only; running the transfer request is a separate write operation. Texture-space mapping does not emulate Bedrock 3D sampling, normals, materials, mipmaps, seam bleed or runtime rendering. Minecraft runtime: NOT RUN.",
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
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": params.get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-uv-mapping-assistant", "version": SERVER_VERSION},
            "instructions": "Use build_uv_mapping_plan to inventory geometry UV regions and expand explicit reference-sheet assignments into a transfer request. Pass transfer_request to map_reference_texture_to_uv after reviewing coverage and overlap warnings. This assistant is read-only.",
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        if name not in TOOL_BY_NAME:
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = build_uv_mapping_plan(params.get("arguments", {}))
        except (ValueError, OSError) as exc:
            payload = _error("INVALID_OR_UNSAFE_INPUT", str(exc))
        except Exception as exc:
            payload = _error("INTERNAL_ERROR", f"unexpected {type(exc).__name__}: {exc}")
        return _tool_result(request_id, payload)
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle_message(message)
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
