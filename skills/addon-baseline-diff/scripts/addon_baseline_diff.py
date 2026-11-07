#!/usr/bin/env python3
"""Compare two Bedrock add-on archives without modifying or executing them.

The comparator is designed for iterative BP/RP workbench releases. It reports
added, removed and modified files, normalizes pack-root folder renames, checks
manifest identity/dependencies and performs bounded JSON/JavaScript syntax
checks. It never extracts files to the project or executes add-on scripts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

MAX_ARCHIVE_MEMBERS = 50_000
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250
ALLOWED_COMPRESSION = {
    zipfile.ZIP_STORED,
    zipfile.ZIP_DEFLATED,
    zipfile.ZIP_BZIP2,
    zipfile.ZIP_LZMA,
}
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class DiffError(ValueError):
    """Unsafe archive or invalid release metadata."""


class DuplicateJSONKey(DiffError):
    """A JSON object contains duplicate keys."""


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: Any, label: str) -> "Version":
        if isinstance(value, list):
            if len(value) != 3 or any(type(part) is not int or part < 0 for part in value):
                raise DiffError(f"{label} must be a three-integer version array")
            return cls(*value)
        if isinstance(value, str):
            match = VERSION_RE.fullmatch(value.strip())
            if match:
                return cls(*(int(part) for part in match.groups()))
        raise DiffError(f"{label} is not a stable MAJOR.MINOR.PATCH version: {value!r}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass
class ManifestRecord:
    path: str
    root: str
    role: str
    document: dict[str, Any]
    header_uuid: str
    header_version: Version
    header_name: str
    format_version: Any
    module_types: list[str]
    module_uuids: list[str]
    module_versions: list[Version]
    dependencies: list[dict[str, Any]]
    min_engine_version: Any


@dataclass
class ArchiveScan:
    path: str
    sha256: str
    file_count: int
    expanded_bytes: int
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    manifests: list[ManifestRecord] = field(default_factory=list)
    json_results: list[dict[str, Any]] = field(default_factory=list)
    js_results: list[dict[str, Any]] = field(default_factory=list)
    payloads: dict[str, bytes] = field(default_factory=dict)
    normalization: dict[str, str] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKey(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise DiffError(f"non-finite JSON constant is forbidden: {value}")


def _parse_json(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8-sig"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except DuplicateJSONKey as exc:
        # Keep the specialized type so a duplicate key can be distinguished
        # from comments/trailing commas and ordinary JSON parse failures.
        raise DuplicateJSONKey(f"{label}: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError, DiffError) as exc:
        raise DiffError(f"{label}: {exc}") from exc
    if not isinstance(value, dict):
        raise DiffError(f"{label}: JSON root must be an object")
    return value


def _canonical_member(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise DiffError(f"unsafe ZIP member name: {name!r}")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise DiffError(f"absolute ZIP member path is forbidden: {name!r}")
    trimmed = name[:-1] if info.is_dir() and name.endswith("/") else name
    parts = trimmed.split("/")
    if not trimmed or any(part in {"", ".", ".."} for part in parts):
        raise DiffError(f"path traversal or invalid ZIP member path: {name!r}")
    if PurePosixPath(trimmed).is_absolute():
        raise DiffError(f"absolute ZIP member path is forbidden: {name!r}")
    mode = (info.external_attr >> 16) & 0xFFFF
    if stat.S_ISLNK(mode):
        raise DiffError(f"symbolic link entry is forbidden: {name!r}")
    if info.flag_bits & 0x1:
        raise DiffError(f"encrypted ZIP member is unsupported: {name!r}")
    if info.compress_type not in ALLOWED_COMPRESSION:
        raise DiffError(f"unsupported ZIP compression method: {name!r}")
    return PurePosixPath(trimmed).as_posix() + ("/" if info.is_dir() else "")


def _validate_member_inventory(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    infos = archive.infolist()
    if not infos or len(infos) > MAX_ARCHIVE_MEMBERS:
        raise DiffError(f"archive member count must be in 1..{MAX_ARCHIVE_MEMBERS}")
    seen: set[str] = set()
    files: set[str] = set()
    directories: set[str] = set()
    expanded_total = 0
    members: list[tuple[zipfile.ZipInfo, str]] = []
    for info in infos:
        canonical = _canonical_member(info)
        key = canonical.rstrip("/").casefold()
        if key in seen:
            raise DiffError(f"duplicate or case-colliding ZIP member: {info.filename!r}")
        seen.add(key)
        if info.is_dir():
            directories.add(key)
        else:
            files.add(key)
            if info.file_size > MAX_MEMBER_BYTES:
                raise DiffError(f"ZIP member exceeds {MAX_MEMBER_BYTES} bytes: {canonical}")
            expanded_total += info.file_size
            if info.file_size > 1024 * 1024:
                ratio = info.file_size / max(info.compress_size, 1)
                if ratio > MAX_COMPRESSION_RATIO:
                    raise DiffError(f"suspicious compression ratio ({ratio:.1f}) in {canonical}")
        if expanded_total > MAX_ARCHIVE_BYTES:
            raise DiffError(f"archive expands beyond {MAX_ARCHIVE_BYTES} bytes")
        members.append((info, canonical))

    for name in files:
        if name in directories:
            raise DiffError(f"ZIP path is both a file and directory: {name!r}")
        parts = name.split("/")
        for index in range(1, len(parts)):
            parent = "/".join(parts[:index]).casefold()
            if parent in files:
                raise DiffError(f"ZIP file path is a parent of another file: {parent!r}")
    return members


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    data = bytearray()
    with archive.open(info, "r") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_MEMBER_BYTES:
                raise DiffError(f"member expanded beyond safety limit: {info.filename!r}")
    if len(data) != info.file_size:
        raise DiffError(f"ZIP member size mismatch: {info.filename!r}")
    return bytes(data)


def _manifest_role(document: dict[str, Any], path: str) -> tuple[str, list[str]]:
    modules = document.get("modules")
    if not isinstance(modules, list) or not modules:
        raise DiffError(f"{path}: modules must be a non-empty array")
    types = []
    for index, module in enumerate(modules):
        if not isinstance(module, dict) or not isinstance(module.get("type"), str):
            raise DiffError(f"{path}: modules[{index}].type must be a string")
        types.append(module["type"])
    type_set = set(types)
    if "resources" in type_set and type_set.intersection({"data", "script", "client_data"}):
        raise DiffError(f"{path}: one manifest cannot mix resource and behavior module types")
    if "resources" in type_set:
        return "RP", types
    if type_set.intersection({"data", "script", "client_data"}):
        return "BP", types
    if "skin_pack" in type_set:
        return "SKIN", types
    if "world_template" in type_set:
        return "WORLD", types
    return "OTHER", types


def _manifest_record(path: str, document: dict[str, Any]) -> ManifestRecord:
    header = document.get("header")
    if not isinstance(header, dict):
        raise DiffError(f"{path}: header must be an object")
    header_uuid = header.get("uuid")
    if not isinstance(header_uuid, str) or not header_uuid.strip():
        raise DiffError(f"{path}: header.uuid is required")
    header_version = Version.parse(header.get("version"), f"{path}: header.version")
    header_name = header.get("name")
    if not isinstance(header_name, str) or not header_name.strip():
        raise DiffError(f"{path}: header.name is required")
    role, types = _manifest_role(document, path)
    module_uuids: list[str] = []
    module_versions: list[Version] = []
    for index, module in enumerate(document["modules"]):
        module_uuid = module.get("uuid")
        if not isinstance(module_uuid, str) or not module_uuid.strip():
            raise DiffError(f"{path}: modules[{index}].uuid is required")
        if module_uuid.casefold() in {x.casefold() for x in module_uuids}:
            raise DiffError(f"{path}: duplicate module UUID {module_uuid!r}")
        module_uuids.append(module_uuid)
        module_versions.append(Version.parse(module.get("version"), f"{path}: modules[{index}].version"))
    dependencies = document.get("dependencies", [])
    if dependencies is None:
        dependencies = []
    if not isinstance(dependencies, list):
        raise DiffError(f"{path}: dependencies must be an array")
    for index, dep in enumerate(dependencies):
        if not isinstance(dep, dict):
            raise DiffError(f"{path}: dependencies[{index}] must be an object")
    root = str(PurePosixPath(path).parent)
    if root == ".":
        root = ""
    return ManifestRecord(
        path=path,
        root=root,
        role=role,
        document=document,
        header_uuid=header_uuid,
        header_version=header_version,
        header_name=header_name,
        format_version=document.get("format_version"),
        module_types=types,
        module_uuids=module_uuids,
        module_versions=module_versions,
        dependencies=dependencies,
        min_engine_version=header.get("min_engine_version"),
    )


def _scan_archive(path: str | Path) -> ArchiveScan:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise DiffError(f"archive must be a regular non-symlink file: {source}")
    source = source.resolve(strict=True)
    scan = ArchiveScan(
        path=str(source),
        sha256=_sha256_file(source),
        file_count=0,
        expanded_bytes=0,
    )
    try:
        with zipfile.ZipFile(source, "r") as archive:
            members = _validate_member_inventory(archive)
            node = shutil.which("node")
            js_temp = tempfile.TemporaryDirectory(prefix="bedrock-js-parse-") if node else None
            try:
                for info, member_path in members:
                    if info.is_dir():
                        continue
                    payload = _read_member(archive, info)
                    digest = hashlib.sha256(payload).hexdigest()
                    scan.records[member_path] = {"sha256": digest, "size_bytes": len(payload)}
                    scan.file_count += 1
                    scan.expanded_bytes += len(payload)
                    lower = member_path.lower()
                    if lower.endswith("manifest.json"):
                        if len(payload) > MAX_JSON_BYTES:
                            raise DiffError(f"manifest exceeds parse size limit ({MAX_JSON_BYTES} bytes): {member_path}")
                        document = _parse_json(payload, member_path)
                        scan.manifests.append(_manifest_record(member_path, document))
                        scan.payloads[member_path] = payload
                    elif lower.endswith(".json"):
                        if len(payload) > MAX_JSON_BYTES:
                            scan.json_results.append({"path": member_path, "status": "NOT_CHECKED", "reason": "JSON file exceeds parse size limit"})
                        else:
                            try:
                                _parse_json(payload, member_path)
                                scan.json_results.append({"path": member_path, "status": "STRICT_JSON_PASS"})
                            except DuplicateJSONKey as exc:
                                scan.json_results.append({"path": member_path, "status": "DUPLICATE_KEY_FAIL", "detail": str(exc)})
                            except DiffError as exc:
                                # Comments/trailing commas and invalid syntax are not
                                # conflated here; this is diagnostic, not a blanket
                                # claim that Minecraft rejects the file.
                                scan.json_results.append({"path": member_path, "status": "NON_STRICT_OR_INVALID_JSON", "detail": str(exc)})
                    elif lower.endswith(".lang"):
                        if len(payload) <= MAX_MEMBER_BYTES:
                            scan.payloads[member_path] = payload
                    elif lower.endswith(".js"):
                        if node and js_temp is not None:
                            temp_path = Path(js_temp.name) / f"{scan.file_count:06d}.mjs"
                            temp_path.write_bytes(payload)
                            result = subprocess.run(
                                [node, "--check", str(temp_path)],
                                capture_output=True,
                                text=True,
                                timeout=30,
                            )
                            scan.js_results.append({
                                "path": member_path,
                                "status": "PASS" if result.returncode == 0 else "FAIL",
                                "stderr": result.stderr.strip()[:4000],
                            })
                        else:
                            scan.js_results.append({"path": member_path, "status": "NOT RUN", "reason": "Node.js is unavailable"})
            finally:
                if js_temp is not None:
                    js_temp.cleanup()
    except (zipfile.BadZipFile, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        if isinstance(exc, DiffError):
            raise
        raise DiffError(f"cannot safely scan archive {source}: {exc}") from exc

    header_uuids: set[str] = set()
    for manifest in scan.manifests:
        key = manifest.header_uuid.casefold()
        if key in header_uuids:
            raise DiffError(f"duplicate header UUID across manifests: {manifest.header_uuid}")
        header_uuids.add(key)

    # Collect all headers before module UUIDs so a module cannot collide with
    # a header declared later in the archive's manifest ordering.
    module_uuids: set[str] = set()
    for manifest in scan.manifests:
        for module_uuid in manifest.module_uuids:
            key = module_uuid.casefold()
            if key in module_uuids or key in header_uuids:
                raise DiffError(f"duplicate pack/module UUID across manifests: {module_uuid}")
            module_uuids.add(key)
    return scan


def _normalise_records(scan: ArchiveScan) -> dict[str, str]:
    role_manifests: dict[str, list[ManifestRecord]] = {}
    for manifest in scan.manifests:
        role_manifests.setdefault(manifest.role, []).append(manifest)
    ambiguous = {role for role, manifests in role_manifests.items() if len(manifests) > 1}
    if ambiguous:
        scan.errors.append({
            "severity": "REVIEW",
            "code": "AMBIGUOUS_PACK_ROOTS",
            "message": "Multiple manifests share a pack role; folder normalization is disabled for those roles.",
            "roles": sorted(ambiguous),
        })
    if len(scan.manifests) > 1 and any(not m.root for m in scan.manifests):
        scan.errors.append({
            "severity": "REVIEW",
            "code": "ROOT_LEVEL_MANIFEST_AMBIGUITY",
            "message": "A root-level manifest coexists with nested manifests; archive pack roots are ambiguous.",
        })
    mappings: dict[str, str] = {}
    for source_path in scan.records:
        mapped = None
        for role, candidates in role_manifests.items():
            if role in ambiguous or len(candidates) != 1:
                continue
            root = candidates[0].root
            if not root:
                if len(scan.manifests) == 1:
                    mapped = f"{role}/{source_path}"
                    break
                continue
            if source_path == root:
                mapped = role
                break
            if source_path.startswith(root + "/"):
                relative = source_path[len(root) + 1:]
                mapped = f"{role}/{relative}"
                break
        mappings[source_path] = mapped or f"ARCHIVE/{source_path}"
    normalised: dict[str, str] = {}
    for source_path, key in mappings.items():
        if key in normalised:
            raise DiffError(f"pack-root normalization creates a path collision at {key!r}")
        normalised[key] = source_path
    scan.normalization = mappings
    return normalised


def _check_manifest_dependencies(scan: ArchiveScan) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    by_uuid = {m.header_uuid.casefold(): m for m in scan.manifests}
    for manifest in scan.manifests:
        for index, dependency in enumerate(manifest.dependencies):
            dep_uuid = dependency.get("uuid")
            if not isinstance(dep_uuid, str) or dep_uuid.casefold() not in by_uuid:
                continue  # built-in script deps or a deliberately external pack
            target = by_uuid[dep_uuid.casefold()]
            try:
                dep_version = Version.parse(dependency.get("version"), f"{manifest.path}: dependencies[{index}].version")
            except DiffError as exc:
                findings.append({"severity": "FAIL", "code": "INVALID_INTERNAL_DEPENDENCY_VERSION", "path": manifest.path, "detail": str(exc)})
                continue
            if dep_version != target.header_version:
                findings.append({
                    "severity": "FAIL", "code": "INTERNAL_DEPENDENCY_VERSION_MISMATCH",
                    "path": manifest.path, "dependency_target": target.path,
                    "expected": str(target.header_version), "actual": str(dep_version),
                })
    bp = next((m for m in scan.manifests if m.role == "BP"), None)
    rp = next((m for m in scan.manifests if m.role == "RP"), None)
    if bp and rp:
        linked = any(
            isinstance(dep.get("uuid"), str)
            and dep["uuid"].casefold() == rp.header_uuid.casefold()
            and dep.get("version") is not None
            for dep in bp.dependencies
        )
        if not linked:
            findings.append({
                "severity": "REVIEW", "code": "BP_RP_DEPENDENCY_NOT_FOUND",
                "path": bp.path, "dependency_target": rp.path,
                "message": "No BP dependency points to the included RP header UUID.",
            })
    return findings


def _localized_title_values(scan: ArchiveScan, manifest: ManifestRecord) -> list[str]:
    values: list[str] = []
    for path, payload in scan.payloads.items():
        if not path.lower().endswith(".lang"):
            continue
        if manifest.root and not path.startswith(manifest.root + "/"):
            continue
        try:
            content = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        for line in content.splitlines():
            if "=" not in line or line.lstrip().startswith(("#", ";")):
                continue
            key, value = line.split("=", 1)
            if key.strip() == manifest.header_name:
                values.append(value.strip())
    return values


def _manifest_delta(baseline: ArchiveScan, candidate: ArchiveScan, release_candidate: bool) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    old_groups: dict[str, list[ManifestRecord]] = {}
    new_groups: dict[str, list[ManifestRecord]] = {}
    for record in baseline.manifests:
        old_groups.setdefault(record.role, []).append(record)
    for record in candidate.manifests:
        new_groups.setdefault(record.role, []).append(record)

    ambiguous_roles = {
        role for role in set(old_groups) | set(new_groups)
        if len(old_groups.get(role, [])) > 1 or len(new_groups.get(role, [])) > 1
    }
    for role in sorted(ambiguous_roles):
        findings.append({
            "severity": "REVIEW", "code": "PACK_ROLE_AMBIGUOUS", "role": role,
            "baseline_manifests": [m.path for m in old_groups.get(role, [])],
            "candidate_manifests": [m.path for m in new_groups.get(role, [])],
            "message": "Multiple manifests share this pack role; role-based identity comparison is withheld.",
        })

    # Only compare roles with exactly one manifest on each relevant side.
    for role, new_records in new_groups.items():
        if role in ambiguous_roles:
            continue
        new = new_records[0]
        old_records = old_groups.get(role, [])
        if not old_records:
            findings.append({"severity": "INFO", "code": "PACK_ADDED", "role": role, "path": new.path})
            # A newly added pack in a release candidate still needs the same
            # title/header/module parity gate as an existing pack.
            for index, module_version in enumerate(new.module_versions):
                if module_version != new.header_version:
                    findings.append({
                        "severity": "FAIL", "code": "MODULE_VERSION_MISMATCH", "role": role,
                        "module_index": index, "header_version": str(new.header_version),
                        "module_version": str(module_version),
                    })
            if release_candidate and not _visible_title_versioned(candidate, new):
                findings.append({
                    "severity": "FAIL", "code": "VISIBLE_TITLE_VERSION_MISSING", "role": role,
                    "manifest": new.path, "expected_version": str(new.header_version),
                })
            continue
        old = old_records[0]
        if new.header_uuid.casefold() != old.header_uuid.casefold():
            findings.append({
                "severity": "FAIL", "code": "PACK_HEADER_UUID_CHANGED", "role": role,
                "baseline": old.header_uuid, "candidate": new.header_uuid,
            })
        if new.format_version != old.format_version:
            findings.append({
                "severity": "REVIEW", "code": "MANIFEST_FORMAT_VERSION_CHANGED", "role": role,
                "baseline": old.format_version, "candidate": new.format_version,
            })
        if len(old.module_types) != len(new.module_types):
            findings.append({
                "severity": "REVIEW", "code": "MODULE_COUNT_CHANGED", "role": role,
                "baseline_count": len(old.module_types), "candidate_count": len(new.module_types),
            })
        for index, (old_type, old_uuid) in enumerate(zip(old.module_types, old.module_uuids)):
            if index >= len(new.module_types):
                continue
            new_type = new.module_types[index]
            new_uuid = new.module_uuids[index]
            if old_type != new_type:
                findings.append({
                    "severity": "REVIEW", "code": "MODULE_LAYOUT_CHANGED", "role": role,
                    "module_index": index, "baseline_type": old_type, "candidate_type": new_type,
                })
                continue
            if new_uuid.casefold() != old_uuid.casefold():
                findings.append({
                    "severity": "REVIEW", "code": "MODULE_UUID_CHANGED", "role": role,
                    "module_index": index, "module_type": old_type,
                    "baseline": old_uuid, "candidate": new_uuid,
                })
        if new.header_version <= old.header_version:
            severity = "FAIL" if release_candidate else "INFO"
            findings.append({
                "severity": severity, "code": "PACK_VERSION_NOT_ADVANCED", "role": role,
                "baseline": str(old.header_version), "candidate": str(new.header_version),
                "release_candidate": release_candidate,
            })
        else:
            findings.append({
                "severity": "INFO", "code": "PACK_VERSION_ADVANCED", "role": role,
                "baseline": str(old.header_version), "candidate": str(new.header_version),
            })
        if new.min_engine_version != old.min_engine_version:
            findings.append({
                "severity": "REVIEW", "code": "MIN_ENGINE_VERSION_CHANGED", "role": role,
                "baseline": old.min_engine_version, "candidate": new.min_engine_version,
            })
        old_api = [(d.get("module_name"), d.get("version")) for d in old.dependencies if isinstance(d.get("module_name"), str)]
        new_api = [(d.get("module_name"), d.get("version")) for d in new.dependencies if isinstance(d.get("module_name"), str)]
        if old_api != new_api:
            findings.append({
                "severity": "REVIEW", "code": "SCRIPT_API_DEPENDENCIES_CHANGED", "role": role,
                "baseline": old_api, "candidate": new_api,
            })
        for index, module_version in enumerate(new.module_versions):
            if module_version != new.header_version:
                findings.append({
                    "severity": "FAIL", "code": "MODULE_VERSION_MISMATCH", "role": role,
                    "module_index": index, "header_version": str(new.header_version),
                    "module_version": str(module_version),
                })
        if release_candidate:
            if new.header_name == old.header_name and not _localized_title_values(candidate, new):
                findings.append({
                    "severity": "REVIEW", "code": "PACK_TITLE_UNCHANGED", "role": role,
                    "title": new.header_name,
                })
            if not _visible_title_versioned(candidate, new):
                findings.append({
                    "severity": "FAIL", "code": "VISIBLE_TITLE_VERSION_MISSING", "role": role,
                    "manifest": new.path, "expected_version": str(new.header_version),
                })

    for role, old_records in old_groups.items():
        if role in ambiguous_roles or role in new_groups:
            continue
        findings.append({"severity": "FAIL" if release_candidate else "REVIEW", "code": "PACK_REMOVED", "role": role})
    return findings


def _visible_title_versioned(scan: ArchiveScan, manifest: ManifestRecord) -> bool:
    """Check a literal pack title or every translation for its localization key.

    Localization is detected from actual matching .lang entries, not from a
    naming heuristic; the key itself remains unchanged in manifest.json.
    """
    suffix = re.compile(rf"(?:^|\s)v?{re.escape(str(manifest.header_version))}$", re.I)
    localized_values = _localized_title_values(scan, manifest)
    if localized_values:
        return all(bool(suffix.search(value)) for value in localized_values)
    # Missing translations for an apparent key cannot prove a visible title.
    # Literal titles can be verified directly from header.name.
    return bool(suffix.search(manifest.header_name))


def compare_archives(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    release_candidate: bool = False,
) -> dict[str, Any]:
    baseline = _scan_archive(baseline_path)
    candidate = _scan_archive(candidate_path)
    old_norm = _normalise_records(baseline)
    new_norm = _normalise_records(candidate)
    old_keys, new_keys = set(old_norm), set(new_norm)
    added_keys = sorted(new_keys - old_keys)
    removed_keys = sorted(old_keys - new_keys)
    shared = old_keys & new_keys
    modified_keys = sorted(
        key for key in shared
        if baseline.records[old_norm[key]]["sha256"] != candidate.records[new_norm[key]]["sha256"]
    )
    added = [{"path": key, "candidate_path": new_norm[key], **candidate.records[new_norm[key]]} for key in added_keys]
    removed = [{"path": key, "baseline_path": old_norm[key], **baseline.records[old_norm[key]]} for key in removed_keys]
    modified = [{
        "path": key,
        "baseline_path": old_norm[key],
        "candidate_path": new_norm[key],
        "baseline_sha256": baseline.records[old_norm[key]]["sha256"],
        "candidate_sha256": candidate.records[new_norm[key]]["sha256"],
        "baseline_size_bytes": baseline.records[old_norm[key]]["size_bytes"],
        "candidate_size_bytes": candidate.records[new_norm[key]]["size_bytes"],
    } for key in modified_keys]

    findings = []
    if not baseline.manifests:
        findings.append({"severity": "REVIEW", "code": "BASELINE_MANIFEST_NOT_FOUND"})
    if not candidate.manifests:
        findings.append({"severity": "FAIL", "code": "CANDIDATE_MANIFEST_NOT_FOUND"})
    findings.extend(_check_manifest_dependencies(candidate))
    findings.extend(_manifest_delta(baseline, candidate, release_candidate))
    findings.extend(baseline.errors)
    findings.extend(candidate.errors)
    if removed:
        findings.append({
            "severity": "REVIEW", "code": "FILES_REMOVED",
            "count": len(removed),
            "message": "Every removed path requires scope review; the comparator never assumes deletion was intentional.",
            "examples": [row["path"] for row in removed[:20]],
        })
    if any(result["status"] == "DUPLICATE_KEY_FAIL" for result in candidate.json_results):
        findings.append({"severity": "FAIL", "code": "JSON_DUPLICATE_KEYS_PRESENT"})
    if any(result["status"] == "FAIL" for result in candidate.js_results):
        findings.append({"severity": "FAIL", "code": "JAVASCRIPT_SYNTAX_FAILURE"})
    # Valid JSONC candidates are not automatically labeled broken. They stay
    # visible for target-version validation and manual review.
    not_checked = [r for r in candidate.json_results if r["status"] == "NOT_CHECKED"]
    if not_checked:
        findings.append({
            "severity": "REVIEW", "code": "JSON_FILES_NOT_CHECKED",
            "count": len(not_checked),
            "examples": [{"path": r["path"], "reason": r.get("reason", "")} for r in not_checked[:10]],
        })
    non_strict = [r for r in candidate.json_results if r["status"] == "NON_STRICT_OR_INVALID_JSON"]
    if non_strict:
        findings.append({
            "severity": "REVIEW", "code": "NON_STRICT_JSON_CANDIDATES",
            "count": len(non_strict),
            "examples": [{"path": r["path"], "detail": r.get("detail", "")[:300]} for r in non_strict[:10]],
        })
    if any(result["status"] == "FAIL" for result in candidate.js_results):
        js_status = "FAIL"
    elif any(result["status"] == "NOT RUN" for result in candidate.js_results):
        js_status = "PARTIAL"
        findings.append({
            "severity": "REVIEW", "code": "JAVASCRIPT_SYNTAX_NOT_RUN",
            "count": sum(1 for result in candidate.js_results if result["status"] == "NOT RUN"),
            "message": "Node.js was unavailable; JavaScript syntax could not be checked.",
        })
    elif candidate.js_results:
        js_status = "PASS"
    else:
        js_status = "NOT APPLICABLE"
    strict_json_pass = sum(1 for r in candidate.json_results if r["status"] == "STRICT_JSON_PASS")
    jsonc_count = sum(1 for r in candidate.json_results if r["status"] == "NON_STRICT_OR_INVALID_JSON")
    duplicate_count = sum(1 for r in candidate.json_results if r["status"] == "DUPLICATE_KEY_FAIL")
    fail_count = sum(1 for f in findings if f["severity"] == "FAIL")
    review_count = sum(1 for f in findings if f["severity"] == "REVIEW")
    manifest_findings = [
        f for f in findings
        if f.get("code", "").startswith(("PACK_", "MODULE_", "INTERNAL_DEPENDENCY_", "INVALID_INTERNAL_DEPENDENCY"))
        or f.get("code") in {"BP_RP_DEPENDENCY_NOT_FOUND", "MIN_ENGINE_VERSION_CHANGED", "MANIFEST_FORMAT_VERSION_CHANGED", "SCRIPT_API_DEPENDENCIES_CHANGED"}
    ]
    manifest_fail = any(f["severity"] == "FAIL" for f in manifest_findings)
    manifest_review = any(f["severity"] == "REVIEW" for f in manifest_findings)
    recommendation = "HOLD" if fail_count else ("REVIEW" if review_count else "STATIC DELTA CLEAN — RUNTIME NOT VERIFIED")

    return {
        "status": "FAIL" if fail_count else ("REVIEW" if review_count else "PASS"),
        "recommendation": recommendation,
        "baseline": {
            "path": baseline.path,
            "sha256": baseline.sha256,
            "files": baseline.file_count,
            "expanded_bytes": baseline.expanded_bytes,
            "manifest_count": len(baseline.manifests),
            "manifests": [_manifest_summary(m) for m in baseline.manifests],
        },
        "candidate": {
            "path": candidate.path,
            "sha256": candidate.sha256,
            "files": candidate.file_count,
            "expanded_bytes": candidate.expanded_bytes,
            "manifest_count": len(candidate.manifests),
            "manifests": [_manifest_summary(m) for m in candidate.manifests],
        },
        "file_delta": {"added": added, "removed": removed, "modified": modified,
                       "summary": {"added": len(added), "removed": len(removed), "modified": len(modified),
                                   "unchanged": len(shared) - len(modified)}},
        "checks": {
            "candidate_archive_safety": "PASS",
            "manifest_and_dependency_findings": "FAIL" if manifest_fail else "REVIEW" if manifest_review else "PASS",
            "strict_json_pass": strict_json_pass,
            "json_non_strict_or_invalid_candidates": jsonc_count,
            "json_duplicate_key_failures": duplicate_count,
            "json_not_checked": len(not_checked),
            "javascript_syntax": js_status,
            "runtime": "NOT RUN",
        },
        "findings": findings,
        "normalization": {
            "baseline_pack_roots": baseline.normalization,
            "candidate_pack_roots": candidate.normalization,
            "note": "Unique BP/RP pack roots are normalized to role prefixes, so changing a top-level pack folder name does not look like a full deletion/addition.",
        },
    }


def _manifest_summary(manifest: ManifestRecord) -> dict[str, Any]:
    return {
        "path": manifest.path,
        "role": manifest.role,
        "header_name": manifest.header_name,
        "header_uuid": manifest.header_uuid,
        "header_version": str(manifest.header_version),
        "format_version": manifest.format_version,
        "module_types": manifest.module_types,
        "module_uuids": manifest.module_uuids,
        "module_versions": [str(v) for v in manifest.module_versions],
        "min_engine_version": manifest.min_engine_version,
        "api_dependencies": [
            {"module_name": d.get("module_name"), "version": d.get("version")}
            for d in manifest.dependencies if isinstance(d.get("module_name"), str)
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", help="known-good .mcaddon/.mcpack/ZIP archive")
    parser.add_argument("candidate", help="candidate .mcaddon/.mcpack/ZIP archive")
    parser.add_argument("--release-candidate", action="store_true", help="require a higher pack version and versioned visible title")
    parser.add_argument("--report", help="write JSON report to this path (must not already exist)")
    args = parser.parse_args(argv)
    try:
        result = compare_archives(args.baseline, args.candidate, release_candidate=args.release_candidate)
        rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.report:
            report_path = Path(args.report)
            if report_path.exists() or report_path.is_symlink():
                raise DiffError(f"report path already exists: {report_path}")
            if not report_path.parent.is_dir():
                raise DiffError("report parent directory must already exist")
            with report_path.open("x", encoding="utf-8") as stream:
                stream.write(rendered)
        print(rendered, end="")
        return 2 if result["status"] == "FAIL" else (1 if result["status"] == "REVIEW" else 0)
    except (DiffError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "recommendation": "HOLD", "error": str(exc)}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
