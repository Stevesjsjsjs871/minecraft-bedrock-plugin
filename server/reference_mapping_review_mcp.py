#!/usr/bin/env python3
"""Human-in-the-loop review gate for visual-reference to Bedrock UV mappings.

Consumes a prior deterministic analyzer result, binds it to the exact PNG by
SHA-256, validates explicit semantic labels/target faces against the current
geometry, and delegates transfer-plan validation to UV Mapping Assistant. It
never writes textures or geometry files.
"""
from __future__ import annotations

import hashlib
import json
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
import reference_texture_transfer_mcp as transfer
import uv_mapping_assistant_mcp as mapping_assistant

ROOT = Path(__file__).resolve().parents[1]
try:
    SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

MAX_DECISIONS = 256
MAX_ANALYSIS_REGIONS = 96
FACES = {"north", "south", "east", "west", "up", "down"}
DECISIONS = {"approve", "reject", "needs_review"}


def _tool() -> dict[str, Any]:
    decision = {
        "type": "object",
        "additionalProperties": False,
        "required": ["source_region_id", "target", "decision"],
        "properties": {
            "source_region_id": {"type": "string", "minLength": 1, "maxLength": 32},
            "target": {
                "type": "object", "additionalProperties": False,
                "required": ["bone", "cube_index", "face"],
                "properties": {
                    "bone": {"type": "string", "minLength": 1, "maxLength": 64},
                    "cube_index": {"type": "integer", "minimum": 0, "maximum": 255},
                    "face": {"type": "string", "enum": sorted(FACES)},
                },
            },
            "decision": {"type": "string", "enum": sorted(DECISIONS)},
            "semantic_label": {"type": "string", "minLength": 1, "maxLength": 64},
            "rotation": {"type": "integer", "enum": [0, 90, 180, 270], "default": 0},
            "flip_x": {"type": "boolean", "default": False},
            "flip_y": {"type": "boolean", "default": False},
            "sampling": {"type": "string", "enum": ["nearest", "bilinear"], "default": "nearest"},
            "opacity": {"type": "integer", "minimum": 0, "maximum": 255, "default": 255},
            "blend_mode": {"type": "string", "enum": ["over", "replace"], "default": "over"},
            "review_note": {"type": "string", "maxLength": 240},
        },
    }
    return {
        "name": "review_reference_mapping",
        "description": (
            "Human-in-the-loop review gate for Minecraft Bedrock visual-reference mapping. Consumes the structured result "
            "from analyze_visual_reference, verifies its reference PNG path/dimensions/SHA-256, and requires explicit "
            "source-region-to-bone/cube/face decisions and optional semantic labels. Re-checks each selected face against "
            "the current geometry, reports heuristic candidate support without treating it as semantic recognition, and "
            "delegates static coverage/overlap/destination checks to build_uv_mapping_plan. Returns an approved mapping "
            "request only when review and plan gates pass. It never writes files or applies texture changes. Minecraft "
            "runtime/rendering remain NOT RUN."
        ),
        "inputSchema": {
            "type": "object", "additionalProperties": False,
            "required": ["project_directory", "geometry_path", "geometry_identifier", "output_path", "analysis_result", "review_decisions"],
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
                "geometry_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "geometry_identifier": {"type": "string", "minLength": 1, "maxLength": 128},
                "output_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "analysis_result": {"type": "object", "minProperties": 1},
                "review_decisions": {"type": "array", "minItems": 1, "maxItems": MAX_DECISIONS, "items": decision},
                "base_texture_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "background_color": {"type": "string", "pattern": r"^#?[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"},
                "allow_uv_overlap": {"type": "boolean", "default": False},
                "allow_layered_assignments": {"type": "boolean", "default": False},
                "require_full_coverage": {"type": "boolean", "default": False},
            },
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    }


