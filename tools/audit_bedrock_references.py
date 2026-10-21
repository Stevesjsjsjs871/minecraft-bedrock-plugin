#!/usr/bin/env python3
"""Heuristic path-reference audit for Bedrock archives; read-only, no extraction.

Detects explicit strings with known file extensions. This is a triage tool, not a
complete Bedrock reference resolver: identifier aliases, format-specific roots,
subpacks, and engine-provided assets need format-aware handling. Run from repo root:
python tools/audit_bedrock_references.py archive.mcpack
"""
from __future__ import annotations
import argparse
import collections
import json
import re
import zipfile
from pathlib import PurePosixPath
from audit_bedrock_archive import parse_json_candidates

PATH_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[A-Za-z0-9_@ .-]+/)*[A-Za-z0-9_@ .-]+\\.(?:png|tga|jpe?g|webp|ogg|wav|mp3|json|material|fsh|vsh|glsl|lang|mcmeta)(?:#[^\\s\\\"']*)?", re.I)
MAX_ITEMS = 100


def strings(value, pointer='$'):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, pointer + '/' + str(key).replace('~', '~0').replace('/', '~1'))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from strings(item, f'{pointer}/{i}')
    elif isinstance(value, str):
        yield pointer, value


def normalize_candidate(raw):
    value = raw.strip().replace('\\\\', '/')
    while value.startswith('./'):
        value = value[2:]
    return value


def audit(path):
    with zipfile.ZipFile(path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        names = {i.filename.casefold() for i in infos}
        name_list = list(names)
        refs, skipped = [], 0
        for info in infos:
            if PurePosixPath(info.filename).suffix.lower() != '.json':
                continue
            mode, data, error = parse_json_candidates(zf.read(info))
            if data is None:
                skipped += 1
                continue
            for pointer, value in strings(data):
                for match in PATH_RE.finditer(value):
                    candidate = normalize_candidate(match.group(0).split('#', 1)[0])
                    if '://' in candidate or candidate.startswith(('minecraft:', 'geometry.', 'controller.', 'animation.', 'query.')):
                        continue
                    parent = str(PurePosixPath(info.filename).parent)
                    relative = str(PurePosixPath(parent) / candidate) if parent != '.' else candidate
                    folded = candidate.casefold()
                    exists = folded in names or relative.casefold() in names or any(n.endswith('/' + folded) for n in name_list)
                    refs.append({'source': info.filename, 'json_pointer': pointer, 'reference': candidate,
                                 'exists_case_insensitive': exists})
        missing = [r for r in refs if not r['exists_case_insensitive']]
        return {
            'archive': path, 'archive_member_count': len(infos),
            'json_parsed': len([i for i in infos if PurePosixPath(i.filename).suffix.lower() == '.json']) - skipped,
            'json_unparsed_skipped': skipped, 'explicit_path_reference_count': len(refs),
            'unresolved_explicit_path_count': len(missing), 'unresolved_examples': missing[:MAX_ITEMS],
            'limitations': [
                'Heuristic only: detects explicit strings with known file extensions, not all Bedrock identifier references.',
                'Relative-path resolution varies by file format; checks archive-root, source-relative, and suffix candidates.',
                'Missing candidates are not proof of a defect: subpacks, aliases, generated content, and engine assets need context.',
                'No files are extracted, rewritten, or executed.'
            ]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive')
    ap.add_argument('--output')
    args = ap.parse_args()
    try:
        result = audit(args.archive)
    except (OSError, zipfile.BadZipFile) as exc:
        ap.error(str(exc))
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(rendered + '\\n')
    print(rendered)

if __name__ == '__main__':
    main()
