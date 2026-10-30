#!/usr/bin/env python3
"""Compare a Plugin Creator ZIP/tar.gz archive with checked-out plugin source.

Repository-side release QA only: the archive is inspected in place, never
extracted, and neither the archive nor the checkout is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

PACKAGE_ROOT_FILES = (
    ".codex-plugin/plugin.json",
    ".mcp.json",
    "CHANGELOG.md",
    "README.md",
    "VERSION",
    "archive_safety.py",
    "mcp.json",
    "plugin.json",
)
PACKAGE_DIRECTORIES = ("server", "skills")
PRUNED_DIRECTORIES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
MAX_ARCHIVE_ENTRIES = 20_000
MAX_ARCHIVE_TOTAL_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_FILE_BYTES = 128 * 1024 * 1024


class ParityError(Exception):
    """Raised for an unsafe or unreadable archive/repository input."""


def _safe_relative_path(raw: str) -> str:
    if not raw or "\x00" in raw or "\\" in raw:
        raise ParityError(f"unsafe archive path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ParityError(f"unsafe archive path: {raw!r}")
    normalized = path.as_posix()
    if normalized != raw.rstrip("/"):
        raise ParityError(f"non-canonical archive path: {raw!r}")
    return normalized


def _collect_repository_files(repo_root: Path) -> tuple[dict[str, Path], list[str]]:
    root = repo_root.resolve(strict=True)
    if not root.is_dir():
        raise ParityError("repository root is not a directory")

    files: dict[str, Path] = {}
    errors: list[str] = []
    for relative in PACKAGE_ROOT_FILES:
        candidate = root / relative
        if candidate.is_symlink():
            errors.append(f"repository package path is a symlink: {relative}")
        elif not candidate.is_file():
            errors.append(f"repository package file is missing: {relative}")
        else:
            files[relative] = candidate

    for directory in PACKAGE_DIRECTORIES:
        base = root / directory
        if base.is_symlink() or not base.is_dir():
            errors.append(f"repository package directory is missing or unsafe: {directory}")
            continue
        for current, dirnames, filenames in os.walk(base, topdown=True, followlinks=False):
            current_path = Path(current)
            kept_dirs: list[str] = []
            for dirname in dirnames:
                if dirname in PRUNED_DIRECTORIES:
                    continue
                child = current_path / dirname
                if child.is_symlink():
                    errors.append(f"repository package directory is a symlink: {child.relative_to(root).as_posix()}")
                else:
                    kept_dirs.append(dirname)
            dirnames[:] = kept_dirs
            for filename in filenames:
                child = current_path / filename
                relative = child.relative_to(root).as_posix()
                if child.is_symlink():
                    errors.append(f"repository package file is a symlink: {relative}")
                elif child.is_file():
                    files[relative] = child
    return files, errors


class ArchiveIndex:
    """Read-only index for ZIP and tar archives with bounded member sizes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.kind = ""
        self.handle: zipfile.ZipFile | tarfile.TarFile
        self.entries: dict[str, zipfile.ZipInfo | tarfile.TarInfo] = {}
        self.errors: list[str] = []
        self._open_and_index()

    def _open_and_index(self) -> None:
        if zipfile.is_zipfile(self.path):
            self.kind = "zip"
            self.handle = zipfile.ZipFile(self.path, "r")
            members: list[zipfile.ZipInfo | tarfile.TarInfo] = self.handle.infolist()
        elif tarfile.is_tarfile(self.path):
            self.kind = "tar"
            self.handle = tarfile.open(self.path, "r:*")
            members = self.handle.getmembers()
        else:
            raise ParityError("archive is neither a supported ZIP nor tar archive")

        if len(members) > MAX_ARCHIVE_ENTRIES:
            self.close()
            raise ParityError(f"archive contains too many entries: {len(members)} > {MAX_ARCHIVE_ENTRIES}")

        total_size = 0
        for member in members:
            if self.kind == "zip":
                assert isinstance(member, zipfile.ZipInfo)
                name = member.filename
                is_directory = member.is_dir()
                mode = (member.external_attr >> 16) & 0xFFFF
                if not is_directory and stat.S_ISLNK(mode):
                    self.errors.append(f"archive entry is a symlink: {name}")
                    continue
                file_type = stat.S_IFMT(mode)
                if not is_directory and file_type and file_type != stat.S_IFREG:
                    self.errors.append(f"archive entry is not a regular file: {name}")
                    continue
                size = member.file_size
            else:
                assert isinstance(member, tarfile.TarInfo)
                name = member.name
                is_directory = member.isdir()
                if not is_directory and not member.isreg():
                    self.errors.append(f"archive entry is not a regular file: {name}")
                    continue
                size = member.size

            try:
                relative = _safe_relative_path(name.rstrip("/") if is_directory else name)
            except ParityError as exc:
                self.errors.append(str(exc))
                continue
            if is_directory:
                continue
            if relative in self.entries:
                self.errors.append(f"duplicate archive entry: {relative}")
                continue
            if size < 0 or size > MAX_ARCHIVE_FILE_BYTES:
                self.errors.append(f"archive entry exceeds size limit: {relative}")
                continue
            total_size += size
            if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                self.close()
                raise ParityError(
                    f"archive uncompressed size exceeds limit: {total_size} > {MAX_ARCHIVE_TOTAL_BYTES}"
                )
            self.entries[relative] = member

    def read(self, relative: str) -> bytes:
        member = self.entries[relative]
        if self.kind == "zip":
            assert isinstance(self.handle, zipfile.ZipFile)
            data = self.handle.read(member)
        else:
            assert isinstance(self.handle, tarfile.TarFile)
            stream = self.handle.extractfile(member)
            if stream is None:
                raise ParityError(f"unable to read regular archive member: {relative}")
            with stream:
                data = stream.read(MAX_ARCHIVE_FILE_BYTES + 1)
        if len(data) > MAX_ARCHIVE_FILE_BYTES:
            raise ParityError(f"archive member exceeded read limit: {relative}")
        return data

    def close(self) -> None:
        handle = getattr(self, "handle", None)
        if handle is not None:
            handle.close()


