"""Pinned, bounded ZIP inspection for static Bedrock archive analysis.

The archive is opened once with O_NOFOLLOW where supported. The same file
 descriptor is used for hashing, central-directory inspection, CRC checks and
 member reads, so a path/symlink swap cannot replace the bytes after preflight.
No archive member is extracted or executed.
"""
from __future__ import annotations

import hashlib
import os
import stat
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 50_000
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
_HASH_CHUNK_BYTES = 1024 * 1024



def validate_zip_member_namespace(archive: zipfile.ZipFile, *, max_ratio: int = 1000) -> list[tuple[zipfile.ZipInfo, str, bool]]:
    """Validate ZIP names/types and return safe (info, normalized_path, is_dir) rows.

    Explicit directory entries are accepted when their sole trailing slash is
    consistent with their type. Duplicate/case/Unicode aliases and file-directory
    namespace collisions are rejected before any member is decompressed.
    """
    import re
    import unicodedata
    from pathlib import PurePosixPath

    if isinstance(max_ratio, bool) or not isinstance(max_ratio, int) or max_ratio < 1:
        raise ValueError("max_ratio must be a positive integer")

    rows: list[tuple[zipfile.ZipInfo, str, bool]] = []
    explicit: dict[str, tuple[str, bool]] = {}
    file_keys: set[str] = set()
    dir_keys: set[str] = set()

    for info in archive.infolist():
        raw = info.filename
        if not isinstance(raw, str) or not raw or "\x00" in raw:
            raise ValueError("empty or NUL-containing ZIP member name")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
            raise ValueError(f"control character in ZIP member path: {raw!r}")
        if "\\" in raw or raw.startswith("/") or raw.startswith("//"):
            raise ValueError(f"absolute or backslash ZIP member path: {raw!r}")

        is_dir = info.is_dir()
        if raw.endswith("/") != is_dir:
            raise ValueError(f"ZIP directory marker/type mismatch: {raw!r}")
        trimmed = raw[:-1] if is_dir else raw
        if not trimmed:
            raise ValueError(f"empty ZIP member path: {raw!r}")
        parts = trimmed.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError(f"empty, dot or parent segment in ZIP path: {raw!r}")
        if re.match(r"^[A-Za-z]:", parts[0]) or PurePosixPath(trimmed).is_absolute():
            raise ValueError(f"drive-prefixed or absolute ZIP path: {raw!r}")

        mode = (info.external_attr >> 16) & 0xFFFF
        kind = stat.S_IFMT(mode)
        if kind == stat.S_IFLNK:
            raise ValueError(f"symlink ZIP member is not supported: {raw!r}")
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError(f"special ZIP member type is not supported: {raw!r}")
        if kind == stat.S_IFDIR and not is_dir:
            raise ValueError(f"directory mode without directory entry: {raw!r}")
        if kind == stat.S_IFREG and is_dir:
            raise ValueError(f"regular-file mode with directory entry: {raw!r}")
        if info.flag_bits & 0x1:
            raise ValueError(f"encrypted ZIP member is not supported: {raw!r}")
        if info.file_size < 0 or info.compress_size < 0:
            raise ValueError(f"negative ZIP size metadata: {raw!r}")
        if info.file_size and info.compress_size == 0:
            raise ValueError(f"invalid zero compressed size: {raw!r}")
        if info.compress_size and info.file_size / info.compress_size > max_ratio:
            raise ValueError(f"ZIP compression ratio exceeds {max_ratio}: {raw!r}")

        normalized = unicodedata.normalize("NFC", trimmed)
        key = normalized.casefold()
        if key in explicit:
            previous, previous_dir = explicit[key]
            if previous_dir != is_dir:
                raise ValueError(f"file/directory collision: {raw!r} conflicts with {previous!r}")
            raise ValueError(f"duplicate or Unicode/case-colliding ZIP path: {raw!r} conflicts with {previous!r}")
        explicit[key] = (raw, is_dir)
        (dir_keys if is_dir else file_keys).add(key)
        rows.append((info, normalized, is_dir))

    collisions = file_keys & dir_keys
    for file_key in file_keys:
        parts = file_key.split("/")
        for idx in range(1, len(parts)):
            parent = "/".join(parts[:idx])
            if parent in file_keys:
                collisions.add(parent)
    if collisions:
        first = sorted(collisions)[0]
        raise ValueError(f"file/directory namespace collision at {first!r}")
    return rows

def _stat_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        getattr(info, "st_mtime_ns", int(info.st_mtime * 1_000_000_000)),
    )


