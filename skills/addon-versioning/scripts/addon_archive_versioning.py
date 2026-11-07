#!/usr/bin/env python3
"""Safely version a .mcaddon/.mcpack ZIP and return a new verified archive.

The input archive is never modified. All work happens in a temporary extracted
copy, and the output archive is created with exclusive/no-overwrite semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from addon_versioning import AddonVersionError, Version, _read_json, plan_update
except ImportError:  # pragma: no cover - exercised by direct script invocation
    from skills.addon_versioning.addon_versioning import AddonVersionError, Version, _read_json, plan_update

MAX_ARCHIVE_MEMBERS = 50_000
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250
_ALLOWED_COMPRESSION = {
    zipfile.ZIP_STORED,
    zipfile.ZIP_DEFLATED,
    zipfile.ZIP_BZIP2,
    zipfile.ZIP_LZMA,
}


class ArchiveVersionError(ValueError):
    """Unsafe archive, invalid pack set, or failed archive verification."""


def _member_path(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ArchiveVersionError(f"unsafe ZIP member name: {name!r}")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ArchiveVersionError(f"absolute ZIP member path is forbidden: {name!r}")
    trimmed = name[:-1] if name.endswith("/") else name
    if any(part in {"", ".", ".."} for part in trimmed.split("/")):
        raise ArchiveVersionError(f"path traversal or invalid ZIP member path: {name!r}")
    path = PurePosixPath(trimmed)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveVersionError(f"path traversal or invalid ZIP member path: {name!r}")
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    if stat.S_ISLNK(unix_mode):
        raise ArchiveVersionError(f"symbolic links are not allowed in add-on archives: {name!r}")
    if info.flag_bits & 0x1:
        raise ArchiveVersionError(f"encrypted ZIP members are not supported: {name!r}")
    if info.compress_type not in _ALLOWED_COMPRESSION:
        raise ArchiveVersionError(f"unsupported compression method in {name!r}")
    return path.as_posix() + ("/" if info.is_dir() else "")


def _validate_archive_metadata(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    infos = archive.infolist()
    if not infos or len(infos) > MAX_ARCHIVE_MEMBERS:
        raise ArchiveVersionError(f"archive member count must be in 1..{MAX_ARCHIVE_MEMBERS}")
    total = 0
    members: list[tuple[zipfile.ZipInfo, str]] = []
    seen: set[str] = set()
    file_names: set[str] = set()
    directory_names: set[str] = set()
    for info in infos:
        relative = _member_path(info)
        canonical = relative.rstrip("/")
        folded = canonical.casefold()
        if folded in seen:
            raise ArchiveVersionError(f"duplicate or case-colliding ZIP member: {info.filename!r}")
        seen.add(folded)
        if info.is_dir():
            directory_names.add(folded)
        else:
            file_names.add(folded)
            if info.file_size > MAX_MEMBER_BYTES:
                raise ArchiveVersionError(f"ZIP member exceeds {MAX_MEMBER_BYTES} bytes: {relative}")
            total += info.file_size
            if info.file_size > 1024 * 1024:
                ratio = info.file_size / max(info.compress_size, 1)
                if ratio > MAX_COMPRESSION_RATIO:
                    raise ArchiveVersionError(f"suspicious compression ratio ({ratio:.1f}) in {relative}")
        if total > MAX_ARCHIVE_BYTES:
            raise ArchiveVersionError(f"archive expands beyond {MAX_ARCHIVE_BYTES} bytes")
        members.append((info, relative))

    for name in file_names:
        if name in directory_names:
            raise ArchiveVersionError(f"ZIP path is both a file and directory: {name!r}")
        parts = name.split("/")
        for i in range(1, len(parts)):
            parent = "/".join(parts[:i]).casefold()
            if parent in file_names:
                raise ArchiveVersionError(f"ZIP file path is a parent of another file: {parent!r}")
    return members


def _read_member_bounded(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    payload = bytearray()
    with archive.open(info, "r") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > MAX_MEMBER_BYTES:
                raise ArchiveVersionError(f"ZIP member expanded beyond {MAX_MEMBER_BYTES} bytes: {info.filename!r}")
    if len(payload) != info.file_size:
        raise ArchiveVersionError(f"ZIP member size mismatch: {info.filename!r}")
    return bytes(payload)


def _extract_safely(input_path: Path, destination: Path) -> tuple[list[tuple[zipfile.ZipInfo, str]], str]:
    if input_path.is_symlink() or not input_path.is_file():
        raise ArchiveVersionError("input archive must be a regular non-symlink file")
    try:
        archive_hash = _sha256(input_path)
    except OSError as exc:
        raise ArchiveVersionError(f"cannot read input archive: {exc}") from exc
    try:
        with zipfile.ZipFile(input_path, "r") as archive:
            members = _validate_archive_metadata(archive)
            # Read every non-directory member through the bounded reader below.
            # ZipExtFile validates CRC at EOF, so this avoids a second unbounded
            # full-archive decompression pass through ZipFile.testzip().
            for info, relative in members:
                target = destination.joinpath(*PurePosixPath(relative.rstrip("/")).parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = _read_member_bounded(archive, info)
                with target.open("xb") as stream:
                    stream.write(payload)
            return members, archive_hash
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        if isinstance(exc, ArchiveVersionError):
            raise
        raise ArchiveVersionError(f"cannot safely read ZIP-compatible add-on: {exc}") from exc


def _discover_archive_manifests(project: Path) -> list[str]:
    manifests = sorted(
        p for p in project.rglob("manifest.json")
        if p.is_file() and not any(part.startswith("__MACOSX") for part in p.relative_to(project).parts)
    )
    if not manifests:
        raise ArchiveVersionError("no manifest.json was found inside the add-on archive")
    if len(manifests) > 2:
        relatives = [p.relative_to(project).as_posix() for p in manifests]
        raise ArchiveVersionError(
            f"archive contains {len(manifests)} manifests {relatives}; expected one pack or a BP/RP pair. "
            "Separate unrelated variants before versioning."
        )
    paths = [p.relative_to(project).as_posix() for p in manifests]
    if len(paths) == 2:
        roles = {"bp": 0, "rp": 0}
        for relative in paths:
            data, _ = _read_json(project / relative)
            modules = data.get("modules")
            if not isinstance(modules, list):
                raise ArchiveVersionError(f"manifest modules must be an array: {relative}")
            module_types = {m.get("type") for m in modules if isinstance(m, dict)}
            if "resources" in module_types:
                roles["rp"] += 1
            elif module_types.intersection({"data", "script"}):
                roles["bp"] += 1
        if roles != {"bp": 1, "rp": 1}:
            raise ArchiveVersionError(f"two-manifest archive must contain one BP and one RP; found {roles}")
    return paths


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_repacked_archive(output_path: Path, plan: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(output_path, "r") as archive:
            corrupt = archive.testzip()
            if corrupt is not None:
                raise ArchiveVersionError(f"output ZIP CRC failed at {corrupt!r}")
            for row in plan["changes"]:
                member = row["manifest"]
                try:
                    manifest = json.loads(archive.read(member).decode("utf-8-sig"))
                except KeyError as exc:
                    raise ArchiveVersionError(f"updated manifest missing from output archive: {member}") from exc
                header = manifest.get("header", {})
                version = Version.parse(header.get("version"), f"{member}: archive header.version")
                expected = Version.parse(row["new_version"], "expected version")
                if version != expected:
                    raise ArchiveVersionError(f"output archive manifest version mismatch at {member}")
                if header.get("name") != row["new_header_name"]:
                    raise ArchiveVersionError(f"output archive manifest name mismatch at {member}")
                if header.get("uuid") != row["header_uuid_preserved"]:
                    raise ArchiveVersionError(f"output archive header UUID changed at {member}")
                for index, module in enumerate(manifest.get("modules", [])):
                    if isinstance(module, dict) and "version" in module:
                        module_version = Version.parse(module["version"], f"{member}: modules[{index}].version")
                        if module_version != expected:
                            raise ArchiveVersionError(f"output archive module version mismatch at {member}[{index}]")
                checks.append({"manifest": member, "version": str(version), "header_name": header.get("name")})

            locale_checks = []
            for locale in plan.get("verification", {}).get("localized_title_checks", []):
                lang_path = (PurePosixPath(locale["manifest"]).parent / "texts" / locale["locale_file"]).as_posix()
                try:
                    content = archive.read(lang_path).decode("utf-8-sig")
                except KeyError as exc:
                    raise ArchiveVersionError(f"localized title file missing from output archive: {lang_path}") from exc
                values = [
                    line.split("=", 1)[1].strip()
                    for line in content.splitlines()
                    if "=" in line and not line.lstrip().startswith(("#", ";"))
                    and line.split("=", 1)[0].strip() == locale["key"]
                ]
                if len(values) != 1 or values[0] != locale["visible_title"]:
                    raise ArchiveVersionError(f"localized title verification failed in output archive: {lang_path}")
                locale_checks.append({"path": lang_path, "visible_title": values[0]})
            for edit in plan.get("pack_dependency_updates", []):
                try:
                    source_doc = json.loads(archive.read(edit["manifest"]).decode("utf-8-sig"))
                    target_row = next(row for row in plan["changes"] if row["manifest"] == edit["target_manifest"])
                    target_version = Version.parse(target_row["new_version"])
                    dep = source_doc["dependencies"][edit["dependency_index"]]
                    dep_version = Version.parse(dep.get("version"), "output archive dependency.version")
                    if dep_version != target_version:
                        raise ArchiveVersionError(
                            f"output archive dependency version mismatch: {edit['manifest']} -> {edit['target_manifest']}"
                        )
                except (KeyError, IndexError, TypeError, StopIteration) as exc:
                    raise ArchiveVersionError(f"could not verify output archive pack dependency: {edit}") from exc
    except (zipfile.BadZipFile, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchiveVersionError(f"could not verify output archive: {exc}") from exc
    return {"passed": True, "archive_crc": "PASS", "manifest_checks": checks, "localized_title_checks": locale_checks}


def _write_output_archive(
    input_path: Path,
    output_path: Path,
    project: Path,
    members: list[tuple[zipfile.ZipInfo, str]],
) -> None:
    if output_path.resolve(strict=False) == input_path.resolve(strict=True):
        raise ArchiveVersionError("output archive path must differ from input archive path")
    if not output_path.parent.is_dir():
        raise ArchiveVersionError("output archive parent directory must already exist")
    try:
        with zipfile.ZipFile(input_path, "r") as source:
            with output_path.open("xb") as destination_file:
                try:
                    with zipfile.ZipFile(destination_file, "w") as destination:
                        destination.comment = source.comment
                        for info, relative in members:
                            if info.is_dir():
                                destination.writestr(info, b"")
                            else:
                                staged_file = project.joinpath(*PurePosixPath(relative).parts)
                                payload = staged_file.read_bytes()
                                destination.writestr(info, payload)
                except Exception:
                    destination_file.flush()
                    raise
    except FileExistsError:
        raise
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        if isinstance(exc, ArchiveVersionError):
            raise
        raise ArchiveVersionError(f"failed to write output archive: {exc}") from exc


def update_archive(
    input_archive: str | Path,
    output_archive: str | Path | None = None,
    *,
    change_type: str,
    title_suffix: str = "v{version}",
    allow_independent_versions: bool = False,
    apply: bool = False,
) -> dict[str, Any]:
    source_input = Path(input_archive)
    if source_input.is_symlink():
        raise ArchiveVersionError("input archive must not be a symbolic link")
    if not source_input.is_file():
        raise ArchiveVersionError("input archive must be a regular file")
    source = source_input.resolve(strict=True)
    output = None
    if output_archive is not None:
        output_input = Path(output_archive)
        if output_input.is_symlink():
            raise ArchiveVersionError("output archive path must not be a symbolic link")
        output = output_input.resolve(strict=False)
    if source.suffix.lower() not in {".mcaddon", ".mcpack", ".zip"}:
        raise ArchiveVersionError("input must be a .mcaddon, .mcpack or ZIP-compatible archive")
    if apply and output is None:
        raise ArchiveVersionError("output_archive is required when apply=True")
    with tempfile.TemporaryDirectory(prefix="bedrock-addon-version-") as temp_root:
        workspace = Path(temp_root)
        project = workspace / "project"
        project.mkdir()
        members, source_hash = _extract_safely(source, project)
        manifest_paths = _discover_archive_manifests(project)
        request = {
            "project_directory": "project",
            "change_type": change_type,
            "title_suffix": title_suffix,
            "manifest_paths": manifest_paths,
            "allow_independent_versions": allow_independent_versions,
        }
        plan = plan_update(request, workspace, apply=apply)
        if not plan.get("verification", {}).get("passed"):
            raise ArchiveVersionError("staged project failed version verification")
        if not apply:
            return {
                "status": "DRY_RUN",
                "input_archive": str(source),
                "input_sha256": source_hash,
                "archive_member_count": len(members),
                "change_type": change_type,
                "versions": plan["changes"],
                "pack_dependency_updates": plan["pack_dependency_updates"],
                "verification": plan["verification"],
                "output_not_created": True,
                "input_modified": False,
                "runtime_status": "NOT RUN",
            }
        if not plan.get("verification", {}).get("verified_after_write"):
            raise ArchiveVersionError("staged project failed post-write version verification")
        assert output is not None
        _write_output_archive(source, output, project, members)
        try:
            archive_verification = _verify_repacked_archive(output, plan)
        except Exception:
            output.unlink(missing_ok=True)
            raise
        return {
            "status": "SUCCESS",
            "input_archive": str(source),
            "input_sha256": source_hash,
            "output_archive": str(output),
            "output_sha256": _sha256(output),
            "output_size_bytes": output.stat().st_size,
            "change_type": change_type,
            "versions": plan["changes"],
            "pack_dependency_updates": plan["pack_dependency_updates"],
            "verification": plan["verification"],
            "archive_verification": archive_verification,
            "input_modified": False,
            "runtime_status": "NOT RUN",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="input .mcaddon/.mcpack archive")
    parser.add_argument("--output", help="new output archive path; required with --apply and never overwritten")
    parser.add_argument("--change-type", choices=("major", "medium", "fix"), required=True)
    parser.add_argument("--title-suffix", default="v{version}")
    parser.add_argument("--allow-independent-versions", action="store_true")
    parser.add_argument("--apply", action="store_true", help="write a new archive; without this flag only preview")
    parser.add_argument("--report", help="optional JSON report path")
    args = parser.parse_args(argv)
    if args.apply and not args.output:
        print(json.dumps({"status": "FAIL", "error": "--output is required with --apply"}, ensure_ascii=False))
        return 2
    report_path = Path(args.report) if args.report else None
    if report_path is not None and (report_path.exists() or report_path.is_symlink() or not report_path.parent.is_dir()):
        print(json.dumps({"status": "FAIL", "error": f"report path is not a new file in an existing directory: {report_path}"}, ensure_ascii=False))
        return 2
    try:
        result = update_archive(
            args.archive,
            args.output,
            change_type=args.change_type,
            title_suffix=args.title_suffix,
            allow_independent_versions=args.allow_independent_versions,
            apply=args.apply,
        )
    except (ArchiveVersionError, AddonVersionError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if report_path is not None:
        with report_path.open("x", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
