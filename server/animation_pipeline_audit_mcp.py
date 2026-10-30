#!/usr/bin/env python3
"""Read-only cross-resource audit for a Bedrock entity animation pipeline."""
from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
_PROJECT = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_ALIAS = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_ANIMATION_ID = re.compile(r"^animation\.[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
_CONTROLLER_ID = re.compile(r"^controller\.animation\.[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
_GEOMETRY_ID = re.compile(r"^geometry\.[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
_MAX_JSON_BYTES = 4 * 1024 * 1024
_MAX_ANIMATION_FILES = 1000
_MAX_CONTROLLER_FILES = 500
_MAX_GEOMETRY_FILES = 1000
_MAX_TOTAL_SCAN_BYTES = 64 * 1024 * 1024
_MAX_FINDINGS = 5000


def _tool_schema() -> dict[str, Any]:
    return {
        "name": "audit_entity_animation_pipeline",
        "description": (
            "Read-only end-to-end static audit of one RP client entity's animation graph. "
            "Resolves geometry aliases, animation aliases, animation-controller aliases, "
            "controller state animation references, scripts.animate entries, clip bone names "
            "and model geometry bones. Detects missing/ambiguous resources and controller cycles. "
            "Does not parse or execute Molang, render models, or launch Minecraft."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
                "client_entity_file": {"type": "string", "minLength": 1, "maxLength": 240},
            },
            "required": ["project_directory", "client_entity_file"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


TOOLS = [_tool_schema()]
WORKFLOW_INSTRUCTIONS = (
    "Run audit_entity_animation_pipeline after creating or modifying an entity's animation clips, "
    "controllers or geometry. This is a read-only static cross-resource audit. "
    "Resolve aliases by exact resource identifiers and file contents; never treat an unresolved "
    "heuristic as proof of engine failure. Molang is not evaluated and Minecraft runtime is NOT RUN."
)


def _json_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("not a regular non-symlink JSON file")
    size = path.stat().st_size
    if size > _MAX_JSON_BYTES:
        raise ValueError(f"JSON file exceeds {_MAX_JSON_BYTES} byte limit")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_no_duplicates)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def _workspace_root() -> Path:
    raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    path = Path(raw).expanduser() if raw else Path.cwd()
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("configured workspace root is not a directory")
    return resolved


def _assert_safe(path: Path, root: Path, label: str, *, must_exist: bool = True) -> None:
    try:
        rel = path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} is outside the project") from exc
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} contains a symlink: {current}")
    if must_exist and not path.exists():
        raise ValueError(f"{label} is missing: {path}")
    if path.exists() and not path.is_dir():
        raise ValueError(f"{label} is not a directory: {path}")
    try:
        path.resolve(strict=must_exist).relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} escapes the project") from exc


def _safe_rp_file(rp_root: Path, relative: str, label: str) -> Path:
    if (not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative
            or relative.startswith("/") or re.match(r"^[A-Za-z]:", relative)):
        raise ValueError(f"{label} must be a safe relative POSIX path inside the RP")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must be a canonical relative POSIX path")
    path = rp_root.joinpath(*parts)
    current = rp_root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} contains a symlink: {relative}")
    try:
        path.resolve(strict=True).relative_to(rp_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} escapes the RP or does not exist") from exc
    if not path.is_file():
        raise ValueError(f"{label} is not a regular file")
    return path


def _project_roots(project_directory: str) -> tuple[Path, Path, Path]:
    if not _PROJECT.fullmatch(project_directory) or "--" in project_directory:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    workspace = _workspace_root()
    project = workspace / project_directory
    if project.is_symlink() or not project.is_dir():
        raise ValueError("project_directory must identify an existing non-symlink project")
    project = project.resolve(strict=True)
    if project.parent != workspace:
        raise ValueError("project_directory must be a direct child of the configured workspace")
    bp_root = project / "behavior_packs" / f"{project_directory}_BP"
    rp_root = project / "resource_packs" / f"{project_directory}_RP"
    for path, label in (
        (project / "behavior_packs", "BP container"), (bp_root, "BP pack"),
        (project / "resource_packs", "RP container"), (rp_root, "RP pack"),
    ):
        _assert_safe(path, project, label)
    bp_manifest = _load_json(bp_root / "manifest.json")
    rp_manifest = _load_json(rp_root / "manifest.json")
    bh, rh = bp_manifest.get("header"), rp_manifest.get("header")
    bm, rm = bp_manifest.get("modules"), rp_manifest.get("modules")
    if not isinstance(bh, dict) or not isinstance(rh, dict) or not isinstance(bm, list) or not isinstance(rm, list):
        raise ValueError("BP/RP manifests do not have valid header/modules structures")
    bp_uuid, rp_uuid = bh.get("uuid"), rh.get("uuid")
    bp_types = {m.get("type") for m in bm if isinstance(m, dict)}
    rp_types = {m.get("type") for m in rm if isinstance(m, dict)}
    deps = bp_manifest.get("dependencies", [])
    linked = isinstance(deps, list) and any(
        isinstance(dep, dict) and dep.get("uuid") == rp_uuid for dep in deps
    )
    if not isinstance(bp_uuid, str) or not isinstance(rp_uuid, str) or "data" not in bp_types or "resources" not in rp_types or not linked:
        raise ValueError("project manifests are not a linked Behavior Pack/Resource Pack scaffold")
    return project, bp_root, rp_root


