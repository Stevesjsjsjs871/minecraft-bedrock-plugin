#!/usr/bin/env python3
"""Safe stdio MCP server for Bedrock animation-controller authoring and validation."""
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
_STATE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_ALIAS = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_IDENTIFIER = re.compile(r"^controller\.animation\.[a-z0-9_.-]+$")
_MAX_CONTROLLER_FILES = 500
_MAX_JSON_BYTES = 2 * 1024 * 1024
_MAX_STATES = 32
_MAX_TRANSITIONS_PER_STATE = 16
_MAX_ANIMATIONS_PER_STATE = 16
_MAX_MOLANG_LENGTH = 512


def _schema_tool(name: str, description: str, properties: dict[str, Any], required: list[str], *, read_only: bool) -> dict[str, Any]:
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


_STATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name"],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 32},
        "animations": {"type": "array", "maxItems": _MAX_ANIMATIONS_PER_STATE, "items": {"type": "string", "minLength": 1, "maxLength": 64}},
        "transitions": {
            "description": "Preferred: ordered array of single-key target/condition objects, matching Bedrock transition priority. Legacy object maps are also accepted for compatibility.",
            "anyOf": [
                {
                    "type": "array",
                    "maxItems": _MAX_TRANSITIONS_PER_STATE,
                    "items": {
                        "type": "object",
                        "minProperties": 1,
                        "maxProperties": 1,
                        "additionalProperties": {"type": "string", "minLength": 1, "maxLength": _MAX_MOLANG_LENGTH}
                    }
                },
                {
                    "type": "object",
                    "maxProperties": _MAX_TRANSITIONS_PER_STATE,
                    "additionalProperties": {"type": "string", "minLength": 1, "maxLength": _MAX_MOLANG_LENGTH}
                }
            ]
        },
        "on_entry": {"type": "array", "maxItems": 16, "items": {"type": "string", "minLength": 1, "maxLength": _MAX_MOLANG_LENGTH}},
        "on_exit": {"type": "array", "maxItems": 16, "items": {"type": "string", "minLength": 1, "maxLength": _MAX_MOLANG_LENGTH}},
        "blend_transition": {"type": "number", "minimum": 0, "maximum": 10},
    },
}

TOOLS = [
    _schema_tool(
        "create_animation_controller",
        "Create a Bedrock animation controller in an existing linked BP/RP scaffold and bind it to an existing RP client-entity JSON. States may select existing entity animation aliases, transition conditions are Molang expressions, and existing entity data is preserved. Refuses collisions, malformed JSON, unresolved animation aliases, unsafe paths and unlinked manifests. Static validation only; Molang execution and Minecraft runtime remain NOT RUN.",
        {
            "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
            "target_game_version": {"type": "string", "minLength": 5, "maxLength": 20},
            "controller_slug": {"type": "string", "minLength": 2, "maxLength": 48, "description": "Lowercase snake_case controller filename suffix."},
            "client_entity_file": {"type": "string", "minLength": 1, "maxLength": 240, "description": "RP-relative path to an existing client-entity JSON, e.g. entity/forest_guardian.entity.json."},
            "animation_alias": {"type": "string", "minLength": 1, "maxLength": 64, "description": "Alias added to description.animations and scripts.animate; defaults to controller_slug."},
            "controller_identifier": {"type": "string", "minLength": 20, "maxLength": 160, "description": "Optional identifier; defaults to controller.animation.<project_namespace>.<controller_slug>."},
            "initial_state": {"type": "string", "minLength": 1, "maxLength": 32},
            "states": {"type": "array", "minItems": 1, "maxItems": _MAX_STATES, "items": _STATE_SCHEMA},
            "animate_condition": {"type": "string", "minLength": 1, "maxLength": _MAX_MOLANG_LENGTH, "description": "Optional Molang condition. When omitted, scripts.animate always evaluates the controller alias."},
        },
        ["project_directory", "target_game_version", "controller_slug", "client_entity_file", "initial_state", "states"],
        read_only=False,
    ),
    _schema_tool(
        "validate_animation_controller",
        "Read-only structural and client-entity linkage check for an existing Bedrock animation controller. Checks states, initial state, transition targets and Molang text shape, animation aliases, controller binding and scripts.animate registration. Does not execute Molang or prove engine runtime behavior.",
        {
            "project_directory": {"type": "string", "minLength": 1, "maxLength": 63},
            "controller_file": {"type": "string", "minLength": 1, "maxLength": 240, "description": "RP-relative controller JSON path, e.g. animation_controllers/forest_guardian.animation_controllers.json."},
            "client_entity_file": {"type": "string", "minLength": 1, "maxLength": 240},
            "animation_alias": {"type": "string", "minLength": 1, "maxLength": 64},
        },
        ["project_directory", "controller_file", "client_entity_file", "animation_alias"],
        read_only=True,
    ),
]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}
WORKFLOW_INSTRUCTIONS = (
    "Animation controller workflow: create_animation_controller creates a new RP controller and links it to an existing RP client entity. "
    "State animation names must be aliases already mapped in client_entity.description.animations. "
    "Prefer ordered transition arrays to preserve Bedrock transition priority; legacy object maps remain accepted. validate_animation_controller checks static structure and linkage only. "
    "Do not claim Molang execution or in-game animation behavior was tested."
)


