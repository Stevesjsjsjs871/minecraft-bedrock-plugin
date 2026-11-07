#!/usr/bin/env python3
"""Plan and apply a coordinated Bedrock add-on version/name update.

The utility is deliberately separate from the Minecraft Bedrock Engineer
plugin package version. It edits only explicitly listed pack manifests and
matching .lang name entries inside one project directory.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

MAX_REQUEST_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_LANG_BYTES = 1024 * 1024
MAX_MANIFESTS = 16
MAX_LANG_FILES = 256
MAX_DISCOVERY_FILES = 20_000
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
TITLE_VERSION_RE = re.compile(
    r"(?:\s*\(\s*v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\s*\)"
    r"|\s*\[\s*v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\s*\]"
    r"|\s+v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\s*)$",
    re.I,
)
LOCALIZATION_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
VALID_CHANGE_TYPES = {"major", "medium", "fix"}
PACK_ROOTS = (
    "behavior_packs",
    "resource_packs",
    "development_behavior_packs",
    "development_resource_packs",
)


class AddonVersionError(ValueError):
    """Raised when the version update cannot be applied safely."""


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: Any, label: str = "version") -> "Version":
        if isinstance(value, list):
            if len(value) != 3 or any(type(part) is not int or part < 0 for part in value):
                raise AddonVersionError(f"{label} must be a three-integer version array or MAJOR.MINOR.PATCH string")
            return cls(*value)
        if isinstance(value, str):
            match = VERSION_RE.fullmatch(value.strip())
            if match:
                return cls(*(int(part) for part in match.groups()))
        raise AddonVersionError(f"{label} must be a stable MAJOR.MINOR.PATCH version; got {value!r}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, change_type: str) -> "Version":
        if change_type == "major":
            return Version(self.major + 1, 0, 0)
        if change_type == "medium":
            return Version(self.major, self.minor + 1, 0)
        if change_type == "fix":
            return Version(self.major, self.minor, self.patch + 1)
        raise AddonVersionError(f"change_type must be one of {sorted(VALID_CHANGE_TYPES)}")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AddonVersionError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise AddonVersionError(f"non-finite JSON constant is not allowed: {value}")


def _safe_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise AddonVersionError(f"{label} must be a non-empty project-relative POSIX path")
    if "\\" in value or "\x00" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise AddonVersionError(f"{label} must be a safe project-relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise AddonVersionError(f"{label} contains an unsafe path segment")
    if PurePosixPath(value).is_absolute():
        raise AddonVersionError(f"{label} must be relative")
    return value


def _resolve_inside(root: Path, relative: str, label: str, *, must_exist: bool = True) -> Path:
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise AddonVersionError(f"{label} traverses a symlink: {relative}")
    try:
        resolved = current.resolve(strict=must_exist)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise AddonVersionError(f"{label} is missing or resolves outside the project: {relative}") from exc
    return resolved


def _encode_like(value: Any, version: Version) -> Any:
    return [version.major, version.minor, version.patch] if isinstance(value, list) else str(version)


def _strip_previous_suffix(name: str) -> str:
    return TITLE_VERSION_RE.sub("", name).rstrip()


def _versioned_title(name: str, version: Version, suffix_template: str) -> str:
    base = _strip_previous_suffix(name)
    suffix = suffix_template.format(version=str(version))
    if not suffix.startswith(" "):
        suffix = " " + suffix
    return base + suffix


def _looks_like_localization_key(value: str) -> bool:
    return bool(LOCALIZATION_KEY_RE.fullmatch(value)) and "." in value and " " not in value


def _lang_files(pack_root: Path) -> list[Path]:
    """Return safe .lang files under texts/ without following symlinks."""
    texts = pack_root / "texts"
    if texts.is_symlink():
        raise AddonVersionError(f"unsafe symlink at localization directory: {texts}")
    if not texts.exists():
        return []
    if not texts.is_dir():
        raise AddonVersionError(f"localization path is not a directory: {texts}")
    files = sorted(texts.rglob("*.lang"))
    if len(files) > MAX_LANG_FILES:
        raise AddonVersionError(f"too many localization files under {texts}; limit is {MAX_LANG_FILES}")
    for path in files:
        if path.is_symlink():
            raise AddonVersionError(f"localization file must not be a symlink: {path}")
        try:
            path.resolve(strict=True).relative_to(pack_root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise AddonVersionError(f"localization file resolves outside pack: {path}") from exc
    return files


def _find_localized_key(pack_root: Path, key: str) -> bool:
    """Detect a localization key from actual .lang content, not its spelling."""
    for path in _lang_files(pack_root):
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise AddonVersionError(f"cannot read localization file {path}: {exc}") from exc
        if len(raw) > MAX_LANG_BYTES:
            raise AddonVersionError(f"localization file exceeds {MAX_LANG_BYTES} bytes: {path}")
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise AddonVersionError(f"localization file is not UTF-8: {path}") from exc
        for line in content.splitlines():
            if "=" in line and not line.lstrip().startswith(("#", ";")):
                lhs, _ = line.split("=", 1)
                if lhs.strip() == key:
                    return True
    return False


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AddonVersionError(f"cannot read {path}: {exc}") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        raise AddonVersionError(f"manifest exceeds {MAX_MANIFEST_BYTES} bytes: {path}")
    try:
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AddonVersionError(f"invalid UTF-8 JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AddonVersionError(f"manifest root must be an object: {path}")
    return data, raw


def _lang_updates(
    pack_root: Path,
    key: str,
    version: Version,
    suffix_template: str,
    localized_display_names: dict[str, str] | None = None,
) -> tuple[dict[Path, bytes], list[dict[str, Any]]]:
    texts = pack_root / "texts"
    if texts.is_symlink() or not texts.is_dir():
        raise AddonVersionError(f"header.name is localization key {key!r}, but no safe texts/ directory exists under {pack_root}")
    lang_files = _lang_files(pack_root)
    edits: dict[Path, bytes] = {}
    occurrences: list[dict[str, Any]] = []
    matched_names: set[str] = set()
    for path in lang_files:
        raw = path.read_bytes()
        has_bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise AddonVersionError(f"localization file is not UTF-8: {path}") from exc
        lines = text.splitlines(keepends=True)
        matched = 0
        new_lines: list[str] = []
        for line in lines:
            content = line.rstrip("\r\n")
            ending = line[len(content):]
            if "=" in content and not content.lstrip().startswith(("#", ";")):
                lhs, rhs = content.split("=", 1)
                if lhs.strip() == key:
                    matched += 1
                    if matched > 1:
                        raise AddonVersionError(f"duplicate localization key {key!r} in {path}")
                    locale_name = path.relative_to(texts).as_posix()
                    override = (localized_display_names or {}).get(locale_name)
                    if override is not None and (not isinstance(override, str) or not override.strip()):
                        raise AddonVersionError(f"localized display name for {locale_name!r} must be a non-empty string")
                    base_value = override if override is not None else rhs.strip()
                    new_value = _versioned_title(base_value, version, suffix_template)
                    leading = rhs[:len(rhs) - len(rhs.lstrip())]
                    trailing = rhs[len(rhs.rstrip()):]
                    new_lines.append(f"{lhs}={leading}{new_value}{trailing}{ending}")
                    matched_names.add(locale_name)
                    occurrences.append({"path": str(path), "key": key, "locale_file": locale_name,
                                        "new_value": new_value, "used_explicit_translation": override is not None})
                    continue
            new_lines.append(line)
        if matched:
            rendered = "".join(new_lines).encode("utf-8")
            if has_bom:
                rendered = b"\xef\xbb\xbf" + rendered
            edits[path] = rendered
    if not edits:
        raise AddonVersionError(f"no .lang file under {texts} defines localization key {key!r}; cannot guarantee the visible pack title is versioned")
    unknown_locales = sorted(set(localized_display_names or {}) - matched_names)
    if unknown_locales:
        raise AddonVersionError(
            f"localized_display_names refer to files without {key!r}: {unknown_locales}"
        )
    return edits, occurrences


@dataclass
class PackChange:
    path: Path
    relative_path: str
    data: dict[str, Any]
    original: bytes
    old_version: Version
    new_version: Version
    header_uuid: str
    old_name: str
    new_name: str


def _prepare_manifest(root: Path, relative: str, change_type: str, suffix_template: str,
                       display_name_override: str | None,
                       localized_display_names: dict[str, str] | None = None) -> tuple[PackChange, dict[Path, bytes], list[dict[str, Any]]]:
    path = _resolve_inside(root, relative, "manifest path")
    if path.name.lower() != "manifest.json" or not path.is_file():
        raise AddonVersionError(f"manifest path must point to an existing manifest.json file: {relative}")
    data, raw = _read_json(path)
    header = data.get("header")
    if not isinstance(header, dict):
        raise AddonVersionError(f"manifest header must be an object: {relative}")
    header_uuid = header.get("uuid")
    if not isinstance(header_uuid, str) or not header_uuid.strip():
        raise AddonVersionError(f"manifest header.uuid must be a non-empty string: {relative}")
    old_version = Version.parse(header.get("version"), f"{relative}: header.version")
    new_version = old_version.bump(change_type)
    old_name = header.get("name")
    if not isinstance(old_name, str) or not old_name.strip():
        raise AddonVersionError(f"manifest header.name must be a non-empty string: {relative}")

    locale_edits: dict[Path, bytes] = {}
    locale_report: list[dict[str, Any]] = []
    pack_root = path.parent
    localized_key_exists = _find_localized_key(pack_root, old_name)
    is_localized_key = localized_key_exists or _looks_like_localization_key(old_name)
    if is_localized_key:
        if display_name_override is not None:
            raise AddonVersionError(
                f"{relative}: header.name is a localization key; keep it unchanged and use localized_display_names "
                "for optional per-language base-title overrides"
            )
        pack_root = path.parent
        locale_edits, locale_report = _lang_updates(
            pack_root, old_name, new_version, suffix_template, localized_display_names
        )
        new_name = old_name
    else:
        if localized_display_names:
            raise AddonVersionError(
                f"{relative}: localized_display_names were provided but header.name is not a verified localization key"
            )
        if display_name_override is not None and (
            not isinstance(display_name_override, str) or not display_name_override.strip()
        ):
            raise AddonVersionError(f"display_name must be a non-empty string when supplied: {relative}")
        new_name = _versioned_title(display_name_override if display_name_override is not None else old_name,
                                    new_version, suffix_template)
    header["name"] = new_name
    header["version"] = _encode_like(header["version"], new_version)

    modules = data.get("modules")
    warnings: list[dict[str, Any]] = []
    if not isinstance(modules, list) or not modules:
        raise AddonVersionError(f"manifest modules must be a non-empty array: {relative}")
    for index, module in enumerate(modules):
        if not isinstance(module, dict):
            raise AddonVersionError(f"manifest modules[{index}] must be an object: {relative}")
        if "version" in module:
            module_version = Version.parse(module["version"], f"{relative}: modules[{index}].version")
            module["version"] = _encode_like(module["version"], new_version)
        else:
            warnings.append({"code": "MODULE_VERSION_MISSING", "path": relative, "module_index": index,
                             "message": "Module has no version field; no field was invented."})

    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return PackChange(path, relative, data, raw, old_version, new_version, header_uuid, old_name, new_name), locale_edits, locale_report + warnings


def plan_update(request: dict[str, Any], workspace: str | Path, *, apply: bool = False) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise AddonVersionError("request root must be a JSON object")
    project_name = request.get("project_directory")
    if not isinstance(project_name, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", project_name) or "--" in project_name:
        raise AddonVersionError("project_directory must be one lowercase kebab-case folder name")
    change_type = request.get("change_type")
    if change_type not in VALID_CHANGE_TYPES:
        raise AddonVersionError(f"change_type must be one of {sorted(VALID_CHANGE_TYPES)}")
    suffix_template = request.get("title_suffix", "v{version}")
    if not isinstance(suffix_template, str) or "{version}" not in suffix_template or len(suffix_template) > 64:
        raise AddonVersionError("title_suffix must be a short string containing {version}, for example 'v{version}'")
    try:
        suffix_template.format(version="1.2.3")
    except (KeyError, IndexError, ValueError) as exc:
        raise AddonVersionError("title_suffix may use only the {version} placeholder") from exc
    raw_paths = request.get("manifest_paths")
    overrides = request.get("display_names", {})
    if not isinstance(overrides, dict):
        raise AddonVersionError("display_names must be an object mapping non-localized manifest paths to visible base names")
    localized_overrides = request.get("localized_display_names", {})
    if not isinstance(localized_overrides, dict):
        raise AddonVersionError("localized_display_names must map manifest paths to per-language base titles")
    independent = request.get("allow_independent_versions", False)
    if type(independent) is not bool:
        raise AddonVersionError("allow_independent_versions must be a boolean")

    ws = Path(workspace).resolve(strict=True)
    if not ws.is_dir():
        raise AddonVersionError("workspace must be a directory")
    project_candidate = ws / project_name
    if project_candidate.is_symlink():
        raise AddonVersionError("project directory must not be a symlink")
    try:
        project = project_candidate.resolve(strict=True)
        if project.parent != ws or not project.is_dir():
            raise ValueError("not a direct project child")
    except (OSError, ValueError) as exc:
        raise AddonVersionError(f"project directory does not exist directly inside workspace: {project_name}") from exc

    if raw_paths is None or raw_paths == "auto":
        paths = _discover_manifest_paths(project)
        if not paths:
            raise AddonVersionError(
                "no pack manifests were discovered; provide manifest_paths explicitly or use "
                "behavior_packs/<pack>/manifest.json and resource_packs/<pack>/manifest.json"
            )
        manifest_selection = "auto-discovered"
    else:
        if not isinstance(raw_paths, list) or not raw_paths or len(raw_paths) > MAX_MANIFESTS:
            raise AddonVersionError(f"manifest_paths must be a non-empty array of at most {MAX_MANIFESTS} paths, or 'auto'")
        paths = [_safe_relative_path(value, f"manifest_paths[{i}]") for i, value in enumerate(raw_paths)]
        manifest_selection = "explicit"
    if len(paths) > MAX_MANIFESTS:
        raise AddonVersionError(f"manifest count exceeds safety limit {MAX_MANIFESTS}")
    if len(set(paths)) != len(paths):
        raise AddonVersionError("manifest_paths contains duplicates")
    unused_display_names = sorted(set(overrides) - set(paths))
    unused_localized_names = sorted(set(localized_overrides) - set(paths))
    if unused_display_names or unused_localized_names:
        raise AddonVersionError(
            f"title override paths are not part of manifest_paths; display_names={unused_display_names}, "
            f"localized_display_names={unused_localized_names}"
        )

    changes: list[PackChange] = []
    all_file_updates: dict[Path, bytes] = {}
    all_localized: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for relative in paths:
        override = overrides.get(relative)
        locale_override = localized_overrides.get(relative, {})
        if not isinstance(locale_override, dict):
            raise AddonVersionError(f"localized_display_names[{relative!r}] must be an object")
        change, locale_edits, extra = _prepare_manifest(
            project, relative, change_type, suffix_template, override, locale_override
        )
        changes.append(change)
        all_file_updates[change.path] = (json.dumps(change.data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        for p, payload in locale_edits.items():
            if p in all_file_updates:
                raise AddonVersionError(f"same file was scheduled for multiple updates: {p}")
            all_file_updates[p] = payload
        all_localized.extend([entry for entry in extra if "key" in entry])
        warnings.extend([entry for entry in extra if "code" in entry])

    if len(changes) > 1 and not independent:
        baselines = {str(change.old_version) for change in changes}
        if len(baselines) != 1:
            raise AddonVersionError(f"selected BP/RP manifests do not share one current version: {sorted(baselines)}; use allow_independent_versions only when intentionally maintaining separate tracks")
    by_uuid = {change.header_uuid.lower(): change for change in changes}
    if len(by_uuid) != len(changes):
        raise AddonVersionError("selected manifests share a header UUID; expected distinct BP/RP pack UUIDs")

    dependency_edits: list[dict[str, Any]] = []
    # Keep BP -> RP pack dependency versions aligned with the updated RP header.
    for change in changes:
        deps = change.data.get("dependencies", [])
        if deps is None:
            continue
        if not isinstance(deps, list):
            raise AddonVersionError(f"manifest dependencies must be an array: {change.relative_path}")
        for index, dep in enumerate(deps):
            if not isinstance(dep, dict):
                raise AddonVersionError(f"manifest dependencies[{index}] must be an object: {change.relative_path}")
            dep_uuid = dep.get("uuid")
            if isinstance(dep_uuid, str) and dep_uuid.lower() in by_uuid:
                dependency_pack = by_uuid[dep_uuid.lower()]
                prior = dep.get("version")
                if prior is not None:
                    Version.parse(prior, f"{change.relative_path}: dependencies[{index}].version")
                    dep["version"] = _encode_like(prior, dependency_pack.new_version)
                else:
                    dep["version"] = _encode_like(
                        dependency_pack.data["header"]["version"], dependency_pack.new_version
                    )
                dependency_edits.append({"manifest": change.relative_path, "dependency_index": index,
                                         "target_manifest": dependency_pack.relative_path,
                                         "new_version": str(dependency_pack.new_version)})
        # Dependencies may have changed after the original serialization above.
        all_file_updates[change.path] = (json.dumps(change.data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    changes_summary = []
    for change in changes:
        changes_summary.append({"manifest": change.relative_path,
                                "old_version": str(change.old_version),
                                "new_version": str(change.new_version),
                                "old_header_name": change.old_name,
                                "new_header_name": change.new_name,
                                "header_uuid_preserved": change.header_uuid})
    if not independent and len({str(c.new_version) for c in changes}) != 1:
        raise AddonVersionError("selected pack manifests would not end up with one aligned version")

    verification = _verify_projection(changes, all_file_updates, dependency_edits, applied=False)
    if not verification["passed"]:
        raise AddonVersionError(
            "version update failed post-plan verification: " + "; ".join(verification["errors"])
        )
    if apply:
        original_snapshot = {path: path.read_bytes() for path in all_file_updates}
        _atomic_replace_many(all_file_updates)
        verification = _verify_projection(changes, all_file_updates, dependency_edits, applied=True)
        if not verification["passed"]:
            try:
                _atomic_replace_many(original_snapshot)
            except Exception as rollback_error:
                raise AddonVersionError(
                    "post-write verification failed and rollback also failed: "
                    + "; ".join(verification["errors"])
                    + f"; rollback error: {rollback_error}"
                ) from rollback_error
            raise AddonVersionError(
                "post-write verification failed; original files were restored: "
                + "; ".join(verification["errors"])
            )

    return {
        "status": "APPLIED" if apply else "DRY_RUN",
        "project_directory": project_name,
        "change_type": change_type,
        "title_suffix": suffix_template,
        "changes": changes_summary,
        "localized_titles": all_localized,
        "pack_dependency_updates": dependency_edits,
        "warnings": warnings,
        "manifest_selection": manifest_selection,
        "verification": verification,
        "files_to_update": sorted(str(path.relative_to(project)) for path in all_file_updates),
        "applied": bool(apply),
        "format_version_changed": False,
        "min_engine_version_changed": False,
        "script_api_dependencies_changed": False,
        "uuid_values_changed": False,
        "runtime_status": "NOT RUN",
    }


def _discover_manifest_paths(project: Path) -> list[str]:
    """Discover one pack or one unambiguous BP/RP pair from standard pack roots.

    More than two manifests or multiple variants are intentionally not guessed;
    callers must provide exact manifest_paths for those projects.
    """
    discovered: list[Path] = []
    inspected = 0
    skip_dirs = {".git", "node_modules", "build", "dist", ".cache", "__pycache__"}
    for root_name in PACK_ROOTS:
        pack_root = project / root_name
        if pack_root.is_symlink():
            raise AddonVersionError(f"pack discovery root must not be a symlink: {root_name}")
        if not pack_root.exists():
            continue
        if not pack_root.is_dir():
            raise AddonVersionError(f"pack discovery root is not a directory: {root_name}")
        for child in sorted(pack_root.iterdir()):
            if child.is_symlink():
                raise AddonVersionError(f"pack discovery encountered a symlink: {child.relative_to(project).as_posix()}")
            if not child.is_dir():
                continue
            candidate = child / "manifest.json"
            if candidate.is_file() and not candidate.is_symlink():
                discovered.append(candidate)
                continue

            nested: list[Path] = []
            for entry in child.rglob("*"):
                inspected += 1
                if inspected > MAX_DISCOVERY_FILES:
                    raise AddonVersionError(f"manifest discovery exceeded {MAX_DISCOVERY_FILES} scanned entries")
                if entry.is_symlink():
                    raise AddonVersionError(
                        f"manifest discovery encountered a symlink: {entry.relative_to(project).as_posix()}"
                    )
                if entry.is_dir() and entry.name in skip_dirs:
                    continue
                if entry.is_file() and entry.name.lower() == "manifest.json":
                    nested.append(entry)
            if len(nested) > 1:
                names = [p.relative_to(project).as_posix() for p in nested]
                raise AddonVersionError(
                    f"multiple manifests found inside {child.relative_to(project).as_posix()}: {names}; "
                    "specify manifest_paths explicitly"
                )
            discovered.extend(nested)

    root_manifest = project / "manifest.json"
    if not discovered and root_manifest.is_file() and not root_manifest.is_symlink():
        discovered.append(root_manifest)

    unique = sorted({p.resolve(strict=True) for p in discovered}, key=lambda p: p.as_posix())
    if len(unique) > MAX_MANIFESTS:
        raise AddonVersionError(f"manifest discovery found {len(unique)} packs; limit is {MAX_MANIFESTS}")
    relative = [p.relative_to(project.resolve(strict=True)).as_posix() for p in unique]

    if len(relative) == 2:
        roles = {"bp": 0, "rp": 0, "unknown": 0}
        for item in relative:
            first = PurePosixPath(item).parts[0]
            if first in {"behavior_packs", "development_behavior_packs"}:
                roles["bp"] += 1
            elif first in {"resource_packs", "development_resource_packs"}:
                roles["rp"] += 1
            else:
                data, _ = _read_json(project / item)
                module_types = {
                    module.get("type") for module in data.get("modules", []) if isinstance(module, dict)
                } if isinstance(data.get("modules"), list) else set()
                if "resources" in module_types:
                    roles["rp"] += 1
                elif module_types.intersection({"data", "script"}):
                    roles["bp"] += 1
                else:
                    roles["unknown"] += 1
        if roles != {"bp": 1, "rp": 1, "unknown": 0}:
            raise AddonVersionError(
                f"auto-discovery found two manifests but could not identify one BP and one RP: {roles}; "
                "specify manifest_paths explicitly"
            )
    elif len(relative) > 2:
        raise AddonVersionError(
            f"auto-discovery found {len(relative)} pack manifests {relative}; "
            "specify exactly which manifests belong to this release"
        )
    return relative


def _verify_projection(
    changes: list[PackChange],
    file_updates: dict[Path, bytes],
    dependency_edits: list[dict[str, Any]],
    *,
    applied: bool,
) -> dict[str, Any]:
    """Verify manifest versions, module versions, visible titles and pack links."""
    errors: list[str] = []
    manifest_checks: list[dict[str, Any]] = []
    localized_checks: list[dict[str, Any]] = []
    for change in changes:
        payload = change.path.read_bytes() if applied else file_updates.get(change.path)
        if payload is None:
            errors.append(f"missing planned manifest update: {change.relative_path}")
            continue
        try:
            projected = json.loads(payload.decode("utf-8-sig"), object_pairs_hook=_unique_pairs)
        except Exception as exc:
            errors.append(f"manifest is not valid JSON: {change.relative_path}: {exc}")
            continue
        header = projected.get("header", {})
        try:
            header_version = Version.parse(header.get("version"), f"{change.relative_path}: header.version")
        except AddonVersionError as exc:
            errors.append(str(exc))
            continue
        if header_version != change.new_version:
            errors.append(f"header.version mismatch in {change.relative_path}: {header_version} != {change.new_version}")
        if header.get("uuid") != change.header_uuid:
            errors.append(f"header.uuid changed in {change.relative_path}")

        localized_key = _find_localized_key(change.path.parent, change.new_name)
        title_versioned = str(change.new_version) in change.new_name
        if localized_key:
            texts_root = change.path.parent / "texts"
            localized_verified_for_current = False
            for locale_path in _lang_files(change.path.parent):
                locale_payload = locale_path.read_bytes() if applied else file_updates.get(locale_path)
                if locale_payload is None:
                    continue
                try:
                    locale_text = locale_payload.decode("utf-8-sig")
                except UnicodeDecodeError:
                    errors.append(f"localized title file is not UTF-8: {locale_path}")
                    continue
                vals = [
                    line.split("=", 1)[1].strip()
                    for line in locale_text.splitlines()
                    if "=" in line and not line.lstrip().startswith(("#", ";"))
                    and line.split("=", 1)[0].strip() == change.new_name
                ]
                if not vals:
                    continue
                if len(vals) != 1 or str(change.new_version) not in vals[0]:
                    errors.append(f"localized title not versioned in {locale_path.relative_to(texts_root).as_posix()}")
                else:
                    localized_verified_for_current = True
                    localized_checks.append({
                        "manifest": change.relative_path,
                        "locale_file": locale_path.relative_to(texts_root).as_posix(),
                        "key": change.new_name,
                        "visible_title": vals[0],
                        "version_present": True,
                    })
            if not localized_verified_for_current:
                errors.append(f"no updated localized visible title was verified for {change.relative_path}")
            title_versioned = localized_verified_for_current
        elif not title_versioned:
            errors.append(f"version not visible in projected pack title for {change.relative_path}")

        module_versions: list[str] = []
        modules = projected.get("modules", [])
        for index, module in enumerate(modules):
            if isinstance(module, dict) and "version" in module:
                try:
                    module_version = Version.parse(module["version"], f"{change.relative_path}: modules[{index}].version")
                except AddonVersionError as exc:
                    errors.append(str(exc))
                    continue
                module_versions.append(str(module_version))
                if module_version != change.new_version:
                    errors.append(f"modules[{index}].version mismatch in {change.relative_path}: {module_version}")
        manifest_checks.append({
            "manifest": change.relative_path,
            "expected_version": str(change.new_version),
            "header_version": str(header_version),
            "module_versions": module_versions,
            "visible_title": change.new_name,
            "title_versioned_or_localized": title_versioned,
            "header_uuid_preserved": header.get("uuid") == change.header_uuid,
        })

    for edit in dependency_edits:
        source = next((c for c in changes if c.relative_path == edit["manifest"]), None)
        target = next((c for c in changes if c.relative_path == edit["target_manifest"]), None)
        if source is None or target is None:
            errors.append(f"unresolved pack dependency verification target: {edit}")
            continue
        raw = source.path.read_bytes() if applied else file_updates[source.path]
        try:
            deps_doc = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_pairs)
            dep = deps_doc["dependencies"][edit["dependency_index"]]
            dep_version = Version.parse(dep.get("version"), f"{source.relative_path}: dependency.version")
            if dep_version != target.new_version:
                errors.append(
                    f"pack dependency mismatch {source.relative_path} -> {target.relative_path}: "
                    f"{dep_version} != {target.new_version}"
                )
        except (KeyError, IndexError, TypeError, AddonVersionError, json.JSONDecodeError) as exc:
            errors.append(f"could not verify pack dependency {edit}: {exc}")

    return {
        "passed": not errors,
        "errors": errors,
        "manifest_checks": manifest_checks,
        "localized_title_checks": localized_checks,
        "pack_dependency_updates": len(dependency_edits),
        "visible_titles_checked": len(manifest_checks) + len(localized_checks),
        "verified_after_write": applied,
    }


def _atomic_replace_many(updates: dict[Path, bytes]) -> None:
    staged: dict[Path, Path] = {}
    originals: dict[Path, bytes] = {}
    committed: list[Path] = []
    try:
        for target, payload in updates.items():
            if target.is_symlink() or not target.is_file():
                raise AddonVersionError(f"refusing to replace missing or symlink file: {target}")
            originals[target] = target.read_bytes()
            original_mode = stat.S_IMODE(target.stat().st_mode)
            fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            tmp = Path(tmp_name)
            staged[target] = tmp
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(tmp, original_mode)
        for target, tmp in staged.items():
            os.replace(tmp, target)
            committed.append(target)
    except Exception as exc:
        # Best-effort rollback of any files already replaced.
        for target in reversed(committed):
            try:
                fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.rollback.", suffix=".tmp", dir=target.parent)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(originals[target])
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp_name, target)
            except Exception:
                pass
        if isinstance(exc, AddonVersionError):
            raise
        raise AddonVersionError(f"atomic manifest update failed and rollback was attempted: {exc}") from exc
    finally:
        for tmp in staged.values():
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


def read_request(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    raw = target.read_bytes()
    if len(raw) > MAX_REQUEST_BYTES:
        raise AddonVersionError(f"request file exceeds {MAX_REQUEST_BYTES} bytes")
    try:
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AddonVersionError(f"invalid request JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise AddonVersionError("request root must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="JSON request file")
    parser.add_argument("--workspace", required=True, help="Directory containing the add-on project folder")
    parser.add_argument("--apply", action="store_true", help="write the coordinated version/name changes; without this flag only preview")
    parser.add_argument("--report", help="optional JSON report output path")
    args = parser.parse_args(argv)
    try:
        result = plan_update(read_request(args.request), args.workspace, apply=args.apply)
    except (AddonVersionError, OSError) as exc:
        rendered = json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2)
        print(rendered)
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
