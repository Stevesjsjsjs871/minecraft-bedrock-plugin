#!/usr/bin/env python3
"""Build a bounded, read-only dependency graph and report change impact.

Edges are directed from a consumer file to the file/resource it depends on.
The impact walk follows reverse edges from changed paths, identifying files
that may need inspection or regression testing. No project code is executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

DEFAULT_IGNORES = {
    ".git", ".mbe", "node_modules", ".venv", "venv", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", "dist", "build",
}
JSON_SUFFIXES = {".json", ".jsonc"}
SCRIPT_SUFFIXES = {".js", ".mjs", ".cjs", ".ts"}
TEXT_SUFFIXES = JSON_SUFFIXES | SCRIPT_SUFFIXES | {".mcfunction", ".lang", ".material"}
IMAGE_SUFFIXES = {".png", ".tga", ".jpg", ".jpeg", ".webp"}
REFERENCE_KEYS = {
    "item", "items", "block", "blocks", "entity", "entities", "animation", "animations",
    "animation_controller", "animation_controllers", "render_controller", "render_controllers", "geometry",
    "particle_effect", "particle_effects", "effect", "sound", "loot_table", "trade_table", "feature", "biome",
    "structure", "spawn_entity",
}
PATH_KEYS = {
    "$ui_defs", "ui_defs", "texture", "texture_path", "texture_file", "image",
    "image_path", "icon", "atlas", "path", "file", "script", "module",
}
NAMESPACE_ID = re.compile(r"^[a-zA-Z0-9_.-]+:[a-zA-Z0-9_./-]+$")
BEDROCK_DOTTED_ID = re.compile(r"^(?:geometry|animation|controller\.(?:animation|render)|render_controller|material)\.[a-zA-Z0-9_.-]+$")
IMPORT_RE = re.compile(
    r"(?:\bimport\s+(?:[^;]*?\s+from\s+)?|\bexport\s+[^;]*?\s+from\s+|\brequire\s*\(|\bimport\s*\()\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)


class ImpactError(ValueError):
    """Raised for invalid arguments or unsafe project paths."""


def sha256_file(path: Path, max_bytes: int) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ImpactError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except ImpactError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImpactError(f"cannot parse JSON: {exc}") from exc


def _safe_project_relative(value: str) -> str:
    raw = value.strip().replace("\\", "/")
    if not raw or "\x00" in raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ImpactError(f"changed path must be a safe relative path: {value!r}")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ImpactError(f"changed path contains an unsafe segment: {value!r}")
    return PurePosixPath(*parts).as_posix()


def _walk_project(root: Path, *, max_files: int, max_total_bytes: int) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    total = 0
    truncated = False
    symlinks = 0
    skipped_large = 0
    skipped_unreadable = 0
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as scan:
                entries = sorted(scan, key=lambda item: item.name.casefold(), reverse=True)
        except OSError:
            skipped_unreadable += 1
            continue
        for entry in entries:
            if entry.is_symlink():
                symlinks += 1
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in DEFAULT_IGNORES and not entry.name.startswith("."):
                        stack.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                path = Path(entry.path)
                rel = path.relative_to(root).as_posix()
                if len(files) >= max_files:
                    truncated = True
                    break
                size = entry.stat(follow_symlinks=False).st_size
                if total + size > max_total_bytes:
                    skipped_large += 1
                    continue
                total += size
                files[rel] = {"path": rel, "size_bytes": size, "suffix": path.suffix.lower()}
            except OSError:
                skipped_unreadable += 1
        if truncated:
            break
    coverage = {
        "scanned_files": len(files),
        "scanned_bytes": total,
        "truncated": truncated,
        "symlinks_skipped": symlinks,
        "files_exceeding_total_byte_budget": skipped_large,
        "unreadable_entries": skipped_unreadable,
        "parse_skipped_size": 0,
        "ignored_directories": sorted(DEFAULT_IGNORES),
    }
    return dict(sorted(files.items())), coverage


def _pack_root(root: Path, file_path: Path) -> Path:
    parts = file_path.parts
    pack_markers = {"behavior_packs", "resource_packs", "development_behavior_packs", "development_resource_packs"}
    for index, part in enumerate(parts[:-1]):
        if part in pack_markers and index + 1 < len(parts):
            return root.joinpath(*parts[: index + 2])
    # Fallback: nearest ancestor with manifest.json, without crossing the project root.
    current = file_path.parent
    while current != root and root in current.parents:
        if (current / "manifest.json").is_file():
            return current
        current = current.parent
    return root


def _iter_values(value: Any, key: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            yield from _iter_values(child_value, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from _iter_values(child, key)
    else:
        yield key, value


def _find_identifier_declarations(data: Any, rel: str) -> list[dict[str, str]]:
    declarations: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return declarations

    def add(value: Any, kind: str) -> None:
        if isinstance(value, str) and (NAMESPACE_ID.fullmatch(value) or BEDROCK_DOTTED_ID.fullmatch(value)):
            declarations.append({"identifier": value, "kind": kind})

    parts = {part.lower() for part in PurePosixPath(rel).parts}
    # Bedrock BP and RP definitions are wrapped in their component identifier.
    for wrapper, kind in (("minecraft:entity", "entity"), ("minecraft:client_entity", "client_entity"),
                          ("minecraft:item", "item"), ("minecraft:block", "block"),
                          ("minecraft:recipe_shaped", "recipe"), ("minecraft:recipe_shapeless", "recipe"),
                          ("minecraft:recipe_furnace", "recipe"), ("minecraft:recipe_brewing_mix", "recipe"),
                          ("minecraft:recipe_brewing_container", "recipe")):
        definition = data.get(wrapper)
        if isinstance(definition, dict) and isinstance(definition.get("description"), dict):
            add(definition["description"].get("identifier"), kind)

    # Also accept simple example/fixture files with a top-level description.
    description = data.get("description")
    if isinstance(description, dict):
        if "entities" in parts or "entity" in parts:
            add(description.get("identifier"), "entity")
        if "items" in parts or "item" in parts:
            add(description.get("identifier"), "item")
        if "blocks" in parts or "block" in parts:
            add(description.get("identifier"), "block")

    geometry_data = data.get("minecraft:geometry")
    geometries = geometry_data if isinstance(geometry_data, list) else [geometry_data] if isinstance(geometry_data, dict) else []
    for geometry in geometries:
        if isinstance(geometry, dict) and isinstance(geometry.get("description"), dict):
            add(geometry["description"].get("identifier"), "geometry")

    for collection, kind in (("animations", "animation"), ("animation_controllers", "animation_controller"), ("render_controllers", "render_controller")):
        values = data.get(collection)
        if isinstance(values, dict):
            for identifier in values:
                add(identifier, kind)
    return declarations


def _add_edge(edges: dict[tuple[str, str, str, str], dict[str, Any]], source: str, target: str,
              kind: str, reference: str, confidence: str = "HIGH") -> None:
    if source == target:
        return
    key = (source, target, kind, reference)
    edges[key] = {
        "from": source,
        "to": target,
        "kind": kind,
        "reference": reference,
        "confidence": confidence,
    }


def _candidate_asset_relpaths(root: Path, source_path: Path, reference: str, *, pack_root: Path,
                              allow_root_relative: bool = True) -> list[str]:
    raw = reference.strip().replace("\\", "/")
    if not raw or raw.startswith(("http://", "https://", "data:")) or "\x00" in raw:
        return []
    raw = raw[1:] if raw.startswith("/") else raw
    while raw.startswith("./"):
        raw = raw[2:]
    parts = raw.split("/")
    if any(part in {"..", "", "."} for part in parts):
        return []
    base = root / pack_root
    options: list[Path] = [base / raw, source_path.parent / raw]
    if allow_root_relative:
        options.append(root / raw)
    suffix = Path(raw).suffix.lower()
    if not suffix:
        for ext in (".json", ".png", ".tga", ".jpg", ".jpeg", ".lang"):
            options.extend([base / f"{raw}{ext}", source_path.parent / f"{raw}{ext}"])
    relative: list[str] = []
    for option in options:
        try:
            rel = option.relative_to(root).as_posix()
        except ValueError:
            continue
        if rel not in relative:
            relative.append(rel)
    return relative


def _resolve_asset_path(root: Path, source_path: Path, reference: str, *, candidates: dict[str, dict[str, Any]],
                        pack_root: Path, allow_root_relative: bool = True) -> str | None:
    for rel in _candidate_asset_relpaths(root, source_path, reference, pack_root=pack_root,
                                         allow_root_relative=allow_root_relative):
        if rel in candidates:
            return rel
    return None


def analyze_project(project_root: Path, changed_paths: list[str], *, max_files: int = 20000,
                    max_file_bytes: int = 2 * 1024 * 1024, max_total_bytes: int = 256 * 1024 * 1024) -> dict[str, Any]:
    root = project_root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ImpactError(f"project root is not a directory: {root}")
    if max_files < 1 or max_file_bytes < 1 or max_total_bytes < 1:
        raise ImpactError("scan budgets must be positive")
    normalized_changes = list(dict.fromkeys(_safe_project_relative(path) for path in changed_paths))
    if not normalized_changes:
        raise ImpactError("at least one --changed-path is required")

    files, coverage = _walk_project(root, max_files=max_files, max_total_bytes=max_total_bytes)
    declarations: dict[str, list[dict[str, str]]] = defaultdict(list)
    references: list[dict[str, str]] = []
    path_references: list[dict[str, str]] = []
    uuid_owners: dict[str, list[str]] = defaultdict(list)
    manifest_dependencies: list[tuple[str, str]] = []
    findings: list[dict[str, Any]] = []
    parse_failures = 0
    parse_skipped_size = 0
    parsed_json = 0
    parsed_scripts = 0

    for rel, meta in files.items():
        suffix = meta["suffix"]
        path = root / PurePosixPath(rel)
        if suffix in JSON_SUFFIXES:
            if meta["size_bytes"] > max_file_bytes:
                parse_skipped_size += 1
                findings.append({"code": "FILE_PARSE_SKIPPED_SIZE", "severity": "INFO", "confidence": "CONFIRMED", "path": rel,
                                 "message": f"JSON file exceeds the {max_file_bytes}-byte parse limit."})
                continue
            try:
                data = _read_json(path)
                parsed_json += 1
            except ImpactError as exc:
                parse_failures += 1
                findings.append({"code": "JSON_PARSE_ERROR", "severity": "MEDIUM", "confidence": "CONFIRMED", "path": rel, "message": str(exc)})
                continue
            for declaration in _find_identifier_declarations(data, rel):
                declarations[declaration["identifier"]].append({"path": rel, "kind": declaration["kind"]})
            for key, value in _iter_values(data):
                if not isinstance(value, str):
                    continue
                if NAMESPACE_ID.fullmatch(value) and key.lower() in REFERENCE_KEYS:
                    references.append({"source": rel, "identifier": value, "kind": f"{key.lower()}_reference"})
                if key.lower() in PATH_KEYS and ("/" in value or Path(value).suffix.lower() in TEXT_SUFFIXES | IMAGE_SUFFIXES):
                    path_references.append({"source": rel, "reference": value, "kind": f"{key.lower()}_path"})
            # Client entity alias tables contain exact binding paths and identifiers.
            client = data.get("minecraft:client_entity") if isinstance(data, dict) else None
            if isinstance(client, dict):
                desc = client.get("description", {})
                if isinstance(desc, dict):
                    for alias_kind, rel_kind in (("geometry", "geometry_alias"), ("animations", "animation_alias"), ("textures", "texture_alias")):
                        table = desc.get(alias_kind)
                        if isinstance(table, dict):
                            for alias, target in table.items():
                                if isinstance(target, str):
                                    if alias_kind == "textures":
                                        path_references.append({"source": rel, "reference": target, "kind": rel_kind})
                                    else:
                                        references.append({"source": rel, "identifier": target, "kind": rel_kind})
                    controllers = desc.get("animation_controllers")
                    if isinstance(controllers, list):
                        for item in controllers:
                            if isinstance(item, str):
                                references.append({"source": rel, "identifier": item, "kind": "animation_controller_binding"})
                            elif isinstance(item, dict):
                                for target in item.values():
                                    if isinstance(target, str):
                                        references.append({"source": rel, "identifier": target, "kind": "animation_controller_binding"})
                    render = desc.get("render_controllers")
                    if isinstance(render, list):
                        for item in render:
                            if isinstance(item, str):
                                references.append({"source": rel, "identifier": item, "kind": "render_controller_binding"})
            if PurePosixPath(rel).name.lower() == "manifest.json":
                header = data.get("header", {}) if isinstance(data, dict) else {}
                if isinstance(header, dict) and isinstance(header.get("uuid"), str):
                    uuid_owners[header["uuid"].lower()].append(rel)
                modules = data.get("modules", []) if isinstance(data, dict) else []
                if isinstance(modules, list):
                    for module in modules:
                        if isinstance(module, dict) and isinstance(module.get("uuid"), str):
                            uuid_owners[module["uuid"].lower()].append(rel)
                deps = data.get("dependencies", []) if isinstance(data, dict) else []
                if isinstance(deps, list):
                    for dep in deps:
                        if isinstance(dep, dict) and isinstance(dep.get("uuid"), str):
                            manifest_dependencies.append((rel, dep["uuid"].lower()))
        elif suffix in SCRIPT_SUFFIXES:
            if meta["size_bytes"] > max_file_bytes:
                parse_skipped_size += 1
                findings.append({"code": "SCRIPT_PARSE_SKIPPED_SIZE", "severity": "INFO", "confidence": "CONFIRMED", "path": rel,
                                 "message": f"Script file exceeds the {max_file_bytes}-byte parse limit."})
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            parsed_scripts += 1
            for match in IMPORT_RE.finditer(content):
                reference = match.group(1)
                if reference.startswith("."):
                    path_references.append({"source": rel, "reference": reference, "kind": "script_import"})

    edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    reference_kind_map = {
        "item_reference": "item", "items_reference": "item",
        "block_reference": "block", "blocks_reference": "block",
        "entity_reference": "entity", "entities_reference": "entity",
        "geometry_alias": "geometry", "animation_alias": "animation",
        "animation_controller_binding": "animation_controller",
        "render_controller_binding": "render_controller",
        "animation_reference": "animation", "animations_reference": "animation",
        "animation_controller_reference": "animation_controller",
        "animation_controllers_reference": "animation_controller",
        "render_controller_reference": "render_controller",
        "render_controllers_reference": "render_controller",
    }
    for reference in references:
        target_owners = declarations.get(reference["identifier"], [])
        expected_kind = reference_kind_map.get(reference["kind"])
        if expected_kind:
            target_owners = [owner for owner in target_owners if owner["kind"] == expected_kind]
        target_owners = list({owner["path"]: owner for owner in target_owners}.values())
        if len(target_owners) == 1:
            _add_edge(edges, reference["source"], target_owners[0]["path"], reference["kind"], reference["identifier"],
                      "HIGH" if reference["kind"] in {"geometry_alias", "animation_alias", "animation_controller_binding", "render_controller_binding"} else "MEDIUM")
        elif len(target_owners) > 1:
            findings.append({"code": "AMBIGUOUS_IDENTIFIER", "severity": "HIGH", "confidence": "CONFIRMED", "path": reference["source"],
                             "reference": reference["identifier"], "owners": sorted({x["path"] for x in target_owners}),
                             "message": f"Identifier {reference['identifier']} has multiple candidate owners."})
        elif not reference["identifier"].startswith(("minecraft:", "c:")):
            findings.append({"code": "UNRESOLVED_IDENTIFIER", "severity": "LOW", "confidence": "LOW", "path": reference["source"],
                             "reference": reference["identifier"], "message": "Namespaced reference has no declaration in the scanned project."})

    for rel, meta in files.items():
        if PurePosixPath(rel).name.lower() != "manifest.json":
            continue
        for manifest_path, dep_uuid in manifest_dependencies:
            owners = sorted(set(uuid_owners.get(dep_uuid, [])))
            if len(owners) == 1:
                _add_edge(edges, manifest_path, owners[0], "manifest_dependency", dep_uuid)
            elif len(owners) > 1:
                findings.append({"code": "AMBIGUOUS_MANIFEST_DEPENDENCY", "severity": "HIGH", "confidence": "CONFIRMED", "path": manifest_path,
                                 "reference": dep_uuid, "owners": sorted(set(owners)), "message": "Manifest dependency UUID has multiple owners."})
            else:
                findings.append({"code": "UNRESOLVED_MANIFEST_DEPENDENCY", "severity": "LOW", "confidence": "LOW", "path": manifest_path,
                                 "reference": dep_uuid, "message": "Manifest dependency UUID is not present in the scanned project."})

    changed_path_set = set(normalized_changes)
    for reference in path_references:
        source_path = root / PurePosixPath(reference["source"])
        pack_root = _pack_root(root, PurePosixPath(reference["source"]))
        target = _resolve_asset_path(root, source_path, reference["reference"], candidates=files, pack_root=pack_root)
        if target:
            _add_edge(edges, reference["source"], target, reference["kind"], reference["reference"], "HIGH")
        else:
            missing_changed_targets = sorted(changed_path_set.intersection(
                _candidate_asset_relpaths(root, source_path, reference["reference"], pack_root=pack_root)
            ))
            if missing_changed_targets:
                for missing_target in missing_changed_targets:
                    _add_edge(edges, reference["source"], missing_target, reference["kind"], reference["reference"], "HIGH")
                findings.append({"code": "CHANGED_DEPENDENCY_MISSING", "severity": "MEDIUM", "confidence": "HIGH", "path": reference["source"],
                                 "reference": reference["reference"], "owners": missing_changed_targets,
                                 "message": "A file reference points to a changed path that is absent from the current workspace; review the removal/rename and dependent file."})
            elif reference["kind"] in {"script_import", "$ui_defs_path", "ui_defs_path", "texture_path", "texture_file_path", "geometry_alias", "animation_alias", "texture_alias"}:
                findings.append({"code": "UNRESOLVED_FILE_REFERENCE", "severity": "MEDIUM", "confidence": "MEDIUM", "path": reference["source"],
                                 "reference": reference["reference"], "message": "Explicit file/path reference could not be resolved inside the scanned project."})

    # Entity behavior and RP client entity declarations are paired by exact identifier.
    id_owners: dict[str, list[dict[str, str]]] = declarations
    for identifier, owners in id_owners.items():
        behavior = [item for item in owners if item["kind"] == "entity"]
        client = [item for item in owners if item["kind"] == "client_entity"]
        if len(behavior) == 1 and len(client) == 1:
            _add_edge(edges, client[0]["path"], behavior[0]["path"], "entity_client_binding", identifier, "HIGH")
        elif len(behavior) > 1 or len(client) > 1:
            findings.append({"code": "AMBIGUOUS_ENTITY_BINDING", "severity": "HIGH", "confidence": "CONFIRMED",
                             "reference": identifier, "owners": sorted(item["path"] for item in behavior + client),
                             "message": "Entity identifier has multiple BP or RP client-entity declarations."})

    for identifier, owners in declarations.items():
        by_kind: dict[str, set[str]] = defaultdict(set)
        for owner in owners:
            by_kind[owner["kind"]].add(owner["path"])
        duplicate_owners = sorted(path for paths in by_kind.values() if len(paths) > 1 for path in paths)
        if duplicate_owners:
            findings.append({"code": "DUPLICATE_IDENTIFIER", "severity": "HIGH", "confidence": "CONFIRMED", "reference": identifier,
                             "owners": duplicate_owners, "message": "Multiple files declare the same resource identifier within the same resource type."})

    # Reverse dependency walk: a changed dependency can affect all its consumers.
    reverse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges.values():
        reverse[edge["to"]].append(edge)
    impacts: dict[str, dict[str, Any]] = {}
    changed_present = []
    for changed in normalized_changes:
        if changed in files:
            changed_present.append(changed)
        else:
            findings.append({"code": "CHANGED_PATH_NOT_IN_WORKSPACE", "severity": "INFO", "confidence": "CONFIRMED", "path": changed,
                             "message": "Changed path is absent from the current workspace; it may have been removed or renamed."})
        impacts.setdefault(changed, {"path": changed, "depth": 0, "via": [], "impact": "DIRECT", "confidence": "HIGH"})
        queue = deque([(changed, 0)])
        visited = {changed}
        while queue:
            current, depth = queue.popleft()
            if depth >= 64:
                continue
            for edge in sorted(reverse.get(current, []), key=lambda item: (item["from"], item["kind"])):
                consumer = edge["from"]
                if consumer in visited:
                    continue
                visited.add(consumer)
                next_depth = depth + 1
                row = impacts.get(consumer)
                if row is None or next_depth < row["depth"]:
                    impacts[consumer] = {
                        "path": consumer,
                        "depth": next_depth,
                        "via": [current],
                        "impact": "INDIRECT",
                        "confidence": edge["confidence"],
                        "relationship": edge["kind"],
                    }
                queue.append((consumer, next_depth))

    sorted_impacts = sorted(impacts.values(), key=lambda item: (item["depth"], item["path"].casefold(), item["path"]))
    coverage["parse_skipped_size"] = parse_skipped_size
    ambiguous_count = sum(item["code"].startswith("AMBIGUOUS") for item in findings)
    changed_dependency_misses = sum(item["code"] == "CHANGED_DEPENDENCY_MISSING" for item in findings)
    unresolved_count = sum(item["code"].startswith("UNRESOLVED") for item in findings) + changed_dependency_misses
    high_count = sum(item["severity"] == "HIGH" for item in findings)
    status = "PARTIAL" if (coverage["truncated"] or coverage["files_exceeding_total_byte_budget"]
                           or coverage["unreadable_entries"] or parse_failures or parse_skipped_size) else "PASS"
    return {
        "schema_version": "1.0.0",
        "project_root_name": root.name,
        "changed_paths": normalized_changes,
        "impact": sorted_impacts,
        "summary": {
            "status": status,
            "direct_changes": len(normalized_changes),
            "affected_files": max(0, len(sorted_impacts) - len(normalized_changes)),
            "graph_edges": len(edges),
            "declared_identifiers": len(declarations),
            "parsed_json_files": parsed_json,
            "parsed_script_files": parsed_scripts,
            "parse_failures": parse_failures,
            "high_severity_findings": high_count,
            "ambiguous_references": ambiguous_count,
            "unresolved_references": unresolved_count,
            "changed_dependency_misses": changed_dependency_misses,
            "changed_paths_present": len(changed_present),
        },
        "coverage": coverage,
        "edges": sorted(edges.values(), key=lambda item: (item["from"], item["to"], item["kind"], item["reference"])),
        "findings": sorted(findings, key=lambda item: (item.get("severity", ""), item.get("path", ""), item.get("code", ""), item.get("reference", ""))),
        "limitations": [
            "This is static dependency analysis; it does not evaluate Molang, scripts, runtime-discovered identifiers or Minecraft loading behavior.",
            "Some Bedrock references use aliases, generated paths or pack-specific conventions that cannot be resolved statically.",
            "Unresolved/ambiguous references are review signals, not proof that a feature is broken.",
            "The analyzer never edits, deletes, executes or packages project files.",
        ],
    }


def _atomic_write(path: Path, content: str, *, overwrite: bool = False) -> None:
    path = path.expanduser()
    if not path.parent.is_dir():
        raise ImpactError(f"output directory does not exist: {path.parent}")
    if path.exists() and not overwrite:
        raise ImpactError(f"output already exists; pass --overwrite to replace: {path}")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not overwrite:
            raise ImpactError(f"output already exists; pass --overwrite to replace: {path}")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--changed-path", action="append", default=[], help="project-relative changed path; repeat for multiple paths")
    parser.add_argument("--output", type=Path, help="optional JSON output path; stdout is always emitted")
    parser.add_argument("--overwrite", action="store_true", help="allow replacing an existing --output")
    parser.add_argument("--max-files", type=int, default=20000)
    parser.add_argument("--max-file-bytes", type=int, default=2 * 1024 * 1024)
    parser.add_argument("--max-total-bytes", type=int, default=256 * 1024 * 1024)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = analyze_project(args.project_root, args.changed_path, max_files=args.max_files,
                                 max_file_bytes=args.max_file_bytes, max_total_bytes=args.max_total_bytes)
        rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            _atomic_write(args.output, rendered, overwrite=args.overwrite)
        sys.stdout.write(rendered)
        return 0 if report["summary"]["status"] == "PASS" else 1
    except (ImpactError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
