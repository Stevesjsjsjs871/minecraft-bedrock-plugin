#!/usr/bin/env python3
"""Deterministic visual-reference region analyzer for Minecraft Bedrock assets.

The analyzer finds connected alpha or quantized-color regions in a PNG reference,
then optionally ranks geometric UV-face candidates by aspect ratio and relative
area. It does not use an ML model, identify semantic body parts, or write files.
All proposed face matches are explicitly heuristic and require human approval.
"""
from __future__ import annotations

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
import texture_painting_mcp as painter

ROOT = Path(__file__).resolve().parents[1]
try:
    SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

MAX_REFERENCE_BYTES = 16 * 1024 * 1024
MAX_REFERENCE_DIMENSION = 2048
MAX_REFERENCE_PIXELS = 1_048_576
MAX_RUNS = 120_000
MAX_MATCHABLE_UV_REGIONS = 512
MAX_REGIONS = 96
MAX_UV_MATCHES = 3


def _tool() -> dict[str, Any]:
    return {
        "name": "analyze_visual_reference",
        "description": (
            "Read-only deterministic image analysis for a Minecraft Bedrock model reference PNG. Segments connected "
            "alpha foreground or quantized-color regions, reports bounds, area, centroid, average color and edge contact, "
            "and optionally ranks source regions against geometry UV faces using aspect ratio and relative area only. "
            "It does NOT use an AI/ML model, recognize characters/body parts, infer semantic correspondence, or create a "
            "transfer request. Candidate mappings are geometric hints and require human confirmation. Supports only "
            "validated non-interlaced 8-bit PNG inputs accepted by the texture painter decoder. Does not modify files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
                "reference_image_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "segmentation_mode": {"type": "string", "enum": ["alpha_components", "color_components"], "default": "color_components"},
                "alpha_threshold": {"type": "integer", "minimum": 1, "maximum": 255, "default": 8},
                "color_bucket_size": {"type": "integer", "enum": [4, 8, 16, 32, 64], "default": 16},
                "min_region_area": {"type": "integer", "minimum": 1, "maximum": 1048576, "default": 8},
                "max_regions": {"type": "integer", "minimum": 1, "maximum": MAX_REGIONS, "default": 48},
                "geometry_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "geometry_identifier": {"type": "string", "minLength": 1, "maxLength": 128},
            },
            "required": ["project_directory", "reference_image_path"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    }


TOOLS = [_tool()]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        result["error"]["details"] = details
    return result


def _safe_relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{label} must be a non-empty relative POSIX path up to 512 characters")
    if "\\" in value or "\x00" in value or value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        raise ValueError(f"{label} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must not contain empty, dot or traversal path segments")
    return value


def _validate_args(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("arguments must be a JSON object")
    props = TOOLS[0]["inputSchema"]["properties"]
    required = set(TOOLS[0]["inputSchema"]["required"])
    extra, missing = set(raw) - set(props), required - set(raw)
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")

    project = raw["project_directory"]
    if not isinstance(project, str) or not painter.PROJECT_RE.fullmatch(project) or "--" in project:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    ref = _safe_relative(raw["reference_image_path"], "reference_image_path")
    rp = ref.split("/")
    if len(rp) < 5 or rp[:3] != ["resource_packs", f"{project}_RP", "textures"] or not ref.endswith(".png"):
        raise ValueError(f"reference_image_path must be a PNG under resource_packs/{project}_RP/textures/")

    mode = raw.get("segmentation_mode", "color_components")
    if mode not in {"alpha_components", "color_components"}:
        raise ValueError("segmentation_mode must be alpha_components or color_components")
    alpha = raw.get("alpha_threshold", 8)
    bucket = raw.get("color_bucket_size", 16)
    min_area = raw.get("min_region_area", 8)
    max_regions = raw.get("max_regions", 48)
    for label, value, low, high in (
        ("alpha_threshold", alpha, 1, 255),
        ("min_region_area", min_area, 1, MAX_REFERENCE_PIXELS),
        ("max_regions", max_regions, 1, MAX_REGIONS),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"{label} must be an integer from {low} to {high}")
    if isinstance(bucket, bool) or not isinstance(bucket, int) or bucket not in {4, 8, 16, 32, 64}:
        raise ValueError("color_bucket_size must be one of 4, 8, 16, 32 or 64")

    geometry_path = raw.get("geometry_path")
    geometry_id = raw.get("geometry_identifier")
    if geometry_path is not None:
        geometry_path = _safe_relative(geometry_path, "geometry_path")
        gp = geometry_path.split("/")
        if len(gp) < 5 or gp[:4] != ["resource_packs", f"{project}_RP", "models", "entity"] or not geometry_path.endswith(".json"):
            raise ValueError(f"geometry_path must be a JSON file under resource_packs/{project}_RP/models/entity/")
    elif geometry_id is not None:
        raise ValueError("geometry_identifier requires geometry_path")
    if geometry_id is not None and (not isinstance(geometry_id, str) or not geometry_id or len(geometry_id) > 128):
        raise ValueError("geometry_identifier must be a non-empty string up to 128 characters")
    return {
        "project_directory": project, "reference_image_path": ref,
        "segmentation_mode": mode, "alpha_threshold": alpha,
        "color_bucket_size": bucket, "min_region_area": min_area,
        "max_regions": max_regions, "geometry_path": geometry_path,
        "geometry_identifier": geometry_id,
    }


def _new_node(parent: list[int], area: list[int], bounds: list[list[int]], sums: list[list[int]],
              x0: int, y: int, x1: int, color_sums: tuple[int, int, int, int]) -> int:
    node = len(parent)
    run_area = x1 - x0
    parent.append(node)
    area.append(run_area)
    bounds.append([x0, y, x1, y + 1])
    # sum(x), sum(y), sum(r), sum(g), sum(b), sum(a)
    sums.append([
        (x0 + x1 - 1) * run_area // 2,
        y * run_area,
        color_sums[0], color_sums[1], color_sums[2], color_sums[3],
    ])
    return node


def _find(parent: list[int], node: int) -> int:
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]
    return node


def _union(parent: list[int], area: list[int], bounds: list[list[int]], sums: list[list[int]], a: int, b: int) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra == rb:
        return
    if area[ra] < area[rb]:
        ra, rb = rb, ra
    parent[rb] = ra
    area[ra] += area[rb]
    ba, bb = bounds[ra], bounds[rb]
    ba[0], ba[1], ba[2], ba[3] = min(ba[0], bb[0]), min(ba[1], bb[1]), max(ba[2], bb[2]), max(ba[3], bb[3])
    sa, sb = sums[ra], sums[rb]
    for i in range(6):
        sa[i] += sb[i]


def _pixel_label(rgba: bytearray, offset: int, mode: str, alpha_threshold: int, bucket: int) -> tuple[int, ...] | None:
    r, g, b, a = rgba[offset:offset + 4]
    if a < alpha_threshold:
        return None
    if mode == "alpha_components":
        return (1,)
    return (r // bucket, g // bucket, b // bucket)


def _segment(width: int, height: int, rgba: bytearray, *, mode: str, alpha_threshold: int,
             bucket: int, min_area: int, max_regions: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parent: list[int] = []
    areas: list[int] = []
    bounds: list[list[int]] = []
    sums: list[list[int]] = []
    previous: list[tuple[int, int, tuple[int, ...], int]] = []
    total_runs = 0

    for y in range(height):
        current: list[tuple[int, int, tuple[int, ...], int]] = []
        x = 0
        while x < width:
            offset = (y * width + x) * 4
            label = _pixel_label(rgba, offset, mode, alpha_threshold, bucket)
            if label is None:
                x += 1
                continue
            x0 = x
            rsum = gsum = bsum = asum = 0
            while x < width:
                offset = (y * width + x) * 4
                this_label = _pixel_label(rgba, offset, mode, alpha_threshold, bucket)
                if this_label != label:
                    break
                rsum += rgba[offset]
                gsum += rgba[offset + 1]
                bsum += rgba[offset + 2]
                asum += rgba[offset + 3]
                x += 1
            node = _new_node(parent, areas, bounds, sums, x0, y, x, (rsum, gsum, bsum, asum))
            current.append((x0, x, label, node))
            total_runs += 1
            if total_runs > MAX_RUNS:
                raise ValueError(f"reference segmentation exceeded the {MAX_RUNS}-run complexity budget; increase color_bucket_size or use alpha_components")

        prev_start = 0
        for x0, x1, label, node in current:
            while prev_start < len(previous) and previous[prev_start][1] <= x0:
                prev_start += 1
            j = prev_start
            while j < len(previous) and previous[j][0] < x1:
                px0, px1, plabel, pnode = previous[j]
                if px1 > x0 and plabel == label:
                    _union(parent, areas, bounds, sums, node, pnode)
                j += 1
        previous = current

    roots: dict[int, int] = {}
    for node in range(len(parent)):
        root = _find(parent, node)
        roots[root] = root

    components: list[dict[str, Any]] = []
    for root in roots:
        area = areas[root]
        if area < min_area:
            continue
        left, top, right, bottom = bounds[root]
        stat = sums[root]
        average = [max(0, min(255, round(stat[i] / area))) for i in (2, 3, 4, 5)]
        components.append({
            "source_rect": {"x": left, "y": top, "width": right - left, "height": bottom - top},
            "pixel_area": area,
            "centroid": [round(stat[0] / area, 2), round(stat[1] / area, 2)],
            "aspect_ratio": round((right - left) / max(1, bottom - top), 4),
            "average_color": "#" + "".join(f"{v:02X}" for v in average[:3]),
            "average_alpha": average[3],
            "edge_contact": {
                "left": left == 0, "top": top == 0,
                "right": right == width, "bottom": bottom == height,
            },
        })
    components.sort(key=lambda item: (-item["pixel_area"], item["source_rect"]["y"], item["source_rect"]["x"]))
    total_qualifying = len(components)
    components = components[:max_regions]
    for index, component in enumerate(components, 1):
        component["region_id"] = f"region_{index:03d}"
        component["coverage"] = round(component["pixel_area"] / (width * height), 6)
        edge_count = sum(bool(value) for value in component["edge_contact"].values())
        component["background_candidate"] = bool(
            mode == "color_components" and component["coverage"] >= 0.15 and edge_count >= 2
        )
    return components, {
        "run_count": total_runs,
        "connected_component_count_after_min_area": total_qualifying,
        "returned_region_count": len(components),
        "truncated": total_qualifying > len(components),
        "discarded_below_min_area": len(roots) - total_qualifying,
    }


def _load_geometry(rp_root: Path, relative: str, identifier: str | None) -> tuple[str, int, int, list[dict[str, Any]], list[dict[str, Any]]]:
    geometry_file = uv._safe_file(rp_root, "/".join(relative.split("/")[2:]), "geometry_path")
    root = uv._read_geometry(geometry_file)
    candidates = []
    for entry in root.get("minecraft:geometry", []) if isinstance(root, dict) else []:
        if not isinstance(entry, dict):
            continue
        desc = entry.get("description")
        gid = desc.get("identifier") if isinstance(desc, dict) else None
        if identifier is None or gid == identifier:
            candidates.append(entry)
    if not candidates:
        raise ValueError(f"geometry JSON did not contain geometry {identifier!r}" if identifier else "geometry JSON has no minecraft:geometry entry")
    if identifier is None and len(candidates) != 1:
        raise ValueError("geometry file contains multiple geometry entries; specify geometry_identifier")
    selected = candidates[0]
    desc = selected.get("description")
    if not isinstance(desc, dict):
        raise ValueError("selected geometry has no description")
    gid = desc.get("identifier") if isinstance(desc.get("identifier"), str) else "<unnamed-geometry>"
    width, height = desc.get("texture_width"), desc.get("texture_height")
    if isinstance(width, bool) or not isinstance(width, int) or isinstance(height, bool) or not isinstance(height, int) or not (1 <= width <= 4096 and 1 <= height <= 4096):
        raise ValueError("selected geometry must declare integer texture_width and texture_height from 1 to 4096")
    regions, findings, cube_count = uv._extract_regions(selected, gid)
    return gid, width, height, regions, findings


def _candidate_matches(regions: list[dict[str, Any]], components: list[dict[str, Any]],
                       source_width: int, source_height: int, canvas_width: int, canvas_height: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    source_area = source_width * source_height
    canvas_area = canvas_width * canvas_height
    for target in regions[:MAX_MATCHABLE_UV_REGIONS]:
        left, top, right, bottom = target["bounds"]
        tw, th = max(0.001, abs(right - left)), max(0.001, abs(bottom - top))
        target_aspect = tw / th
        target_fraction = (tw * th) / canvas_area
        ranked = []
        for source in components:
            rect = source["source_rect"]
            source_aspect = rect["width"] / max(1, rect["height"])
            source_fraction = source["pixel_area"] / source_area
            aspect_score = math.exp(-abs(math.log(max(1e-9, source_aspect / target_aspect))))
            area_score = math.exp(-abs(math.log(max(1e-9, source_fraction / max(1e-9, target_fraction)))))
            score = 0.8 * aspect_score + 0.2 * area_score
            ranked.append({
                "region_id": source["region_id"],
                "source_rect": rect,
                "score": round(score, 4),
                "aspect_score": round(aspect_score, 4),
                "relative_area_score": round(area_score, 4),
            })
        ranked.sort(key=lambda item: (-item["score"], item["region_id"]))
        results.append({
            "target": {"bone": target["bone"], "cube_index": target["cube_index"], "face": target["face"],
                       "uv_bounds": target["bounds"], "uv_size": [round(tw, 4), round(th, 4)]},
            "candidates": ranked[:MAX_UV_MATCHES],
            "matching_basis": "aspect ratio (80%) + normalized source/target area (20%); no semantic recognition",
        })
    return results


def analyze_visual_reference(raw_args: Any) -> dict[str, Any]:
    args = _validate_args(raw_args)
    _, rp_root = uv._resolve_roots(args["project_directory"])
    ref_relative = "/".join(args["reference_image_path"].split("/")[2:])
    ref_path = uv._safe_file(rp_root, ref_relative, "reference_image_path")
    size = ref_path.stat().st_size
    if size < 45 or size > MAX_REFERENCE_BYTES:
        raise ValueError(f"reference PNG must be between 45 bytes and {MAX_REFERENCE_BYTES} bytes")
    payload = ref_path.read_bytes()
    if len(payload) != size:
        raise ValueError("reference PNG changed while it was being read")
    width, height, rgba = painter._decode_png_rgba(payload)
    if width > MAX_REFERENCE_DIMENSION or height > MAX_REFERENCE_DIMENSION or width * height > MAX_REFERENCE_PIXELS:
        raise ValueError(f"reference PNG exceeds analyzer limits ({MAX_REFERENCE_DIMENSION}px per side and {MAX_REFERENCE_PIXELS} pixels total)")

    components, segmentation = _segment(
        width, height, rgba, mode=args["segmentation_mode"],
        alpha_threshold=args["alpha_threshold"], bucket=args["color_bucket_size"],
        min_area=args["min_region_area"], max_regions=args["max_regions"],
    )
    if not components:
        raise ValueError("no visible connected regions met min_region_area; lower the threshold or use color_components")

    alpha_nontransparent = sum(1 for index in range(3, len(rgba), 4) if rgba[index] >= args["alpha_threshold"])
    geometry_info = None
    matches = []
    geometry_findings: list[dict[str, Any]] = []
    if args["geometry_path"]:
        gid, cw, ch, uv_regions, geometry_findings = _load_geometry(rp_root, args["geometry_path"], args["geometry_identifier"])
        matches = _candidate_matches(uv_regions, components, width, height, cw, ch)
        geometry_info = {"identifier": gid, "path": args["geometry_path"], "texture_canvas": [cw, ch],
                         "uv_face_regions": len(uv_regions), "uv_candidate_matches": len(matches),
                         "uv_matching_truncated": len(uv_regions) > len(matches)}

    warnings: list[dict[str, Any]] = []
    if args["segmentation_mode"] == "alpha_components" and len(components) == 1 and not segmentation["truncated"]:
        warnings.append({"code": "SINGLE_ALPHA_SILHOUETTE", "message": "The visible subject is one connected silhouette. Use color_components or supply a reference with separated transparent regions to inspect internal parts."})
    if segmentation["truncated"]:
        warnings.append({"code": "REGION_RESULTS_TRUNCATED", "message": "More components met min_region_area than max_regions; only the largest are returned."})
    if any(region.get("background_candidate") for region in components):
        warnings.append({"code": "POSSIBLE_BACKGROUND_REGION", "message": "One or more large color components touch multiple image edges. They may be background; inspect before assigning them to a UV face."})
    if geometry_info and geometry_info["uv_matching_truncated"]:
        warnings.append({"code": "UV_CANDIDATE_MATCHING_TRUNCATED", "message": f"Only the first {MAX_MATCHABLE_UV_REGIONS} UV face regions were ranked against reference components."})
    if any(item.get("code") == "UNSUPPORTED_MESH_UV_SCOPE" for item in geometry_findings):
        warnings.append({"code": "UNSUPPORTED_GEOMETRY_UV", "message": "Some geometry mesh UVs are outside this cube-face analyzer."})

    return {
        "status": "success",
        "reference": {"path": args["reference_image_path"], "width": width, "height": height,
                      "bytes": size, "sha256": __import__("hashlib").sha256(payload).hexdigest(),
                      "alpha_nontransparent_pixels": alpha_nontransparent,
                      "segmentation_mode": args["segmentation_mode"]},
        "segmentation": segmentation,
        "regions": components,
        "geometry": geometry_info,
        "geometric_candidates": matches,
        "geometry_findings": geometry_findings[:100],
        "warnings": warnings,
        "scope_note": (
            "This is deterministic connected-component segmentation, not AI image understanding. Region IDs have no semantic meaning; "
            "matching scores use only aspect ratio and normalized area and must not be treated as body-part recognition. "
            "Use the returned source_rect only after visually confirming the intended fragment, then explicitly supply it to UV Mapping Assistant. "
            "No files were written or modified. PNG decoding accepts validated 8-bit non-interlaced PNGs only. Minecraft runtime/rendering: NOT RUN."
        ),
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
            "serverInfo": {"name": "minecraft-bedrock-visual-reference-analyzer", "version": SERVER_VERSION},
            "instructions": "Use analyze_visual_reference on a PNG in the existing project's Resource Pack textures. It reports connected alpha/color components and optional geometry-only face candidates. All semantic mapping requires human confirmation; the tool is read-only.",
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name, arguments = params.get("name"), params.get("arguments", {})
        if name not in TOOL_BY_NAME:
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = analyze_visual_reference(arguments)
        except (ValueError, OSError) as exc:
            payload = _error("REFERENCE_ANALYSIS_ERROR", str(exc))
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