def _error(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "error": {"code": code, "message": message}}


def _json_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


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
    for path, label in ((resolved / "behavior_packs", "BP pack container"), (bp_root, "BP"), (bp_root / "entities", "BP entities"), (resolved / "resource_packs", "RP pack container"), (rp_root, "RP"), (rp_root / "entity", "RP entity"), (rp_root / "animation_controllers", "RP animation controllers")):
        _assert_safe_directory(path, resolved, label)
    bp_manifest = _read_manifest(bp_root / "manifest.json", "BP")
    rp_manifest = _read_manifest(rp_root / "manifest.json", "RP")
    bp_uuid = bp_manifest["header"].get("uuid")
    rp_uuid = rp_manifest["header"].get("uuid")
    bp_types = {x.get("type") for x in bp_manifest["modules"] if isinstance(x, dict)}
    rp_types = {x.get("type") for x in rp_manifest["modules"] if isinstance(x, dict)}
    dependencies = bp_manifest.get("dependencies", [])
    linked = isinstance(dependencies, list) and any(isinstance(d, dict) and d.get("uuid") == rp_uuid for d in dependencies)
    if not isinstance(bp_uuid, str) or not isinstance(rp_uuid, str) or "data" not in bp_types or "resources" not in rp_types or not linked:
        raise ValueError("project manifests are not a linked Behavior Pack/Resource Pack scaffold")
    return resolved, bp_root, rp_root


def _read_manifest(path: Path, label: str) -> dict[str, Any]:
    data = _load_json(path, f"{label} manifest")
    if not isinstance(data.get("header"), dict) or not isinstance(data.get("modules"), list):
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


