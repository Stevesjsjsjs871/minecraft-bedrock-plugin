#!/usr/bin/env python3
"""Safe file inventory, provenance verification and deterministic tar.gz packaging."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import stat
import tarfile
import unicodedata
from pathlib import Path
from typing import Any

PLUGIN_NAME = "minecraft-bedrock-engineer"
PROVENANCE_FILE = "BUILD_PROVENANCE.json"
MAX_FILES = 10_000
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_PROVENANCE_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_TAR_METADATA_BYTES = 64 * 1024
MAX_TAR_METADATA_TOTAL_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_TRAILING_BYTES = 1024 * 1024
MAX_ARCHIVE_HEADERS = 2 * (MAX_FILES + 1)
MAX_ARCHIVE_STREAM_BYTES = (
    MAX_TOTAL_BYTES
    + MAX_PROVENANCE_BYTES
    + 3 * (MAX_FILES + 1) * tarfile.BLOCKSIZE
    + MAX_TAR_METADATA_TOTAL_BYTES
    + MAX_ARCHIVE_TRAILING_BYTES
)
ARCHIVE_READ_CHUNK_BYTES = 1024 * 1024
MAX_SIDECAR_BYTES = 256
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


class PackageSafetyError(ValueError):
    pass


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _safe_path(value: str) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return False
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts) or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return False
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    for part in parts:
        if ":" in part or part.endswith((".", " ")):
            return False
        if part.split(".", 1)[0].upper() in reserved:
            return False
    return not Path(value).is_absolute()


def _hash_file(path: Path, before: os.stat_result) -> str:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
        if not stat.S_ISREG(opened.st_mode) or identity(opened) != identity(before):
            raise PackageSafetyError(f"file changed or is not regular: {path}")
        digest = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if identity(os.fstat(fd)) != identity(opened):
            raise PackageSafetyError(f"file changed while hashing: {path}")
        return digest.hexdigest()
    finally:
        os.close(fd)


def scan_package(root: Path, exclude: set[str] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    root = Path(root).absolute()
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise PackageSafetyError(f"cannot inspect package root: {type(exc).__name__}: {exc}") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise PackageSafetyError("package root must be a real directory, not a symlink or special file")
    excluded = exclude or set()
    records, errors, total = [], [], 0
    stack = [(root, "")]
    entries_seen = 0
    while stack:
        directory, prefix = stack.pop()
        try:
            entries = []
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    entries_seen += 1
                    if entries_seen > MAX_FILES * 2:
                        errors.append(f"package exceeds {MAX_FILES} file/entry safety budget")
                        stack.clear()
                        break
                    entries.append(entry)
            entries.sort(key=lambda item: item.name)
        except OSError as exc:
            errors.append(f"cannot scan {prefix or '.'}: {type(exc).__name__}")
            continue
        for entry in entries:
            rel = f"{prefix}/{entry.name}" if prefix else entry.name
            if rel in excluded or any(rel.startswith(item.rstrip("/") + "/") for item in excluded):
                continue
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                errors.append(f"cannot stat {rel}: {type(exc).__name__}")
                continue
            if stat.S_ISLNK(info.st_mode):
                errors.append(f"symlink is forbidden: {rel}")
                continue
            if stat.S_ISDIR(info.st_mode):
                if entry.name == "__pycache__":
                    errors.append(f"generated Python cache directory is forbidden: {rel}")
                else:
                    stack.append((Path(entry.path), rel))
                continue
            if not stat.S_ISREG(info.st_mode):
                errors.append(f"non-regular file is forbidden: {rel}")
                continue
            if Path(entry.name).suffix.lower() in {".pyc", ".pyo"}:
                errors.append(f"generated Python bytecode is forbidden: {rel}")
                continue
            if not _safe_path(rel):
                errors.append(f"unsafe relative path: {rel!r}")
                continue
            if info.st_size > MAX_FILE_BYTES:
                errors.append(f"file exceeds {MAX_FILE_BYTES} bytes: {rel}")
                continue
            total += info.st_size
            if total > MAX_TOTAL_BYTES:
                errors.append(f"package exceeds {MAX_TOTAL_BYTES} total bytes")
                stack.clear()
                break
            try:
                digest = _hash_file(Path(entry.path), info)
            except (OSError, PackageSafetyError) as exc:
                errors.append(f"cannot safely hash {rel}: {type(exc).__name__}: {exc}")
                continue
            records.append({"path": rel, "size_bytes": info.st_size, "sha256": digest})
            if len(records) > MAX_FILES:
                errors.append(f"package exceeds {MAX_FILES} files")
                stack.clear()
                break
    records.sort(key=lambda item: item["path"])
    return records, errors


def payload_sha256(records: list[dict[str, Any]]) -> str:
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def make_provenance(root: Path, records: list[dict[str, Any]], source_commit: str, source_date_epoch: int, source_ref: str | None = None) -> dict[str, Any]:
    if not isinstance(source_commit, str) or not GIT_SHA_RE.fullmatch(source_commit):
        raise PackageSafetyError("source_commit must be a full 40- or 64-character lowercase Git object ID")
    if isinstance(source_date_epoch, bool) or not isinstance(source_date_epoch, int) or source_date_epoch < 0:
        raise PackageSafetyError("source_date_epoch must be a non-negative integer")
    files = [item for item in records if item["path"] != PROVENANCE_FILE]
    version = (Path(root) / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER_RE.fullmatch(version):
        raise PackageSafetyError(f"invalid package version: {version!r}")
    result = {
        "schema_version": 1,
        "plugin": PLUGIN_NAME,
        "version": version,
        "git_commit": source_commit,
        "source_date_epoch": source_date_epoch,
        "archive_format": "tar.gz",
        "payload_file_count": len(files),
        "payload_total_bytes": sum(item["size_bytes"] for item in files),
        "payload_sha256": payload_sha256(files),
        "provenance_file_excluded_from_payload_hash": True,
        "files": files,
    }
    if source_ref:
        result["source_ref"] = source_ref
    return result


def validate_provenance(provenance: Any, records: list[dict[str, Any]], expected_version: str | None = None) -> tuple[bool, str]:
    required = {"schema_version", "plugin", "version", "git_commit", "source_date_epoch", "archive_format", "payload_file_count", "payload_total_bytes", "payload_sha256", "provenance_file_excluded_from_payload_hash", "files"}
    if not isinstance(provenance, dict):
        return False, "provenance must be a JSON object"
    missing = sorted(required - provenance.keys())
    if missing:
        return False, "missing provenance fields: " + ", ".join(missing)
    if type(provenance["schema_version"]) is not int or provenance["schema_version"] != 1:
        return False, "unsupported provenance schema_version"
    if provenance["plugin"] != PLUGIN_NAME:
        return False, "provenance plugin identity mismatch"
    version = provenance["version"]
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version) or (expected_version and version != expected_version):
        return False, "provenance version does not match valid package SemVer"
    if not isinstance(provenance["git_commit"], str) or not GIT_SHA_RE.fullmatch(provenance["git_commit"]):
        return False, "provenance git_commit must be a full lowercase Git object ID"
    epoch = provenance["source_date_epoch"]
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        return False, "invalid provenance source_date_epoch"
    if provenance["archive_format"] != "tar.gz" or provenance["provenance_file_excluded_from_payload_hash"] is not True:
        return False, "unsupported archive format or invalid provenance self-exclusion marker"
    listed = provenance["files"]
    if not isinstance(listed, list):
        return False, "provenance files must be an array"
    normalized, seen = [], set()
    for index, item in enumerate(listed):
        if not isinstance(item, dict) or set(item) != {"path", "size_bytes", "sha256"}:
            return False, f"invalid provenance file record at index {index}"
        path, size, digest = item["path"], item["size_bytes"], item["sha256"]
        if not _safe_path(path) or path == PROVENANCE_FILE or path in seen:
            return False, f"unsafe, reserved or duplicate provenance path at index {index}"
        if isinstance(size, bool) or not isinstance(size, int) or size < 0 or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            return False, f"invalid size or SHA-256 for {path}"
        seen.add(path)
        normalized.append({"path": path, "size_bytes": size, "sha256": digest})
    if normalized != sorted(normalized, key=lambda item: item["path"]):
        return False, "provenance file records are not sorted"
    actual = sorted((item for item in records if item["path"] != PROVENANCE_FILE), key=lambda item: item["path"])
    if normalized != actual:
        return False, "provenance inventory or per-file SHA-256 does not match the package"
    if type(provenance["payload_file_count"]) is not int or provenance["payload_file_count"] != len(actual):
        return False, "provenance payload_file_count must be an integer matching the package"
    total = sum(item["size_bytes"] for item in actual)
    if type(provenance["payload_total_bytes"]) is not int or provenance["payload_total_bytes"] != total:
        return False, "provenance payload_total_bytes must be an integer matching the package"
    if "source_ref" in provenance and (not isinstance(provenance["source_ref"], str) or not provenance["source_ref"] or len(provenance["source_ref"]) > 1024):
        return False, "invalid provenance source_ref"
    digest = provenance["payload_sha256"]
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest) or digest != payload_sha256(actual):
        return False, "provenance payload_sha256 mismatch"
    return True, f"Verified {len(actual)} files / {total} bytes against Git commit {provenance['git_commit']}"


def verify_provenance(root: Path, records: list[dict[str, Any]], expected_version: str | None = None) -> tuple[bool, str]:
    path = Path(root) / PROVENANCE_FILE
    try:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_size > MAX_PROVENANCE_BYTES:
            return False, "BUILD_PROVENANCE.json must be a small regular non-symlink file"
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(fd)
            identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
            if not stat.S_ISREG(opened.st_mode) or identity(opened) != identity(info):
                return False, "BUILD_PROVENANCE.json changed while opening"
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(MAX_PROVENANCE_BYTES + 1)
            if len(raw) != opened.st_size or len(raw) > MAX_PROVENANCE_BYTES or identity(os.fstat(fd)) != identity(opened):
                return False, "BUILD_PROVENANCE.json changed or exceeded its read limit"
            provenance = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
        finally:
            os.close(fd)
    except FileNotFoundError:
        return False, "BUILD_PROVENANCE.json is missing; release candidates require provenance"
    except Exception as exc:
        return False, f"cannot read BUILD_PROVENANCE.json: {type(exc).__name__}: {exc}"
    return validate_provenance(provenance, records, expected_version)


def _hash_path(path: Path) -> str:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PackageSafetyError(f"expected a regular non-symlink file: {path}")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
        if identity(opened) != identity(info):
            raise PackageSafetyError(f"file changed while opening: {path}")
        digest = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if identity(os.fstat(fd)) != identity(opened):
            raise PackageSafetyError(f"file changed while hashing: {path}")
        return digest.hexdigest()
    finally:
        os.close(fd)


def _file_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        getattr(info, "st_ctime_ns", 0),
    )


def _open_path_without_symlinks(path: Path, flags: int) -> int:
    """Open a path without following any POSIX path-component symlinks."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    if (
        os.name == "posix"
        and nofollow
        and directory
        and os.open in getattr(os, "supports_dir_fd", set())
    ):
        parts = absolute.parts
        if not absolute.anchor or len(parts) < 2:
            raise PackageSafetyError("archive path must name a file below a filesystem root")
        current = os.open(absolute.anchor, os.O_RDONLY | directory)
        try:
            for component in parts[1:-1]:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | directory | nofollow,
                    dir_fd=current,
                )
                os.close(current)
                current = next_fd
            return os.open(parts[-1], flags | nofollow, dir_fd=current)
        finally:
            os.close(current)
    return os.open(absolute, flags | nofollow)


