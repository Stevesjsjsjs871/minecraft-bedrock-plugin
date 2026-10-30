#!/usr/bin/env python3
"""Safe stdio MCP server for Minecraft Bedrock animation-clip authoring."""
from __future__ import annotations

import json
import math
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

_PROJECT = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_SLUG = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,63}$")
_ALIAS = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_ANIMATION_ID = re.compile(r"^animation\.[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
_GEOMETRY_ID = re.compile(r"^geometry\.[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
_MAX_JSON_BYTES = 4 * 1024 * 1024
_MAX_ANIMATION_FILES = 1000
_MAX_GEOMETRY_FILES = 1000
_MAX_BONES = 64
_MAX_KEYFRAMES_PER_CHANNEL = 128
_MAX_TOTAL_KEYFRAMES = 512
_MAX_ANIMATION_LENGTH = 600.0
_MAX_VALUE_MAGNITUDE = 10000.0
_MAX_MOLANG_LENGTH = 512


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str], *, read_only: bool) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": read_only,
            "destructiveHint": False,
            "idempotentHint": read_only,
            "openWorldHint": False,
        },
    }


_KEYFRAME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["time"],
    "properties": {
        "time": {"type": "number", "minimum": 0, "maximum": _MAX_ANIMATION_LENGTH},
        "value": {},
        "pre": {},
        "post": {},
    },
    "oneOf": [
        {"required": ["value"], "not": {"anyOf": [{"required": ["pre"]}, {"required": ["post"]}]}},
        {"required": ["pre", "post"], "not": {"required": ["value"]}},
    ],
}
_BONE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name"],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 64},
        "rotation": {"type": "array", "minItems": 1, "maxItems": _MAX_KEYFRAMES_PER_CHANNEL, "items": _KEYFRAME_SCHEMA},
        "position": {"type": "array", "minItems": 1, "maxItems": _MAX_KEYFRAMES_PER_CHANNEL, "items": _KEYFRAME_SCHEMA},
        "scale": {"type": "array", "minItems": 1, "maxItems": _MAX_KEYFRAMES_PER_CHANNEL, "items": _KEYFRAME_SCHEMA},
    },
}

TOOLS = [
    _tool(
        "create_animation_clip",
        "Create a new Bedrock RP animation clip (format_version 1.8.0) from bone channels and keyframes, then register its animation alias in an existing client entity. Intended for use by animation controllers or scripts/animate. Checks linked BP/RP manifests, keyframe bounds/order, paths, geometry references and collisions. Does not parse or execute Molang; Minecraft runtime remains NOT RUN.",
        {
            "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
            "target_game_version": {"type": "string", "minLength": 5, "maxLength": 20},
            "animation_slug": {"type": "string", "minLength": 2, "maxLength": 48},
            "client_entity_file": {"type": "string", "minLength": 1, "maxLength": 240},
            "animation_length": {"type": "number", "exclusiveMinimum": 0, "maximum": _MAX_ANIMATION_LENGTH},
            "bones": {"type": "array", "minItems": 1, "maxItems": _MAX_BONES, "items": _BONE_SCHEMA},
            "animation_alias": {"type": "string", "minLength": 1, "maxLength": 64},
            "animation_identifier": {"type": "string", "minLength": 12, "maxLength": 160},
            "loop": {"type": "boolean"},
            "override_previous_animation": {"type": "boolean"},
            "anim_time_update": {"type": "string", "minLength": 1, "maxLength": _MAX_MOLANG_LENGTH},
            "blend_weight": {"type": "string", "minLength": 1, "maxLength": _MAX_MOLANG_LENGTH},
            "geometry_alias": {"type": "string", "minLength": 1, "maxLength": 64},
            "geometry_file": {"type": "string", "minLength": 1, "maxLength": 240},
        },
        ["project_directory", "target_game_version", "animation_slug", "client_entity_file", "animation_length", "bones"],
        read_only=False,
    ),
    _tool(
        "validate_animation_clip",
        "Read-only validation for a Bedrock animation clip and its client-entity alias. Checks format, animation identifier, duration, bone/channel keyframes, values, alias binding and optional geometry bone names. It cannot evaluate Molang or prove in-game animation behavior.",
        {
            "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
            "animation_file": {"type": "string", "minLength": 1, "maxLength": 240},
            "client_entity_file": {"type": "string", "minLength": 1, "maxLength": 240},
            "animation_alias": {"type": "string", "minLength": 1, "maxLength": 64},
            "geometry_alias": {"type": "string", "minLength": 1, "maxLength": 64},
            "geometry_file": {"type": "string", "minLength": 1, "maxLength": 240},
        },
        ["project_directory", "animation_file", "client_entity_file", "animation_alias"],
        read_only=True,
    ),
]
TOOL_BY_NAME = {item["name"]: item for item in TOOLS}
WORKFLOW_INSTRUCTIONS = (
    "Animation clip workflow: create_animation_clip writes raw RP keyframe data and registers an alias in the client entity. "
    "Animation controllers can reference that alias in their state animations list. It does not add the alias to scripts.animate, "
    "because controllers may own playback; use scripts.animate separately only when direct playback is intended. "
    "Keyframe/Molang checks are static and text-bounded only. Always report Minecraft runtime as NOT RUN unless actually tested."
)


