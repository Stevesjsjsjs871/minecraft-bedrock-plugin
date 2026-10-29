#!/usr/bin/env python3
"""Index Mojang Bedrock sample examples from an explicitly supplied local ZIP.

This creates a compact searchable manifest of file paths, sizes, hashes and a
small allowlisted set of parsed identifiers. It does not extract archive
members, execute files, install dependencies or rewrite the sample ZIP.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import zipfile
from pathlib import PurePosixPath
from typing import Any

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 50_000
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
TEXT_SUFFIXES = {".json", ".md", ".lang", ".molang", ".txt", ".js", ".ts", ".html"}
MAX_TEXT_READ_BYTES = 2 * 1024 * 1024
MAX_INDEX_FILES = 30_000
DEFAULT_CATEGORIES = {
    "behavior_pack/items": "item",
    "behavior_pack/blocks": "block",
    "behavior_pack/entities": "entity_behavior",
    "behavior_pack/recipes": "recipe",
    "behavior_pack/loot_tables": "loot_table",
    "behavior_pack/trading": "trading",
    "behavior_pack/functions": "function",
    "behavior_pack/feature_rules": "feature_rule",
    "behavior_pack/features": "feature",
    "resource_pack/entity": "client_entity",
    "resource_pack/models/entity": "geometry",
    "resource_pack/animations": "animation",
    "resource_pack/animation_controllers": "animation_controller",
    "resource_pack/render_controllers": "render_controller",
    "resource_pack/particles": "particle",
    "resource_pack/ui": "ui",
    "resource_pack/textures": "texture",
    "resource_pack/sounds": "sound",
    "resource_pack/attachables": "attachable",
    "resource_pack/texts": "localization",
    "resource_pack/materials": "material",
    "resource_pack/particles": "particle",
    "resource_pack/models/blocks": "block_model",
}
IDENTIFIER_FIELDS = {
    "identifier", "description.identifier", "geometry", "animation", "animations",
    "animation_controllers", "render_controllers", "particle_effect", "sound"
}
ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")


def safe_member_path(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name or any(ord(c) < 32 for c in name):
        return False
    # Validate raw segments before PurePosixPath normalization (which collapses // and .).
    raw_parts = name.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        return False
    path = PurePosixPath(name)
    if path.is_absolute():
        return False
    # Refuse drive-prefixed and UNC-ish forms even if treated as relative by POSIX.
    if re.match(r"^[A-Za-z]:", name) or name.startswith("//"):
        return False
    return True


def parse_json_allowlisted(raw: bytes) -> dict[str, Any] | list[Any] | None:
    """Parse strict JSON only; Mojang files with comments are left unparsed."""
    try:
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, (dict, list)) else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def get_ids(obj: Any) -> list[str]:
    found: set[str] = set()
    def walk(value: Any, depth: int = 0) -> None:
        if depth > 16:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "identifier" and isinstance(child, str) and ID_RE.fullmatch(child):
                    found.add(child)
                elif key in {"geometry", "animation", "animation_controller", "render_controller"}:
                    if isinstance(child, str) and ID_RE.fullmatch(child):
                        found.add(child)
                    elif isinstance(child, dict):
                        for v in child.values():
                            if isinstance(v, str) and ID_RE.fullmatch(v):
                                found.add(v)
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:5000]:
                walk(child, depth + 1)
    walk(obj)
    return sorted(found)[:500]


def categorize(path: str) -> str:
    choices = sorted(DEFAULT_CATEGORIES.items(), key=lambda kv: len(kv[0]), reverse=True)
    for prefix, category in choices:
        if path.startswith(prefix + "/") or path == prefix:
            return category
    suffix = PurePosixPath(path).suffix.lower()
    return {".json": "json", ".png": "texture", ".tga": "texture", ".lang": "localization",
            ".js": "script", ".ts": "script", ".ogg": "sound", ".fsb": "sound"}.get(suffix, "other")


def sha256_file(path: Any) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="Path to the local Mojang bedrock-samples ZIP")
    parser.add_argument("--output", required=True, help="Write JSON index here")
    parser.add_argument("--target-version", default="1.26.50.4")
    parser.add_argument("--max-files", type=int, default=MAX_INDEX_FILES)
    args = parser.parse_args()
    archive_path = __import__("pathlib").Path(args.archive).expanduser().resolve()
    output_path = __import__("pathlib").Path(args.output).expanduser().resolve()
    if args.max_files < 1 or args.max_files > MAX_INDEX_FILES:
        print(json.dumps({"status": "error", "error": "max-files must be 1..30000"}))
        return 2
    try:
        size = archive_path.stat().st_size
        if size > MAX_ARCHIVE_BYTES:
            raise ValueError(f"archive compressed bytes {size} exceed limit {MAX_ARCHIVE_BYTES}")
        with zipfile.ZipFile(archive_path) as z:
            infos = z.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ValueError(f"entry count {len(infos)} exceeds limit {MAX_ENTRIES}")
            total = 0
            unsafe = []
            for info in infos:
                if info.is_dir():
                    continue
                if not safe_member_path(info.filename):
                    unsafe.append(info.filename[:240])
                if info.file_size > MAX_MEMBER_BYTES:
                    raise ValueError(f"member exceeds per-file limit: {info.filename[:160]}")
                total += info.file_size
                if total > MAX_TOTAL_BYTES:
                    raise ValueError(f"declared uncompressed payload exceeds limit {MAX_TOTAL_BYTES}")
            if unsafe:
                raise ValueError(f"archive contains unsafe member paths (first: {unsafe[:3]})")
            entries = []
            indexed = 0
            for info in infos:
                if info.is_dir():
                    continue
                if indexed >= args.max_files:
                    break
                path = info.filename
                suffix = PurePosixPath(path).suffix.lower()
                if suffix not in TEXT_SUFFIXES and not any(path.startswith(p + "/") for p in DEFAULT_CATEGORIES):
                    continue
                ids: list[str] = []
                json_parsed = False
                if suffix == ".json" and info.file_size <= MAX_TEXT_READ_BYTES:
                    try:
                        raw = z.read(info)
                    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
                        raise ValueError(f"cannot read archive member {path}: {exc}") from exc
                    digest = hashlib.sha256(raw).hexdigest()
                    parsed = parse_json_allowlisted(raw)
                    json_parsed = parsed is not None
                    if parsed is not None:
                        ids = get_ids(parsed)
                else:
                    # Hash non-JSON/binary entries only when they fit the read cap.
                    if info.file_size <= MAX_TEXT_READ_BYTES:
                        try:
                            raw = z.read(info)
                        except (zipfile.BadZipFile, RuntimeError, OSError):
                            raw = b""
                        digest = hashlib.sha256(raw).hexdigest() if raw else ""
                    else:
                        digest = ""
                entries.append({
                    "path": path,
                    "category": categorize(path),
                    "size_bytes": info.file_size,
                    "sha256": digest,
                    "identifiers": ids,
                    "json_parsed": json_parsed,
                })
                indexed += 1
        payload = {
            "schema_version": 1,
            "dataset_id": "mojang-bedrock-samples",
            "target_version": args.target_version,
            "source": "https://github.com/Mojang/bedrock-samples",
            "archive_file_name": archive_path.name,
            "archive_sha256": sha256_file(archive_path),
            "index_policy": {
                "no_extraction": True,
                "no_execution": True,
                "no_network": True,
                "note": "The indexer reads selected ZIP member bytes in memory to hash/parse content; it never writes members to disk.",
                "strict_json_only": True,
                "path_policy": "relative POSIX paths only",
                "limits": {
                    "compressed_bytes": MAX_ARCHIVE_BYTES,
                    "entries": MAX_ENTRIES,
                    "member_bytes": MAX_MEMBER_BYTES,
                    "total_uncompressed_bytes": MAX_TOTAL_BYTES,
                    "max_indexed_files": args.max_files,
                    "max_json_parse_bytes": MAX_TEXT_READ_BYTES,
                    "max_hashed_member_bytes": MAX_TEXT_READ_BYTES
                }
            },
            "archive_stats": {
                "entry_count": len(infos),
                "indexed_count": len(entries),
                "declared_uncompressed_bytes": total
            },
            "entries": entries
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if output_path.suffix.lower() == ".gz":
            with output_path.open("wb") as raw_output:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, compresslevel=9, mtime=0) as compressed_output:
                    compressed_output.write(serialized)
        else:
            output_path.write_bytes(serialized + b"\n")
        print(json.dumps({"status": "ok", "output": str(output_path), "indexed_count": len(entries),
                          "archive_sha256": payload["archive_sha256"]}, ensure_ascii=False))
        return 0
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
