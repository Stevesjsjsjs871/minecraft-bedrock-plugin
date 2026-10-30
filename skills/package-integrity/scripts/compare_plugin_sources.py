#!/usr/bin/env python3
"""Read-only, bounded source-tree parity audit for Minecraft Bedrock Engineer packages."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from package_provenance import (
    PackageSafetyError,
    _open_path_without_symlinks,
    _open_regular_file,
    _read_open_file_limited,
    scan_package,
)

EXPECTED_NAME = "minecraft-bedrock-engineer"
MAX_METADATA_BYTES = 2 * 1024 * 1024
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
README_VERSION = re.compile(
    r"(?m)^#\s+Minecraft Bedrock Engineer\s*[—-]\s*"
    r"((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)\s*$"
)
CHANGELOG_VERSION = re.compile(
    r"(?m)^##\s+((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)\b"
)


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _read_bytes(root: Path, relative: str) -> bytes:
    fd, snapshot = _open_regular_file(root / relative, relative)
    try:
        return _read_open_file_limited(fd, snapshot, MAX_METADATA_BYTES, relative)
    finally:
        os.close(fd)


def _read_text(root: Path, relative: str) -> str:
    return _read_bytes(root, relative).decode("utf-8")


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads(
        _read_text(root, relative),
        object_pairs_hook=_pairs_no_duplicates,
        parse_constant=_reject_constant,
    )
    if not isinstance(value, dict):
        raise ValueError(f"{relative} must contain a JSON object")
    return value


def _prompt_hash(value: list[str]) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def inspect_package_metadata(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    result: dict[str, Any] = {
        "plugin_name": None,
        "version": None,
        "version_markers": {},
        "prompt_count": None,
        "prompts_sha256": None,
        "first_three_prompts_sha256": None,
        "internal_prompt_parity": False,
        "valid": False,
        "errors": errors,
    }
    try:
        root_manifest = _read_json(root, "plugin.json")
        compatibility_manifest = _read_json(root, ".codex-plugin/plugin.json")
        version_file = _read_text(root, "VERSION").strip()
        readme = _read_text(root, "README.md")
        changelog = _read_text(root, "CHANGELOG.md")
    except Exception as exc:
        errors.append(f"metadata read failed: {type(exc).__name__}: {exc}")
        return result

    root_name = root_manifest.get("name")
    compatibility_name = compatibility_manifest.get("name")
    if root_name != EXPECTED_NAME or compatibility_name != EXPECTED_NAME:
        errors.append("both manifests must retain the minecraft-bedrock-engineer package name")
    if root_name != compatibility_name:
        errors.append("manifest plugin names differ")

    root_version = root_manifest.get("version")
    compatibility_version = compatibility_manifest.get("version")
    readme_match = README_VERSION.search(readme)
    changelog_match = CHANGELOG_VERSION.search(changelog)
    markers = {
        "VERSION": version_file,
        "plugin.json": root_version,
        ".codex-plugin/plugin.json": compatibility_version,
        "README.md": readme_match.group(1) if readme_match else None,
        "CHANGELOG.md": changelog_match.group(1) if changelog_match else None,
    }
    result["version_markers"] = markers
    if not readme_match:
        errors.append("README.md does not have the expected version heading")
    if not changelog_match:
        errors.append("CHANGELOG.md does not have a versioned first release heading")
    if any(not isinstance(value, str) or not SEMVER.fullmatch(value) for value in markers.values()):
        errors.append("all five version markers must contain valid SemVer strings")
    elif len(set(markers.values())) != 1:
        errors.append("VERSION, both manifests, README and CHANGELOG versions differ")

    extensions = root_manifest.get("extensions")
    com_openai = extensions.get("com.openai") if isinstance(extensions, dict) else None
    root_interface = com_openai.get("interface") if isinstance(com_openai, dict) else None
    compatibility_interface = compatibility_manifest.get("interface")
    root_prompts = root_interface.get("defaultPrompt") if isinstance(root_interface, dict) else None
    compatibility_prompts = (
        compatibility_interface.get("defaultPrompt")
        if isinstance(compatibility_interface, dict)
        else None
    )
    prompts_valid = all(
        isinstance(value, list)
        and len(value) >= 3
        and all(isinstance(item, str) and item.strip() for item in value)
        for value in (root_prompts, compatibility_prompts)
    )
    if not prompts_valid:
        errors.append("both manifests must contain at least three non-empty string default prompts")
    else:
        internal_match = root_prompts == compatibility_prompts
        result["prompt_count"] = len(root_prompts)
        result["prompts_sha256"] = _prompt_hash(root_prompts)
        result["first_three_prompts_sha256"] = _prompt_hash(root_prompts[:3])
        result["internal_prompt_parity"] = internal_match
        if not internal_match:
            errors.append("defaultPrompt arrays differ between the two manifests")

    result["plugin_name"] = root_name if root_name == compatibility_name else None
    result["version"] = version_file if isinstance(version_file, str) else None
    result["valid"] = not errors
    return result


def _collision_errors(records: list[dict[str, Any]], label: str) -> list[str]:
    seen: dict[str, str] = {}
    errors: list[str] = []
    for record in records:
        path = record["path"]
        portable = unicodedata.normalize("NFC", path).casefold()
        previous = seen.get(portable)
        if previous is not None and previous != path:
            errors.append(f"{label}: portable path collision: {previous!r} and {path!r}")
        else:
            seen[portable] = path
    return errors


def _scan(root: Path, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        records, errors = scan_package(root)
    except Exception as exc:
        return [], [f"{label}: scan failed: {type(exc).__name__}: {exc}"]
    errors = list(errors) + _collision_errors(records, label)
    return records, errors


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def compare_roots(reference_root: Path, candidate_root: Path) -> dict[str, Any]:
    reference_root = Path(os.path.abspath(os.fspath(reference_root)))
    candidate_root = Path(os.path.abspath(os.fspath(candidate_root)))
    reference_records, reference_errors = _scan(reference_root, "reference")
    candidate_records, candidate_errors = _scan(candidate_root, "candidate")
    reference_map = {record["path"]: record for record in reference_records}
    candidate_map = {record["path"]: record for record in candidate_records}

    reference_paths = set(reference_map)
    candidate_paths = set(candidate_map)
    common = sorted(reference_paths & candidate_paths)
    identical = [
        path
        for path in common
        if reference_map[path]["size_bytes"] == candidate_map[path]["size_bytes"]
        and reference_map[path]["sha256"] == candidate_map[path]["sha256"]
    ]
    changed = [
        {
            "path": path,
            "reference": reference_map[path],
            "candidate": candidate_map[path],
        }
        for path in common
        if path not in set(identical)
    ]
    only_reference = sorted(reference_paths - candidate_paths)
    only_candidate = sorted(candidate_paths - reference_paths)

    reference_metadata = inspect_package_metadata(reference_root)
    candidate_metadata = inspect_package_metadata(candidate_root)
    metadata_parity = {
        "plugin_names_match": (
            reference_metadata["plugin_name"] is not None
            and reference_metadata["plugin_name"] == candidate_metadata["plugin_name"]
        ),
        "versions_match": (
            reference_metadata["version"] is not None
            and reference_metadata["version"] == candidate_metadata["version"]
        ),
        "all_default_prompts_match": (
            reference_metadata["prompts_sha256"] is not None
            and reference_metadata["prompts_sha256"] == candidate_metadata["prompts_sha256"]
        ),
        "original_first_three_prompts_match": (
            reference_metadata["first_three_prompts_sha256"] is not None
            and reference_metadata["first_three_prompts_sha256"]
            == candidate_metadata["first_three_prompts_sha256"]
        ),
    }

    safety_errors = reference_errors + candidate_errors
    metadata_errors = reference_metadata["errors"] + candidate_metadata["errors"]
    metadata_valid = reference_metadata["valid"] and candidate_metadata["valid"]
    exact_files = not changed and not only_reference and not only_candidate
    exact_metadata = all(metadata_parity.values())

    if safety_errors or metadata_errors or not metadata_valid:
        status = "FAIL"
    elif not exact_files or not exact_metadata:
        status = "DIFFERENT"
    else:
        status = "PASS"

    return {
        "schema_version": 1,
        "status": status,
        "roots": {
            "reference": reference_root.name,
            "candidate": candidate_root.name,
        },
        "summary": {
            "reference_files": len(reference_records),
            "candidate_files": len(candidate_records),
            "identical_files": len(identical),
            "changed_files": len(changed),
            "only_in_reference": len(only_reference),
            "only_in_candidate": len(only_candidate),
            "safety_errors": len(safety_errors),
            "metadata_errors": len(metadata_errors),
        },
        "files": {
            "changed": changed,
            "only_in_reference": only_reference,
            "only_in_candidate": only_candidate,
        },
        "metadata": {
            "reference": reference_metadata,
            "candidate": candidate_metadata,
            "parity": metadata_parity,
            "plugin_backend_id": (
                "NOT_EMBEDDED_IN_PACKAGE; verify separately against Plugin Creator metadata"
            ),
        },
        "safety_errors": safety_errors,
        "metadata_errors": metadata_errors,
        "limitations": [
            "This command compares already-extracted directory trees; it does not extract archives.",
            "A PASS proves file and manifest parity for these two snapshots, not Plugin Creator backend identity.",
            "Minecraft import, Blockbench interoperability and in-game runtime are outside this audit.",
        ],
    }


def write_json_report(path: Path, report: dict[str, Any], roots: tuple[Path, Path]) -> None:
    output = Path(os.path.abspath(os.fspath(path)))
    absolute_roots = tuple(Path(os.path.abspath(os.fspath(root))) for root in roots)
    if any(_is_within(output, root) for root in absolute_roots):
        raise ValueError("JSON report must be written outside both compared package roots")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = _open_path_without_symlinks(output, flags)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_root", type=Path, help="clean GitHub source snapshot")
    parser.add_argument("candidate_root", type=Path, help="extracted Plugin Creator package")
    parser.add_argument("--json-out", type=Path, help="create a new JSON report outside both roots")
    args = parser.parse_args(argv)

    report = compare_roots(args.reference_root, args.candidate_root)
    if args.json_out:
        try:
            write_json_report(args.json_out, report, (args.reference_root, args.candidate_root))
        except Exception as exc:
            print(f"ERROR: cannot write JSON report: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    if report["status"] == "PASS":
        return 0
    return 1 if report["status"] == "DIFFERENT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
