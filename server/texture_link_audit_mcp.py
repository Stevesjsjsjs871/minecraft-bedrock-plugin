#!/usr/bin/env python3
"""Read-only Bedrock BP/RP texture-link auditor exposed as a stdio MCP server.

Checks the static dependency chain from BP block/item definitions, through the
correct RP atlas, to the actual PNG files. It never modifies a project.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
from png_validation import validate_png_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
try:
    SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

PROJECT_NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_ATLAS_BYTES = 8 * 1024 * 1024
MAX_PNG_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 16_777_216
MAX_DEFINITION_FILES = 5000
MAX_ATLAS_ENTRIES = 5000
MAX_UNIQUE_PNG_FILES = 2000
MAX_TOTAL_PNG_BYTES = 128 * 1024 * 1024


class DuplicateJsonKey(ValueError):
    pass


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKey(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _tool() -> dict[str, Any]:
    return {
        "name": "audit_texture_links",
        "description": (
            "Read-only audit of a Minecraft Bedrock project's texture dependency chain. Scans the project's "
            "Behavior Pack block and item JSON, checks minecraft:material_instances and minecraft:icon "
            "references against the matching Resource Pack terrain/item atlas, then validates the referenced PNG "
            "image stream: chunk order/CRCs, legal IHDR metadata, bounded zlib decompression, exact scanline "
            "lengths/filters and Adam7 layout. Reports missing atlas keys, malformed JSON, broken PNG streams, "
            "unsafe paths and unused atlas entries. Caches repeated PNG paths and enforces atlas-entry, unique-file "
            "and aggregate-byte budgets; the result states whether analysis was complete. It never writes files. "
            "Static analysis only; Minecraft runtime remains NOT RUN."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 63,
                    "description": "One existing project directory directly inside MINECRAFT_BEDROCK_WORKSPACE, e.g. ruby-addon.",
                }
            },
            "required": ["project_directory"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


TOOLS = [_tool()]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def _validate_arguments(name: str, raw_args: Any) -> dict[str, str]:
    if name not in TOOL_BY_NAME:
        raise ValueError(f"unknown tool {name!r}")
    if not isinstance(raw_args, dict):
        raise ValueError("arguments must be a JSON object")
    extras = set(raw_args) - {"project_directory"}
    if extras:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extras))}")
    value = raw_args.get("project_directory")
    if not isinstance(value, str) or not value or len(value) > 63:
        raise ValueError("project_directory must be a non-empty string of at most 63 characters")
    if not PROJECT_NAME_RE.fullmatch(value) or "--" in value:
        raise ValueError("project_directory must be one lowercase kebab-case directory name, not a path")
    return {"project_directory": value}


def _workspace_root() -> Path:
    raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    base = Path(raw).expanduser() if raw else Path.cwd()
    try:
        resolved = base.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"configured workspace does not exist: {base}") from exc
    if not resolved.is_dir():
        raise ValueError("configured workspace must be a directory")
    return resolved


def _resolve_project(project_name: str) -> tuple[Path, Path, Path, Path]:
    workspace = _workspace_root()
    candidate = workspace / project_name
    if candidate.is_symlink():
        raise ValueError("project_directory must not be a symlink")
    try:
        project = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"project_directory is unavailable: {project_name}") from exc
    if project.parent != workspace or not project.is_dir():
        raise ValueError("project_directory must be an existing real directory directly under the configured workspace")

    pack_paths: list[Path] = []
    for container_name, pack_name in (
        ("behavior_packs", f"{project_name}_BP"),
        ("resource_packs", f"{project_name}_RP"),
    ):
        container = project / container_name
        pack = container / pack_name
        if container.is_symlink() or pack.is_symlink():
            raise ValueError(f"{container_name}/{pack_name} contains a symlink; refusing to audit outside the project")
        try:
            resolved_container = container.resolve(strict=True)
            resolved_pack = pack.resolve(strict=True)
            resolved_container.relative_to(project)
            resolved_pack.relative_to(resolved_container)
        except (OSError, ValueError) as exc:
            raise ValueError(f"expected {container_name}/{pack_name} must exist inside the selected project") from exc
        if not resolved_container.is_dir() or not resolved_pack.is_dir():
            raise ValueError(f"expected {container_name}/{pack_name} must be a directory")
        manifest = resolved_pack / "manifest.json"
        if manifest.is_symlink() or not manifest.is_file():
            raise ValueError(f"{container_name}/{pack_name}/manifest.json is missing or unsafe")
        pack_paths.append(resolved_pack)
    return workspace, project, pack_paths[0], pack_paths[1]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return "<outside-project>"


def _read_json(path: Path, *, max_bytes: int) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError("path is not a regular non-symlink file")
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"JSON file exceeds the {max_bytes}-byte safety limit")
    raw = path.read_bytes()
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateJsonKey) as exc:
        raise ValueError(str(exc)) from exc


def _walk_json_files(root: Path, project: Path, findings: list[dict[str, str]]) -> list[Path]:
    results: list[Path] = []
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        safe_dirs: list[str] = []
        for name in sorted(dirs):
            candidate = current_path / name
            if candidate.is_symlink():
                findings.append({
                    "severity": "error", "code": "UNSAFE_DEFINITION_DIRECTORY",
                    "path": _relative(candidate, project),
                    "message": "symlinked definition directory was skipped",
                })
            else:
                safe_dirs.append(name)
        dirs[:] = safe_dirs
        for name in sorted(files):
            if not name.lower().endswith(".json"):
                continue
            candidate = current_path / name
            if candidate.is_symlink():
                findings.append({
                    "severity": "error", "code": "UNSAFE_DEFINITION_FILE",
                    "path": _relative(candidate, project),
                    "message": "symlinked definition file was skipped",
                })
                continue
            results.append(candidate)
            if len(results) > MAX_DEFINITION_FILES:
                findings.append({
                    "severity": "error", "code": "DEFINITION_SCAN_LIMIT",
                    "path": _relative(root, project),
                    "message": f"definition scan exceeded the {MAX_DEFINITION_FILES}-file limit; results may be incomplete",
                })
                return results[:MAX_DEFINITION_FILES]
    return results


def _png_header(path: Path) -> tuple[int, int]:
    """Fully validate the PNG image stream and return its dimensions."""
    return validate_png_file(
        path,
        max_bytes=MAX_PNG_BYTES,
        max_dimension=MAX_DIMENSION,
        max_pixels=MAX_PIXELS,
    )


def _atlas_texture_values(value: Any) -> list[str]:
    if not isinstance(value, dict) or "textures" not in value:
        raise ValueError("atlas entry must be an object containing 'textures'")
    textures = value["textures"]
    if isinstance(textures, str):
        values = [textures]
    elif isinstance(textures, list) and textures and all(isinstance(item, str) for item in textures):
        values = textures
    else:
        raise ValueError("atlas 'textures' must be a non-empty string or array of strings")
    if any(not item for item in values):
        raise ValueError("atlas texture paths must not be empty")
    return values


def _resolve_atlas_texture(rp_root: Path, reference: str) -> Path:
    if "\\" in reference or "\x00" in reference or reference.startswith("/") or re.match(r"^[A-Za-z]:", reference):
        raise ValueError("atlas texture path must be relative POSIX form")
    value = reference[:-4] if reference.endswith(".png") else reference
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts) or parts[0] != "textures":
        raise ValueError("atlas texture path must start with textures/ and contain no traversal segments")
    if len(parts) < 3:
        raise ValueError("atlas texture path must include a texture category and filename")
    candidate = rp_root.joinpath(*parts)
    current = rp_root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("atlas texture path contains a symlink")
    png = candidate if candidate.suffix.lower() == ".png" else candidate.with_suffix(".png")
    try:
        resolved = png.resolve(strict=True)
        resolved.relative_to(rp_root)
    except (OSError, ValueError) as exc:
        raise ValueError("referenced PNG is missing or resolves outside the Resource Pack") from exc
    if resolved.suffix.lower() != ".png":
        raise ValueError("atlas path does not resolve to a PNG file")
    return resolved


def _find_material_texture_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        texture = value.get("texture")
        if isinstance(texture, str) and texture:
            refs.append(texture)
        elif "texture" in value:
            # A malformed material entry is surfaced later as an unresolved reference.
            refs.append("")
        for key, child in value.items():
            if key != "texture":
                refs.extend(_find_material_texture_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_find_material_texture_refs(child))
    return refs


def _find_icon_refs(icon: Any) -> list[str]:
    if isinstance(icon, str):
        return [icon] if icon else [""]
    if not isinstance(icon, dict):
        return [""]
    refs: list[str] = []
    texture = icon.get("texture")
    if isinstance(texture, str) and texture:
        refs.append(texture)
    elif "texture" in icon:
        refs.append("")
    textures = icon.get("textures")
    if isinstance(textures, dict):
        for value in textures.values():
            if isinstance(value, str) and value:
                refs.append(value)
            else:
                refs.append("")
    elif textures is not None:
        refs.append("")
    if not refs:
        refs.append("")
    return refs


def _definition_refs(
    files: list[Path], *, kind: str, project: Path, findings: list[dict[str, str]]
) -> tuple[list[dict[str, str]], int]:
    references: list[dict[str, str]] = []
    recognized = 0
    expected_root = "minecraft:block" if kind == "blocks" else "minecraft:item"
    component_key = "minecraft:material_instances" if kind == "blocks" else "minecraft:icon"
    for path in files:
        relative = _relative(path, project)
        try:
            data = _read_json(path, max_bytes=MAX_JSON_BYTES)
        except (OSError, ValueError) as exc:
            findings.append({"severity": "error", "code": "INVALID_DEFINITION_JSON", "path": relative, "message": str(exc)})
            continue
        if not isinstance(data, dict) or not isinstance(data.get(expected_root), dict):
            findings.append({"severity": "warning", "code": "UNRECOGNIZED_DEFINITION", "path": relative, "message": f"JSON file does not contain an object-valued {expected_root} root; texture references were not inspected"})
            continue
        definition = data[expected_root]
        components = definition.get("components")
        if not isinstance(components, dict) or component_key not in components:
            continue
        recognized += 1
        component = components[component_key]
        refs = _find_material_texture_refs(component) if kind == "blocks" else _find_icon_refs(component)
        identifier = definition.get("description", {}).get("identifier") if isinstance(definition.get("description"), dict) else None
        for texture_key in refs:
            references.append({
                "kind": kind,
                "definition": relative,
                "identifier": identifier if isinstance(identifier, str) else "",
                "texture_key": texture_key,
            })
    return references, recognized


def audit_texture_links(raw_args: Any) -> dict[str, Any]:
    args = _validate_arguments("audit_texture_links", raw_args)
    project_name = args["project_directory"]
    _, project, bp_root, rp_root = _resolve_project(project_name)
    findings: list[dict[str, str]] = []

    blocks_root = bp_root / "blocks"
    items_root = bp_root / "items"
    if blocks_root.is_symlink():
        findings.append({"severity": "error", "code": "UNSAFE_DEFINITION_DIRECTORY", "path": _relative(blocks_root, project), "message": "Behavior Pack blocks root is a symlink and was not scanned"})
    if items_root.is_symlink():
        findings.append({"severity": "error", "code": "UNSAFE_DEFINITION_DIRECTORY", "path": _relative(items_root, project), "message": "Behavior Pack items root is a symlink and was not scanned"})
    block_files = _walk_json_files(blocks_root, project, findings) if blocks_root.is_dir() and not blocks_root.is_symlink() else []
    item_files = _walk_json_files(items_root, project, findings) if items_root.is_dir() and not items_root.is_symlink() else []
    if not blocks_root.is_dir() and not blocks_root.is_symlink():
        findings.append({"severity": "warning", "code": "BLOCK_DEFINITION_FOLDER_MISSING", "path": _relative(blocks_root, project), "message": "Behavior Pack blocks folder is missing"})
    if not items_root.is_dir() and not items_root.is_symlink():
        findings.append({"severity": "warning", "code": "ITEM_DEFINITION_FOLDER_MISSING", "path": _relative(items_root, project), "message": "Behavior Pack items folder is missing"})

    block_refs, block_definitions = _definition_refs(block_files, kind="blocks", project=project, findings=findings)
    item_refs, item_definitions = _definition_refs(item_files, kind="items", project=project, findings=findings)
    references = block_refs + item_refs

    atlas_data: dict[str, dict[str, Any]] = {}
    textures_root = rp_root / "textures"
    atlas_paths = {
        "blocks": textures_root / "terrain_texture.json",
        "items": textures_root / "item_texture.json",
    }
    # A project can intentionally reuse one PNG from multiple atlas keys. Cache
    # both successful and failed validations so repeated references do not
    # multiply disk reads or decompression work.
    png_validation_cache: dict[str, tuple[int, int] | str] = {}
    png_bytes_inspected = 0
    atlas_keys_checked = 0
    incomplete_codes = {
        "UNSAFE_DEFINITION_DIRECTORY", "UNSAFE_DEFINITION_FILE", "DEFINITION_SCAN_LIMIT",
        "BLOCK_DEFINITION_FOLDER_MISSING", "ITEM_DEFINITION_FOLDER_MISSING", "UNSAFE_TEXTURES_DIRECTORY",
        "INVALID_DEFINITION_JSON", "INVALID_ATLAS_JSON", "INVALID_ATLAS_SHAPE", "INVALID_ATLAS_ENTRY", "ATLAS_MISSING",
    }
    analysis_complete = not any(item["code"] in incomplete_codes for item in findings)
    validated_atlas_keys: dict[str, set[str]] = {"blocks": set(), "items": set()}
    if textures_root.is_symlink() or not textures_root.is_dir():
        findings.append({
            "severity": "error", "code": "UNSAFE_TEXTURES_DIRECTORY",
            "path": _relative(textures_root, project),
            "message": "Resource Pack textures directory is missing or is a symlink; atlas files were not read",
        })
    atlas_entries: dict[str, dict[str, Any]] = {"blocks": {}, "items": {}}
    for kind, atlas_path in atlas_paths.items():
        relative = _relative(atlas_path, project)
        if textures_root.is_symlink() or not textures_root.is_dir():
            continue
        if atlas_path.is_symlink():
            findings.append({"severity": "error", "code": "UNSAFE_ATLAS_PATH", "path": relative, "message": "atlas file is a symlink"})
            continue
        if not atlas_path.exists():
            findings.append({"severity": "warning", "code": "ATLAS_MISSING", "path": relative, "message": f"{kind} texture atlas does not exist"})
            continue
        try:
            atlas = _read_json(atlas_path, max_bytes=MAX_ATLAS_BYTES)
        except (OSError, ValueError) as exc:
            findings.append({"severity": "error", "code": "INVALID_ATLAS_JSON", "path": relative, "message": str(exc)})
            continue
        expected_name = "atlas.terrain" if kind == "blocks" else "atlas.items"
        if not isinstance(atlas, dict) or atlas.get("texture_name") != expected_name or not isinstance(atlas.get("texture_data"), dict):
            findings.append({"severity": "error", "code": "INVALID_ATLAS_SHAPE", "path": relative, "message": f"atlas must contain texture_name={expected_name!r} and an object-valued texture_data"})
            continue
        atlas_entries[kind] = atlas["texture_data"]
        atlas_data[kind] = atlas
        all_entries = sorted(atlas_entries[kind].items(), key=lambda item: item[0])
        if len(all_entries) > MAX_ATLAS_ENTRIES:
            analysis_complete = False
            findings.append({
                "severity": "error", "code": "ATLAS_ENTRY_SCAN_LIMIT", "path": relative,
                "message": f"atlas has {len(all_entries)} entries; only the first {MAX_ATLAS_ENTRIES} are deeply validated",
            })
        entries_to_check = all_entries[:MAX_ATLAS_ENTRIES]
        for key, entry in entries_to_check:
            atlas_keys_checked += 1
            try:
                values = _atlas_texture_values(entry)
            except ValueError as exc:
                findings.append({"severity": "error", "code": "INVALID_ATLAS_ENTRY", "path": relative, "message": f"texture_data[{key!r}]: {exc}"})
                continue
            key_is_valid = True
            for value in values:
                try:
                    png_path = _resolve_atlas_texture(rp_root, value)
                    cache_key = str(png_path)
                    cached = png_validation_cache.get(cache_key)
                    if cached is None:
                        cache_result = True
                        if len(png_validation_cache) >= MAX_UNIQUE_PNG_FILES:
                            analysis_complete = False
                            cached = f"unique PNG inspection limit ({MAX_UNIQUE_PNG_FILES}) reached"
                            cache_result = False
                        else:
                            file_size = png_path.stat().st_size
                            if png_bytes_inspected + file_size > MAX_TOTAL_PNG_BYTES:
                                analysis_complete = False
                                cached = f"aggregate PNG byte inspection limit ({MAX_TOTAL_PNG_BYTES}) reached"
                            else:
                                png_bytes_inspected += file_size
                                try:
                                    cached = _png_header(png_path)
                                except (OSError, ValueError) as exc:
                                    cached = str(exc)
                        if cache_result:
                            png_validation_cache[cache_key] = cached
                    if isinstance(cached, str):
                        key_is_valid = False
                        findings.append({"severity": "error", "code": "BROKEN_ATLAS_TEXTURE", "path": relative, "message": f"texture_data[{key!r}] -> {value!r}: {cached}"})
                        continue
                    width, height = cached
                except (OSError, ValueError) as exc:
                    key_is_valid = False
                    findings.append({"severity": "error", "code": "BROKEN_ATLAS_TEXTURE", "path": relative, "message": f"texture_data[{key!r}] -> {value!r}: {exc}"})
                    continue
                findings.append({"severity": "info", "code": "ATLAS_TEXTURE_OK", "path": _relative(png_path, project), "message": f"atlas key {key!r} resolves to a PNG ({width}x{height})"})
            if key_is_valid:
                validated_atlas_keys[kind].add(key)

    used_keys: dict[str, set[str]] = {"blocks": set(), "items": set()}
    for ref in references:
        kind = ref["kind"]
        key = ref["texture_key"]
        atlas_path = _relative(atlas_paths[kind], project)
        if not key:
            findings.append({"severity": "error", "code": "INVALID_TEXTURE_REFERENCE", "path": ref["definition"], "message": f"{kind} definition {ref['identifier']!r} has a missing or non-string texture reference"})
        elif key not in atlas_entries[kind]:
            findings.append({"severity": "error", "code": "MISSING_ATLAS_KEY", "path": ref["definition"], "message": f"{kind} definition {ref['identifier']!r} references {key!r}, but {atlas_path} has no matching texture_data key"})
        else:
            used_keys[kind].add(key)
            if key in validated_atlas_keys[kind]:
                findings.append({"severity": "info", "code": "TEXTURE_LINK_OK", "path": ref["definition"], "message": f"{kind} definition {ref['identifier']!r} references validated atlas key {key!r}"})
            else:
                analysis_complete = False
                findings.append({"severity": "warning", "code": "ATLAS_KEY_NOT_VALIDATED", "path": ref["definition"], "message": f"{kind} definition {ref['identifier']!r} references atlas key {key!r}, but its PNG entry was not fully validated because of an atlas/PNG inspection limit or an invalid atlas entry"})

    for kind in ("blocks", "items"):
        keys_for_unused_check = sorted(atlas_entries[kind])[:MAX_ATLAS_ENTRIES]
        for key in keys_for_unused_check:
            if key not in used_keys[kind]:
                findings.append({
                    "severity": "warning", "code": "UNUSED_ATLAS_ENTRY",
                    "path": _relative(atlas_paths[kind], project),
                    "message": f"atlas entry {key!r} was not referenced by scanned BP {kind} definitions; it may be intentionally shared or dynamically referenced",
                })

    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    info = sum(item["severity"] == "info" for item in findings)
    return {
        "status": "issues_found" if errors else "completed",
        "project_directory": project_name,
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
        "summary": {
            "block_json_files": len(block_files),
            "item_json_files": len(item_files),
            "block_definitions_with_material_instances": block_definitions,
            "item_definitions_with_icons": item_definitions,
            "block_texture_references": len(block_refs),
            "item_texture_references": len(item_refs),
            "terrain_atlas_entries": len(atlas_entries["blocks"]),
            "item_atlas_entries": len(atlas_entries["items"]),
            "atlas_keys_checked": atlas_keys_checked,
            "unique_png_files_inspected": len(png_validation_cache),
            "png_bytes_inspected": png_bytes_inspected,
            "analysis_complete": analysis_complete,
            "errors": errors,
            "warnings": warnings,
            "informational_findings": info,
        },
        "references": references,
        "findings": findings,
        "scope_note": "Audits BP block/item material and icon links to matching RP atlases and deeply validates PNG image streams. analysis_complete=false means a safety scan budget or an unsafe/missing scan directory prevented full coverage. It does not infer runtime-only texture usage or validate rendering in Minecraft.",
    }


def _tool_result(request_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
            "structuredContent": payload,
            "isError": payload.get("status") == "error",
        },
    }


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid JSON-RPC request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {})
    if not isinstance(method, str) or not isinstance(params, dict):
        return _jsonrpc_error(request_id, -32600, "Invalid method or params")
    if "id" not in message:
        return None
    if method == "initialize":
        requested = params.get("protocolVersion", "2024-11-05")
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": requested,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-texture-link-auditor", "version": SERVER_VERSION},
            "instructions": "Use audit_texture_links on an existing Minecraft Bedrock Engineer BP/RP project. The auditor reads block/item definitions, both RP atlases and referenced PNG files without changing any project files. Minecraft runtime remains NOT RUN.",
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str):
            return _jsonrpc_error(request_id, -32602, "tools/call requires a string name")
        if name not in TOOL_BY_NAME:
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = audit_texture_links(arguments)
        except ValueError as exc:
            payload = _error("INVALID_ARGUMENT", str(exc))
        except OSError as exc:
            payload = _error("AUDIT_IO_ERROR", f"could not inspect project safely: {exc}")
        except Exception as exc:  # Keep protocol output structured and traceback-free.
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