def _open_regular_file(path: Path, label: str) -> tuple[int, os.stat_result]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    try:
        before = absolute.lstat()
    except OSError as exc:
        raise PackageSafetyError(f"{label} is unavailable: {type(exc).__name__}") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise PackageSafetyError(f"{label} must be a regular non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    try:
        fd = _open_path_without_symlinks(absolute, flags)
    except OSError as exc:
        raise PackageSafetyError(f"cannot safely open {label}: {type(exc).__name__}: {exc}") from exc
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or _file_identity(opened) != _file_identity(before):
            raise PackageSafetyError(f"{label} changed while opening or is not regular")
        return fd, opened
    except Exception:
        os.close(fd)
        raise


def _hash_open_file(fd: int, snapshot: os.stat_result, label: str) -> str:
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while chunk := os.read(fd, ARCHIVE_READ_CHUNK_BYTES):
        digest.update(chunk)
    if _file_identity(os.fstat(fd)) != _file_identity(snapshot):
        raise PackageSafetyError(f"{label} changed while hashing")
    os.lseek(fd, 0, os.SEEK_SET)
    return digest.hexdigest()


def _read_open_file_limited(fd: int, snapshot: os.stat_result, limit: int, label: str) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    total = 0
    while True:
        chunk = os.read(fd, min(64 * 1024, limit - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise PackageSafetyError(f"{label} exceeds its {limit}-byte read limit")
        chunks.append(chunk)
    if _file_identity(os.fstat(fd)) != _file_identity(snapshot):
        raise PackageSafetyError(f"{label} changed while reading")
    return b"".join(chunks)


class _BoundedArchiveReader:
    """Cap bytes returned by the decompressor; never allow read-all requests."""

    def __init__(self, source, limit: int):
        self.source = source
        self.limit = limit
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        if not isinstance(size, int) or size < 0:
            raise PackageSafetyError("archive verifier forbids unbounded stream reads")
        if size == 0:
            return b""
        remaining = self.limit - self.bytes_read
        chunk = self.source.read(min(size, remaining + 1))
        self.bytes_read += len(chunk)
        if self.bytes_read > self.limit:
            raise PackageSafetyError(
                f"decompressed archive stream exceeds {self.limit} bytes"
            )
        return chunk


def verify_archive(archive: Path, sidecar: Path) -> dict[str, Any]:
    """Verify a tar.gz archive in one bounded streaming pass without extraction.

    The archive is hashed and parsed through the same no-follow file descriptor.
    gzip.GzipFile supplies bounded decompression and validates the gzip trailer;
    tarfile's stream mode avoids getmembers() and random-access member caching.
    Local PAX headers are allowed only within strict per-header and aggregate
    budgets. Global PAX, GNU long-name/link and sparse extensions are rejected.
    """
    archive_path = Path(os.path.abspath(os.fspath(archive)))
    sidecar_path = Path(os.path.abspath(os.fspath(sidecar)))
    archive_fd, archive_snapshot = _open_regular_file(archive_path, "archive")
    try:
        if archive_snapshot.st_size > MAX_ARCHIVE_BYTES:
            raise PackageSafetyError(
                f"archive exceeds the {MAX_ARCHIVE_BYTES}-byte compressed size limit"
            )
        digest = _hash_open_file(archive_fd, archive_snapshot, "archive")
        sidecar_fd, sidecar_snapshot = _open_regular_file(sidecar_path, "archive SHA-256 sidecar")
        try:
            sidecar_data = _read_open_file_limited(
                sidecar_fd, sidecar_snapshot, MAX_SIDECAR_BYTES, "archive SHA-256 sidecar"
            )
        finally:
            os.close(sidecar_fd)
        expected = f"{digest}  {archive_path.name}\n".encode("ascii")
        if sidecar_data != expected:
            raise PackageSafetyError("archive SHA-256 sidecar is missing or incorrect")

        records: list[dict[str, Any]] = []
        provenance = None
        seen: set[str] = set()
        total = 0
        member_count = 0

        class BoundedTarInfo(tarfile.TarInfo):
            metadata_total = 0
            header_count = 0

            def _proc_gnusparse_01(self, next_member, pax_headers):
                raise PackageSafetyError("GNU sparse PAX maps are not supported in release archives")

            def _proc_gnusparse_00(self, next_member, raw_headers):
                raise PackageSafetyError("GNU sparse PAX headers are not supported in release archives")

            def _proc_gnusparse_10(self, next_member, pax_headers, tarfile_object):
                raise PackageSafetyError("GNU sparse PAX maps are not supported in release archives")

            def _proc_member(self, tarfile_object):
                type(self).header_count += 1
                if type(self).header_count > MAX_ARCHIVE_HEADERS:
                    raise PackageSafetyError(
                        f"archive header count exceeds {MAX_ARCHIVE_HEADERS}"
                    )
                if self.type == tarfile.XHDTYPE:
                    if self.size < 0 or self.size > MAX_TAR_METADATA_BYTES:
                        raise PackageSafetyError(
                            f"PAX header exceeds the {MAX_TAR_METADATA_BYTES}-byte limit"
                        )
                    type(self).metadata_total += self.size
                    if type(self).metadata_total > MAX_TAR_METADATA_TOTAL_BYTES:
                        raise PackageSafetyError(
                            "aggregate PAX metadata exceeds its safety limit"
                        )
                elif self.type in {
                    tarfile.XGLTYPE,
                    getattr(tarfile, "SOLARIS_XHDTYPE", b"X"),
                    tarfile.GNUTYPE_LONGNAME,
                    tarfile.GNUTYPE_LONGLINK,
                    tarfile.GNUTYPE_SPARSE,
                }:
                    raise PackageSafetyError(
                        f"unsupported tar extension type: {self.type!r}"
                    )
                return super()._proc_member(tarfile_object)

        with os.fdopen(os.dup(archive_fd), "rb") as raw:
            raw.seek(0)
            with gzip.GzipFile(fileobj=raw, mode="rb") as decompressed:
                bounded = _BoundedArchiveReader(decompressed, MAX_ARCHIVE_STREAM_BYTES)
                try:
                    with tarfile.open(
                        fileobj=bounded,
                        mode="r|",
                        tarinfo=BoundedTarInfo,
                        errorlevel=2,
                    ) as tar:
                        for member in tar:
                            member_count += 1
                            if member_count > MAX_FILES + 1:
                                raise PackageSafetyError(
                                    f"archive file count exceeds {MAX_FILES} payload files"
                                )
                            name = member.name
                            if (
                                not isinstance(name, str)
                                or not _safe_path(name)
                                or member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE)
                                or not member.isfile()
                                or member.linkname
                                or member.issparse()
                            ):
                                raise PackageSafetyError(
                                    f"unsafe, duplicate or non-regular archive member: {name!r}"
                                )
                            portable_name = unicodedata.normalize("NFC", name).casefold()
                            if portable_name in seen:
                                raise PackageSafetyError(
                                    f"duplicate or case-colliding archive member: {name!r}"
                                )
                            seen.add(portable_name)
                            if (
                                member.mode < 0
                                or member.mode & 0o7022
                                or member.size < 0
                            ):
                                raise PackageSafetyError(
                                    f"unsafe mode or size on archive member: {name!r}"
                                )
                            member_limit = (
                                MAX_PROVENANCE_BYTES if name == PROVENANCE_FILE else MAX_FILE_BYTES
                            )
                            if member.size > member_limit:
                                raise PackageSafetyError(
                                    f"archive member {name!r} exceeds its {member_limit}-byte limit"
                                )
                            total += member.size
                            if total > MAX_TOTAL_BYTES + MAX_PROVENANCE_BYTES:
                                raise PackageSafetyError(
                                    "archive uncompressed file data exceeds safety limit"
                                )
                            stream = tar.extractfile(member)
                            if stream is None:
                                raise PackageSafetyError(f"cannot read archive member: {name}")
                            with stream:
                                if name == PROVENANCE_FILE:
                                    raw_provenance = stream.read(MAX_PROVENANCE_BYTES + 1)
                                    if len(raw_provenance) != member.size or len(raw_provenance) > MAX_PROVENANCE_BYTES:
                                        raise PackageSafetyError("invalid provenance member size")
                                    if stream.read(1):
                                        raise PackageSafetyError("provenance member exceeds its declared size")
                                    provenance = json.loads(
                                        raw_provenance.decode("utf-8"),
                                        object_pairs_hook=_pairs_no_duplicates,
                                    )
                                else:
                                    hasher = hashlib.sha256()
                                    size = 0
                                    while chunk := stream.read(ARCHIVE_READ_CHUNK_BYTES):
                                        size += len(chunk)
                                        if size > member.size or size > MAX_FILE_BYTES:
                                            raise PackageSafetyError(
                                                f"archive member exceeds its declared or allowed size: {name}"
                                            )
                                        hasher.update(chunk)
                                    if size != member.size:
                                        raise PackageSafetyError(
                                            f"archive member size mismatch: {name}"
                                        )
                                    records.append(
                                        {"path": name, "size_bytes": size, "sha256": hasher.hexdigest()}
                                    )

                        trailing_bytes = 0
                        while chunk := tar.fileobj.read(64 * 1024):
                            trailing_bytes += len(chunk)
                            if trailing_bytes > MAX_ARCHIVE_TRAILING_BYTES:
                                raise PackageSafetyError(
                                    "tar archive has excessive trailing padding"
                                )
                            if any(chunk):
                                raise PackageSafetyError(
                                    "tar archive contains non-zero data after its end marker"
                                )
                        if trailing_bytes < 1024:
                            raise PackageSafetyError(
                                "tar archive is missing its two zero end-of-archive blocks"
                            )
                except PackageSafetyError:
                    raise
                except Exception as exc:
                    raise PackageSafetyError(
                        f"archive stream is invalid: {type(exc).__name__}: {exc}"
                    ) from exc

        if _file_identity(os.fstat(archive_fd)) != _file_identity(archive_snapshot):
            raise PackageSafetyError("archive changed during verification")
        if provenance is None:
            raise PackageSafetyError("archive is missing BUILD_PROVENANCE.json")
        records.sort(key=lambda item: item["path"])
        ok, message = validate_provenance(provenance, records)
        if not ok:
            raise PackageSafetyError(message)
        return {
            "archive": str(archive_path),
            "archive_sha256": digest,
            "payload_file_count": len(records),
            "payload_total_bytes": sum(item["size_bytes"] for item in records),
            "provenance": provenance,
        }
    finally:
        os.close(archive_fd)

def build_archive(root: Path, output: Path, source_commit: str, source_date_epoch: int, source_ref: str | None = None, exclude: set[str] | None = None) -> dict[str, Any]:
    root, output = Path(root).absolute(), Path(output).absolute()
    if not GIT_SHA_RE.fullmatch(source_commit):
        raise PackageSafetyError("source_commit must be a full lowercase Git object ID")
    if isinstance(source_date_epoch, bool) or not isinstance(source_date_epoch, int) or source_date_epoch < 0:
        raise PackageSafetyError("source_date_epoch must be a non-negative integer")
    if root.is_symlink() or not root.is_dir() or output.parent.is_symlink() or not output.parent.is_dir():
        raise PackageSafetyError("package root and output parent must be existing real directories")
    try:
        inside = os.path.commonpath([str(root), str(output)]) == str(root)
    except ValueError:
        inside = False
    if inside:
        raise PackageSafetyError("archive output must be outside the package root")
    sidecar = Path(str(output) + ".sha256")
    if output.exists() or output.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise PackageSafetyError("archive and sidecar must not already exist")
    records, violations = scan_package(root, exclude)
    if violations:
        raise PackageSafetyError("package hygiene failed: " + "; ".join(violations[:20]))
    if any(item["path"] == PROVENANCE_FILE for item in records):
        raise PackageSafetyError("source already contains stale BUILD_PROVENANCE.json")
    provenance = make_provenance(root, records, source_commit, source_date_epoch, source_ref)
    raw_provenance = (json.dumps(provenance, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    created_archive = created_sidecar = False
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
        created_archive = True
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=source_date_epoch) as gz:
                with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                    for name in sorted([item["path"] for item in records] + [PROVENANCE_FILE]):
                        if name == PROVENANCE_FILE:
                            data, mode = raw_provenance, 0o644
                            source = None
                        else:
                            source = root / name
                            info = source.stat(follow_symlinks=False)
                            mode = 0o755 if info.st_mode & 0o111 else 0o644
                            data = None
                        member = tarfile.TarInfo(name)
                        member.size = len(data) if data is not None else next(item["size_bytes"] for item in records if item["path"] == name)
                        member.mtime, member.uid, member.gid = source_date_epoch, 0, 0
                        member.uname, member.gname, member.mode, member.pax_headers = "", "", mode, {}
                        if data is not None:
                            import io
                            tar.addfile(member, io.BytesIO(data))
                        else:
                            fd = os.open(source, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
                            try:
                                opened = os.fstat(fd)
                                if not stat.S_ISREG(opened.st_mode) or opened.st_size != member.size:
                                    raise PackageSafetyError(f"source file changed or is not regular: {name}")
                                with os.fdopen(fd, "rb", closefd=False) as stream:
                                    tar.addfile(member, stream)
                                if (os.fstat(fd).st_dev, os.fstat(fd).st_ino, os.fstat(fd).st_size, os.fstat(fd).st_mtime_ns) != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns):
                                    raise PackageSafetyError(f"source file changed while archiving: {name}")
                            finally:
                                os.close(fd)
            raw.flush()
            os.fsync(raw.fileno())
        archive_hash = _hash_path(output)
        fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
        created_sidecar = True
        with os.fdopen(fd, "wb") as stream:
            stream.write(f"{archive_hash}  {output.name}\n".encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        return verify_archive(output, sidecar)
    except Exception:
        if created_sidecar:
            try: sidecar.unlink()
            except OSError: pass
        if created_archive:
            try: output.unlink()
            except OSError: pass
        raise
