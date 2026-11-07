#!/usr/bin/env python3
"""Build a bounded, read-only provenance and manifest index for Bedrock ZIP archives.

The tool never extracts or executes archive members. It records archive/member
metadata, pack manifests, Script API module dependencies and extension counts.
"""
from __future__ import annotations
import argparse, json, sys, zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 50_000
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from archive_safety import open_bounded_zip, validate_zip_member_namespace


def safe_path(name: str) -> bool:
    """Compatibility predicate for one non-directory POSIX ZIP path."""
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        return False
    if name.startswith("/") or any(ord(c) < 32 or ord(c) == 127 for c in name):
        return False
    trimmed = name[:-1] if name.endswith("/") else name
    if not trimmed:
        return False
    parts = trimmed.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        return False
    if len(name) > 1 and name[1] == ":":
        return False
    return not PurePosixPath(name).is_absolute()


def manifest_summary(path: str, obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {'path': path, 'parse_status': 'valid_json_non_object'}
    header = obj.get('header') if isinstance(obj.get('header'), dict) else {}
    modules = obj.get('modules') if isinstance(obj.get('modules'), list) else []
    deps = obj.get('dependencies') if isinstance(obj.get('dependencies'), list) else []
    script_modules = [m for m in modules if isinstance(m, dict) and m.get('type') == 'script']
    api_deps = [d for d in deps if isinstance(d, dict) and isinstance(d.get('module_name'), str) and d['module_name'].startswith('@minecraft/')]
    pack_deps = [d for d in deps if isinstance(d, dict) and isinstance(d.get('uuid'), str)]
    return {
        'path': path, 'parse_status': 'valid', 'name': header.get('name'),
        'header_version': header.get('version'), 'min_engine_version': header.get('min_engine_version'),
        'modules': [{'type': m.get('type'), 'version': m.get('version'), 'language': m.get('language')} for m in modules if isinstance(m, dict)],
        'script_module_count': len(script_modules),
        'script_api_dependencies': [{'module_name': d.get('module_name'), 'version': d.get('version')} for d in api_deps],
        'pack_uuid_dependencies': [{'uuid': d.get('uuid'), 'version': d.get('version')} for d in pack_deps],
        'capabilities': obj.get('capabilities', []),
        'experiments': obj.get('settings', {}).get('experiments', []) if isinstance(obj.get('settings'), dict) else [],
    }


def build_index(archive: Path, source_url: str = '', source_label: str = '') -> dict[str, Any]:
    """Index a bounded ZIP using one pinned descriptor for hash and member reads."""
    archive = Path(archive).expanduser()
    with open_bounded_zip(archive) as (z, pinned):
        members = validate_zip_member_namespace(z)
        bad = z.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC/decompression failure at member: {bad!r}")

        ext_counts = Counter(PurePosixPath(name).suffix.lower() or '[no extension]'
                             for _, name, is_dir in members if not is_dir)
        manifests = []
        total = int(pinned['uncompressed_bytes'])
        for info, name, is_dir in members:
            if is_dir or PurePosixPath(name).name.lower() != 'manifest.json':
                continue
            if info.file_size > MAX_MANIFEST_BYTES:
                manifests.append({'path': name, 'parse_status': 'skipped_size_limit'})
                continue
            try:
                with z.open(info) as stream:
                    raw = stream.read(MAX_MANIFEST_BYTES + 1)
                if len(raw) > MAX_MANIFEST_BYTES:
                    raise ValueError('manifest exceeds read limit')
                obj = json.loads(raw.decode('utf-8-sig'))
                manifests.append(manifest_summary(name, obj))
            except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError, zipfile.BadZipFile, OSError, ValueError) as exc:
                manifests.append({'path': name, 'parse_status': 'invalid_or_unreadable', 'error': str(exc)[:240]})

        return {
            'schema_version': 1, 'dataset_type': 'bedrock_reference_archive',
            'source_label': source_label or archive.name, 'source_url': source_url or None,
            'archive_name': archive.name, 'archive_size_bytes': int(pinned['compressed_bytes']),
            'archive_sha256': str(pinned['sha256']),
            'archive_stats': {'entry_count': len(members), 'file_count': sum(not row[2] for row in members),
                              'directory_count': sum(row[2] for row in members),
                              'declared_uncompressed_bytes': total,
                              'extension_counts': dict(sorted(ext_counts.items()))},
            'safety': {'path_traversal': 'PASS', 'absolute_paths': 'PASS', 'symlinks': 'PASS',
                       'duplicate_paths': 'REJECTED', 'case_unicode_collisions': 'REJECTED',
                       'file_directory_collisions': 'REJECTED', 'special_files': 'REJECTED',
                       'crc_test': 'PASS', 'hash_source': 'same_pinned_descriptor',
                       'extraction_performed': False, 'embedded_code_executed': False},
            'manifests': manifests,
            'limits': {'compressed_bytes': MAX_ARCHIVE_BYTES, 'entries': MAX_ENTRIES,
                       'member_bytes': MAX_MEMBER_BYTES, 'total_uncompressed_bytes': MAX_TOTAL_BYTES,
                       'manifest_bytes': MAX_MANIFEST_BYTES, 'compression_ratio': 1000}
        }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archives', nargs='+')
    p.add_argument('--output', required=True)
    p.add_argument('--source-url', default='')
    p.add_argument('--source-label', default='')
    a = p.parse_args()
    try:
        results = [build_index(Path(x).expanduser(), a.source_url, a.source_label) for x in a.archives]
        out = Path(a.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({'schema_version': 1, 'archives': results}, ensure_ascii=False, indent=2) + '\n'
        with out.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(payload)
        print(json.dumps({'status': 'ok', 'output': str(out), 'archives': len(results), 'manifests': sum(len(x['manifests']) for x in results)}))
        return 0
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