TOOLS = [_tool()]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{label} must be a non-empty relative POSIX path up to 512 characters")
    if "\\" in value or "\x00" in value or value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        raise ValueError(f"{label} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must not contain empty, dot or parent-traversal segments")
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
    geometry_path = _relative_path(raw["geometry_path"], "geometry_path")
    gp = geometry_path.split("/")
    if len(gp) < 5 or gp[:4] != ["resource_packs", f"{project}_RP", "models", "entity"] or not geometry_path.endswith(".json"):
        raise ValueError(f"geometry_path must be inside resource_packs/{project}_RP/models/entity/")
    output_path = _relative_path(raw["output_path"], "output_path")
    op = output_path.split("/")
    if len(op) < 5 or op[:4] != ["resource_packs", f"{project}_RP", "textures", "entity"] or not output_path.endswith(".png"):
        raise ValueError(f"output_path must be a PNG inside resource_packs/{project}_RP/textures/entity/")

    geometry_id = raw["geometry_identifier"]
    if not isinstance(geometry_id, str) or not geometry_id or len(geometry_id) > 128:
        raise ValueError("geometry_identifier must be a non-empty string up to 128 characters")

    analysis = raw["analysis_result"]
    if not isinstance(analysis, dict) or analysis.get("status") != "success":
        raise ValueError("analysis_result must be a successful analyze_visual_reference result")
    reference = analysis.get("reference")
    regions = analysis.get("regions")
    if not isinstance(reference, dict) or not isinstance(regions, list) or not regions:
        raise ValueError("analysis_result must contain reference metadata and non-empty regions")
    if len(regions) > MAX_ANALYSIS_REGIONS:
        raise ValueError(f"analysis_result exceeds the {MAX_ANALYSIS_REGIONS}-region review limit")

    decisions = raw["review_decisions"]
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= MAX_DECISIONS:
        raise ValueError(f"review_decisions must contain 1 to {MAX_DECISIONS} entries")
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(decisions):
        label = f"review_decisions[{index}]"
        allowed = {"source_region_id", "target", "decision", "semantic_label", "rotation", "flip_x", "flip_y", "sampling", "opacity", "blend_mode", "review_note"}
        if not isinstance(entry, dict) or set(entry) - allowed:
            raise ValueError(f"{label} has unsupported fields or is not an object")
        source_id = entry.get("source_region_id")
        if not isinstance(source_id, str) or not source_id or len(source_id) > 32:
            raise ValueError(f"{label}.source_region_id must be a non-empty region ID")
        target = entry.get("target")
        if not isinstance(target, dict) or set(target) != {"bone", "cube_index", "face"}:
            raise ValueError(f"{label}.target must contain bone, cube_index and face")
        bone = target["bone"]
        if not isinstance(bone, str) or not bone or len(bone) > 64:
            raise ValueError(f"{label}.target.bone must be a non-empty bone name")
        cube_index = target["cube_index"]
        if isinstance(cube_index, bool) or not isinstance(cube_index, int) or not 0 <= cube_index <= 255:
            raise ValueError(f"{label}.target.cube_index must be an integer from 0 to 255")
        face = target["face"]
        if not isinstance(face, str) or face not in FACES:
            raise ValueError(f"{label}.target.face must be one of {sorted(FACES)}")
        choice = entry.get("decision")
        if not isinstance(choice, str) or choice not in DECISIONS:
            raise ValueError(f"{label}.decision must be approve, reject or needs_review")
        semantic = entry.get("semantic_label")
        if semantic is not None and (not isinstance(semantic, str) or not semantic.strip() or len(semantic) > 64):
            raise ValueError(f"{label}.semantic_label must contain 1 to 64 non-whitespace characters")
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
        blend = entry.get("blend_mode", "over")
        if not isinstance(blend, str) or blend not in {"over", "replace"}:
            raise ValueError(f"{label}.blend_mode must be over or replace")
        note = entry.get("review_note", "")
        if not isinstance(note, str) or len(note) > 240:
            raise ValueError(f"{label}.review_note must be a string up to 240 characters")
        normalized.append({
            "source_region_id": source_id,
            "target": {"bone": bone, "cube_index": cube_index, "face": face},
            "decision": choice,
            "semantic_label": semantic.strip() if isinstance(semantic, str) else None,
            "rotation": rotation, "flip_x": flip_x, "flip_y": flip_y,
            "sampling": sampling, "opacity": opacity, "blend_mode": blend,
            "review_note": note,
        })

    flags: dict[str, bool] = {}
    for key in ("allow_uv_overlap", "allow_layered_assignments", "require_full_coverage"):
        value = raw.get(key, False)
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a boolean")
        flags[key] = value
    if flags["allow_layered_assignments"] and not flags["allow_uv_overlap"]:
        raise ValueError("allow_layered_assignments requires allow_uv_overlap=true because downstream transfer shares one overlap gate")

    base = raw.get("base_texture_path")
    if base is not None:
        base = _relative_path(base, "base_texture_path")
        bp = base.split("/")
        if len(bp) < 5 or bp[:4] != ["resource_packs", f"{project}_RP", "textures", "entity"] or not base.endswith(".png"):
            raise ValueError(f"base_texture_path must be a PNG inside resource_packs/{project}_RP/textures/entity/")
    reference_path = analysis["reference"].get("path")
    if isinstance(reference_path, str) and output_path == reference_path:
        raise ValueError("output_path must be distinct from the reference image")
    if base is not None and (base == output_path or base == reference_path):
        raise ValueError("base_texture_path must be distinct from output and reference images")
    background = raw.get("background_color")
    if background is not None:
        painter._parse_color(background, "background_color")
        if base is not None:
            raise ValueError("background_color cannot be combined with base_texture_path")
    return {"project_directory": project, "geometry_path": geometry_path, "geometry_identifier": geometry_id,
            "output_path": output_path, "analysis_result": analysis, "review_decisions": normalized,
            "base_texture_path": base, "background_color": background, **flags}