def _error(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "error": {"code": code, "message": message}}


def _json_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON object key: {key}")
        obj[key] = value
    return obj


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_JSON_BYTES:
        raise ValueError(f"{label} is missing, oversized or unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_no_duplicates)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} is not valid unambiguous UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


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


def _assert_safe_dir(path: Path, project: Path, label: str, *, must_exist: bool = True) -> None:
    try:
        relative = path.relative_to(project)
    except ValueError as exc:
        raise ValueError(f"{label} is outside the project") from exc
    current = project
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} path contains a symlink: {current}")
    if must_exist and not path.is_dir():
        raise ValueError(f"{label} directory is missing: {path}")
    if path.exists() and not path.is_dir():
        raise ValueError(f"{label} is not a directory: {path}")
    try:
        path.resolve(strict=must_exist).relative_to(project)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} escapes the project") from exc


def _safe_project(project_directory: str) -> tuple[Path, Path, Path]:
    workspace = _workspace_root()
    project = workspace / project_directory
    if project.is_symlink() or not project.is_dir():
        raise ValueError("project_directory must identify an existing non-symlink project scaffold")
    try:
        resolved = project.resolve(strict=True)
        resolved.relative_to(workspace)
    except (OSError, ValueError) as exc:
        raise ValueError("project_directory escapes the configured workspace") from exc
    if resolved.parent != workspace:
        raise ValueError("project_directory must be a direct child of the configured workspace")
    bp_root = resolved / "behavior_packs" / f"{project_directory}_BP"
    rp_root = resolved / "resource_packs" / f"{project_directory}_RP"
    for path, label in (
        (resolved / "behavior_packs", "BP pack container"),
        (bp_root, "BP"),
        (resolved / "resource_packs", "RP pack container"),
        (rp_root, "RP"),
        (rp_root / "entity", "RP entity"),
    ):
        _assert_safe_dir(path, resolved, label)
    bp_manifest = _read_manifest(bp_root / "manifest.json", "BP")
    rp_manifest = _read_manifest(rp_root / "manifest.json", "RP")
    bp_uuid = bp_manifest["header"].get("uuid")
    rp_uuid = rp_manifest["header"].get("uuid")
    bp_types = {m.get("type") for m in bp_manifest["modules"] if isinstance(m, dict)}
    rp_types = {m.get("type") for m in rp_manifest["modules"] if isinstance(m, dict)}
    dependencies = bp_manifest.get("dependencies", [])
    linked = isinstance(dependencies, list) and any(
        isinstance(dep, dict) and dep.get("uuid") == rp_uuid for dep in dependencies
    )
    if not isinstance(bp_uuid, str) or not isinstance(rp_uuid, str) or "data" not in bp_types or "resources" not in rp_types or not linked:
        raise ValueError("project manifests are not a linked Behavior Pack/Resource Pack scaffold")
    return resolved, bp_root, rp_root


def _read_manifest(path: Path, label: str) -> dict[str, Any]:
    data = _load_json(path, f"{label} manifest")
    if not isinstance(data.get("header"), dict) or not isinstance(data.get("modules"), list):
        raise ValueError(f"{label} manifest has an unexpected structure")
    return data