def _scan_json(root: Path, rp_root: Path, cap: int, label: str, findings: list[dict[str, Any]], budget: list[int]) -> tuple[list[Path], bool]:
    if root.is_symlink():
        findings.append({"code": "SYMLINK_DIRECTORY", "severity": "HIGH", "confidence": "HIGH", "file": root.relative_to(rp_root).as_posix(), "message": f"{label} root is a symlink and was not followed."})
        return [], False
    if not root.exists():
        return [], True
    _assert_safe(root, rp_root, label)
    paths: list[Path] = []
    complete = True
    for current, dirs, files in os.walk(root, followlinks=False):
        base = Path(current)
        safe_dirs = []
        for name in dirs:
            child = base / name
            if child.is_symlink():
                findings.append({"code": "SYMLINK_DIRECTORY", "severity": "HIGH", "confidence": "HIGH", "file": child.relative_to(rp_root).as_posix(), "message": f"{label} contains a symlink directory; that subtree was skipped."})
                complete = False
            else:
                safe_dirs.append(name)
        dirs[:] = safe_dirs
        for name in files:
            if not name.lower().endswith(".json"):
                continue
            path = base / name
            if path.is_symlink() or not path.is_file():
                findings.append({"code": "UNSAFE_JSON_PATH", "severity": "HIGH", "confidence": "HIGH", "file": path.relative_to(rp_root).as_posix(), "message": f"{label} contains a symlink or non-regular JSON path."})
                complete = False
                continue
            file_size = path.stat().st_size
            if file_size > _MAX_JSON_BYTES:
                findings.append({"code": "RESOURCE_FILE_TOO_LARGE", "severity": "WARNING", "confidence": "HIGH", "file": path.relative_to(rp_root).as_posix(), "message": f"{label} JSON file exceeds the per-file {_MAX_JSON_BYTES} byte limit and was skipped."})
                complete = False
                continue
            if budget[0] + file_size > _MAX_TOTAL_SCAN_BYTES:
                findings.append({"code": "SCAN_BYTE_LIMIT", "severity": "WARNING", "confidence": "HIGH", "file": root.relative_to(rp_root).as_posix(), "message": f"The total JSON scan budget of {_MAX_TOTAL_SCAN_BYTES} bytes was reached; remaining {label} files were not inspected."})
                complete = False
                return paths, complete
            budget[0] += file_size
            paths.append(path)
            if len(paths) > cap:
                findings.append({"code": "SCAN_LIMIT", "severity": "WARNING", "confidence": "HIGH", "file": root.relative_to(rp_root).as_posix(), "message": f"{label} exceeds the {cap} JSON-file scan limit; analysis is incomplete."})
                complete = False
                return paths[:cap], complete
    return sorted(paths), complete


def _finding(findings: list[dict[str, Any]], code: str, severity: str, confidence: str, file: str, pointer: str, message: str) -> None:
    if len(findings) >= _MAX_FINDINGS:
        return
    findings.append({"code": code, "severity": severity, "confidence": confidence, "file": file, "pointer": pointer, "message": message})


