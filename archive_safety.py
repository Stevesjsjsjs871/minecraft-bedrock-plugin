"""Shared bounded ZIP inspection for the MCP server and standalone analyzer CLI.

This module never extracts archive members or executes embedded content.
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 50_000
MAX_MEMBER_BYTES = 128 * 1024 * 1024


def validate_zip_limits(path: str | Path) -> dict[str, int]:
    """Validate a ZIP-compatible archive's declared resource limits.

    The method checks compressed size, entry count, per-member and cumulative
    uncompressed sizes before any caller reads member payloads. It deliberately
    does not perform a CRC scan; the analyzer performs that as a separate step
    after the resource limits have passed.
    """
    archive_path = Path(path)
    try:
        size = os.path.getsize(archive_path)
    except OSError as exc:
        raise ValueError(f"archive is unavailable: {archive_path}") from exc

    if size > MAX_ARCHIVE_BYTES:
        raise ValueError(
            f"archive exceeds the {MAX_ARCHIVE_BYTES}-byte compressed size limit"
        )
    if not zipfile.is_zipfile(archive_path):
        raise ValueError("not a valid ZIP-compatible archive")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_MEMBERS:
                raise ValueError(
                    f"archive member count {len(entries)} exceeds the {MAX_ARCHIVE_MEMBERS}-entry limit"
                )
            uncompressed = 0
            for info in entries:
                if info.is_dir():
                    continue
                if info.file_size > MAX_MEMBER_BYTES:
                    raise ValueError(
                        f"archive member {info.filename!r} exceeds the {MAX_MEMBER_BYTES}-byte per-member limit"
                    )
                uncompressed += info.file_size
                if uncompressed > MAX_UNCOMPRESSED_BYTES:
                    raise ValueError(
                        f"archive declared uncompressed bytes exceed the {MAX_UNCOMPRESSED_BYTES}-byte limit"
                    )
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError(f"archive central directory is invalid: {exc}") from exc

    return {
        "compressed_bytes": size,
        "entry_count": len(entries),
        "uncompressed_bytes": uncompressed,
    }