def _safe_rp_file(rp_root: Path, relative: str, label: str) -> Path:
    if (not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative
            or relative.startswith("/") or re.match(r"^[A-Za-z]:", relative)):
        raise ValueError(f"{label} must be a safe relative POSIX path inside the RP")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must be a canonical relative POSIX path")
    current = rp_root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} contains a symlink: {relative}")
    try:
        current.resolve(strict=False).relative_to(rp_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} escapes the RP") from exc
    return current


def _read_client_entity(rp_root: Path, relative: str) -> tuple[Path, bytes, dict[str, Any], dict[str, Any]]:
    if not relative.startswith("entity/") or not relative.endswith(".entity.json"):
        raise ValueError("client_entity_file must be inside RP entity/ and end with .entity.json")
    path = _safe_rp_file(rp_root, relative, "client_entity_file")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_JSON_BYTES:
        raise ValueError("client entity file is missing, oversized or unsafe")
    original = path.read_bytes()
    data = _load_json(path, "client entity file")
    client = data.get("minecraft:client_entity")
    description = client.get("description") if isinstance(client, dict) else None
    if not isinstance(description, dict) or not isinstance(description.get("identifier"), str):
        raise ValueError("client entity JSON must contain minecraft:client_entity.description.identifier")
    animations = description.setdefault("animations", {})
    if not isinstance(animations, dict):
        raise ValueError("client entity description.animations must be an object")
    return path, original, data, description


def _check_version(value: Any) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", value):
        raise ValueError("target_game_version must be a three-part numeric version, for example 1.26.50")


def _finite_number(value: Any, label: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{label} must be at most {maximum}")
    return number


def _molang_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_MOLANG_LENGTH or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} must be a non-empty printable Molang string of at most {_MAX_MOLANG_LENGTH} characters")
    return value.strip()


def _format_time(value: float) -> str:
    return format(value, ".9g")


def _value(value: Any, label: str) -> Any:
    """Validate a Bedrock transform scalar or 1/3 component vector."""
    if isinstance(value, str):
        return _molang_text(value, label)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _finite_number(value, label, minimum=-_MAX_VALUE_MAGNITUDE, maximum=_MAX_VALUE_MAGNITUDE)
    if isinstance(value, list) and len(value) in (1, 3):
        clean = []
        for index, component in enumerate(value):
            if isinstance(component, str):
                clean.append(_molang_text(component, f"{label}[{index}]"))
            else:
                clean.append(_finite_number(component, f"{label}[{index}]", minimum=-_MAX_VALUE_MAGNITUDE, maximum=_MAX_VALUE_MAGNITUDE))
        return clean
    raise ValueError(f"{label} must be a number, Molang string, or one/three-component array")


def _normalize_channel(raw_frames: Any, label: str, animation_length: float) -> tuple[dict[str, Any], int, int]:
    if not isinstance(raw_frames, list) or not 1 <= len(raw_frames) <= _MAX_KEYFRAMES_PER_CHANNEL:
        raise ValueError(f"{label} must contain 1 to {_MAX_KEYFRAMES_PER_CHANNEL} keyframes")
    output: dict[str, Any] = {}
    previous = -1.0
    molang_count = 0
    for index, frame in enumerate(raw_frames):
        at = f"{label}[{index}]"
        if not isinstance(frame, dict) or set(frame) - {"time", "value", "pre", "post"}:
            raise ValueError(f"{at} must contain only time and value or pre/post fields")
        time = _finite_number(frame.get("time"), f"{at}.time", minimum=0, maximum=animation_length)
        if time <= previous:
            raise ValueError(f"{label} keyframe times must be strictly increasing")
        previous = time
        has_value = "value" in frame
        has_pre = "pre" in frame
        has_post = "post" in frame
        if has_value == (has_pre or has_post) or (has_pre != has_post):
            raise ValueError(f"{at} must define either value or both pre and post")
        if has_value:
            normalized = _value(frame["value"], f"{at}.value")
            output[_format_time(time)] = normalized
            values = [frame["value"]]
        else:
            pre = _value(frame["pre"], f"{at}.pre")
            post = _value(frame["post"], f"{at}.post")
            output[_format_time(time)] = {"pre": pre, "post": post}
            values = [frame["pre"], frame["post"]]
        if any(isinstance(v, str) or (isinstance(v, list) and any(isinstance(x, str) for x in v)) for v in values):
            molang_count += 1
        if len(output) != index + 1:
            raise ValueError(f"{label} contains keyframe times that collide after JSON number formatting")
    return output, len(raw_frames), molang_count