def _issue_path(path: Path, project: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return path.name


def _index_definitions(paths: list[Path], project: Path, section: str, findings: list[dict[str, Any]]) -> tuple[dict[str, list[tuple[Path, dict[str, Any]]]], int, bool]:
    index: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    parsed = 0
    complete = True
    for path in paths:
        rel = _issue_path(path, project)
        try:
            data = _load_json(path)
            parsed += 1
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            _finding(findings, "RESOURCE_JSON_INVALID", "HIGH", "HIGH", rel, "$", f"Cannot safely parse {section} JSON: {exc}")
            complete = False
            continue
        definitions = data.get(section)
        if not isinstance(definitions, dict):
            _finding(findings, "RESOURCE_SECTION_MISSING", "WARNING", "MEDIUM", rel, f"$/{section}", f"{section} is missing or is not an object; file was not indexed.")
            complete = False
            continue
        for identifier, definition in definitions.items():
            if not isinstance(identifier, str) or not isinstance(definition, dict):
                _finding(findings, "RESOURCE_DEFINITION_INVALID", "WARNING", "HIGH", rel, f"$/{section}/{identifier}", f"Invalid {section} definition entry.")
                complete = False
                continue
            index[identifier].append((path, definition))
    for identifier, sources in index.items():
        if len(sources) > 1:
            files = ", ".join(_issue_path(p, project) for p, _ in sources[:5])
            _finding(findings, "DUPLICATE_RESOURCE_IDENTIFIER", "HIGH", "HIGH", files, f"$/{section}/{identifier}", f"Resource identifier {identifier!r} is defined in {len(sources)} files.")
    return index, parsed, complete


def _geometry_bones(geometry: dict[str, Any]) -> set[str]:
    raw = geometry.get("bones")
    if not isinstance(raw, list):
        return set()
    return {item["name"] for item in raw if isinstance(item, dict) and isinstance(item.get("name"), str)}



def _inspect_animation_shape(animation: dict[str, Any], path: Path, project: Path,
                             identifier: str, findings: list[dict[str, Any]]) -> set[str]:
    """Check the structural portion of a clip without evaluating Molang."""
    rel = _issue_path(path, project)
    bone_data = animation.get("bones", {})
    if not isinstance(bone_data, dict):
        _finding(findings, "ANIMATION_BONES_INVALID", "HIGH", "HIGH", rel,
                 f"$/animations/{identifier}/bones", "Animation bones must be an object.")
        return set()
    length = animation.get("animation_length")
    if length is not None and (isinstance(length, bool) or not isinstance(length, (int, float))
                               or not math.isfinite(length)
                               or length < 0):
        _finding(findings, "ANIMATION_LENGTH_INVALID", "HIGH", "HIGH", rel,
                 f"$/animations/{identifier}/animation_length", "animation_length must be a finite nonnegative number.")
        length = None
    if "loop" in animation and not isinstance(animation["loop"], (bool, str, int, float)):
        _finding(findings, "ANIMATION_LOOP_INVALID", "WARNING", "MEDIUM", rel,
                 f"$/animations/{identifier}/loop", "loop has an unsupported value shape.")
    bone_names: set[str] = set()
    for bone_name, channels in bone_data.items():
        if not isinstance(bone_name, str) or not isinstance(channels, dict):
            _finding(findings, "ANIMATION_BONE_INVALID", "HIGH", "HIGH", rel,
                     f"$/animations/{identifier}/bones/{bone_name}", "Animation bone entry must be an object keyed by a bone name.")
            continue
        bone_names.add(bone_name)
        for channel_name, channel in channels.items():
            ptr = f"$/animations/{identifier}/bones/{bone_name}/{channel_name}"
            if channel_name not in {"rotation", "position", "scale"}:
                _finding(findings, "ANIMATION_CHANNEL_UNKNOWN", "WARNING", "MEDIUM", rel, ptr,
                         f"Channel {channel_name!r} is not a standard bone transform channel.")
                continue
            if isinstance(channel, list):
                if not 1 <= len(channel) <= 3:
                    _finding(findings, "ANIMATION_STATIC_TRANSFORM_INVALID", "HIGH", "HIGH", rel, ptr,
                             "Static transform arrays must contain one or three components.")
                continue
            if not isinstance(channel, dict) or not channel:
                _finding(findings, "ANIMATION_CHANNEL_INVALID", "HIGH", "HIGH", rel, ptr,
                         "Animation channel must be a static transform array or non-empty keyframe object.")
                continue
            seen_times: set[float] = set()
            for raw_time, frame_value in channel.items():
                try:
                    at = float(raw_time)
                except (TypeError, ValueError):
                    at = float("nan")
                if not math.isfinite(at) or at < 0 or (length is not None and at > length):
                    _finding(findings, "ANIMATION_KEYFRAME_TIME_INVALID", "HIGH", "HIGH", rel, ptr,
                             f"Keyframe time {raw_time!r} is not finite, nonnegative and within animation_length.")
                    continue
                if at in seen_times:
                    _finding(findings, "ANIMATION_KEYFRAME_TIME_DUPLICATE", "HIGH", "HIGH", rel, ptr,
                             f"Two timestamp keys represent the same numeric time ({at}).")
                seen_times.add(at)
                if isinstance(frame_value, dict):
                    if set(frame_value) != {"pre", "post"}:
                        _finding(findings, "ANIMATION_PRE_POST_INVALID", "HIGH", "HIGH", rel, ptr,
                                 "Discontinuous keyframes must contain both pre and post values only.")
                    elif any(not isinstance(frame_value[key], (list, int, float, str)) or isinstance(frame_value[key], bool)
                             for key in ("pre", "post")):
                        _finding(findings, "ANIMATION_PRE_POST_VALUE_INVALID", "HIGH", "HIGH", rel, ptr,
                                 "Discontinuous pre/post values must be scalar, vector or Molang string values.")
                elif not isinstance(frame_value, (list, int, float, str)) or isinstance(frame_value, bool):
                    _finding(findings, "ANIMATION_KEYFRAME_VALUE_INVALID", "HIGH", "HIGH", rel, ptr,
                             "Keyframe value must be a scalar, vector or pre/post object.")
    return bone_names

def _audit(args: dict[str, Any]) -> dict[str, Any]:
    project, bp_root, rp_root = _project_roots(args["project_directory"])
    entity_path = _safe_rp_file(rp_root, args["client_entity_file"], "client_entity_file")
    if not args["client_entity_file"].startswith("entity/") or not args["client_entity_file"].endswith(".entity.json"):
        raise ValueError("client_entity_file must be inside RP entity/ and end with .entity.json")
    entity = _load_json(entity_path)
    client = entity.get("minecraft:client_entity")
    description = client.get("description") if isinstance(client, dict) else None
    if not isinstance(description, dict) or not isinstance(description.get("identifier"), str):
        raise ValueError("client entity must contain minecraft:client_entity.description.identifier")

    findings: list[dict[str, Any]] = []
    complete = True
    entity_rel = _issue_path(entity_path, project)
    entity_identifier = description["identifier"]
    entity_namespace = entity_identifier.split(":", 1)[0] if ":" in entity_identifier else None

    animations_map = description.get("animations", {})
    geometry_map = description.get("geometry", {})
    scripts = description.get("scripts", {})
    animate_list = scripts.get("animate", []) if isinstance(scripts, dict) else []
    if not isinstance(animations_map, dict):
        raise ValueError("client entity description.animations must be an object")
    if not isinstance(geometry_map, dict):
        _finding(findings, "GEOMETRY_MAP_INVALID", "HIGH", "HIGH", entity_rel, "$/minecraft:client_entity/description/geometry", "description.geometry must be an object.")
        geometry_map = {}
    if not isinstance(animate_list, list):
        _finding(findings, "ANIMATE_LIST_INVALID", "HIGH", "HIGH", entity_rel, "$/minecraft:client_entity/description/scripts/animate", "scripts.animate must be an array.")
        animate_list = []

    anim_dir = rp_root / "animations"
    controller_dir = rp_root / "animation_controllers"
    geometry_dir = rp_root / "models" / "entity"
    # Keep scan failures local to the project; the walker does not follow symlinks.
    scan_budget = [0]
    anim_paths, ok = _scan_json(anim_dir, rp_root, _MAX_ANIMATION_FILES, "animations", findings, scan_budget); complete &= ok
    controller_paths, ok = _scan_json(controller_dir, rp_root, _MAX_CONTROLLER_FILES, "animation_controllers", findings, scan_budget); complete &= ok
    geometry_paths, ok = _scan_json(geometry_dir, rp_root, _MAX_GEOMETRY_FILES, "geometry", findings, scan_budget); complete &= ok

    animation_index, animation_files_parsed, ok = _index_definitions(anim_paths, project, "animations", findings); complete &= ok
    controller_index, controller_files_parsed, ok = _index_definitions(controller_paths, project, "animation_controllers", findings); complete &= ok

    geometry_index: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    geometry_files_parsed = 0
    for path in geometry_paths:
        rel = _issue_path(path, project)
        try:
            data = _load_json(path)
            geometry_files_parsed += 1
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            _finding(findings, "RESOURCE_JSON_INVALID", "HIGH", "HIGH", rel, "$", f"Cannot safely parse geometry JSON: {exc}")
            complete = False
            continue
        raw_geometries = data.get("minecraft:geometry")
        if not isinstance(raw_geometries, list):
            _finding(findings, "GEOMETRY_SECTION_INVALID", "WARNING", "MEDIUM", rel, "$/minecraft:geometry", "minecraft:geometry is missing or is not an array; file was not indexed.")
            complete = False
            continue
        for geometry in raw_geometries:
            desc = geometry.get("description") if isinstance(geometry, dict) else None
            identifier = desc.get("identifier") if isinstance(desc, dict) else None
            if not isinstance(identifier, str) or not isinstance(geometry, dict):
                _finding(findings, "GEOMETRY_DEFINITION_INVALID", "WARNING", "HIGH", rel, "$/minecraft:geometry", "Geometry definition has no valid description.identifier.")
                complete = False
                continue
            geometry_index[identifier].append((path, geometry))
    for identifier, sources in geometry_index.items():
        if len(sources) > 1:
            _finding(findings, "DUPLICATE_GEOMETRY_IDENTIFIER", "HIGH", "HIGH", ", ".join(_issue_path(p, project) for p, _ in sources[:5]), f"$/minecraft:geometry/{identifier}", f"Geometry identifier {identifier!r} is defined in {len(sources)} files.")

    alias_targets: dict[str, tuple[str, str]] = {}
    resolved_clips: dict[str, tuple[Path, dict[str, Any]]] = {}
    resolved_controllers: dict[str, tuple[Path, dict[str, Any]]] = {}
    for alias, identifier in animations_map.items():
        ptr = f"$/minecraft:client_entity/description/animations/{alias}"
        if not isinstance(alias, str) or not _ALIAS.fullmatch(alias) or not isinstance(identifier, str):
            _finding(findings, "ANIMATION_ALIAS_INVALID", "WARNING", "HIGH", entity_rel, ptr, "Animation alias or resource identifier is not a supported static string.")
            complete = False
            continue
        if identifier.startswith("animation."):
            if not _ANIMATION_ID.fullmatch(identifier):
                _finding(findings, "ANIMATION_IDENTIFIER_INVALID", "WARNING", "HIGH", entity_rel, ptr, f"Animation identifier {identifier!r} is malformed.")
                continue
            matches = animation_index.get(identifier, [])
            if not matches:
                resource_namespace = identifier.split(".", 2)[1] if len(identifier.split(".")) >= 3 else None
                if entity_namespace and resource_namespace == entity_namespace:
                    _finding(findings, "ANIMATION_RESOURCE_MISSING", "HIGH", "HIGH", entity_rel, ptr, f"Alias {alias!r} points to local identifier {identifier!r}, but no matching animation definition was indexed.")
                else:
                    _finding(findings, "ANIMATION_EXTERNAL_REFERENCE", "INFO", "LOW", entity_rel, ptr, f"Alias {alias!r} points to {identifier!r}, which is not defined in this RP and appears to be an external/vanilla resource reference.")
                    alias_targets[alias] = ("external_animation", identifier)
            elif len(matches) > 1:
                _finding(findings, "ANIMATION_RESOURCE_AMBIGUOUS", "HIGH", "HIGH", entity_rel, ptr, f"Alias {alias!r} points to {identifier!r}, which has multiple definitions.")
            else:
                alias_targets[alias] = ("animation", identifier)
                resolved_clips[identifier] = matches[0]
        elif identifier.startswith("controller.animation."):
            if not _CONTROLLER_ID.fullmatch(identifier):
                _finding(findings, "CONTROLLER_IDENTIFIER_INVALID", "WARNING", "HIGH", entity_rel, ptr, f"Controller identifier {identifier!r} is malformed.")
                continue
            matches = controller_index.get(identifier, [])
            if not matches:
                parts = identifier.split(".")
                resource_namespace = parts[2] if len(parts) >= 4 else None
                if entity_namespace and resource_namespace == entity_namespace:
                    _finding(findings, "CONTROLLER_RESOURCE_MISSING", "HIGH", "HIGH", entity_rel, ptr, f"Alias {alias!r} points to local identifier {identifier!r}, but no matching controller definition was indexed.")
                else:
                    _finding(findings, "CONTROLLER_EXTERNAL_REFERENCE", "INFO", "LOW", entity_rel, ptr, f"Alias {alias!r} points to {identifier!r}, which is not defined in this RP and appears to be an external/vanilla controller reference.")
                    alias_targets[alias] = ("external_controller", identifier)
            elif len(matches) > 1:
                _finding(findings, "CONTROLLER_RESOURCE_AMBIGUOUS", "HIGH", "HIGH", entity_rel, ptr, f"Alias {alias!r} points to {identifier!r}, which has multiple definitions.")
            else:
                alias_targets[alias] = ("controller", identifier)
                resolved_controllers[identifier] = matches[0]
        else:
            _finding(findings, "UNCLASSIFIED_ANIMATION_TARGET", "INFO", "LOW", entity_rel, ptr, f"Alias {alias!r} uses resource target {identifier!r}, which is not a recognized animation/controller identifier. It may be an external/dynamic reference.")
            alias_targets[alias] = ("external", identifier)

    # Resolve geometry aliases declared on this exact client entity.
    resolved_geometries: dict[str, tuple[Path, dict[str, Any]]] = {}
    for alias, identifier in geometry_map.items():
        ptr = f"$/minecraft:client_entity/description/geometry/{alias}"
        if not isinstance(alias, str) or not isinstance(identifier, str) or not _GEOMETRY_ID.fullmatch(identifier):
            _finding(findings, "GEOMETRY_ALIAS_INVALID", "WARNING", "HIGH", entity_rel, ptr, "Geometry alias or identifier is not a supported static geometry identifier.")
            continue
        matches = geometry_index.get(identifier, [])
        if not matches:
            resource_namespace = identifier.split(".", 2)[1] if len(identifier.split(".")) >= 3 else None
            if entity_namespace and resource_namespace == entity_namespace:
                _finding(findings, "GEOMETRY_RESOURCE_MISSING", "HIGH", "HIGH", entity_rel, ptr, f"Geometry alias {alias!r} points to local identifier {identifier!r}, but no matching geometry definition was indexed.")
            else:
                _finding(findings, "GEOMETRY_EXTERNAL_REFERENCE", "INFO", "LOW", entity_rel, ptr, f"Geometry alias {alias!r} points to {identifier!r}, which is not defined in this RP and appears to be an external/vanilla geometry dependency.")
        elif len(matches) > 1:
            _finding(findings, "GEOMETRY_RESOURCE_AMBIGUOUS", "HIGH", "HIGH", entity_rel, ptr, f"Geometry identifier {identifier!r} has multiple definitions.")
        else:
            resolved_geometries[alias] = matches[0]

    # Validate bone names for each clip used by the entity against each resolved geometry.
    entity_geometry_bones = {alias: _geometry_bones(geometry) for alias, (_path, geometry) in resolved_geometries.items()}
    for identifier, (path, animation) in resolved_clips.items():
        bone_names = _inspect_animation_shape(animation, path, project, identifier, findings)
        for geometry_alias, model_bones in entity_geometry_bones.items():
            missing = sorted(bone_names - model_bones)
            for bone in missing[:100]:
                _finding(findings, "ANIMATION_BONE_NOT_IN_GEOMETRY", "WARNING", "HIGH", _issue_path(path, project), f"$/animations/{identifier}/bones/{bone}", f"Animated bone {bone!r} is not present in geometry alias {geometry_alias!r}. This may indicate a typo or an intentional animation for a different geometry variant.")

    # Inspect every controller definition from every indexed controller file, not only those directly aliased.
    controller_graph: dict[str, set[str]] = defaultdict(set)
    controller_state_count = 0
    controller_transition_count = 0
    for identifier, (path, definition) in resolved_controllers.items():
        states = definition.get("states")
        initial = definition.get("initial_state", "default")
        if not isinstance(states, dict) or not states:
            _finding(findings, "CONTROLLER_STATES_INVALID", "HIGH", "HIGH", _issue_path(path, project), f"$/animation_controllers/{identifier}/states", "Controller states must be a non-empty object.")
            continue
        controller_state_count += len(states)
        if not isinstance(initial, str) or initial not in states:
            _finding(findings, "CONTROLLER_INITIAL_STATE_MISSING", "HIGH", "HIGH", _issue_path(path, project), f"$/animation_controllers/{identifier}/initial_state", f"Controller initial state {initial!r} does not resolve to a declared state.")
        for state_name, state in states.items():
            if not isinstance(state_name, str) or not isinstance(state, dict):
                _finding(findings, "CONTROLLER_STATE_INVALID", "WARNING", "HIGH", _issue_path(path, project), f"$/animation_controllers/{identifier}/states", "Controller has an invalid state entry.")
                continue
            state_ptr = f"$/animation_controllers/{identifier}/states/{state_name}"
            state_animations = state.get("animations", [])
            if not isinstance(state_animations, list):
                _finding(findings, "CONTROLLER_ANIMATIONS_INVALID", "HIGH", "HIGH", _issue_path(path, project), f"{state_ptr}/animations", "Controller state's animations must be an array.")
            else:
                for idx, item in enumerate(state_animations):
                    raw_aliases: list[str] = []
                    if isinstance(item, str):
                        raw_aliases = [item]
                    elif isinstance(item, dict) and len(item) == 1:
                        raw_aliases = list(item.keys())
                    else:
                        _finding(findings, "CONTROLLER_ANIMATION_ENTRY_INVALID", "WARNING", "HIGH", _issue_path(path, project), f"{state_ptr}/animations/{idx}", "Controller animation entry must be an alias string or a one-key alias-to-Molang object.")
                    for raw_alias in raw_aliases:
                        if raw_alias not in alias_targets:
                            _finding(findings, "CONTROLLER_ANIMATION_ALIAS_MISSING", "HIGH", "HIGH", _issue_path(path, project), f"{state_ptr}/animations/{idx}", f"Controller references alias {raw_alias!r}, but it is not resolved in this client entity's description.animations map.")
                            continue
                        target_type, target_id = alias_targets[raw_alias]
                        if target_type == "controller":
                            controller_graph[identifier].add(target_id)
                        elif target_type == "external_controller":
                            _finding(findings, "CONTROLLER_NESTED_EXTERNAL", "INFO", "LOW", _issue_path(path, project), f"{state_ptr}/animations/{idx}", f"Controller alias {raw_alias!r} points to an external controller that is not indexed in this RP.")
            transitions = state.get("transitions", [])
            if not isinstance(transitions, list):
                _finding(findings, "CONTROLLER_TRANSITIONS_INVALID", "WARNING", "HIGH", _issue_path(path, project), f"{state_ptr}/transitions", "Controller transitions must be an array.")
            else:
                for idx, transition in enumerate(transitions):
                    if not isinstance(transition, dict) or len(transition) != 1:
                        _finding(findings, "CONTROLLER_TRANSITION_INVALID", "WARNING", "HIGH", _issue_path(path, project), f"{state_ptr}/transitions/{idx}", "Controller transition must be a one-key state-to-Molang object.")
                        continue
                    destination = next(iter(transition))
                    controller_transition_count += 1
                    if destination not in states:
                        _finding(findings, "CONTROLLER_TRANSITION_TARGET_MISSING", "HIGH", "HIGH", _issue_path(path, project), f"{state_ptr}/transitions/{idx}", f"Transition destination {destination!r} is not a state in this controller.")

    # Check direct playback entries. A controller alias is valid here too.
    scripts_animate_aliases: list[str] = []
    for idx, item in enumerate(animate_list):
        if isinstance(item, str):
            alias = item
        elif isinstance(item, dict) and len(item) == 1:
            alias = next(iter(item))
        else:
            _finding(findings, "SCRIPT_ANIMATE_ENTRY_INVALID", "WARNING", "MEDIUM", entity_rel, f"$/minecraft:client_entity/description/scripts/animate/{idx}", "scripts.animate entry must be an alias string or one-key alias-to-Molang object.")
            continue
        scripts_animate_aliases.append(alias)
        if alias not in alias_targets:
            _finding(findings, "SCRIPT_ANIMATE_ALIAS_MISSING", "HIGH", "HIGH", entity_rel, f"$/minecraft:client_entity/description/scripts/animate/{idx}", f"scripts.animate references alias {alias!r}, which is missing or unresolved in description.animations.")

    # Detect cycles in nested controller references. This is a static directed graph only.
    color: dict[str, int] = {}
    cycle_nodes: set[str] = set()
    def visit(node: str, stack: list[str]) -> None:
        color[node] = 1
        stack.append(node)
        for nxt in controller_graph.get(node, set()):
            if nxt not in resolved_controllers:
                continue
            if color.get(nxt, 0) == 0:
                visit(nxt, stack)
            elif color.get(nxt) == 1:
                cycle_nodes.update(stack[stack.index(nxt):])
        stack.pop()
        color[node] = 2
    for controller_id in list(resolved_controllers):
        if color.get(controller_id, 0) == 0:
            visit(controller_id, [])
    for node in sorted(cycle_nodes):
        _finding(findings, "CONTROLLER_REFERENCE_CYCLE", "WARNING", "HIGH", _issue_path(resolved_controllers[node][0], project), f"$/animation_controllers/{node}", "Nested controller references contain a cycle. Engine behavior should be checked against the target runtime.")

    active_roots = {
        alias_targets[alias][1]
        for alias in scripts_animate_aliases
        if alias in alias_targets and alias_targets[alias][0] == "controller"
    }
    reachable = set()
    pending = list(active_roots)
    while pending:
        current = pending.pop()
        if current in reachable or current not in resolved_controllers:
            continue
        reachable.add(current)
        pending.extend(controller_graph.get(current, set()) - reachable)
    for controller_id in sorted(set(resolved_controllers) - reachable):
        _finding(findings, "CONTROLLER_ALIAS_NOT_ACTIVATED", "INFO", "MEDIUM", _issue_path(resolved_controllers[controller_id][0], project), f"$/animation_controllers/{controller_id}", "This controller is mapped by the client entity but is not reachable from scripts.animate. It may be intentionally invoked by external/dynamic logic.")

    severity_counts = defaultdict(int)
    for finding in findings:
        severity_counts[finding["severity"]] += 1
    error_count = severity_counts["HIGH"] + severity_counts["MEDIUM"]
    status = "valid" if error_count == 0 and complete else ("partial" if not complete else "issues_found")
    return {
        "status": status,
        "analysis_complete": bool(complete),
        "scan_bytes_read_budget_used": scan_budget[0],
        "project_directory": str(project),
        "target_entity_identifier": entity_identifier,
        "client_entity_file": entity_rel,
        "inventory": {
            "animation_files_scanned": len(anim_paths),
            "animation_files_parsed": animation_files_parsed,
            "animation_definitions": sum(len(v) for v in animation_index.values()),
            "controller_files_scanned": len(controller_paths),
            "controller_files_parsed": controller_files_parsed,
            "controller_definitions": sum(len(v) for v in controller_index.values()),
            "controller_states": controller_state_count,
            "controller_transitions": controller_transition_count,
            "geometry_files_scanned": len(geometry_paths),
            "geometry_files_parsed": geometry_files_parsed,
            "geometry_definitions": sum(len(v) for v in geometry_index.values()),
            "entity_animation_aliases": len(animations_map),
            "resolved_animation_aliases": sum(1 for x in alias_targets.values() if x[0] == "animation"),
            "resolved_controller_aliases": sum(1 for x in alias_targets.values() if x[0] == "controller"),
            "entity_geometry_aliases": len(geometry_map),
            "resolved_geometry_aliases": len(resolved_geometries),
            "scripts_animate_entries": len(scripts_animate_aliases),
        },
        "severity_counts": dict(sorted(severity_counts.items())),
        "findings": findings,
        "molang_validation": "NOT PARSED OR EXECUTED",
        "runtime_status": "NOT RUN",
        "note": "Static cross-resource analysis only. Dynamic identifiers, external vanilla resources, Molang semantics, rendering, interpolation, state timing and Minecraft runtime behavior are not executed or proven.",
        "mcp_server_version": SERVER_VERSION,
    }


def _validate_args(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("arguments must be an object")
    extra = set(raw) - {"project_directory", "client_entity_file"}
    missing = {"project_directory", "client_entity_file"} - set(raw)
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    project = raw["project_directory"]
    entity = raw["client_entity_file"]
    if not isinstance(project, str) or not isinstance(entity, str):
        raise ValueError("project_directory and client_entity_file must be strings")
    if not 1 <= len(project) <= 63 or not 1 <= len(entity) <= 240:
        raise ValueError("project_directory or client_entity_file length is invalid")
    if not _PROJECT.fullmatch(project) or "--" in project:
        raise ValueError("project_directory must be lowercase kebab-case")
    return {"project_directory": project, "client_entity_file": entity}


def call_tool(name: str, raw_args: Any) -> dict[str, Any]:
    if name != "audit_entity_animation_pipeline":
        return {"status": "error", "error": {"code": "UNKNOWN_TOOL", "message": f"unknown tool: {name}"}}
    try:
        return _audit(_validate_args(raw_args))
    except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "error", "error": {"code": "INVALID_OR_UNSAFE_PROJECT", "message": str(exc)}}
    except Exception as exc:  # Do not leak tracebacks to MCP clients.
        return {"status": "error", "error": {"code": "INTERNAL_ERROR", "message": f"unexpected {type(exc).__name__}: {exc}"}}


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
            "serverInfo": {"name": "minecraft-bedrock-animation-pipeline-audit", "version": SERVER_VERSION},
            "instructions": WORKFLOW_INSTRUCTIONS,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        result = call_tool(name, args) if isinstance(name, str) else {"status": "error", "error": {"code": "INVALID_ARGUMENT", "message": "tool name must be a string"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, separators=(",", ":"))}],
            "structuredContent": result,
            "isError": result.get("status") == "error",
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
