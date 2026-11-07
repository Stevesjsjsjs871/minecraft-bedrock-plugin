#!/usr/bin/env python3
"""Conservative static dependency audit for a Minecraft Bedrock entity BP/RP bundle.

This tool checks JSON integrity and literal identifier/alias edges. It is not a
complete Bedrock schema validator or a Minecraft runtime emulator.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=_pairs_no_duplicates,
        parse_constant=_reject_constant,
    )


def walk_json(root: Path, patterns: tuple[str, ...]) -> tuple[list[tuple[Path, Any]], list[dict[str, str]]]:
    found: list[tuple[Path, Any]] = []
    errors: list[dict[str, str]] = []
    if not root.is_dir():
        errors.append({"path": str(root), "message": "directory does not exist"})
        return found, errors
    candidates: set[Path] = set()
    for pattern in patterns:
        candidates.update(root.glob(pattern))
    for path in sorted(p for p in candidates if p.is_file()):
        try:
            found.append((path, load_json(path)))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append({"path": path.as_posix(), "message": str(exc)})
    return found, errors


def nested(obj: Any, *keys: str) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def ids_from_definitions(entries: list[tuple[Path, Any]], top_key: str, id_path: tuple[str, ...]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    for path, data in entries:
        root = data.get(top_key) if isinstance(data, dict) else None
        candidates = root if isinstance(root, list) else [root]
        for candidate in candidates:
            value = nested(candidate, *id_path)
            if isinstance(value, str) and value:
                index[value].append(path.as_posix())
    return dict(index)


def add(findings: list[dict[str, str]], status: str, code: str, path: str, message: str) -> None:
    findings.append({"status": status, "code": code, "path": path, "message": message})


def _literal_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_literal_values(item))
        return out
    if isinstance(value, dict):
        out = []
        for key, item in value.items():
            if isinstance(key, str) and (key.startswith("animation.") or key.startswith("controller.")):
                out.append(key)
            out.extend(_literal_values(item))
        return out
    return []


def audit(bp_root: Path, rp_root: Path, entity_id: str | None = None) -> dict[str, Any]:
    bp_entries, bp_errors = walk_json(bp_root, ("entities/**/*.json", "entities/*.json"))
    rp_client, client_errors = walk_json(rp_root, ("entity/**/*.json", "entity/*.json", "entities/**/*.json"))
    geometry, geometry_errors = walk_json(rp_root, ("models/entity/**/*.geo.json", "models/entity/*.geo.json"))
    animations, animation_errors = walk_json(rp_root, ("animations/**/*.animation.json", "animations/*.animation.json"))
    controllers, controller_errors = walk_json(rp_root, ("animation_controllers/**/*.json", "animation_controllers/*.json"))
    renderers, renderer_errors = walk_json(rp_root, ("render_controllers/**/*.json", "render_controllers/*.json"))

    findings: list[dict[str, str]] = []
    for group, errors in (("bp-json", bp_errors), ("client-json", client_errors), ("geometry-json", geometry_errors), ("animation-json", animation_errors), ("controller-json", controller_errors), ("render-json", renderer_errors)):
        for error in errors:
            add(findings, "FAIL", "JSON_INVALID", error["path"], f"{group}: {error['message']}")

    bp_ids: dict[str, list[str]] = defaultdict(list)
    for path, data in bp_entries:
        value = nested(data, "minecraft:entity", "description", "identifier")
        if isinstance(value, str):
            bp_ids[value].append(path.as_posix())

    client_index: dict[str, list[tuple[Path, Any]]] = defaultdict(list)
    for path, data in rp_client:
        value = nested(data, "minecraft:client_entity", "description", "identifier")
        if isinstance(value, str):
            client_index[value].append((path, data))

    geometry_ids = ids_from_definitions(geometry, "minecraft:geometry", ("description", "identifier"))
    animation_ids: dict[str, list[str]] = defaultdict(list)
    for path, data in animations:
        defs = data.get("animations") if isinstance(data, dict) else None
        if isinstance(defs, dict):
            for key in defs:
                if isinstance(key, str):
                    animation_ids[key].append(path.as_posix())
    controller_ids: dict[str, list[str]] = defaultdict(list)
    for path, data in controllers:
        defs = data.get("animation_controllers") if isinstance(data, dict) else None
        if isinstance(defs, dict):
            for key in defs:
                if isinstance(key, str):
                    controller_ids[key].append(path.as_posix())
    render_ids: dict[str, list[str]] = defaultdict(list)
    for path, data in renderers:
        defs = data.get("render_controllers") if isinstance(data, dict) else None
        if isinstance(defs, dict):
            for key in defs:
                if isinstance(key, str):
                    render_ids[key].append(path.as_posix())

    duplicates = []
    for kind, index in (("BP entity", bp_ids), ("RP client entity", {k: [p.as_posix() for p, _ in v] for k, v in client_index.items()}), ("geometry", geometry_ids), ("animation", animation_ids), ("animation controller", controller_ids), ("render controller", render_ids)):
        for ident, paths in index.items():
            if len(paths) > 1:
                add(findings, "WARN", "DUPLICATE_IDENTIFIER", "; ".join(paths), f"{kind} identifier {ident!r} appears more than once")

    wanted = [entity_id] if entity_id else sorted(set(bp_ids) | set(client_index))
    if not wanted:
        add(findings, "WARN", "NO_ENTITY_FOUND", str(bp_root), "no literal BP or RP entity identifiers were indexed")

    checked_clients = 0
    for ident in wanted:
        bp_paths = bp_ids.get(ident, [])
        clients = client_index.get(ident, [])
        if entity_id and not bp_paths:
            add(findings, "FAIL", "BP_ENTITY_MISSING", str(bp_root), f"requested entity {ident!r} has no indexed BP definition")
        if entity_id and not clients:
            add(findings, "FAIL", "CLIENT_ENTITY_MISSING", str(rp_root), f"requested entity {ident!r} has no indexed RP client entity")
        if bp_paths and not clients:
            add(findings, "WARN", "CLIENT_ENTITY_MISSING", "; ".join(bp_paths), f"no RP client entity found for {ident!r}")
        if clients and not bp_paths:
            add(findings, "WARN", "BP_ENTITY_MISSING", "; ".join(p.as_posix() for p, _ in clients), f"no BP entity found for RP client entity {ident!r}")

        for client_path, client_data in clients:
            checked_clients += 1
            desc = nested(client_data, "minecraft:client_entity", "description") or {}
            geometry_aliases = desc.get("geometry", {}) if isinstance(desc, dict) else {}
            animation_aliases = desc.get("animations", {}) if isinstance(desc, dict) else {}
            render_refs = desc.get("render_controllers", []) if isinstance(desc, dict) else []
            texture_aliases = desc.get("textures", {}) if isinstance(desc, dict) else {}

            if isinstance(geometry_aliases, dict):
                for alias, target in geometry_aliases.items():
                    if isinstance(target, str) and target not in geometry_ids:
                        add(findings, "FAIL", "GEOMETRY_UNRESOLVED", client_path.as_posix(), f"geometry alias {alias!r} points to missing identifier {target!r}")
            if isinstance(animation_aliases, dict):
                for alias, target in animation_aliases.items():
                    refs = _literal_values(target)
                    for ref in refs:
                        if ref.startswith("controller.animation.") and ref not in controller_ids:
                            add(findings, "FAIL", "ANIMATION_CONTROLLER_UNRESOLVED", client_path.as_posix(), f"animation alias {alias!r} points to missing controller {ref!r}")
                        elif ref.startswith("animation.") and ref not in animation_ids:
                            add(findings, "FAIL", "ANIMATION_UNRESOLVED", client_path.as_posix(), f"animation alias {alias!r} points to missing animation {ref!r}")
            for ref in _literal_values(render_refs):
                if ref.startswith("controller.render.") and ref not in render_ids:
                    add(findings, "FAIL", "RENDER_CONTROLLER_UNRESOLVED", client_path.as_posix(), f"client entity references missing render controller {ref!r}")
            if isinstance(texture_aliases, dict):
                for alias, ref in texture_aliases.items():
                    if not isinstance(ref, str) or ref.startswith("#") or "{" in ref or "}" in ref:
                        continue
                    raw = ref if Path(ref).suffix else f"{ref}.png"
                    candidate = rp_root / raw
                    if not candidate.is_file():
                        add(findings, "WARN", "TEXTURE_PATH_UNRESOLVED", client_path.as_posix(), f"texture alias {alias!r} path {ref!r} did not resolve to {raw!r} under RP root")

            # Validate only controller state references reached through this
            # client entity's explicit animation alias map.
            referenced_controllers = set()
            if isinstance(animation_aliases, dict):
                for alias_target in animation_aliases.values():
                    referenced_controllers.update(
                        ref for ref in _literal_values(alias_target)
                        if ref.startswith("controller.animation.")
                    )
            for ctrl_id in sorted(referenced_controllers):
                for ctrl_path, ctrl_data in controllers:
                    defs = ctrl_data.get("animation_controllers", {}) if isinstance(ctrl_data, dict) else {}
                    ctrl = defs.get(ctrl_id) if isinstance(defs, dict) else None
                    if not isinstance(ctrl, dict):
                        continue
                    states = ctrl.get("states", {})
                    if not isinstance(states, dict):
                        continue
                    aliases = animation_aliases if isinstance(animation_aliases, dict) else {}
                    for state_name, state in states.items():
                        if not isinstance(state, dict):
                            continue
                        state_refs = _literal_values(state.get("animations", []))
                        for state_ref in state_refs:
                            if state_ref in aliases:
                                continue
                            if state_ref.startswith("animation.") and state_ref in animation_ids:
                                continue
                            if state_ref.startswith("controller.animation.") and state_ref in controller_ids:
                                continue
                            # Non-resource names are often client-entity aliases
                            # or dynamic selectors. Report unknown aliases as
                            # review warnings rather than false hard failures.
                            if state_ref and not state_ref.startswith("query."):
                                add(findings, "WARN", "CONTROLLER_ANIMATION_ALIAS_REVIEW", ctrl_path, f"controller {ctrl_id!r} state {state_name!r} uses {state_ref!r}; verify it is a client-entity animation alias")

    fail_count = sum(item["status"] == "FAIL" for item in findings)
    warn_count = sum(item["status"] == "WARN" for item in findings)
    return {
        "status": "FAIL" if fail_count else ("WARN" if warn_count else "PASS"),
        "scope": "static literal-reference audit; not a complete Bedrock validator",
        "target_version_default": "1.26.50",
        "entity_filter": entity_id,
        "inventory": {
            "bp_entity_json": len(bp_entries),
            "rp_client_entity_json": len(rp_client),
            "geometry_json": len(geometry),
            "animation_json": len(animations),
            "animation_controller_json": len(controllers),
            "render_controller_json": len(renderers),
            "checked_client_entity_definitions": checked_clients,
        },
        "indexed_identifiers": {
            "bp_entities": len(bp_ids), "rp_client_entities": len(client_index),
            "geometries": len(geometry_ids), "animations": len(animation_ids),
            "animation_controllers": len(controller_ids), "render_controllers": len(render_ids),
        },
        "summary": {"fail": fail_count, "warn": warn_count, "findings": len(findings)},
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bp-root", required=True, type=Path)
    parser.add_argument("--rp-root", required=True, type=Path)
    parser.add_argument("--entity-id", help="optional namespace:name filter")
    parser.add_argument("--output", type=Path, help="write JSON report to this path")
    args = parser.parse_args(argv)
    report = audit(args.bp_root.resolve(), args.rp_root.resolve(), args.entity_id)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