def _read_archive_json(archive: ArchiveIndex, path: str) -> Any:
    if path not in archive.entries:
        raise ParityError(f"required metadata file is missing from archive: {path}")
    try:
        return json.loads(archive.read(path).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile, tarfile.TarError) as exc:
        raise ParityError(f"invalid JSON metadata {path}: {exc}") from exc


def _metadata_errors(archive: ArchiveIndex) -> list[str]:
    errors: list[str] = []
    try:
        root_manifest = _read_archive_json(archive, "plugin.json")
        compat_manifest = _read_archive_json(archive, ".codex-plugin/plugin.json")
        dot_mcp = _read_archive_json(archive, ".mcp.json")
        mcp = _read_archive_json(archive, "mcp.json")
        version = archive.read("VERSION").decode("utf-8").strip() if "VERSION" in archive.entries else ""
    except ParityError as exc:
        return [str(exc)]
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, tarfile.TarError) as exc:
        return [f"unable to read release metadata: {exc}"]

    if not isinstance(root_manifest, dict) or not isinstance(compat_manifest, dict):
        errors.append("plugin manifests must be JSON objects")
        return errors
    if root_manifest.get("name") != compat_manifest.get("name"):
        errors.append("plugin names differ between root and compatibility manifests")
    versions = [version, root_manifest.get("version"), compat_manifest.get("version")]
    if not all(isinstance(value, str) and value for value in versions) or len(set(versions)) != 1:
        errors.append("VERSION, plugin.json and compatibility manifest versions differ")

    try:
        prompts = root_manifest["extensions"]["com.openai"]["interface"]["defaultPrompt"]
        compat_prompts = compat_manifest["interface"]["defaultPrompt"]
        if not isinstance(prompts, list) or len(prompts) != 3:
            errors.append("root manifest must contain exactly three default prompts")
        if prompts != compat_prompts:
            errors.append("default prompts differ between root and compatibility manifests")
    except (KeyError, TypeError):
        errors.append("default prompts are missing or malformed")

    config_sets: list[set[str]] = []
    for config_path, config in ((".mcp.json", dot_mcp), ("mcp.json", mcp)):
        if not isinstance(config, dict) or not isinstance(config.get("mcpServers"), dict):
            errors.append(f"{config_path} must contain an mcpServers object")
            continue
        servers = config["mcpServers"]
        config_sets.append(set(servers))
        for server_name, server in servers.items():
            if not isinstance(server, dict) or server.get("type") != "stdio":
                errors.append(f"{config_path}: {server_name} is not a stdio server")
                continue
            args = server.get("args", [])
            if not isinstance(args, list):
                errors.append(f"{config_path}: {server_name} args must be an array")
                continue
            for arg in args:
                if not isinstance(arg, str):
                    continue
                normalized = arg.replace("\\", "/")
                marker = "${PLUGIN_ROOT}/"
                if marker in normalized:
                    relative = normalized.split(marker, 1)[1]
                elif normalized.endswith(".py") and not PurePosixPath(normalized).is_absolute():
                    relative = normalized.removeprefix("./")
                else:
                    continue
                try:
                    relative = _safe_relative_path(relative)
                except ParityError:
                    errors.append(f"{config_path}: unsafe server script path for {server_name}: {arg}")
                    continue
                if relative not in archive.entries:
                    errors.append(f"{config_path}: server script is absent from archive: {relative}")
    if len(config_sets) == 2 and config_sets[0] != config_sets[1]:
        errors.append("MCP server names differ between .mcp.json and mcp.json")
    return errors