def _normalize_bones(raw_bones: Any, animation_length: float) -> tuple[dict[str, Any], int, int, int, list[str]]:
    if not isinstance(raw_bones, list) or not 1 <= len(raw_bones) <= _MAX_BONES:
        raise ValueError(f"bones must contain 1 to {_MAX_BONES} bone objects")
    result: dict[str, Any] = {}
    total_frames = 0
    channel_count = 0
    molang_count = 0
    for index, bone in enumerate(raw_bones):
        label = f"bones[{index}]"
        if not isinstance(bone, dict) or set(bone) - {"name", "rotation", "position", "scale"}:
            raise ValueError(f"{label} must contain a name and supported transform channels only")
        name = bone.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError(f"{label}.name must begin with a letter and contain only letters, digits, underscores or periods")
        if name in result:
            raise ValueError(f"duplicate animation bone name: {name}")
        channels: dict[str, Any] = {}
        for channel in ("rotation", "position", "scale"):
            if channel in bone:
                frames, count, molang = _normalize_channel(bone[channel], f"{label}.{channel}", animation_length)
                total_frames += count
                if total_frames > _MAX_TOTAL_KEYFRAMES:
                    raise ValueError(f"animation exceeds {_MAX_TOTAL_KEYFRAMES} total keyframes")
                channel_count += 1
                molang_count += molang
                channels[channel] = frames
        if not channels:
            raise ValueError(f"{label} must define at least one of rotation, position or scale")
        result[name] = channels
    return result, total_frames, channel_count, molang_count, sorted(result)


def _scan_json_files(root: Path, glob_pattern: str, limit: int, label: str) -> list[Path]:
    if not root.exists():
        return []
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"{label} directory is unsafe")
    entries: list[Path] = []
    for current_root, dirs, files in os.walk(root, followlinks=False):
        base = Path(current_root)
        safe_dirs = []
        for name in dirs:
            child = base / name
            if child.is_symlink():
                raise ValueError(f"{label} contains a symlink directory: {child}")
            safe_dirs.append(name)
        dirs[:] = safe_dirs
        for name in files:
            child = base / name
            if name.lower().endswith(".json"):
                if child.is_symlink() or not child.is_file():
                    raise ValueError(f"{label} contains an unsafe JSON file: {child}")
                entries.append(child)
                if len(entries) > limit:
                    raise ValueError(f"{label} contains more than {limit} JSON files; cannot safely complete uniqueness/reference scan")
    return sorted(entries)


def _check_animation_identifier(rp_root: Path, identifier: str) -> None:
    animation_root = rp_root / "animations"
    files = _scan_json_files(animation_root, "*.json", _MAX_ANIMATION_FILES, "RP animations")
    for path in files:
        data = _load_json(path, f"existing animation file {path.name}")
        definitions = data.get("animations")
        if isinstance(definitions, dict) and identifier in definitions:
            raise ValueError(f"animation identifier already exists in {path.relative_to(rp_root).as_posix()}: {identifier}")


