#!/usr/bin/env python3
"""Safe stdio MCP server for authoring a first-pass Bedrock custom entity bundle."""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

_IDENTIFIER = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_.-]+$")
_SLUG = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_BONE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_MAX_GEOMETRY_BYTES = 256 * 1024
_MAX_ENTITY_FILES_SCANNED = 500
_MAX_EXISTING_ENTITY_BYTES = 2 * 1024 * 1024


def _tool() -> dict[str, Any]:
    vector = {
        "type": "array", "minItems": 3, "maxItems": 3,
        "items": {"type": "number"},
    }
    cube = {
        "type": "object", "additionalProperties": False,
        "required": ["origin", "size", "uv"],
        "properties": {
            "origin": vector,
            "size": vector,
            "uv": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer", "minimum": 0}},
            "pivot": vector,
            "rotation": vector,
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
    return {
        "name": "create_addon_entity_with_geometry_with_geometry",
        "description": (
            "Create a custom Minecraft Bedrock entity in an EXISTING Minecraft Bedrock Engineer project scaffold. "
            "Writes a BP entity definition, RP client-entity definition, geometry model and render controller. "
            "The geometry is supplied as a bounded bone/cube structure; this tool does not invent a texture or animations. "
            "Refuses existing outputs, duplicate entity identifiers, malformed manifests, symlinks and unsafe paths. "
            "Requires the project scaffold folders to exist. Static JSON/resource references only; Minecraft runtime remains NOT RUN."
        ),
        "inputSchema": {
            "type": "object", "additionalProperties": False,
            "required": ["project_directory", "entity_name", "entity_slug", "target_game_version", "geometry"],
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63, "description": "One existing project directory created by create_addon_project."},
                "entity_name": {"type": "string", "minLength": 2, "maxLength": 80},
                "entity_slug": {"type": "string", "minLength": 2, "maxLength": 48, "description": "Lowercase snake_case file/entity suffix."},
                "target_game_version": {"type": "string", "minLength": 5, "maxLength": 20},
                "geometry": geometry,
                "health": {"type": "integer", "minimum": 1, "maximum": 1024, "default": 20},
                "movement_speed": {"type": "number", "minimum": 0, "maximum": 1.5, "default": 0.25},
                "collision_width": {"type": "number", "exclusiveMinimum": 0, "maximum": 8, "default": 0.6},
                "collision_height": {"type": "number", "exclusiveMinimum": 0, "maximum": 16, "default": 1.8},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    }


TOOLS = [_tool()]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}
WORKFLOW_INSTRUCTIONS = (
    "Entity authoring: create_addon_entity_with_geometry_with_geometry writes a linked BP entity + RP client entity, geometry and render controller. "
    "Supply bone/cube geometry explicitly; texture and animations are separate follow-up resources. "
    "Refuses output collisions and only writes inside an existing scaffold. Static checks do not prove game import/rendering."
)


def _error(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "error": {"code": code, "message": message}}


def _number(value: Any, label: str, minimum: float, maximum: float, *, exclusive_minimum: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if (number <= minimum if exclusive_minimum else number < minimum) or number > maximum:
        op = ">" if exclusive_minimum else ">="
        raise ValueError(f"{label} must be {op} {minimum} and <= {maximum}")
    return number


def _vector(value: Any, label: str, minimum: float, maximum: float) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{label} must contain exactly three numbers")
    return [_number(part, f"{label}[{index}]", minimum, maximum) for index, part in enumerate(value)]


def _validate_geometry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("geometry must be an object")
    allowed = {"texture_width", "texture_height", "visible_bounds_width", "visible_bounds_height", "visible_bounds_offset", "bones"}
    extra = set(raw) - allowed
    if extra:
        raise ValueError(f"unsupported geometry field(s): {', '.join(sorted(extra))}")

    def integer_field(key: str, default: int) -> int:
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 4096:
            raise ValueError(f"geometry.{key} must be an integer from 1 to 4096")
        return value

    texture_width = integer_field("texture_width", 64)
    texture_height = integer_field("texture_height", 64)
    visible_width = _number(raw.get("visible_bounds_width", 2.0), "geometry.visible_bounds_width", 0, 64, exclusive_minimum=True)
    visible_height = _number(raw.get("visible_bounds_height", 2.0), "geometry.visible_bounds_height", 0, 64, exclusive_minimum=True)
    visible_offset = _vector(raw.get("visible_bounds_offset", [0, 1, 0]), "geometry.visible_bounds_offset", -128, 128)

    bones_raw = raw.get("bones")
    if not isinstance(bones_raw, list) or not 1 <= len(bones_raw) <= 64:
        raise ValueError("geometry.bones must contain 1 to 64 bones")
    bones: list[dict[str, Any]] = []
    bone_names: set[str] = set()
    parent_by_name: dict[str, str | None] = {}
    total_cubes = 0

    for bone_index, entry in enumerate(bones_raw):
        label = f"geometry.bones[{bone_index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{label} must be an object")
        allowed_bone = {"name", "parent", "pivot", "cubes", "locators"}
        extra_bone = set(entry) - allowed_bone
        if extra_bone:
            raise ValueError(f"{label} has unsupported field(s): {', '.join(sorted(extra_bone))}")
        name = entry.get("name")
        if not isinstance(name, str) or not _BONE_NAME.fullmatch(name):
            raise ValueError(f"{label}.name must start with a letter and contain only letters, digits or underscores")
        if name in bone_names:
            raise ValueError(f"duplicate bone name: {name}")
        bone_names.add(name)
        parent = entry.get("parent")
        if parent is not None and (not isinstance(parent, str) or not _BONE_NAME.fullmatch(parent)):
            raise ValueError(f"{label}.parent is not a valid bone name")
        parent_by_name[name] = parent
        pivot = _vector(entry.get("pivot"), f"{label}.pivot", -128, 128)
        bone_data: dict[str, Any] = {"name": name, "pivot": pivot}
        if parent is not None:
            bone_data["parent"] = parent

        cubes_raw = entry.get("cubes", [])
        if not isinstance(cubes_raw, list) or len(cubes_raw) > 64:
            raise ValueError(f"{label}.cubes must be an array with at most 64 cubes")
        total_cubes += len(cubes_raw)
        if total_cubes > 256:
            raise ValueError("geometry may contain at most 256 cubes total")
        cubes: list[dict[str, Any]] = []
        for cube_index, cube in enumerate(cubes_raw):
            cube_label = f"{label}.cubes[{cube_index}]"
            if not isinstance(cube, dict):
                raise ValueError(f"{cube_label} must be an object")
            allowed_cube = {"origin", "size", "uv", "pivot", "rotation", "mirror", "inflate"}
            extra_cube = set(cube) - allowed_cube
            if extra_cube:
                raise ValueError(f"{cube_label} has unsupported field(s): {', '.join(sorted(extra_cube))}")
            origin = _vector(cube.get("origin"), f"{cube_label}.origin", -128, 128)
            size = _vector(cube.get("size"), f"{cube_label}.size", 0, 64)
            if not any(component > 0 for component in size):
                raise ValueError(f"{cube_label}.size cannot be all zero")
            uv = cube.get("uv")
            if not isinstance(uv, list) or len(uv) != 2:
                raise ValueError(f"{cube_label}.uv must be a two-integer UV origin")
            if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in uv):
                raise ValueError(f"{cube_label}.uv must contain non-negative integers")
            # Box UV layout occupies (2*depth + 2*width) by (depth + height).
            uv_right = uv[0] + (2 * size[2]) + (2 * size[0])
            uv_bottom = uv[1] + size[2] + size[1]
            if uv_right > texture_width or uv_bottom > texture_height:
                raise ValueError(f"{cube_label}.uv box exceeds the {texture_width}x{texture_height} texture bounds")
            cube_data: dict[str, Any] = {"origin": origin, "size": size, "uv": uv}
            if "pivot" in cube:
                cube_data["pivot"] = _vector(cube["pivot"], f"{cube_label}.pivot", -128, 128)
            if "rotation" in cube:
                cube_data["rotation"] = _vector(cube["rotation"], f"{cube_label}.rotation", -180, 180)
            if "mirror" in cube:
                if not isinstance(cube["mirror"], bool):
                    raise ValueError(f"{cube_label}.mirror must be a boolean")
                cube_data["mirror"] = cube["mirror"]
            if "inflate" in cube:
                cube_data["inflate"] = _number(cube["inflate"], f"{cube_label}.inflate", -16, 16)
            cubes.append(cube_data)
        if cubes:
            bone_data["cubes"] = cubes

        locators_raw = entry.get("locators", {})
        if not isinstance(locators_raw, dict) or len(locators_raw) > 32:
            raise ValueError(f"{label}.locators must be an object with at most 32 entries")
        if locators_raw:
            locators: dict[str, list[float]] = {}
            for locator_name, locator_position in locators_raw.items():
                if not isinstance(locator_name, str) or not _BONE_NAME.fullmatch(locator_name):
                    raise ValueError(f"{label}.locators contains an invalid locator name")
                locators[locator_name] = _vector(locator_position, f"{label}.locators.{locator_name}", -128, 128)
            bone_data["locators"] = locators
        bones.append(bone_data)

    for bone_name, parent in parent_by_name.items():
        if parent is not None and parent not in bone_names:
            raise ValueError(f"bone {bone_name!r} references missing parent {parent!r}")
        if parent == bone_name:
            raise ValueError(f"bone {bone_name!r} cannot parent itself")
    for bone_name in bone_names:
        seen: set[str] = set()
        current: str | None = bone_name
        while current is not None:
            if current in seen:
                raise ValueError(f"bone hierarchy contains a cycle at {current!r}")
            seen.add(current)
            current = parent_by_name.get(current)

    normalized = {
        "texture_width": texture_width,
        "texture_height": texture_height,
        "visible_bounds_width": visible_width,
        "visible_bounds_height": visible_height,
        "visible_bounds_offset": visible_offset,
        "bones": bones,
    }
    encoded = json.dumps(normalized, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > _MAX_GEOMETRY_BYTES:
        raise ValueError("geometry definition exceeds the 256 KiB input limit")
    return normalized


def _validate_arguments(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise ValueError("arguments must be a JSON object")
    allowed = {"project_directory", "entity_name", "entity_slug", "target_game_version", "geometry", "health", "movement_speed", "collision_width", "collision_height"}
    extra = set(args) - allowed
    required = {"project_directory", "entity_name", "entity_slug", "target_game_version", "geometry"}
    missing = required - set(args)
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")

    project_directory = args["project_directory"]
    if not isinstance(project_directory, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", project_directory) or "--" in project_directory:
        raise ValueError("project_directory must be one lowercase kebab-case directory name, not a path")
    entity_name = args["entity_name"]
    if not isinstance(entity_name, str) or not 2 <= len(entity_name) <= 80 or entity_name != entity_name.strip() or not entity_name:
        raise ValueError("entity_name must be 2 to 80 characters with no surrounding whitespace")
    entity_slug = args["entity_slug"]
    if not isinstance(entity_slug, str) or not _SLUG.fullmatch(entity_slug) or len(entity_slug) > 48:
        raise ValueError("entity_slug must be lowercase snake_case and start with a letter")
    version = args["target_game_version"]
    if not isinstance(version, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", version):
        raise ValueError("target_game_version must be a three-part numeric version, for example 1.26.50")

    def integer_option(key: str, default: int, lower: int, upper: int) -> int:
        value = args.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
            raise ValueError(f"{key} must be an integer from {lower} to {upper}")
        return value

    normalized = {
        "project_directory": project_directory,
        "entity_name": entity_name,
        "entity_slug": entity_slug,
        "target_game_version": version,
        "geometry": _validate_geometry(args["geometry"]),
        "health": integer_option("health", 20, 1, 1024),
        "movement_speed": _number(args.get("movement_speed", 0.25), "movement_speed", 0, 1.5),
        "collision_width": _number(args.get("collision_width", 0.6), "collision_width", 0, 8, exclusive_minimum=True),
        "collision_height": _number(args.get("collision_height", 1.8), "collision_height", 0, 16, exclusive_minimum=True),
    }
    return normalized


def _workspace_root() -> Path:
    raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    root = Path(raw).expanduser() if raw else Path.cwd()
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"configured workspace does not exist: {root}") from exc
    if not resolved.is_dir():
        raise ValueError("configured workspace must be a directory")
    return resolved


def _read_manifest(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError(f"{label} manifest is missing, oversized or unsafe")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} manifest is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("header"), dict) or not isinstance(data.get("modules"), list):
        raise ValueError(f"{label} manifest has an unexpected structure")
    return data


def _assert_safe_directory(path: Path, project: Path, label: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{label} directory is missing or unsafe: {path}")
    try:
        relative = path.relative_to(project)
        current = project
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"{label} path contains a symlink: {current}")
        path.resolve(strict=True).relative_to(project)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} directory escapes the project or contains an unsafe path") from exc


def _check_identifier_unique(bp_entities: Path, identifier: str) -> None:
    entries = sorted(bp_entities.glob("*.json"))
    if len(entries) > _MAX_ENTITY_FILES_SCANNED:
        raise ValueError(f"BP entities directory contains more than {_MAX_ENTITY_FILES_SCANNED} JSON files; cannot safely check identifier uniqueness")
    for entry in entries:
        if entry.is_symlink() or not entry.is_file() or entry.stat().st_size > _MAX_EXISTING_ENTITY_BYTES:
            raise ValueError(f"existing BP entity file is unsafe or oversized: {entry.name}")
        try:
            data = json.loads(entry.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot establish identifier uniqueness because {entry.name} is not valid JSON") from exc
        description = data.get("minecraft:entity", {}).get("description", {}) if isinstance(data, dict) else {}
        if isinstance(description, dict) and description.get("identifier") == identifier:
            raise ValueError(f"entity identifier already exists in {entry.name}: {identifier}")


def _create_entity(args: dict[str, Any]) -> dict[str, Any]:
    workspace = _workspace_root()
    project = workspace / args["project_directory"]
    if project.is_symlink() or not project.is_dir():
        raise ValueError("project_directory must identify an existing non-symlink project scaffold")
    try:
        project_resolved = project.resolve(strict=True)
        project_resolved.relative_to(workspace)
    except (OSError, ValueError) as exc:
        raise ValueError("project_directory escapes the configured workspace") from exc
    if project_resolved.parent != workspace:
        raise ValueError("project_directory must be a direct child of the configured workspace")

    bp_root = project / "behavior_packs" / f"{args['project_directory']}_BP"
    rp_root = project / "resource_packs" / f"{args['project_directory']}_RP"
    bp_entities = bp_root / "entities"
    rp_entity = rp_root / "entity"
    rp_geometry = rp_root / "models" / "entity"
    rp_render = rp_root / "render_controllers"
    for path, label in ((bp_root, "BP"), (bp_entities, "BP entities"), (rp_root, "RP"), (rp_entity, "RP entity"), (rp_geometry, "RP geometry"), (rp_render, "RP render controllers")):
        _assert_safe_directory(path, project_resolved, label)

    bp_manifest = _read_manifest(bp_root / "manifest.json", "BP")
    rp_manifest = _read_manifest(rp_root / "manifest.json", "RP")
    bp_header_uuid = bp_manifest["header"].get("uuid")
    rp_header_uuid = rp_manifest["header"].get("uuid")
    bp_module_types = {module.get("type") for module in bp_manifest["modules"] if isinstance(module, dict)}
    rp_module_types = {module.get("type") for module in rp_manifest["modules"] if isinstance(module, dict)}
    dependencies = bp_manifest.get("dependencies", [])
    linked = isinstance(dependencies, list) and any(
        isinstance(item, dict) and item.get("uuid") == rp_header_uuid for item in dependencies
    )
    if not isinstance(bp_header_uuid, str) or not isinstance(rp_header_uuid, str) or "data" not in bp_module_types or "resources" not in rp_module_types or not linked:
        raise ValueError("project manifests are not a linked Behavior Pack/Resource Pack scaffold")

    namespace = args["project_directory"].replace("-", "_")
    identifier = f"{namespace}:{args['entity_slug']}"
    geometry_identifier = f"geometry.{namespace}.{args['entity_slug']}"
    controller_identifier = f"controller.render.{namespace}.{args['entity_slug']}"
    _check_identifier_unique(bp_entities, identifier)

    slug = args["entity_slug"]
    bp_payload = {
        "format_version": "1.21.0",
        "minecraft:entity": {
            "description": {
                "identifier": identifier,
                "is_spawnable": True,
                "is_summonable": True,
                "is_experimental": False,
            },
            "components": {
                "minecraft:type_family": {"family": [slug, "mob"]},
                "minecraft:health": {"value": args["health"], "max": args["health"]},
                "minecraft:collision_box": {"width": args["collision_width"], "height": args["collision_height"]},
                "minecraft:movement": {"value": args["movement_speed"]},
                "minecraft:physics": {},
                "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
            },
        },
    }
    client_payload = {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": identifier,
                "materials": {"default": "entity_alphatest"},
                "textures": {"default": f"textures/entity/{namespace}/{slug}"},
                "geometry": {"default": geometry_identifier},
                "render_controllers": [controller_identifier],
            },
        },
    }
    geometry_payload = {
        "format_version": "1.21.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": geometry_identifier,
                "texture_width": args["geometry"]["texture_width"],
                "texture_height": args["geometry"]["texture_height"],
                "visible_bounds_width": args["geometry"]["visible_bounds_width"],
                "visible_bounds_height": args["geometry"]["visible_bounds_height"],
                "visible_bounds_offset": args["geometry"]["visible_bounds_offset"],
            },
            "bones": args["geometry"]["bones"],
        }],
    }
    render_payload = {
        "format_version": "1.8.0",
        "render_controllers": {
            controller_identifier: {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.default"],
            },
        },
    }

    destinations = {
        bp_entities / f"{slug}.json": bp_payload,
        rp_entity / f"{slug}.entity.json": client_payload,
        rp_geometry / f"{slug}.geo.json": geometry_payload,
        rp_render / f"{slug}.render_controllers.json": render_payload,
    }
    payloads: list[tuple[Path, bytes]] = []
    for path, data in destinations.items():
        if path.is_symlink() or path.exists():
            raise ValueError(f"output already exists or is a symlink; refusing to overwrite: {path.relative_to(project).as_posix()}")
        try:
            path.resolve(strict=False).relative_to(project_resolved)
        except (OSError, ValueError) as exc:
            raise ValueError("generated entity path escapes the project") from exc
        payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        payloads.append((path, payload))

    created: list[Path] = []
    try:
        for path, payload in payloads:
            with path.open("xb") as stream:
                created.append(path)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        for path in reversed(created):
            try:
                if path.is_file() and not path.is_symlink():
                    path.unlink()
            except OSError:
                pass
        raise

    files_created = [path.relative_to(project).as_posix() for path, _ in payloads]
    texture_file = f"resource_packs/{args['project_directory']}_RP/textures/entity/{namespace}/{slug}.png"
    return {
        "status": "created",
        "project_directory": str(project_resolved),
        "entity_name": args["entity_name"],
        "entity_identifier": identifier,
        "geometry_identifier": geometry_identifier,
        "render_controller_identifier": controller_identifier,
        "target_game_version": args["target_game_version"],
        "files_created": files_created,
        "texture_file_expected": texture_file,
        "texture_file_status": "NOT CREATED — supply a PNG or use generate_texture, then verify its UV mapping in-game",
        "animation_files_created": [],
        "geometry_summary": {"bones": len(args["geometry"]["bones"]), "cubes": sum(len(bone.get("cubes", [])) for bone in args["geometry"]["bones"]), "texture_size": [args["geometry"]["texture_width"], args["geometry"]["texture_height"]]},
        "runtime_status": "NOT RUN",
        "mcp_server_version": SERVER_VERSION,
        "note": "Generated a static first-pass entity bundle. A texture PNG and animation clips/controllers are intentionally not fabricated; the referenced texture path must be populated before visual rendering can be verified. Entity import, spawning and rendering were not tested in Minecraft.",
    }