def audit_archive(archive_path: Path, repo_root: Path) -> dict[str, Any]:
    expected, repository_errors = _collect_repository_files(repo_root)
    report: dict[str, Any] = {
        "status": "FAIL",
        "archive": str(archive_path),
        "repository_root": str(repo_root),
        "archive_type": None,
        "summary": {},
        "missing": [],
        "extra": [],
        "mismatched": [],
        "errors": list(repository_errors),
    }

    try:
        archive = ArchiveIndex(archive_path)
        report["archive_type"] = archive.kind
        report["errors"].extend(archive.errors)
        expected_names = set(expected)
        actual_names = set(archive.entries)
        report["missing"] = sorted(expected_names - actual_names)
        report["extra"] = sorted(actual_names - expected_names)

        matched = 0
        for relative in sorted(expected_names & actual_names):
            try:
                archive_bytes = archive.read(relative)
                repository_bytes = expected[relative].read_bytes()
            except (OSError, zipfile.BadZipFile, tarfile.TarError, RuntimeError, ParityError) as exc:
                report["errors"].append(f"unable to compare {relative}: {exc}")
                continue
            if archive_bytes != repository_bytes:
                report["mismatched"].append({
                    "path": relative,
                    "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
                    "repository_sha256": hashlib.sha256(repository_bytes).hexdigest(),
                })
            else:
                matched += 1

        report["errors"].extend(_metadata_errors(archive))
        report["summary"] = {
            "repository_files": len(expected),
            "archive_files": len(archive.entries),
            "byte_identical_files": matched,
            "missing_files": len(report["missing"]),
            "extra_files": len(report["extra"]),
            "mismatched_files": len(report["mismatched"]),
        }
        archive.close()
    except (OSError, zipfile.BadZipFile, tarfile.TarError, ParityError) as exc:
        report["errors"].append(str(exc))

    if not any((report["missing"], report["extra"], report["mismatched"], report["errors"])):
        report["status"] = "PASS"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path, help="Plugin Creator .zip or .tar.gz archive")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="checked-out plugin repository root")
    parser.add_argument("--json-output", type=Path, help="optional path for a machine-readable JSON report")
    args = parser.parse_args(argv)

    report = audit_archive(args.archive, args.repo_root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    print(rendered if args.json_output is None else f"{report['status']}: {report['summary']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