def _safe_rp_file(rp_root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative or relative.startswith("/") or re.match(r"^[A-Za-z]:", relative):
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
        path.resolve(strict=False).relative_to(rp_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} escapes the RP") from exc
    return path


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


def _check_version(version: Any) -> None:
    if not isinstance(version, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", version):
        raise ValueError("target_game_version must be a three-part numeric version, for example 1.26.50")


def _validate_molang(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_MOLANG_LENGTH or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} must be a non-empty Molang string of at most {_MAX_MOLANG_LENGTH} printable characters")
    return value.strip()


def _validate_states(raw_states: Any, initial_state: Any, available_animation_aliases: set[str]) -> tuple[dict[str, Any], int, int, list[str]]:
    if not isinstance(raw_states, list) or not 1 <= len(raw_states) <= _MAX_STATES:
        raise ValueError(f"states must contain 1 to {_MAX_STATES} state objects")
    names: set[str] = set()
    clean: dict[str, Any] = {}
    animation_aliases: set[str] = set()
    transition_count = 0
    molang_count = 0

    for index, raw in enumerate(raw_states):
        label = f"states[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{label} must be an object")
        allowed = {"name", "animations", "transitions", "on_entry", "on_exit", "blend_transition"}
        extra = set(raw) - allowed
        if extra:
            raise ValueError(f"{label} has unsupported fields: {', '.join(sorted(extra))}")
        name = raw.get("name")
        if not isinstance(name, str) or not _STATE.fullmatch(name):
            raise ValueError(f"{label}.name must be lowercase snake_case state text")
        if name in names:
            raise ValueError(f"duplicate animation controller state: {name}")
        names.add(name)
        state: dict[str, Any] = {}

        animations = raw.get("animations", [])
        if not isinstance(animations, list) or len(animations) > _MAX_ANIMATIONS_PER_STATE:
            raise ValueError(f"{label}.animations must be an array with at most {_MAX_ANIMATIONS_PER_STATE} aliases")
        for alias in animations:
            if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
                raise ValueError(f"{label}.animations entries must be animation aliases")
            if alias not in available_animation_aliases:
                raise ValueError(f"animation alias {alias!r} is not defined in the linked client entity")
        if animations:
            state["animations"] = list(animations)
            animation_aliases.update(animations)

        # Prefer an ordered array so transition priority is explicit. Keep the
        # original object-map shorthand for backward compatibility with 1.1.1 callers.
        transitions = raw.get("transitions", [])
        if isinstance(transitions, dict):
            transition_items = list(transitions.items())
        elif isinstance(transitions, list):
            transition_items = []
            for transition_index, entry in enumerate(transitions):
                if not isinstance(entry, dict) or len(entry) != 1:
                    raise ValueError(f"{label}.transitions[{transition_index}] must contain exactly one target state")
                transition_items.append(next(iter(entry.items())))
        else:
            raise ValueError(f"{label}.transitions must be an ordered array or an object map")
        if len(transition_items) > _MAX_TRANSITIONS_PER_STATE:
            raise ValueError(f"{label}.transitions must contain at most {_MAX_TRANSITIONS_PER_STATE} entries")
        if transition_items:
            state_transitions = []
            for target, condition in transition_items:
                if not isinstance(target, str) or not _STATE.fullmatch(target):
                    raise ValueError(f"{label}.transitions contains an invalid target state name")
                expression = _validate_molang(condition, f"{label}.transitions.{target}")
                state_transitions.append({target: expression})
            state["transitions"] = state_transitions
            transition_count += len(state_transitions)
            molang_count += len(state_transitions)

        for field in ("on_entry", "on_exit"):
            values = raw.get(field, [])
            if not isinstance(values, list) or len(values) > 16:
                raise ValueError(f"{label}.{field} must be an array with at most 16 Molang commands")
            if values:
                state[field] = [_validate_molang(value, f"{label}.{field}[{i}]") for i, value in enumerate(values)]
                molang_count += len(values)

        if "blend_transition" in raw:
            value = raw["blend_transition"]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 10:
                raise ValueError(f"{label}.blend_transition must be a finite number from 0 to 10")
            state["blend_transition"] = float(value)
        clean[name] = state

    if not isinstance(initial_state, str) or not _STATE.fullmatch(initial_state) or initial_state not in names:
        raise ValueError("initial_state must match one of the declared state names")
    for state_name, state in clean.items():
        for transition in state.get("transitions", []):
            target = next(iter(transition))
            if target not in names:
                raise ValueError(f"state {state_name!r} transitions to unknown state {target!r}")
    return clean, len(names), transition_count, sorted(animation_aliases)


def _check_identifier_unique(directory: Path, identifier: str) -> None:
    entries = sorted(directory.glob("*.json"))
    if len(entries) > _MAX_CONTROLLER_FILES:
        raise ValueError(f"RP animation_controllers contains more than {_MAX_CONTROLLER_FILES} JSON files; cannot safely check identifier uniqueness")
    for entry in entries:
        if entry.is_symlink() or not entry.is_file() or entry.stat().st_size > _MAX_JSON_BYTES:
            raise ValueError(f"existing animation controller file is unsafe or oversized: {entry.name}")
        data = _load_json(entry, f"existing animation controller {entry.name}")
        definitions = data.get("animation_controllers")
        if isinstance(definitions, dict) and identifier in definitions:
            raise ValueError(f"animation controller identifier already exists in {entry.name}: {identifier}")


def _atomic_update_existing(path: Path, original: bytes, replacement: bytes) -> None:
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("xb") as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink() or not path.is_file() or path.read_bytes() != original:
            raise ValueError("client entity changed during controller creation; refusing to overwrite concurrent edits")
        os.replace(temp_path, path)
    finally:
        try:
            if temp_path.exists() and not temp_path.is_symlink():
                temp_path.unlink()
        except OSError:
            pass


def _create_controller(args: dict[str, Any]) -> dict[str, Any]:
    project, _bp_root, rp_root = _safe_project(args["project_directory"])
    client_path, client_original, client_data, description = _read_client_entity(rp_root, args["client_entity_file"])
    namespace = args["project_directory"].replace("-", "_")
    identifier = args.get("controller_identifier") or f"controller.animation.{namespace}.{args['controller_slug']}"
    if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
        raise ValueError("controller_identifier must look like controller.animation.namespace.name")
    alias = args.get("animation_alias", args["controller_slug"])
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise ValueError("animation_alias must be a simple client-entity alias")
    existing_animations = description.get("animations", {})
    if alias in existing_animations and existing_animations[alias] != identifier:
        raise ValueError(f"animation alias {alias!r} is already mapped to a different resource")
    available = {key for key, value in existing_animations.items() if isinstance(key, str) and isinstance(value, str) and key != alias}
    states, state_count, transition_count, referenced_aliases = _validate_states(args["states"], args["initial_state"], available)
    animate_condition = args.get("animate_condition")
    if animate_condition is not None:
        animate_condition = _validate_molang(animate_condition, "animate_condition")

    controller_data = {
        "format_version": "1.10.0",
        "animation_controllers": {
            identifier: {
                "initial_state": args["initial_state"],
                "states": states,
            }
        },
    }
    controller_path = rp_root / "animation_controllers" / f"{args['controller_slug']}.animation_controllers.json"
    if controller_path.is_symlink() or controller_path.exists():
        raise ValueError(f"controller output already exists or is a symlink; refusing to overwrite: {controller_path.relative_to(project).as_posix()}")
    _check_identifier_unique(controller_path.parent, identifier)

    scripts = description.setdefault("scripts", {})
    if not isinstance(scripts, dict):
        raise ValueError("client entity description.scripts must be an object")
    animate = scripts.setdefault("animate", [])
    if not isinstance(animate, list):
        raise ValueError("client entity description.scripts.animate must be an array")
    for item in animate:
        if isinstance(item, str) and item == alias:
            raise ValueError(f"client entity scripts.animate already contains alias {alias!r}")
        if isinstance(item, dict) and alias in item:
            raise ValueError(f"client entity scripts.animate already contains alias {alias!r}")
    description.setdefault("animations", {})[alias] = identifier
    animate_entry: Any = {alias: animate_condition} if animate_condition is not None else alias
    animate.append(animate_entry)

    controller_bytes = (json.dumps(controller_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    client_bytes = (json.dumps(client_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    created_controller = False
    client_updated = False
    try:
        with controller_path.open("xb") as stream:
            created_controller = True
            stream.write(controller_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        _atomic_update_existing(client_path, client_original, client_bytes)
        client_updated = True
    except Exception:
        if created_controller:
            try:
                if controller_path.is_file() and not controller_path.is_symlink():
                    controller_path.unlink()
            except OSError:
                pass
        if client_updated:
            try:
                _atomic_update_existing(client_path, client_bytes, client_original)
            except Exception:
                pass
        raise

    return {
        "status": "created",
        "project_directory": str(project),
        "client_entity_identifier": description["identifier"],
        "controller_identifier": identifier,
        "animation_alias": alias,
        "initial_state": args["initial_state"],
        "state_count": state_count,
        "transition_count": transition_count,
        "referenced_animation_aliases": referenced_aliases,
        "files_created": [controller_path.relative_to(project).as_posix()],
        "files_updated": [client_path.relative_to(project).as_posix()],
        "molang_expressions": transition_count + sum(len(state.get("on_entry", [])) + len(state.get("on_exit", [])) for state in states.values()) + (1 if animate_condition is not None else 0),
        "molang_validation": "TEXT SHAPE ONLY — EXPRESSIONS NOT EXECUTED",
        "target_game_version": args["target_game_version"],
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
        "note": "The controller is structurally generated and bound to the client entity. Existing animation aliases must resolve to real animation resources. Transition expressions and commands were not executed in Bedrock; in-game state transitions, blend behavior and rendering remain unverified.",
    }


def _validate_controller_file(project: Path, rp_root: Path, controller_file: str, client_entity_file: str, alias: str) -> dict[str, Any]:
    controller_path = _safe_rp_file(rp_root, controller_file, "controller_file")
    if not controller_file.startswith("animation_controllers/") or not controller_file.endswith(".json"):
        raise ValueError("controller_file must be inside RP animation_controllers/ and end with .json")
    controller = _load_json(controller_path, "animation controller file")
    definitions = controller.get("animation_controllers")
    if not isinstance(definitions, dict) or len(definitions) != 1:
        raise ValueError("animation controller file must contain exactly one animation_controllers definition")
    identifier, definition = next(iter(definitions.items()))
    if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier) or not isinstance(definition, dict):
        raise ValueError("animation controller definition has an invalid identifier or shape")
    client_path, _original, _client_data, description = _read_client_entity(rp_root, client_entity_file)
    animations = description.get("animations", {})
    scripts = description.get("scripts", {})
    animate = scripts.get("animate", []) if isinstance(scripts, dict) else []
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise ValueError("animation_alias must be a simple client-entity alias")
    if not isinstance(animations, dict) or animations.get(alias) != identifier:
        raise ValueError(f"client entity description.animations does not map {alias!r} to {identifier!r}")
    if not isinstance(animate, list) or not any((item == alias if isinstance(item, str) else isinstance(item, dict) and alias in item) for item in animate):
        raise ValueError(f"client entity scripts.animate does not reference alias {alias!r}")

    states_obj = definition.get("states")
    initial = definition.get("initial_state")
    if not isinstance(states_obj, dict) or not 1 <= len(states_obj) <= _MAX_STATES:
        raise ValueError("controller states must be an object with 1 to 32 states")
    if not isinstance(initial, str) or initial not in states_obj:
        raise ValueError("controller initial_state does not resolve to a declared state")
    referenced: set[str] = set()
    transitions = 0
    molang = 0
    for state_name, state in states_obj.items():
        if not isinstance(state_name, str) or not _STATE.fullmatch(state_name) or not isinstance(state, dict):
            raise ValueError("controller contains an invalid state name or state object")
        animations_list = state.get("animations", [])
        if not isinstance(animations_list, list):
            raise ValueError(f"state {state_name!r} animations must be an array")
        for value in animations_list:
            if not isinstance(value, str) or value not in animations:
                raise ValueError(f"state {state_name!r} references missing client-entity animation alias: {value!r}")
            referenced.add(value)
        state_transitions = state.get("transitions", [])
        if not isinstance(state_transitions, list):
            raise ValueError(f"state {state_name!r} transitions must be an array")
        for entry in state_transitions:
            if not isinstance(entry, dict) or len(entry) != 1:
                raise ValueError(f"state {state_name!r} contains a malformed transition")
            target, condition = next(iter(entry.items()))
            if target not in states_obj:
                raise ValueError(f"state {state_name!r} transitions to missing state {target!r}")
            _validate_molang(condition, f"state {state_name}.transitions.{target}")
            transitions += 1
            molang += 1
        for hook in ("on_entry", "on_exit"):
            commands = state.get(hook, [])
            if not isinstance(commands, list):
                raise ValueError(f"state {state_name!r} {hook} must be an array")
            for idx, command in enumerate(commands):
                _validate_molang(command, f"state {state_name}.{hook}[{idx}]")
                molang += 1
    return {
        "status": "valid",
        "controller_identifier": identifier,
        "initial_state": initial,
        "state_count": len(states_obj),
        "transition_count": transitions,
        "referenced_animation_aliases": sorted(referenced),
        "client_entity_identifier": description["identifier"],
        "animation_alias": alias,
        "molang_expressions_inspected": molang,
        "molang_validation": "TEXT SHAPE ONLY — EXPRESSIONS NOT EXECUTED",
        "runtime_status": "NOT RUN",
        "files_inspected": [controller_path.relative_to(project).as_posix(), client_path.relative_to(project).as_posix()],
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
    for key, value in raw.items():
        kind = properties[key].get("type")
        if kind == "string":
            if not isinstance(value, str) or not properties[key].get("minLength", 0) <= len(value) <= properties[key].get("maxLength", 4096):
                raise ValueError(f"{key} must be a string of valid length")
        elif kind == "array" and not isinstance(value, list):
            raise ValueError(f"{key} must be an array")
    normalized = dict(raw)
    if not _PROJECT.fullmatch(normalized["project_directory"]) or "--" in normalized["project_directory"]:
        raise ValueError("project_directory must be one lowercase kebab-case directory name")
    if name == "create_animation_controller":
        _check_version(normalized["target_game_version"])
        if not _SLUG.fullmatch(normalized["controller_slug"]) or len(normalized["controller_slug"]) > 48:
            raise ValueError("controller_slug must be lowercase snake_case and start with a letter")
        if normalized["client_entity_file"].startswith("../"):
            raise ValueError("client_entity_file cannot use parent-directory traversal")
        normalized.setdefault("animation_alias", normalized["controller_slug"])
        if not _STATE.fullmatch(normalized["initial_state"]):
            raise ValueError("initial_state must be a lowercase snake_case state name")
        if not isinstance(normalized["states"], list) or len(normalized["states"]) > _MAX_STATES:
            raise ValueError(f"states must contain 1 to {_MAX_STATES} states")
        if "animate_condition" in normalized:
            _validate_molang(normalized["animate_condition"], "animate_condition")
    else:
        if not normalized["controller_file"].startswith("animation_controllers/"):
            raise ValueError("controller_file must be inside animation_controllers/")
        if not normalized["client_entity_file"].startswith("entity/"):
            raise ValueError("client_entity_file must be inside entity/")
        if not _ALIAS.fullmatch(normalized["animation_alias"]):
            raise ValueError("animation_alias must be a simple client-entity alias")
    return normalized


def call_tool(name: str, raw_args: Any) -> dict[str, Any]:
    try:
        args = _validate_arguments(name, raw_args)
        if name == "create_animation_controller":
            return _create_controller(args)
        if name == "validate_animation_controller":
            project, _bp, rp = _safe_project(args["project_directory"])
            return _validate_controller_file(project, rp, args["controller_file"], args["client_entity_file"], args["animation_alias"])
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
            "serverInfo": {"name": "minecraft-bedrock-animation-controller-authoring", "version": SERVER_VERSION},
            "instructions": WORKFLOW_INSTRUCTIONS,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        payload = call_tool(name, args) if isinstance(name, str) else _error("INVALID_ARGUMENT", "tool name must be a string")
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
