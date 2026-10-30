#!/usr/bin/env python3
"""One-call, human-approved reference-to-Bedrock-UV retargeting MCP server.

The tool composes the existing deterministic reference analyzer, explicit UV
mapping planner and PNG transfer engine. It never guesses semantic correspondence:
callers must supply reviewed source rectangles and exact geometry face selectors.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import texture_painting_mcp as painter
import visual_reference_analyzer_mcp as analyzer
import uv_mapping_assistant_mcp as mapping_assistant
import reference_texture_transfer_mcp as transfer

ROOT = Path(__file__).resolve().parents[1]
try:
    SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

MAX_ASSIGNMENTS = 256
MAX_FILE_BYTES = 16 * 1024 * 1024
FACES = {"north", "south", "east", "west", "up", "down"}


def _tool() -> dict[str, Any]:
    assignment = {
        "type": "object",
        "additionalProperties": False,
        "required": ["selector", "source_rect", "semantic_label", "approved"],
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
            "semantic_label": {"type": "string", "minLength": 1, "maxLength": 64},
            "approved": {"type": "boolean", "const": True},
            "rotation": {"type": "integer", "enum": [0, 90, 180, 270], "default": 0},
            "flip_x": {"type": "boolean", "default": False},
            "flip_y": {"type": "boolean", "default": False},
            "sampling": {"type": "string", "enum": ["nearest", "bilinear"], "default": "nearest"},
            "opacity": {"type": "integer", "minimum": 0, "maximum": 255, "default": 255},
            "blend_mode": {"type": "string", "enum": ["over", "replace"], "default": "over"},
        },
    }
    return {
        "name": "retarget_texture_to_entity",
        "description": (
            "One-call, guarded reference-to-texture pipeline for a Minecraft Bedrock entity. Runs bounded reference-image "
            "analysis, validates caller-reviewed semantic crops and exact bone/cube/face selectors, builds a geometry-aware "
            "UV transfer plan, executes the existing PNG transfer engine, and verifies output PNG dimensions and SHA-256. "
            "Every assignment must carry an explicit semantic_label and approved=true, and the caller must set "
            "review_confirmed=true. No automatic body-part recognition or 3D projection is claimed. Refuses traversal, "
            "out-of-bounds UVs/crops, unapproved assignments, incomplete coverage when requested, unsafe inputs and output "
            "collisions. Creates one new PNG and never overwrites existing textures. Minecraft runtime/rendering remain NOT RUN."
        ),
        "inputSchema": {
            "type": "object", "additionalProperties": False,
            "required": ["project_directory", "geometry_path", "geometry_identifier", "reference_image_path", "output_path", "source_assignments", "review_confirmed"],
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
                "geometry_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "geometry_identifier": {"type": "string", "minLength": 1, "maxLength": 128},
                "reference_image_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "output_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "base_texture_path": {"type": "string", "minLength": 1, "maxLength": 512},
                "background_color": {"type": "string", "minLength": 6, "maxLength": 9},
                "source_assignments": {"type": "array", "minItems": 1, "maxItems": MAX_ASSIGNMENTS, "items": assignment},
                "review_confirmed": {"type": "boolean", "const": True},
                "allow_uv_overlap": {"type": "boolean", "default": False},
                "allow_layered_assignments": {"type": "boolean", "default": False},
                "require_full_coverage": {"type": "boolean", "default": False},
            },
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    }


TOOLS = [_tool()]
TOOL_BY_NAME = {item["name"]: item for item in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def _validate_args(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("arguments must be a JSON object")
    schema = TOOLS[0]["inputSchema"]
    props = schema["properties"]
    extra, missing = set(raw) - set(props), set(schema["required"]) - set(raw)
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    if raw.get("review_confirmed") is not True:
        raise ValueError("review_confirmed must be true; texture mapping requires explicit human approval")
    project = raw.get("project_directory")
    if not isinstance(project, str) or not painter.PROJECT_RE.fullmatch(project) or "--" in project:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    if not isinstance(raw.get("geometry_identifier"), str) or not raw["geometry_identifier"] or len(raw["geometry_identifier"]) > 128:
        raise ValueError("geometry_identifier must be a non-empty string up to 128 characters")
    for key in ("geometry_path", "reference_image_path", "output_path"):
        value = raw.get(key)
        if not isinstance(value, str) or not value or len(value) > 512:
            raise ValueError(f"{key} must be a non-empty relative POSIX path")
        if "\\" in value or "\x00" in value or value.startswith("/") or (len(value) > 1 and value[1] == ":"):
            raise ValueError(f"{key} must be a safe relative POSIX path")
        if any(part in {"", ".", ".."} for part in value.split("/")):
            raise ValueError(f"{key} must not contain empty, dot or parent-traversal segments")
    gp = raw["geometry_path"].split("/")
    rp = raw["reference_image_path"].split("/")
    op = raw["output_path"].split("/")
    if len(gp) < 5 or gp[:4] != ["resource_packs", f"{project}_RP", "models", "entity"] or not raw["geometry_path"].endswith(".json"):
        raise ValueError(f"geometry_path must be a .json file inside resource_packs/{project}_RP/models/entity/")
    if len(rp) < 5 or rp[:3] != ["resource_packs", f"{project}_RP", "textures"] or not raw["reference_image_path"].endswith(".png"):
        raise ValueError(f"reference_image_path must be a PNG inside resource_packs/{project}_RP/textures/")
    if len(op) < 5 or op[:4] != ["resource_packs", f"{project}_RP", "textures", "entity"] or not raw["output_path"].endswith(".png"):
        raise ValueError(f"output_path must be a PNG inside resource_packs/{project}_RP/textures/entity/")
    source_assignments = raw.get("source_assignments")
    if not isinstance(source_assignments, list) or not 1 <= len(source_assignments) <= MAX_ASSIGNMENTS:
        raise ValueError(f"source_assignments must be an array with 1 to {MAX_ASSIGNMENTS} entries")
    for index, item in enumerate(source_assignments):
        if not isinstance(item, dict):
            raise ValueError(f"source_assignments[{index}] must be an object")
        if item.get("approved") is not True:
            raise ValueError(f"source_assignments[{index}] is not explicitly approved")
        if not isinstance(item.get("semantic_label"), str) or not item["semantic_label"].strip() or len(item["semantic_label"]) > 64:
            raise ValueError(f"source_assignments[{index}].semantic_label must be a non-empty reviewed label")
    return raw


def _project_file(project: str, rel_path: str, label: str) -> Path:
    _, _, rp_root = painter._resolve_project(project)
    relative = "/".join(rel_path.split("/")[2:])
    return painter._resolve_file(rp_root, relative, label)


def _stable_file_hash(path: Path, label: str) -> tuple[str, int]:
    before = path.stat()
    if not path.is_file() or before.st_size < 1 or before.st_size > MAX_FILE_BYTES:
        raise ValueError(f"{label} must be a regular file no larger than {MAX_FILE_BYTES} bytes")
    payload = path.read_bytes()
    after = path.stat()
    if before.st_size != len(payload) or after.st_size != len(payload) or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError(f"{label} changed while it was being read")
    return hashlib.sha256(payload).hexdigest(), len(payload)


def retarget_texture_to_entity(raw_args: Any) -> dict[str, Any]:
    args = _validate_args(raw_args)
    project = args["project_directory"]
    try:
        geometry_file = _project_file(project, args["geometry_path"], "geometry_path")
        reference_file = _project_file(project, args["reference_image_path"], "reference_image_path")
        geometry_hash_before, geometry_bytes = _stable_file_hash(geometry_file, "geometry")
        reference_hash_before, reference_bytes = _stable_file_hash(reference_file, "reference image")
    except (ValueError, OSError) as exc:
        return _error("INPUT_READ_FAILED", str(exc))

    analysis_args = {
        "project_directory": project,
        "reference_image_path": args["reference_image_path"],
        "geometry_path": args["geometry_path"],
        "geometry_identifier": args["geometry_identifier"],
    }
    try:
        analysis = analyzer.analyze_visual_reference(analysis_args)
    except Exception as exc:
        return _error("REFERENCE_ANALYSIS_FAILED", f"analyzer raised {type(exc).__name__}: {exc}")
    if not isinstance(analysis, dict) or analysis.get("status") != "success":
        return _error("REFERENCE_ANALYSIS_FAILED", "reference analyzer did not return a successful result", analysis)
    analyzed_reference = analysis.get("reference")
    if not isinstance(analyzed_reference, dict) or analyzed_reference.get("sha256") != reference_hash_before:
        return _error("REFERENCE_CHANGED", "reference image hash differs from the bytes analyzed")

    assignments = []
    for item in args["source_assignments"]:
        assignment = {key: value for key, value in item.items() if key not in {"semantic_label", "approved"}}
        assignments.append(assignment)
    plan_args: dict[str, Any] = {
        "project_directory": project,
        "geometry_path": args["geometry_path"],
        "geometry_identifier": args["geometry_identifier"],
        "reference_image_path": args["reference_image_path"],
        "output_path": args["output_path"],
        "source_assignments": assignments,
        "allow_uv_overlap": args.get("allow_uv_overlap", False),
        "allow_layered_assignments": args.get("allow_layered_assignments", False),
        "require_full_coverage": args.get("require_full_coverage", False),
    }
    if args.get("base_texture_path"):
        plan_args["base_texture_path"] = args["base_texture_path"]
    if args.get("background_color"):
        plan_args["background_color"] = args["background_color"]
    try:
        plan = mapping_assistant.build_uv_mapping_plan(plan_args)
    except Exception as exc:
        return _error("UV_PLAN_FAILED", f"UV planner raised {type(exc).__name__}: {exc}")
    if not isinstance(plan, dict) or plan.get("status") != "success":
        return _error("UV_PLAN_FAILED", "UV planner rejected the reviewed mapping", plan)
    if not plan.get("can_execute_transfer") or not isinstance(plan.get("transfer_request"), dict):
        return _error("UV_PLAN_NOT_READY", "mapping plan has unresolved coverage/overlap requirements and is not executable", {
            "plan_status": plan.get("plan_status"), "coverage": plan.get("coverage"), "overlap": plan.get("overlap"),
            "warnings": plan.get("warnings", []),
        })
    if plan.get("reference", {}).get("sha256") != reference_hash_before:
        return _error("REFERENCE_CHANGED", "reference image changed after analysis or UV planning")

    try:
        geometry_hash_now, _ = _stable_file_hash(geometry_file, "geometry")
        reference_hash_now, _ = _stable_file_hash(reference_file, "reference image")
    except (ValueError, OSError) as exc:
        return _error("INPUT_RECHECK_FAILED", str(exc))
    if geometry_hash_now != geometry_hash_before or reference_hash_now != reference_hash_before:
        return _error("INPUT_CHANGED", "geometry or reference image changed during planning; transfer was not started")

    transfer_request = plan["transfer_request"]
    try:
        transfer_result = transfer.map_reference_texture_to_uv(transfer_request)
    except Exception as exc:
        return _error("TRANSFER_FAILED", f"transfer engine raised {type(exc).__name__}: {exc}")
    if not isinstance(transfer_result, dict) or transfer_result.get("status") != "success":
        return _error("TRANSFER_FAILED", "texture transfer did not complete successfully", transfer_result)

    try:
        geometry_hash_after, _ = _stable_file_hash(geometry_file, "geometry")
        reference_hash_after, _ = _stable_file_hash(reference_file, "reference image")
        output_file = _project_file(project, args["output_path"], "output_path")
        output_width, output_height, _pixels, output_png = transfer._load_png(output_file)
        output_hash = hashlib.sha256(output_png).hexdigest()
        expected_size = plan["geometry"]["texture_size"]
        expected_output_hash = transfer_result.get("texture", {}).get("sha256")
        if [output_width, output_height] != expected_size:
            raise ValueError(f"output PNG size {[output_width, output_height]} does not match geometry texture size {expected_size}")
        if expected_output_hash != output_hash:
            raise ValueError("output PNG SHA-256 does not match the transfer engine result")
        if geometry_hash_after != geometry_hash_before or reference_hash_after != reference_hash_before:
            raise ValueError("geometry or reference input changed while transfer was executing")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Delete only a file that this invocation created and whose bytes match
        # the successful transfer report; never remove an unrelated replacement.
        try:
            output_file = _project_file(project, args["output_path"], "output_path")
            if output_file.is_file():
                actual = hashlib.sha256(output_file.read_bytes()).hexdigest()
                if actual == transfer_result.get("texture", {}).get("sha256"):
                    output_file.unlink()
        except (ValueError, OSError):
            pass
        return _error("POST_TRANSFER_VERIFICATION_FAILED", str(exc), {"created_output": args["output_path"]})

    return {
        "status": "success",
        "pipeline": "reference-analysis -> reviewed UV plan -> PNG transfer -> integrity verification",
        "approval": {"review_confirmed": True, "assignment_count": len(assignments),
                     "semantic_labels": [item["semantic_label"] for item in args["source_assignments"]]},
        "analysis": {"reference_sha256": reference_hash_before,
                     "region_count": len(analysis.get("regions", [])),
                     "segmentation_mode": analysis.get("segmentation", {}).get("mode") if isinstance(analysis.get("segmentation"), dict) else None,
                     "geometric_candidate_count": len(analysis.get("geometric_candidates", [])) if isinstance(analysis.get("geometric_candidates"), list) else 0,
                     "note": "Analyzer regions and candidate scores are descriptive heuristics only; approved source rectangles and face selectors came from the caller."},
        "mapping_plan": {"status": plan.get("plan_status"), "coverage": plan.get("coverage"),
                         "overlap": plan.get("overlap"), "warnings": plan.get("warnings", [])},
        "inputs": {"geometry_path": args["geometry_path"], "geometry_sha256": geometry_hash_before,
                   "geometry_bytes": geometry_bytes, "reference_path": args["reference_image_path"],
                   "reference_sha256": reference_hash_before, "reference_bytes": reference_bytes},
        "texture": transfer_result.get("texture"),
        "transfer": transfer_result.get("transfer"),
        "verification": {"output_png_validated": True, "output_dimensions_match_geometry": True,
                         "output_sha256_verified": True, "input_hashes_unchanged": True},
        "runtime_status": "NOT RUN",
        "scope_note": "This tool composes existing deterministic algorithms into one write operation. It does not perform AI semantic recognition, automatic portrait-to-3D projection, face-orientation rendering, mip/seam simulation, Blockbench preview or Minecraft runtime validation. The semantic labels and exact source-to-face assignments were supplied and approved by the caller.",
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
            "serverInfo": {"name": "minecraft-bedrock-uv-texture-retarget", "version": SERVER_VERSION},
            "instructions": "Supply explicit reviewed source rectangles and exact bone/cube/face selectors. Set approved=true for every assignment and review_confirmed=true only after visually reviewing the mapping. The tool runs analysis, UV planning, transfer and output integrity verification in one request. No automatic semantic recognition is performed.",
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
            payload = retarget_texture_to_entity(arguments)
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