def _load_geometry(project: str, geometry_path: str, geometry_identifier: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], int, str]:
    _, _, rp_root = painter._resolve_project(project)
    relative = "/".join(geometry_path.split("/")[2:])
    file_path = painter._resolve_file(rp_root, relative, "geometry_path")
    try:
        size_before = file_path.stat().st_size
        if size_before > uv.MAX_JSON_BYTES:
            raise ValueError(f"geometry JSON exceeds the {uv.MAX_JSON_BYTES}-byte safety limit")
        raw_geometry = file_path.read_bytes()
        size_after = file_path.stat().st_size
        if len(raw_geometry) != size_before or size_after != size_before:
            raise ValueError("geometry file changed while it was being read")
        document = json.loads(raw_geometry.decode("utf-8"), object_pairs_hook=uv._no_duplicate_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, uv.DuplicateJsonKey) as exc:
        raise ValueError(f"geometry JSON is invalid or changed during read: {exc}") from exc
    geometry_sha256 = hashlib.sha256(raw_geometry).hexdigest()
    geometries = document.get("minecraft:geometry") if isinstance(document, dict) else None
    if not isinstance(geometries, list):
        raise ValueError("geometry JSON must contain a minecraft:geometry array")
    matches = []
    for geometry in geometries:
        if not isinstance(geometry, dict):
            continue
        desc = geometry.get("description")
        if isinstance(desc, dict) and desc.get("identifier") == geometry_identifier:
            matches.append(geometry)
    if len(matches) != 1:
        raise ValueError("geometry_identifier must match exactly one geometry entry")
    selected = matches[0]
    regions, findings, cube_count = uv._extract_regions(selected, geometry_identifier)
    if not regions:
        raise ValueError("selected geometry has no supported cube-face UV regions")
    return selected, regions, findings, cube_count, geometry_sha256