def call_tool(name: str, raw_args: Any) -> dict[str, Any]:
    if name != "create_addon_entity_with_geometry_with_geometry":
        return _error("UNKNOWN_TOOL", f"unknown tool: {name}")
    try:
        args = _validate_arguments(raw_args)
        return _create_entity(args)
    except ValueError as exc:
        return _error("INVALID_ARGUMENT", str(exc))
    except OSError as exc:
        return _error("WRITE_FAILED", f"filesystem operation failed: {exc}")
    except Exception as exc:  # Avoid returning internal stack traces over MCP.
        return _error("INTERNAL_ERROR", f"unexpected {type(exc).__name__}: {exc}")


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid JSON-RPC request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if not isinstance(method, str) or not isinstance(params, dict):
        return _jsonrpc_error(request_id, -32600, "Invalid method or params")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        requested = params.get("protocolVersion", "2025-03-26")
        supported = {"2024-11-05", "2025-03-26", "2025-06-18"}
        selected = requested if requested in supported else "2025-03-26"
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": selected,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-entity-authoring", "version": SERVER_VERSION},
            "instructions": WORKFLOW_INSTRUCTIONS,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        payload = call_tool(name, arguments) if isinstance(name, str) else _error("INVALID_ARGUMENT", "tool name must be a string")
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": text}],
            "structuredContent": payload,
            "isError": payload.get("status") == "error",
        }}
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