def _geometry_details(rp_root: Path, description: dict[str, Any], bone_names: list[str], geometry_alias: str | None, geometry_file: str | None) -> dict[str, Any]:
    warnings: list[str] = []
    geometry_map = description.get("geometry", {})
    if not isinstance(geometry_map, dict):
        raise ValueError("client entity description.geometry must be an object")

    selected_alias = geometry_alias
    if selected_alias is None and len(geometry_map) == 1:
        selected_alias = next(iter(geometry_map))
    if selected_alias is None:
        if len(geometry_map) == 0:
            return {"status": "NOT CHECKED", "geometry_alias": None, "geometry_identifier": None, "geometry_file": None, "bone_names_checked": 0, "unknown_bone_names": [], "warnings": ["Client entity has no statically declared geometry mapping."]}
        return {"status": "AMBIGUOUS", "geometry_alias": None, "geometry_identifier": None, "geometry_file": None, "bone_names_checked": 0, "unknown_bone_names": [], "warnings": ["Multiple geometry aliases exist; specify geometry_alias to check model bones."]}
    if not isinstance(selected_alias, str) or not _ALIAS.fullmatch(selected_alias):
        raise ValueError("geometry_alias must be a simple client-entity alias")
    geometry_identifier = geometry_map.get(selected_alias)
    if not isinstance(geometry_identifier, str) or not _GEOMETRY_ID.fullmatch(geometry_identifier):
        raise ValueError(f"client entity geometry alias {selected_alias!r} does not map to a valid geometry identifier")

    model_root = rp_root / "models"
    selected_path: Path | None = None
    if geometry_file is not None:
        selected_path = _safe_rp_file(rp_root, geometry_file, "geometry_file")
        if not geometry_file.startswith("models/") or not geometry_file.endswith(".geo.json"):
            raise ValueError("geometry_file must be a Resource Pack path under models/ ending in .geo.json")
        if selected_path.is_symlink() or not selected_path.is_file() or selected_path.stat().st_size > _MAX_JSON_BYTES:
            raise ValueError("geometry_file is missing, oversized or unsafe")
    else:
        files = _scan_json_files(model_root, "*.json", _MAX_GEOMETRY_FILES, "RP models")
        matches: list[Path] = []
        for path in files:
            if not path.name.endswith(".geo.json"):
                continue
            data = _load_json(path, f"geometry candidate {path.name}")
            definitions = data.get("minecraft:geometry")
            if isinstance(definitions, list) and any(
                isinstance(entry, dict) and isinstance(entry.get("description"), dict)
                and entry["description"].get("identifier") == geometry_identifier
                for entry in definitions
            ):
                matches.append(path)
        if len(matches) != 1:
            status = "NOT FOUND" if not matches else "AMBIGUOUS"
            warnings.append("Could not uniquely resolve the selected geometry identifier to one RP .geo.json file.")
            return {"status": status, "geometry_alias": selected_alias, "geometry_identifier": geometry_identifier, "geometry_file": None, "bone_names_checked": 0, "unknown_bone_names": [], "warnings": warnings}
        selected_path = matches[0]

    model = _load_json(selected_path, "geometry file")
    definitions = model.get("minecraft:geometry")
    if not isinstance(definitions, list):
        raise ValueError("geometry_file must contain a minecraft:geometry array")
    matched = [entry for entry in definitions if isinstance(entry, dict) and isinstance(entry.get("description"), dict) and entry["description"].get("identifier") == geometry_identifier]
    if len(matched) != 1:
        raise ValueError(f"geometry_file does not contain exactly one definition for {geometry_identifier!r}")
    model_bones = matched[0].get("bones")
    if not isinstance(model_bones, list):
        raise ValueError("matched geometry definition must contain a bones array")
    model_names = {item.get("name") for item in model_bones if isinstance(item, dict) and isinstance(item.get("name"), str)}
    unknown = sorted(set(bone_names) - model_names)
    if unknown:
        warnings.append("Animation references bone names absent from the selected geometry; Bedrock documentation says missing bones are ignored.")
    return {
        "status": "RESOLVED",
        "geometry_alias": selected_alias,
        "geometry_identifier": geometry_identifier,
        "geometry_file": selected_path.relative_to(rp_root).as_posix(),
        "bone_names_checked": len(bone_names),
        "unknown_bone_names": unknown,
        "warnings": warnings,
    }


def _atomic_update_existing(path: Path, original: bytes, replacement: bytes) -> None:
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("xb") as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink() or not path.is_file() or path.read_bytes() != original:
            raise ValueError("client entity changed during animation creation; refusing to overwrite concurrent edits")
        os.replace(temp_path, path)
    finally:
        try:
            if temp_path.exists() and not temp_path.is_symlink():
                temp_path.unlink()
        except OSError:
            pass