def review_reference_mapping(raw_args: Any) -> dict[str, Any]:
    args = _validate_args(raw_args)
    project = args["project_directory"]
    analysis = args["analysis_result"]
    ref_meta = analysis["reference"]
    ref_path = ref_meta.get("path")
    if not isinstance(ref_path, str):
        return _error("INVALID_ANALYSIS_REFERENCE", "analysis_result.reference.path is missing")
    ref_path = _relative_path(ref_path, "analysis_result.reference.path")
    ref_parts = ref_path.split("/")
    if len(ref_parts) < 5 or ref_parts[:3] != ["resource_packs", f"{project}_RP", "textures"] or not ref_path.endswith(".png"):
        return _error("INVALID_ANALYSIS_REFERENCE", "analysis reference must be a PNG inside the selected project's RP textures folder")

    try:
        _, _, rp_root = painter._resolve_project(project)
        ref_relative = "/".join(ref_parts[2:])
        ref_file = painter._resolve_file(rp_root, ref_relative, "reference_image_path")
        ref_width, ref_height, _pixels, payload = transfer._load_png(ref_file)
    except (ValueError, OSError) as exc:
        return _error("REFERENCE_READ_FAILED", str(exc))

    actual_hash = hashlib.sha256(payload).hexdigest()
    if ref_meta.get("sha256") != actual_hash:
        return _error("REFERENCE_HASH_MISMATCH", "reference PNG no longer matches the analyzer result SHA-256", {
            "expected_sha256": ref_meta.get("sha256"), "actual_sha256": actual_hash,
        })
    if ref_meta.get("width") != ref_width or ref_meta.get("height") != ref_height:
        return _error("REFERENCE_DIMENSION_MISMATCH", "reference PNG dimensions no longer match the analyzer result", {
            "analysis_size": [ref_meta.get("width"), ref_meta.get("height")],
            "actual_size": [ref_width, ref_height],
        })

    region_by_id: dict[str, dict[str, Any]] = {}
    for index, region in enumerate(analysis["regions"]):
        if not isinstance(region, dict):
            return _error("INVALID_ANALYSIS_REGION", f"analysis_result.regions[{index}] must be an object")
        region_id = region.get("region_id")
        rect = region.get("source_rect")
        if not isinstance(region_id, str) or not region_id or region_id in region_by_id:
            return _error("INVALID_ANALYSIS_REGION", "analysis region IDs must be non-empty and unique")
        if not isinstance(rect, dict) or set(rect) != {"x", "y", "width", "height"}:
            return _error("INVALID_ANALYSIS_REGION", f"region {region_id} has an invalid source_rect")
        for key in ("x", "y", "width", "height"):
            value = rect[key]
            lower = 1 if key in {"width", "height"} else 0
            if isinstance(value, bool) or not isinstance(value, int) or value < lower:
                return _error("INVALID_ANALYSIS_REGION", f"region {region_id} source_rect.{key} is invalid")
        if rect["x"] + rect["width"] > ref_width or rect["y"] + rect["height"] > ref_height:
            return _error("INVALID_ANALYSIS_REGION", f"region {region_id} source_rect exceeds the verified reference PNG")
        region_by_id[region_id] = region

    try:
        geometry, uv_regions, geometry_findings, cube_count, geometry_sha256 = _load_geometry(project, args["geometry_path"], args["geometry_identifier"])
    except (ValueError, OSError) as exc:
        return _error("GEOMETRY_READ_FAILED", str(exc))

    uv_lookup: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for region in uv_regions:
        key = (region["bone"], region["cube_index"], region["face"])
        uv_lookup.setdefault(key, []).append(region)

    geometric_candidates = analysis.get("geometric_candidates", [])
    candidate_score_by_pair: dict[tuple[str, tuple[str, int, str]], float] = {}
    if isinstance(geometric_candidates, list):
        for candidate_group in geometric_candidates:
            if not isinstance(candidate_group, dict) or not isinstance(candidate_group.get("target"), dict):
                continue
            target = candidate_group["target"]
            target_key = (target.get("bone"), target.get("cube_index"), target.get("face"))
            for candidate in candidate_group.get("candidates", []) if isinstance(candidate_group.get("candidates"), list) else []:
                if isinstance(candidate, dict) and isinstance(candidate.get("region_id"), str) and isinstance(candidate.get("score"), (int, float)):
                    candidate_score_by_pair[(candidate["region_id"], target_key)] = float(candidate["score"])

    approved_assignments: list[dict[str, Any]] = []
    reviewed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_targets: dict[tuple[str, int, str], int] = {}
    for index, decision in enumerate(args["review_decisions"]):
        source_id = decision["source_region_id"]
        if source_id not in region_by_id:
            errors.append({"index": index, "code": "UNKNOWN_SOURCE_REGION", "source_region_id": source_id})
            continue
        target = decision["target"]
        key = (target["bone"], target["cube_index"], target["face"])
        matches = uv_lookup.get(key, [])
        if len(matches) != 1:
            errors.append({"index": index, "code": "TARGET_FACE_NOT_UNIQUE", "target": target, "match_count": len(matches)})
            continue
        target_region = matches[0]
        source_rect = dict(region_by_id[source_id]["source_rect"])
        candidate_score = candidate_score_by_pair.get((source_id, key))
        record = {
            "decision_index": index,
            "source_region_id": source_id,
            "semantic_label": decision["semantic_label"],
            "target": target,
            "decision": decision["decision"],
            "source_rect": source_rect,
            "uv_bounds": list(target_region["bounds"]),
            "rotation": decision["rotation"],
            "flip_x": decision["flip_x"],
            "flip_y": decision["flip_y"],
            "sampling": decision["sampling"],
            "opacity": decision["opacity"],
            "blend_mode": decision["blend_mode"],
            "geometric_candidate_score": round(candidate_score, 4) if candidate_score is not None else None,
            "candidate_score_note": "shape/area heuristic only; not semantic confidence" if candidate_score is not None else "no candidate rank available for this pair",
            "review_note": decision["review_note"],
        }
        reviewed.append(record)
        if decision["decision"] == "approve":
            seen_targets[key] = seen_targets.get(key, 0) + 1
            approved_assignments.append({
                "selector": {"bone": target["bone"], "cube_index": target["cube_index"], "face": target["face"]},
                "source_rect": source_rect,
                "rotation": decision["rotation"], "flip_x": decision["flip_x"], "flip_y": decision["flip_y"],
                "sampling": decision["sampling"], "opacity": decision["opacity"], "blend_mode": decision["blend_mode"],
            })

    if errors:
        return _error("REVIEW_DECISIONS_INVALID", "some review decisions do not refer to valid source regions or unique geometry faces", {
            "findings": errors[:100], "count": len(errors),
        })

    duplicate_targets = [
        {"target": {"bone": key[0], "cube_index": key[1], "face": key[2]}, "assignment_count": count}
        for key, count in seen_targets.items() if count > 1
    ]
    if duplicate_targets and not args["allow_layered_assignments"]:
        return _error("DUPLICATE_REVIEW_TARGET", "multiple approved source regions target the same face; set allow_layered_assignments=true only for intentional ordered overlays", {
            "targets": duplicate_targets[:100], "count": len(duplicate_targets),
        })

    decision_material = {
        "project_directory": project,
        "geometry_path": args["geometry_path"],
        "geometry_identifier": args["geometry_identifier"],
        "geometry_sha256": geometry_sha256,
        "output_path": args["output_path"],
        "base_texture_path": args["base_texture_path"],
        "background_color": args["background_color"],
        "reference_sha256": actual_hash,
        "reviewed": reviewed,
        "flags": {key: args[key] for key in ("allow_uv_overlap", "allow_layered_assignments", "require_full_coverage")},
    }
    review_digest = hashlib.sha256(json.dumps(decision_material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    approved_count = sum(1 for item in reviewed if item["decision"] == "approve")
    rejected_count = sum(1 for item in reviewed if item["decision"] == "reject")
    pending_count = sum(1 for item in reviewed if item["decision"] == "needs_review")

    mapping_plan = None
    mapping_error = None
    transfer_request = None
    if approved_assignments:
        mapping_args: dict[str, Any] = {
            "project_directory": project,
            "geometry_path": args["geometry_path"],
            "geometry_identifier": args["geometry_identifier"],
            "reference_image_path": ref_path,
            "output_path": args["output_path"],
            "source_assignments": approved_assignments,
            "allow_uv_overlap": args["allow_uv_overlap"],
            "allow_layered_assignments": args["allow_layered_assignments"],
            "require_full_coverage": args["require_full_coverage"],
        }
        if args["base_texture_path"]:
            mapping_args["base_texture_path"] = args["base_texture_path"]
        if args["background_color"]:
            mapping_args["background_color"] = args["background_color"]
        mapping_plan = mapping_assistant.build_uv_mapping_plan(mapping_args)
        if mapping_plan.get("status") == "success":
            transfer_request = mapping_plan.get("transfer_request")
        else:
            mapping_error = mapping_plan.get("error", {"code": "MAPPING_PLAN_FAILED", "message": "downstream UV plan did not succeed"})

    plan_ready = bool(transfer_request)
    review_complete = pending_count == 0
    if pending_count:
        status = "needs_review"
    elif not approved_count:
        status = "review_only"
    elif plan_ready and review_complete:
        status = "approved"
    else:
        status = "needs_review"

    return {
        "status": "success",
        "review_status": status,
        "review_manifest_sha256": review_digest,
        "reference": {"path": ref_path, "size": [ref_width, ref_height], "sha256": actual_hash},
        "geometry": {"path": args["geometry_path"], "identifier": args["geometry_identifier"],
                     "sha256": geometry_sha256, "uv_face_regions": len(uv_regions), "cube_count": cube_count,
                     "geometry_findings": geometry_findings[:100]},
        "summary": {"decision_count": len(reviewed), "approved": approved_count, "rejected": rejected_count,
                    "pending": pending_count, "review_complete": review_complete,
                    "plan_ready": plan_ready, "duplicate_targets": len(duplicate_targets)},
        "decisions": reviewed,
        "mapping_plan": mapping_plan,
        "mapping_plan_error": mapping_error,
        "transfer_request": transfer_request if review_complete else None,
        "scope_note": (
            "Semantic labels and approve/reject decisions are explicitly supplied by the reviewer. Candidate scores, when shown, "
            "come only from aspect-ratio/area heuristics and are not semantic confidence. This gate verifies that the reviewed "
            "reference image is byte-identical to the analyzer input and that target selectors exist uniquely in the current geometry. "
            "It prepares but does not execute map_reference_texture_to_uv; no project files are written. Texture rasterization, "
            "Minecraft import/rendering and runtime remain NOT RUN."
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
            "serverInfo": {"name": "minecraft-bedrock-reference-mapping-review", "version": SERVER_VERSION},
            "instructions": "Use analyze_visual_reference first, visually inspect its regions, then call review_reference_mapping with explicit semantic labels and exact bone/cube/face decisions. Pass its returned transfer_request to map_reference_texture_to_uv only after reviewing the result. This server does not write files.",
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
            payload = review_reference_mapping(params.get("arguments", {}))
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