def _hash_bounded_stream(stream, declared_size: int) -> str:
    digest = hashlib.sha256()
    total = 0
    while True:
        # Read at most one byte beyond the configured limit. This also bounds
        # hashing if another process grows the opened file while it is read.
        remaining = MAX_ARCHIVE_BYTES + 1 - total
        if remaining <= 0:
            raise ValueError(
                f"archive exceeds the {MAX_ARCHIVE_BYTES}-byte compressed size limit"
            )
        block = stream.read(min(_HASH_CHUNK_BYTES, remaining))
        if not block:
            break
        total += len(block)
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError(
                f"archive exceeds the {MAX_ARCHIVE_BYTES}-byte compressed size limit"
            )
        digest.update(block)
    if total != declared_size:
        raise ValueError("archive changed while its bytes were being hashed")
    return digest.hexdigest()


@contextmanager
def open_bounded_zip(path: str | Path) -> Iterator[tuple[zipfile.ZipFile, dict[str, int | str]]]:
    """Yield a ZIP reader and metadata backed by one pinned, bounded file.

    The caller must finish all CRC checks and member reads inside the context.
    The descriptor remains open until the caller exits, and a final fstat
    detects in-place changes to the opened file during inspection.
    """
    archive_path = Path(path)
    fd: int | None = None
    try:
        try:
            path_stat = os.lstat(archive_path)
            if stat.S_ISLNK(path_stat.st_mode):
                raise ValueError(f"archive is unavailable or is a symlink: {archive_path}")
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(archive_path, flags)
        except OSError as exc:
            raise ValueError(f"archive is unavailable or is a symlink: {archive_path}") from exc

        try:
            stream = os.fdopen(fd, "rb", closefd=True)
        except OSError as exc:
            raise ValueError("archive must be a regular file") from exc
        fd = None  # stream now owns the descriptor
        with stream:
            opened_stat = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened_stat.st_mode):
                raise ValueError("archive must be a regular file")
            if (opened_stat.st_dev, opened_stat.st_ino) != (path_stat.st_dev, path_stat.st_ino):
                raise ValueError("archive path changed or resolved through a symlink while opening")

            size = opened_stat.st_size
            if size > MAX_ARCHIVE_BYTES:
                raise ValueError(
                    f"archive exceeds the {MAX_ARCHIVE_BYTES}-byte compressed size limit"
                )
            identity = _stat_identity(opened_stat)
            digest = _hash_bounded_stream(stream, size)
            if _stat_identity(os.fstat(stream.fileno())) != identity:
                raise ValueError("archive changed while its bytes were being hashed")
            stream.seek(0)

            try:
                archive = zipfile.ZipFile(stream)
            except (OSError, zipfile.BadZipFile, RuntimeError, EOFError, UnicodeDecodeError) as exc:
                raise ValueError(f"archive central directory is invalid: {exc}") from exc

            with archive:
                try:
                    entries = archive.infolist()
                    if len(entries) > MAX_ARCHIVE_MEMBERS:
                        raise ValueError(
                            f"archive member count {len(entries)} exceeds the {MAX_ARCHIVE_MEMBERS}-entry limit"
                        )
                    uncompressed = 0
                    for member in entries:
                        if member.is_dir():
                            continue
                        if member.file_size > MAX_MEMBER_BYTES:
                            raise ValueError(
                                f"archive member {member.filename!r} exceeds the {MAX_MEMBER_BYTES}-byte per-member limit"
                            )
                        if member.file_size and member.compress_size == 0:
                            raise ValueError(f"archive member {member.filename!r} has zero compressed size")
                        if member.compress_size and member.file_size / member.compress_size > MAX_COMPRESSION_RATIO:
                            raise ValueError(
                                f"archive member {member.filename!r} exceeds the {MAX_COMPRESSION_RATIO}:1 compression ratio limit"
                            )
                        uncompressed += member.file_size
                        if uncompressed > MAX_UNCOMPRESSED_BYTES:
                            raise ValueError(
                                f"archive declared uncompressed bytes exceed the {MAX_UNCOMPRESSED_BYTES}-byte limit"
                            )
                except (OSError, zipfile.BadZipFile, RuntimeError, EOFError, UnicodeDecodeError) as exc:
                    raise ValueError(f"archive central directory is invalid: {exc}") from exc

                metadata: dict[str, int | str] = {
                    "compressed_bytes": size,
                    "entry_count": len(entries),
                    "uncompressed_bytes": uncompressed,
                    "sha256": digest,
                }
                yield archive, metadata

                if _stat_identity(os.fstat(stream.fileno())) != identity:
                    raise ValueError("archive changed while its contents were being inspected")
    finally:
        if fd is not None:
            os.close(fd)


def validate_zip_limits(path: str | Path) -> dict[str, int]:
    """Validate ZIP resource limits without extraction or path re-opening.

    Retained as a compatibility API for callers that only need declared
    archive metadata. New readers should use :func:`open_bounded_zip` and keep
    all subsequent inspection inside its context.
    """
    with open_bounded_zip(path) as (_, metadata):
        return {
            key: int(metadata[key])
            for key in ("compressed_bytes", "entry_count", "uncompressed_bytes")
        }
