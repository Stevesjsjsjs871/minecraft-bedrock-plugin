#!/usr/bin/env python3
"""Regenerate the pinned Mojang Samples index from a SHA-256-verified official ZIP."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_INDEX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RestoreIndexError(ValueError):
    pass


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _regular_file(path: Path, max_bytes: int) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
        raise RestoreIndexError(f"expected a regular non-symlink file within {max_bytes} bytes: {path}")
    return info


def _read_json(path: Path, max_bytes: int = 2 * 1024 * 1024) -> Any:
    info = _regular_file(path, max_bytes)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        if identity(opened) != identity(info):
            raise RestoreIndexError(f"metadata changed while opening: {path}")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) != opened.st_size or len(raw) > max_bytes:
            raise RestoreIndexError(f"metadata changed or exceeded read limit: {path}")
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates, parse_constant=_reject_constant)
    finally:
        os.close(fd)


def _sha256(path: Path, max_bytes: int) -> str:
    info = _regular_file(path, max_bytes)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        if identity(opened) != identity(info):
            raise RestoreIndexError(f"archive changed while opening: {path}")
        digest = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if identity(os.fstat(fd)) != identity(opened):
            raise RestoreIndexError(f"archive changed while hashing: {path}")
        return digest.hexdigest()
    finally:
        os.close(fd)


def restore_index(archive: Path, metadata_path: Path, indexer: Path, output: Path) -> dict[str, Any]:
    archive, metadata_path, indexer, output = map(Path, (archive, metadata_path, indexer, output))
    metadata = _read_json(metadata_path)
    if not isinstance(metadata, dict):
        raise RestoreIndexError("INDEX_METADATA.json must be an object")
    required = {"source_archive", "target_version", "zip_sha256", "entry_count", "indexed_count", "declared_uncompressed_bytes", "category_counts"}
    missing = sorted(required - metadata.keys())
    if missing:
        raise RestoreIndexError("index metadata is missing: " + ", ".join(missing))
    source_name = metadata["source_archive"]
    target_version = metadata["target_version"]
    expected_sha = metadata["zip_sha256"]
    if not isinstance(source_name, str) or not source_name or Path(source_name).name != source_name:
        raise RestoreIndexError("source_archive must be a filename")
    if archive.name != source_name:
        raise RestoreIndexError(f"archive filename mismatch: expected {source_name!r}, got {archive.name!r}")
    if not isinstance(target_version, str) or not re.fullmatch(r"\d+(?:\.\d+){2,}", target_version):
        raise RestoreIndexError("target_version is invalid")
    if not isinstance(expected_sha, str) or not SHA256_RE.fullmatch(expected_sha):
        raise RestoreIndexError("zip_sha256 must be a lowercase SHA-256")
    for field in ("entry_count", "indexed_count", "declared_uncompressed_bytes"):
        if type(metadata[field]) is not int or metadata[field] < 0:
            raise RestoreIndexError(f"{field} must be a non-negative integer")
    categories = metadata["category_counts"]
    if not isinstance(categories, dict) or any(not isinstance(key, str) or type(value) is not int or value < 0 for key, value in categories.items()):
        raise RestoreIndexError("category_counts is invalid")
    tag, asset, url = metadata.get("source_release_tag"), metadata.get("source_asset_name"), metadata.get("source_asset_url")
    if any(value is not None for value in (tag, asset, url)):
        expected_url = f"https://github.com/Mojang/bedrock-samples/releases/download/{tag}/{asset}"
        if not isinstance(tag, str) or not isinstance(asset, str) or asset != source_name or url != expected_url:
            raise RestoreIndexError("official release tag/asset URL metadata is inconsistent")

    archive_sha = _sha256(archive, MAX_ARCHIVE_BYTES)
    if archive_sha != expected_sha:
        raise RestoreIndexError(f"official ZIP SHA-256 mismatch: expected {expected_sha}, got {archive_sha}")
    _regular_file(indexer, 2 * 1024 * 1024)
    parent_info = output.parent.lstat()
    if stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode):
        raise RestoreIndexError("output parent must be an existing real directory")
    if output.exists() or output.is_symlink():
        raise RestoreIndexError("refusing to overwrite an existing index")
    try:
        completed = subprocess.run(
            [sys.executable, str(indexer), str(archive), "--output", str(output), "--target-version", target_version],
            check=False, capture_output=True, text=True, timeout=600,
        )
        if completed.returncode != 0:
            raise RestoreIndexError("indexer failed: " + (completed.stderr or completed.stdout)[-2000:])
        output_info = _regular_file(output, MAX_INDEX_BYTES)
        with gzip.open(output, "rb") as stream:
            raw = stream.read(MAX_INDEX_UNCOMPRESSED_BYTES + 1)
        if len(raw) > MAX_INDEX_UNCOMPRESSED_BYTES:
            raise RestoreIndexError("decompressed generated index exceeds 64 MiB")
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates, parse_constant=_reject_constant)
        if not isinstance(payload, dict):
            raise RestoreIndexError("generated index must be a JSON object")
        stats = payload.get("archive_stats")
        entries = payload.get("entries")
        if not isinstance(stats, dict) or not isinstance(entries, list):
            raise RestoreIndexError("generated index archive_stats/entries are malformed")
        actual_categories = Counter(item.get("category") for item in entries if isinstance(item, dict) and isinstance(item.get("category"), str))
        expected_stats = {
            "entry_count": metadata["entry_count"],
            "indexed_count": metadata["indexed_count"],
            "declared_uncompressed_bytes": metadata["declared_uncompressed_bytes"],
        }
        if (
            payload.get("archive_file_name") != source_name
            or payload.get("archive_sha256") != archive_sha
            or payload.get("target_version") != target_version
            or stats != expected_stats
            or len(entries) != metadata["indexed_count"]
            or dict(sorted(actual_categories.items())) != dict(sorted(categories.items()))
        ):
            raise RestoreIndexError("generated index does not match pinned archive statistics/category metadata")
        expected_index_bytes = metadata.get("index_file_bytes")
        if expected_index_bytes is not None and (type(expected_index_bytes) is not int or output_info.st_size != expected_index_bytes):
            raise RestoreIndexError(f"generated index size mismatch: expected {expected_index_bytes}, got {output_info.st_size}")
        index_sha = _sha256(output, MAX_INDEX_BYTES)
        expected_index_sha = metadata.get("index_sha256")
        if expected_index_sha is not None and (not isinstance(expected_index_sha, str) or not SHA256_RE.fullmatch(expected_index_sha) or index_sha != expected_index_sha):
            raise RestoreIndexError("generated index SHA-256 does not match pinned index metadata")
        return {
            "status": "ok",
            "output": str(output),
            "index_bytes": output_info.st_size,
            "index_sha256": index_sha,
            "source_zip_sha256": archive_sha,
            "entry_count": stats["entry_count"],
            "indexed_count": stats["indexed_count"],
            "category_counts": dict(sorted(actual_categories.items())),
        }
    except Exception:
        try:
            if not output.is_symlink() and output.is_file():
                output.unlink()
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="Downloaded official Mojang full sample ZIP")
    parser.add_argument("--metadata", required=True, help="Pinned INDEX_METADATA.json")
    parser.add_argument("--indexer", required=True, help="Repository index_mojang_samples.py")
    parser.add_argument("--output", required=True, help="New generated .json.gz index path")
    args = parser.parse_args(argv)
    try:
        result = restore_index(Path(args.archive), Path(args.metadata), Path(args.indexer), Path(args.output))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, gzip.BadGzipFile) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