def _create_clip(args: dict[str, Any]) -> dict[str, Any]:
    project, _bp_root, rp_root = _safe_project(args["project_directory"])
    client_path, client_original, client_data, description = _read_client_entity(rp_root, args["client_entity_file"])
    slug = args["animation_slug"]
    alias = args.get("animation_alias", slug)
    identifier = args.get("animation_identifier") or f"animation.{args['project_directory'].replace('-', '_')}.{slug}"
    if not _SLUG.fullmatch(slug) or len(slug) > 48:
        raise ValueError("animation_slug must be lowercase snake_case and start with a letter")
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise ValueError("animation_alias must be a simple client-entity alias")
    if not isinstance(identifier, str) or not _ANIMATION_ID.fullmatch(identifier):
        raise ValueError("animation_identifier must look like animation.namespace.name")
    animation_length = _finite_number(args["animation_length"], "animation_length", minimum=0.000001, maximum=_MAX_ANIMATION_LENGTH)
    existing_animations = description.get("animations", {})
    if not isinstance(existing_animations, dict):
        raise ValueError("client entity description.animations must be an object")
    if alias in existing_animations and existing_animations[alias] != identifier:
        raise ValueError(f"animation alias {alias!r} is already mapped to a different resource")

    normalized_bones, keyframe_count, channel_count, molang_count, bone_names = _normalize_bones(args["bones"], animation_length)
    geometry = _geometry_details(rp_root, description, bone_names, args.get("geometry_alias"), args.get("geometry_file"))
    animation: dict[str, Any] = {
        "loop": args.get("loop", False),
        "animation_length": animation_length,
        "bones": normalized_bones,
    }
    if "override_previous_animation" in args:
        if not isinstance(args["override_previous_animation"], bool):
            raise ValueError("override_previous_animation must be a boolean")
        animation["override_previous_animation"] = args["override_previous_animation"]
    for field in ("anim_time_update", "blend_weight"):
        if field in args:
            animation[field] = _molang_text(args[field], field)
            molang_count += 1

    animation_data = {"format_version": "1.8.0", "animations": {identifier: animation}}
    animation_dir = rp_root / "animations"
    _assert_safe_dir(animation_dir, project, "RP animations directory", must_exist=False)
    _check_animation_identifier(rp_root, identifier)
    animation_path = _safe_rp_file(rp_root, f"animations/{slug}.animation.json", "animation output")
    if animation_path.is_symlink() or animation_path.exists():
        raise ValueError(f"animation output already exists or is a symlink; refusing to overwrite: {animation_path.relative_to(project).as_posix()}")

    description["animations"] = dict(existing_animations)
    description["animations"][alias] = identifier
    animation_bytes = (json.dumps(animation_data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    client_bytes = (json.dumps(client_data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    created_dir = False
    created_animation = False
    try:
        if not animation_dir.exists():
            animation_dir.mkdir()
            created_dir = True
        with animation_path.open("xb") as stream:
            created_animation = True
            stream.write(animation_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        _atomic_update_existing(client_path, client_original, client_bytes)
    except Exception:
        if created_animation:
            try:
                if animation_path.is_file() and not animation_path.is_symlink():
                    animation_path.unlink()
            except OSError:
                pass
        if created_dir:
            try:
                animation_dir.rmdir()
            except OSError:
                pass
        raise

    warnings = list(geometry.get("warnings", []))
    return {
        "status": "created",
        "project_directory": str(project),
        "target_game_version": args["target_game_version"],
        "animation_identifier": identifier,
        "animation_alias": alias,
        "client_entity_identifier": description["identifier"],
        "animation_length": animation_length,
        "loop": animation["loop"],
        "bone_count": len(bone_names),
        "channel_count": channel_count,
        "keyframe_count": keyframe_count,
        "molang_values_inspected": molang_count,
        "molang_validation": "TEXT SHAPE ONLY — EXPRESSIONS NOT PARSED OR EXECUTED",
        "geometry": geometry,
        "files_created": [animation_path.relative_to(project).as_posix()],
        "files_updated": [client_path.relative_to(project).as_posix()],
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
        "warnings": warnings,
        "note": "The raw animation clip and client-entity alias were statically written. An animation controller may reference the alias in its state animations list; this tool intentionally does not change scripts.animate. In-game rendering, interpolation, Molang evaluation and controller playback remain unverified.",
    }


def _inspect_clip(rp_root: Path, animation_file: str, client_entity_file: str, alias: str, geometry_alias: str | None, geometry_file: str | None) -> dict[str, Any]:
    animation_path = _safe_rp_file(rp_root, animation_file, "animation_file")
    if not animation_file.startswith("animations/") or not animation_file.endswith(".animation.json"):
        raise ValueError("animation_file must be inside RP animations/ and end with .animation.json")
    data = _load_json(animation_path, "animation clip")
    if data.get("format_version") != "1.8.0":
        raise ValueError("animation clip format_version must be 1.8.0")
    definitions = data.get("animations")
    if not isinstance(definitions, dict) or len(definitions) != 1:
        raise ValueError("animation clip file must contain exactly one animations definition")
    identifier, animation = next(iter(definitions.items()))
    if not isinstance(identifier, str) or not _ANIMATION_ID.fullmatch(identifier) or not isinstance(animation, dict):
        raise ValueError("animation definition has an invalid identifier or shape")
    client_path, _original, _client_data, description = _read_client_entity(rp_root, client_entity_file)
    animations = description.get("animations", {})
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise ValueError("animation_alias must be a simple client-entity alias")
    if not isinstance(animations, dict) or animations.get(alias) != identifier:
        raise ValueError(f"client entity description.animations does not map {alias!r} to {identifier!r}")

    length = _finite_number(animation.get("animation_length"), "animation.animation_length", minimum=0.000001, maximum=_MAX_ANIMATION_LENGTH)
    if set(animation) - {"loop", "animation_length", "bones", "override_previous_animation", "anim_time_update", "blend_weight"}:
        raise ValueError("animation contains unsupported top-level fields")
    if not isinstance(animation.get("loop", False), bool):
        raise ValueError("animation.loop must be a boolean")
    if "override_previous_animation" in animation and not isinstance(animation["override_previous_animation"], bool):
        raise ValueError("animation.override_previous_animation must be a boolean")
    bones = animation.get("bones")
    if not isinstance(bones, dict) or not 1 <= len(bones) <= _MAX_BONES:
        raise ValueError("animation.bones must be an object with 1 to 64 bones")
    frame_count = 0
    channel_count = 0
    molang_count = 0
    bone_names: list[str] = []
    for bone_name, channels in bones.items():
        if not isinstance(bone_name, str) or not _NAME.fullmatch(bone_name) or not isinstance(channels, dict):
            raise ValueError("animation contains an invalid bone name or channel object")
        if set(channels) - {"rotation", "position", "scale"} or not channels:
            raise ValueError(f"bone {bone_name!r} has unsupported or empty channels")
        bone_names.append(bone_name)
        for channel in ("rotation", "position", "scale"):
            if channel not in channels:
                continue
            values = channels[channel]
            if not isinstance(values, dict) or not 1 <= len(values) <= _MAX_KEYFRAMES_PER_CHANNEL:
                raise ValueError(f"bone {bone_name!r} channel {channel!r} must contain 1 to {_MAX_KEYFRAMES_PER_CHANNEL} keyframes")
            previous = -1.0
            for raw_time, value in values.items():
                try:
                    at = float(raw_time)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"bone {bone_name!r} channel {channel!r} has a nonnumeric time key") from exc
                at = _finite_number(at, "keyframe time", minimum=0, maximum=length)
                if at <= previous:
                    raise ValueError(f"bone {bone_name!r} channel {channel!r} keyframe times must be strictly increasing")
                previous = at
                frame_count += 1
                if isinstance(value, dict):
                    if set(value) != {"pre", "post"}:
                        raise ValueError("keyframe object must contain exactly pre and post")
                    candidates = [value["pre"], value["post"]]
                else:
                    candidates = [value]
                for candidate in candidates:
                    _value(candidate, f"{bone_name}.{channel}.{raw_time}")
                    if isinstance(candidate, str) or (isinstance(candidate, list) and any(isinstance(x, str) for x in candidate)):
                        molang_count += 1
            channel_count += 1
    if frame_count > _MAX_TOTAL_KEYFRAMES:
        raise ValueError(f"animation exceeds {_MAX_TOTAL_KEYFRAMES} total keyframes")
    for field in ("anim_time_update", "blend_weight"):
        if field in animation:
            _molang_text(animation[field], field)
            molang_count += 1
    geometry = _geometry_details(rp_root, description, bone_names, geometry_alias, geometry_file)
    return {
        "status": "valid",
        "animation_identifier": identifier,
        "animation_alias": alias,
        "client_entity_identifier": description["identifier"],
        "animation_length": length,
        "loop": animation.get("loop", False),
        "bone_count": len(bones),
        "channel_count": channel_count,
        "keyframe_count": frame_count,
        "molang_values_inspected": molang_count,
        "molang_validation": "TEXT SHAPE ONLY — EXPRESSIONS NOT PARSED OR EXECUTED",
        "geometry": geometry,
        "files_inspected": [animation_path.relative_to(rp_root).as_posix(), client_path.relative_to(rp_root).as_posix()],
        "runtime_status": "NOT RUN",
    }


def _validate_arguments(name: str, raw: Any) -> dict[str, Any]:
    if name not in TOOL_BY_NAME:
        raise ValueError(f"unknown tool: {name}")
    if not isinstance(raw, dict):
        raise ValueError("arguments must be a JSON object")
    schema = TOOL_BY_NAME[name]["inputSchema"]
    properties = schema["properties"]
    extra = set(raw) - set(properties)
    missing = set(schema["required"]) - set(raw)
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    normalized = dict(raw)
    for key, value in raw.items():
        kind = properties[key].get("type")
        if kind == "string":
            if not isinstance(value, str) or not properties[key].get("minLength", 0) <= len(value) <= properties[key].get("maxLength", 4096):
                raise ValueError(f"{key} must be a string of valid length")
        elif kind == "array" and not isinstance(value, list):
            raise ValueError(f"{key} must be an array")
        elif kind == "boolean" and not isinstance(value, bool):
            raise ValueError(f"{key} must be a boolean")
        elif kind == "number":
            _finite_number(value, key, minimum=properties[key].get("minimum"), maximum=properties[key].get("maximum"))
    if not _PROJECT.fullmatch(normalized["project_directory"]) or "--" in normalized["project_directory"]:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    if name == "create_animation_clip":
        _check_version(normalized["target_game_version"])
        if not _SLUG.fullmatch(normalized["animation_slug"]) or len(normalized["animation_slug"]) > 48:
            raise ValueError("animation_slug must be lowercase snake_case and start with a letter")
        if "geometry_alias" in normalized and not _ALIAS.fullmatch(normalized["geometry_alias"]):
            raise ValueError("geometry_alias must be a simple client-entity alias")
    else:
        if not normalized["animation_file"].startswith("animations/"):
            raise ValueError("animation_file must be inside animations/")
        if not normalized["client_entity_file"].startswith("entity/"):
            raise ValueError("client_entity_file must be inside entity/")
        if not _ALIAS.fullmatch(normalized["animation_alias"]):
            raise ValueError("animation_alias must be a simple client-entity alias")
    return normalized


def call_tool(name: str, raw_args: Any) -> dict[str, Any]:
    try:
        args = _validate_arguments(name, raw_args)
        if name == "create_animation_clip":
            return _create_clip(args)
        if name == "validate_animation_clip":
            _project, _bp, rp = _safe_project(args["project_directory"])
            return _inspect_clip(rp, args["animation_file"], args["client_entity_file"], args["animation_alias"], args.get("geometry_alias"), args.get("geometry_file"))
        return _error("UNKNOWN_TOOL", f"unknown tool: {name}")
    except ValueError as exc:
        return _error("INVALID_ARGUMENT", str(exc))
    except OSError as exc:
        return _error("WRITE_FAILED", f"filesystem operation failed: {exc}")
    except Exception as exc:
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
            "serverInfo": {"name": "minecraft-bedrock-animation-clip-authoring", "version": SERVER_VERSION},
            "instructions": WORKFLOW_INSTRUCTIONS,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        tool_name = params.get("name")
        raw_args = params.get("arguments", {})
        payload = call_tool(tool_name, raw_args) if isinstance(tool_name, str) else _error("INVALID_ARGUMENT", "tool name must be a string")
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": serialized}],
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
