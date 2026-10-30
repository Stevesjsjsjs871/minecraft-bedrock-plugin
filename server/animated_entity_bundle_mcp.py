#!/usr/bin/env python3
"""Transactional high-level authoring for a Bedrock entity + animation system.

This orchestration layer composes the project's existing entity, animation-clip,
animation-controller and pipeline-audit MCP tools. It creates new resources only;
it never overwrites an existing entity or resource. If any authoring/validation
step fails, files successfully created by this bundle are removed when their
contents still match the last state written by this operation.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = Path(__file__).resolve().parent
SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
_PROJECT = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_SLUG = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_ALIAS = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_MAX_ANIMATIONS = 16
_MAX_TOTAL_INPUT_BYTES = 2 * 1024 * 1024


def _tool_schema() -> dict[str, Any]:
    vector = {
        "type": "array", "minItems": 3, "maxItems": 3,
        "items": {"type": "number"},
    }
    cube = {
        "type": "object", "additionalProperties": False,
        "required": ["origin", "size", "uv"],
        "properties": {
            "origin": vector, "size": vector,
            "uv": {"type": "array", "minItems": 2, "maxItems": 2,
                  "items": {"type": "integer", "minimum": 0}},
            "pivot": vector, "rotation": vector,
            "mirror": {"type": "boolean"},
            "inflate": {"type": "number", "minimum": -16, "maximum": 16},
        },
    }
    bone = {
        "type": "object", "additionalProperties": False,
        "required": ["name", "pivot"],
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 64},
            "parent": {"type": "string", "minLength": 1, "maxLength": 64},
            "pivot": vector,
            "cubes": {"type": "array", "maxItems": 64, "items": cube},
            "locators": {"type": "object", "maxProperties": 32, "additionalProperties": vector},
        },
    }
    geometry = {
        "type": "object", "additionalProperties": False,
        "required": ["bones"],
        "properties": {
            "texture_width": {"type": "integer", "minimum": 1, "maximum": 4096},
            "texture_height": {"type": "integer", "minimum": 1, "maximum": 4096},
            "visible_bounds_width": {"type": "number", "exclusiveMinimum": 0, "maximum": 64},
            "visible_bounds_height": {"type": "number", "exclusiveMinimum": 0, "maximum": 64},
            "visible_bounds_offset": vector,
            "bones": {"type": "array", "minItems": 1, "maxItems": 64, "items": bone},
        },
    }
    keyframe = {
        "type": "object", "additionalProperties": False, "required": ["time"],
        "properties": {"time": {"type": "number", "minimum": 0, "maximum": 600},
                       "value": {}, "pre": {}, "post": {}},
        "oneOf": [
            {"required": ["value"], "not": {"anyOf": [{"required": ["pre"]}, {"required": ["post"]}]}},
            {"required": ["pre", "post"], "not": {"required": ["value"]}},
        ],
    }
    anim_bone = {
        "type": "object", "additionalProperties": False, "required": ["name"],
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 64},
            "rotation": {"type": "array", "minItems": 1, "maxItems": 128, "items": keyframe},
            "position": {"type": "array", "minItems": 1, "maxItems": 128, "items": keyframe},
            "scale": {"type": "array", "minItems": 1, "maxItems": 128, "items": keyframe},
        },
    }
    clip = {
        "type": "object", "additionalProperties": False,
        "required": ["animation_slug", "animation_length", "bones"],
        "properties": {
            "animation_slug": {"type": "string", "minLength": 2, "maxLength": 48},
            "animation_alias": {"type": "string", "minLength": 1, "maxLength": 64},
            "animation_identifier": {"type": "string", "minLength": 12, "maxLength": 160},
            "animation_length": {"type": "number", "exclusiveMinimum": 0, "maximum": 600},
            "bones": {"type": "array", "minItems": 1, "maxItems": 64, "items": anim_bone},
            "loop": {"type": "boolean"},
            "override_previous_animation": {"type": "boolean"},
            "anim_time_update": {"type": "string", "minLength": 1, "maxLength": 512},
            "blend_weight": {"type": "string", "minLength": 1, "maxLength": 512},
        },
    }
    state = {
        "type": "object", "additionalProperties": False, "required": ["name"],
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 32},
            "animations": {"type": "array", "maxItems": 16,
                          "items": {"type": "string", "minLength": 1, "maxLength": 64}},
            "transitions": {"type": "object", "maxProperties": 16,
                            "additionalProperties": {"type": "string", "minLength": 1, "maxLength": 512}},
            "on_entry": {"type": "array", "maxItems": 16,
                         "items": {"type": "string", "minLength": 1, "maxLength": 512}},
            "on_exit": {"type": "array", "maxItems": 16,
                        "items": {"type": "string", "minLength": 1, "maxLength": 512}},
            "blend_transition": {"type": "number", "minimum": 0, "maximum": 10},
        },
    }
    controller = {
        "type": "object", "additionalProperties": False,
        "required": ["controller_slug", "initial_state", "states"],
        "properties": {
            "controller_slug": {"type": "string", "minLength": 2, "maxLength": 48},
            "animation_alias": {"type": "string", "minLength": 1, "maxLength": 64},
            "controller_identifier": {"type": "string", "minLength": 20, "maxLength": 160},
            "initial_state": {"type": "string", "minLength": 1, "maxLength": 32},
            "states": {"type": "array", "minItems": 1, "maxItems": 32, "items": state},
            "animate_condition": {"type": "string", "minLength": 1, "maxLength": 512},
        },
    }
    return {
        "name": "create_animated_entity_bundle",
        "description": (
            "Create a new linked BP/RP entity, geometry, multiple animation clips and one animation controller "
            "as a single validated operation. The controller owns animation playback. All files must be new; "
            "existing resources are never overwritten. The tool rolls back files it created if any authoring "
            "or static validation step fails. Textures/spawn rules/custom gameplay scripts are not generated; "
            "Molang and Minecraft runtime behavior remain unexecuted/NOT RUN."
        ),
        "inputSchema": {
            "type": "object", "additionalProperties": False,
            "required": ["project_directory", "entity_name", "entity_slug", "target_game_version", "geometry", "animations", "controller"],
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
                "entity_name": {"type": "string", "minLength": 2, "maxLength": 80},
                "entity_slug": {"type": "string", "minLength": 2, "maxLength": 48},
                "target_game_version": {"type": "string", "minLength": 5, "maxLength": 20},
                "geometry": geometry,
                "health": {"type": "integer", "minimum": 1, "maximum": 1024},
                "movement_speed": {"type": "number", "minimum": 0, "maximum": 1.5},
                "collision_width": {"type": "number", "exclusiveMinimum": 0, "maximum": 8},
                "collision_height": {"type": "number", "exclusiveMinimum": 0, "maximum": 16},
                "animations": {"type": "array", "minItems": 1, "maxItems": _MAX_ANIMATIONS, "items": clip},
                "controller": controller,
            },
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False,
                        "idempotentHint": False, "openWorldHint": False},
    }


TOOLS = [_tool_schema()]
WORKFLOW_INSTRUCTIONS = (
    "Use create_animated_entity_bundle for a fresh entity that needs a complete first-pass animation system. "
    "The tool creates the entity/geometry, adds animation clips and binds one controller, then validates the "
    "clip/controller/resource graph. It refuses existing outputs and rolls back its own successful writes if "
    "a later step fails. Supply geometry bone names that exactly match animation bone names. Textures are "
    "not generated; Molang and Minecraft runtime behavior are not executed."
)


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if extra:
        result.update(extra)
    return result


def _modules() -> tuple[Any, Any, Any, Any]:
    # When invoked as a stdio script, Python includes server/ in sys.path. Keep
    # an explicit entry for hosts that import this module from another working dir.
    server_dir = str(SERVER_DIR)
    if server_dir not in sys.path:
        sys.path.insert(0, server_dir)
    return (
        importlib.import_module("entity_authoring_mcp"),
        importlib.import_module("animation_clip_mcp"),
        importlib.import_module("animation_controller_mcp"),
        importlib.import_module("animation_pipeline_audit_mcp"),
    )


def _validate_shape(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("arguments must be a JSON object")
    props = TOOLS[0]["inputSchema"]["properties"]
    extra = set(raw) - set(props)
    missing = set(TOOLS[0]["inputSchema"]["required"]) - set(raw)
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    for key in ("project_directory", "entity_name", "entity_slug", "target_game_version"):
        value = raw.get(key)
        schema = props[key]
        if not isinstance(value, str) or not schema["minLength"] <= len(value) <= schema["maxLength"]:
            raise ValueError(f"{key} must be a string of valid length")
    if not _PROJECT.fullmatch(raw["project_directory"]) or "--" in raw["project_directory"]:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    if not _SLUG.fullmatch(raw["entity_slug"]) or len(raw["entity_slug"]) > 48:
        raise ValueError("entity_slug must be lowercase snake_case and start with a letter")
    if raw["entity_name"] != raw["entity_name"].strip():
        raise ValueError("entity_name must not contain surrounding whitespace")
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", raw["target_game_version"]):
        raise ValueError("target_game_version must be a three-part numeric version, for example 1.26.50")
    if not isinstance(raw["geometry"], dict):
        raise ValueError("geometry must be an object")
    if not isinstance(raw["animations"], list) or not 1 <= len(raw["animations"]) <= _MAX_ANIMATIONS:
        raise ValueError(f"animations must contain 1 to {_MAX_ANIMATIONS} animation clips")
    if not isinstance(raw["controller"], dict):
        raise ValueError("controller must be an object")
    for key, kind in (("health", int), ("movement_speed", (int, float)),
                      ("collision_width", (int, float)), ("collision_height", (int, float))):
        if key in raw:
            value = raw[key]
            if isinstance(value, bool) or not isinstance(value, kind):
                raise ValueError(f"{key} has an invalid numeric type")
    # Bound the untrusted nested structure before passing it to lower-level tools.
    encoded = json.dumps(raw, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > _MAX_TOTAL_INPUT_BYTES:
        raise ValueError(f"request exceeds {_MAX_TOTAL_INPUT_BYTES} byte limit")
    return dict(raw)


def _safe_project_path(project_directory: str) -> Path:
    workspace_raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    workspace = Path(workspace_raw).expanduser() if workspace_raw else Path.cwd()
    workspace = workspace.resolve(strict=True)
    project = workspace / project_directory
    if project.is_symlink() or not project.is_dir():
        raise ValueError("project_directory must identify an existing non-symlink project scaffold")
    resolved = project.resolve(strict=True)
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("project_directory escapes the configured workspace") from exc
    if resolved.parent != workspace:
        raise ValueError("project_directory must be a direct child of the configured workspace")
    return resolved


def _safe_relative_file(project: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts) or "\\" in relative or "\x00" in relative:
        raise ValueError(f"unsafe generated path: {relative!r}")
    path = project.joinpath(*pure.parts)
    current = project
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"generated path contains a symlink: {relative}")
    try:
        path.resolve(strict=False).relative_to(project)
    except (OSError, ValueError) as exc:
        raise ValueError(f"generated path escapes project: {relative}") from exc
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_created(project: Path, paths: Any, tracked: dict[str, str]) -> None:
    if not isinstance(paths, list):
        raise ValueError("authoring tool returned malformed files_created metadata")
    for relative in paths:
        if not isinstance(relative, str):
            raise ValueError("authoring tool returned a non-string generated path")
        path = _safe_relative_file(project, relative)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"authoring tool did not create a regular file: {relative}")
        tracked[relative] = _sha256(path)


def _refresh_tracked_hashes(project: Path, tracked: dict[str, str]) -> None:
    for relative in list(tracked):
        path = _safe_relative_file(project, relative)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"a generated file disappeared or became unsafe during authoring: {relative}")
        tracked[relative] = _sha256(path)


def _rollback(project: Path, tracked: dict[str, str]) -> list[str]:
    removed: list[str] = []
    conflicts: list[str] = []
    for relative, expected_hash in reversed(list(tracked.items())):
        try:
            path = _safe_relative_file(project, relative)
            if path.is_symlink() or not path.is_file():
                conflicts.append(relative)
                continue
            if _sha256(path) != expected_hash:
                conflicts.append(relative)
                continue
            path.unlink()
            removed.append(relative)
        except (OSError, ValueError):
            conflicts.append(relative)
    return removed + ([f"CONCURRENT_CHANGE_NOT_REMOVED:{x}" for x in conflicts])


def _build_subcalls(raw: dict[str, Any], entity_module: Any, clip_module: Any, controller_module: Any) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], str, str, str, list[str]]:
    project_directory = raw["project_directory"]
    entity_slug = raw["entity_slug"]
    target_version = raw["target_game_version"]
    client_entity_file = f"entity/{entity_slug}.entity.json"
    geometry_file = f"models/entity/{entity_slug}.geo.json"

    entity_args = {
        "project_directory": project_directory,
        "entity_name": raw["entity_name"],
        "entity_slug": entity_slug,
        "target_game_version": target_version,
        "geometry": raw["geometry"],
    }
    for key in ("health", "movement_speed", "collision_width", "collision_height"):
        if key in raw:
            entity_args[key] = raw[key]
    entity_module._validate_arguments(entity_args)

    geometry_bones = {item["name"] for item in raw["geometry"].get("bones", []) if isinstance(item, dict) and isinstance(item.get("name"), str)}
    seen_slugs: set[str] = set()
    seen_aliases: set[str] = set()
    clip_calls: list[dict[str, Any]] = []
    for index, clip in enumerate(raw["animations"]):
        if not isinstance(clip, dict):
            raise ValueError(f"animations[{index}] must be an object")
        slug = clip.get("animation_slug")
        if not isinstance(slug, str) or not _SLUG.fullmatch(slug) or len(slug) > 48:
            raise ValueError(f"animations[{index}].animation_slug must be lowercase snake_case")
        alias = clip.get("animation_alias", slug)
        if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
            raise ValueError(f"animations[{index}].animation_alias is invalid")
        if slug in seen_slugs:
            raise ValueError(f"duplicate animation_slug: {slug}")
        if alias in seen_aliases:
            raise ValueError(f"duplicate animation_alias: {alias}")
        seen_slugs.add(slug)
        seen_aliases.add(alias)
        animation_bones = clip.get("bones")
        if not isinstance(animation_bones, list):
            raise ValueError(f"animations[{index}].bones must be an array")
        referenced_bones = {entry.get("name") for entry in animation_bones if isinstance(entry, dict)}
        unknown_bones = sorted(name for name in referenced_bones if name not in geometry_bones)
        if unknown_bones:
            raise ValueError(f"animations[{index}] references bone(s) absent from the supplied geometry: {', '.join(unknown_bones)}")
        clip_args = {
            "project_directory": project_directory,
            "target_game_version": target_version,
            "animation_slug": slug,
            "client_entity_file": client_entity_file,
            "animation_length": clip.get("animation_length"),
            "bones": animation_bones,
            "geometry_alias": "default",
            "geometry_file": geometry_file,
        }
        if "animation_alias" in clip:
            clip_args["animation_alias"] = alias
        for key in ("animation_identifier", "loop", "override_previous_animation", "anim_time_update", "blend_weight"):
            if key in clip:
                clip_args[key] = clip[key]
        clip_module._validate_arguments("create_animation_clip", clip_args)
        clip_calls.append(clip_args)

    controller_input = raw["controller"]
    if not isinstance(controller_input, dict):
        raise ValueError("controller must be an object")
    controller_slug = controller_input.get("controller_slug")
    if not isinstance(controller_slug, str) or not _SLUG.fullmatch(controller_slug) or len(controller_slug) > 48:
        raise ValueError("controller.controller_slug must be lowercase snake_case")
    controller_alias = controller_input.get("animation_alias", controller_slug)
    if not isinstance(controller_alias, str) or not _ALIAS.fullmatch(controller_alias):
        raise ValueError("controller.animation_alias is invalid")
    if controller_alias in seen_aliases:
        raise ValueError("controller alias conflicts with a generated animation alias")
    controller_args = {
        "project_directory": project_directory,
        "target_game_version": target_version,
        "controller_slug": controller_slug,
        "client_entity_file": client_entity_file,
        "initial_state": controller_input.get("initial_state"),
        "states": controller_input.get("states"),
        "animation_alias": controller_alias,
    }
    for key in ("controller_identifier", "animate_condition"):
        if key in controller_input:
            controller_args[key] = controller_input[key]
    controller_module._validate_arguments("create_animation_controller", controller_args)
    # Validate all controller-state alias/transition references before writing the entity.
    controller_module._validate_states(controller_args["states"], controller_args["initial_state"], seen_aliases)

    used_aliases = {
        alias
        for state in controller_args["states"]
        if isinstance(state, dict)
        for alias in state.get("animations", [])
        if isinstance(alias, str)
    }
    unused_aliases = sorted(seen_aliases - used_aliases)
    controller_file = f"animation_controllers/{controller_slug}.animation_controllers.json"
    return entity_args, clip_calls, controller_args, client_entity_file, geometry_file, controller_file, unused_aliases


def _preflight_outputs(project: Path, raw: dict[str, Any], client_entity_file: str, geometry_file: str, controller_file: str) -> None:
    entity_slug = raw["entity_slug"]
    expected = [
        f"behavior_packs/{raw['project_directory']}_BP/entities/{entity_slug}.json",
        f"resource_packs/{raw['project_directory']}_RP/{client_entity_file}",
        f"resource_packs/{raw['project_directory']}_RP/{geometry_file}",
        f"resource_packs/{raw['project_directory']}_RP/render_controllers/{entity_slug}.render_controllers.json",
        f"resource_packs/{raw['project_directory']}_RP/{controller_file}",
    ]
    expected.extend(f"resource_packs/{raw['project_directory']}_RP/animations/{clip['animation_slug']}.animation.json" for clip in raw["animations"])
    for relative in expected:
        path = _safe_relative_file(project, relative)
        if path.exists() or path.is_symlink():
            raise ValueError(f"output already exists; bundle refuses to overwrite: {relative}")


def _execute_bundle(raw: dict[str, Any]) -> dict[str, Any]:
    entity_module, clip_module, controller_module, audit_module = _modules()
    project = _safe_project_path(raw["project_directory"])
    entity_args, clip_calls, controller_args, client_entity_file, geometry_file, controller_file, unused_aliases = _build_subcalls(raw, entity_module, clip_module, controller_module)
    _preflight_outputs(project, raw, client_entity_file, geometry_file, controller_file)

    tracked: dict[str, str] = {}
    completed: list[dict[str, Any]] = []
    try:
        entity_result = entity_module.call_tool("create_addon_entity", entity_args)
        if entity_result.get("status") != "created":
            raise RuntimeError(f"create_addon_entity failed: {entity_result.get('error', entity_result)}")
        _record_created(project, entity_result.get("files_created"), tracked)
        completed.append(entity_result)

        clip_results: list[dict[str, Any]] = []
        for clip_args in clip_calls:
            clip_result = clip_module.call_tool("create_animation_clip", clip_args)
            if clip_result.get("status") != "created":
                raise RuntimeError(f"create_animation_clip failed for {clip_args['animation_slug']}: {clip_result.get('error', clip_result)}")
            _record_created(project, clip_result.get("files_created"), tracked)
            _refresh_tracked_hashes(project, tracked)
            completed.append(clip_result)
            clip_results.append(clip_result)

        controller_result = controller_module.call_tool("create_animation_controller", controller_args)
        if controller_result.get("status") != "created":
            raise RuntimeError(f"create_animation_controller failed: {controller_result.get('error', controller_result)}")
        _record_created(project, controller_result.get("files_created"), tracked)
        _refresh_tracked_hashes(project, tracked)
        completed.append(controller_result)

        clip_validations: list[dict[str, Any]] = []
        for clip_args in clip_calls:
            validation = clip_module.call_tool("validate_animation_clip", {
                "project_directory": raw["project_directory"],
                "animation_file": f"animations/{clip_args['animation_slug']}.animation.json",
                "client_entity_file": client_entity_file,
                "animation_alias": clip_args.get("animation_alias", clip_args["animation_slug"]),
                "geometry_alias": "default",
                "geometry_file": geometry_file,
            })
            if validation.get("status") != "valid":
                raise RuntimeError(f"validate_animation_clip failed: {validation.get('error', validation)}")
            clip_validations.append(validation)

        controller_validation = controller_module.call_tool("validate_animation_controller", {
            "project_directory": raw["project_directory"],
            "controller_file": controller_file,
            "client_entity_file": client_entity_file,
            "animation_alias": controller_args["animation_alias"],
        })
        if controller_validation.get("status") != "valid":
            raise RuntimeError(f"validate_animation_controller failed: {controller_validation.get('error', controller_validation)}")

        graph_audit = audit_module.call_tool("audit_entity_animation_pipeline", {
            "project_directory": raw["project_directory"],
            "client_entity_file": client_entity_file,
        })
        if graph_audit.get("status") != "valid" or graph_audit.get("analysis_complete") is not True:
            raise RuntimeError(f"audit_entity_animation_pipeline did not return a complete valid graph: {graph_audit.get('status')}")

        return {
            "status": "created",
            "project_directory": str(project),
            "target_game_version": raw["target_game_version"],
            "entity_identifier": entity_result.get("entity_identifier"),
            "geometry_identifier": entity_result.get("geometry_identifier"),
            "controller_identifier": controller_result.get("controller_identifier"),
            "controller_alias": controller_result.get("animation_alias"),
            "animation_count": len(clip_results),
            "animation_aliases": [item.get("animation_alias") for item in clip_results],
            "unused_animation_aliases": unused_aliases,
            "geometry_summary": entity_result.get("geometry_summary"),
            "files_created": list(tracked),
            "files_updated": [f"resource_packs/{raw['project_directory']}_RP/{client_entity_file}"],
            "validation": {
                "animation_clips": clip_validations,
                "animation_controller": controller_validation,
                "animation_pipeline": {
                    "status": graph_audit.get("status"),
                    "analysis_complete": graph_audit.get("analysis_complete"),
                    "inventory": graph_audit.get("inventory"),
                    "severity_counts": graph_audit.get("severity_counts"),
                    "findings": graph_audit.get("findings", []),
                },
            },
            "texture_file_expected": entity_result.get("texture_file_expected"),
            "texture_status": "NOT CREATED — add a correctly UV-mapped PNG before visual rendering can be validated",
            "molang_status": "TEXT SHAPE ONLY — EXPRESSIONS NOT PARSED OR EXECUTED",
            "runtime_status": "NOT RUN",
            "note": "The entity, geometry, clips and controller were generated and their static resource graph validated. Import, rendering, interpolation, animation blending, Molang and gameplay behavior were not tested in Minecraft.",
            "mcp_server_version": SERVER_VERSION,
        }
    except Exception as exc:
        rollback = _rollback(project, tracked)
        return _error("BUNDLE_AUTHORING_FAILED", str(exc), rollback={"removed": [x for x in rollback if not x.startswith("CONCURRENT_CHANGE_NOT_REMOVED:")], "conflicts": [x.split(":", 1)[1] for x in rollback if x.startswith("CONCURRENT_CHANGE_NOT_REMOVED:")]},
                      runtime_status="NOT RUN")


def call_tool(name: str, raw_args: Any) -> dict[str, Any]:
    if name != "create_animated_entity_bundle":
        return _error("UNKNOWN_TOOL", f"unknown tool: {name}")
    try:
        raw = _validate_shape(raw_args)
        return _execute_bundle(raw)
    except (ValueError, TypeError, KeyError) as exc:
        return _error("INVALID_ARGUMENT", str(exc), runtime_status="NOT RUN")
    except Exception as exc:
        return _error("INTERNAL_ERROR", f"unexpected {type(exc).__name__}: {exc}", runtime_status="NOT RUN")


def _rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _rpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid JSON-RPC request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if not isinstance(method, str) or not isinstance(params, dict):
        return _rpc_error(request_id, -32600, "Invalid method or params")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        requested = params.get("protocolVersion", "2025-03-26")
        supported = {"2024-11-05", "2025-03-26", "2025-06-18"}
        selected = requested if requested in supported else "2025-03-26"
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": selected,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-animated-entity-authoring", "version": SERVER_VERSION},
            "instructions": WORKFLOW_INSTRUCTIONS,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        payload = call_tool(tool_name, args) if isinstance(tool_name, str) else _error("INVALID_ARGUMENT", "tool name must be a string")
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
            "structuredContent": payload,
            "isError": payload.get("status") == "error",
        }}
    return _rpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle_message(json.loads(line))
        except json.JSONDecodeError:
            response = _rpc_error(None, -32700, "Parse error")
        except Exception as exc:
            response = _rpc_error(None, -32603, f"Internal error: {type(exc).__name__}")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
