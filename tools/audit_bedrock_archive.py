#!/usr/bin/env python3
"""Read-only static audit for Minecraft Bedrock .mcpack/.mcaddon/.zip archives.

Uses only Python's standard library. It does not extract files or modify archives.
This is a triage tool, not a replacement for version-aware Bedrock validation or
in-game testing. Run: python tools/audit_bedrock_archive.py path/to/archive.mcpack
"""
from __future__ import annotations
import argparse
import collections
import json
import sys
import zipfile
from pathlib import PurePosixPath

MAX_REPORT_EXAMPLES = 20


def strip_json_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving strings and line numbers."""
    out = []
    i = 0
    state = "normal"
    quote = ""
    escaped = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "normal":
            if ch in ('"', "'"):
                quote, state = ch, "string"
                out.append(ch); i += 1
            elif ch == "/" and nxt == "/":
                out.extend("  "); state = "line_comment"; i += 2
            elif ch == "/" and nxt == "*":
                out.extend("  "); state = "block_comment"; i += 2
            else:
                out.append(ch); i += 1
        elif state == "string":
            out.append(ch); i += 1
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == quote: state = "normal"
        elif state == "line_comment":
            if ch == "\n": out.append("\n"); state = "normal"
            else: out.append(" ")
            i += 1
        else:
            if ch == "*" and nxt == "/":
                out.extend("  "); i += 2; state = "normal"
            else:
                out.append("\n" if ch == "\n" else " "); i += 1
    return "".join(out)


def strip_trailing_commas(text: str) -> str:
    """Remove commas immediately before } or ], outside strings."""
    out = []
    i = 0
    quote = ""
    escaped = False
    while i < len(text):
        ch = text[i]
        if quote:
            out.append(ch)
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == quote: quote = ""
            i += 1
        elif ch in ('"', "'"):
            quote = ch; out.append(ch); i += 1
        elif ch == ",":
            j = i + 1
            while j < len(text) and text[j].isspace(): j += 1
            if j < len(text) and text[j] in "]}": i += 1
            else: out.append(ch); i += 1
        else:
            out.append(ch); i += 1
    return "".join(out)


def parse_json_candidates(raw: bytes):
    """Recovery modes are diagnostic only; never rewrite the source."""
    text = raw.decode("utf-8-sig", errors="replace")
    try:
        return "strict_json", json.loads(text), None
    except Exception as strict_error:
        no_comments = strip_json_comments(text)
        try:
            return "json_with_comments", json.loads(no_comments), str(strict_error)
        except Exception:
            relaxed = strip_trailing_commas(no_comments)
            try:
                return "json_comments_trailing_commas", json.loads(relaxed), str(strict_error)
            except Exception as final_error:
                return "invalid_or_nonstandard", None, f"strict: {strict_error}; recovery: {final_error}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="Path to .mcpack, .mcaddon, or ZIP archive")
    args = parser.parse_args()
    try:
        zf = zipfile.ZipFile(args.archive)
    except (OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"archive": args.archive, "error": str(exc)}, indent=2))
        return 2

    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        names = [i.filename for i in infos]
        counts = collections.Counter()
        examples = collections.defaultdict(list)
        manifests = []
        findings = []
        duplicates = [n for n, count in collections.Counter(names).items() if count > 1]
        unsafe_paths = []
        expanded_bytes = sum(i.file_size for i in infos)
        bad_member = zf.testzip()

        for info in infos:
            name = info.filename
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                unsafe_paths.append(name)
            if path.suffix:
                counts[path.suffix.lower()] += 1
            if info.file_size > 5 * 1024 * 1024:
                examples["large_files"].append({"path": name, "bytes": info.file_size})
            if path.suffix.lower() != ".json":
                continue
            raw = zf.read(info)
            if raw.startswith(b"\xef\xbb\xbf"):
                counts["json_bom"] += 1
            mode, data, error = parse_json_candidates(raw)
            counts["json_" + mode] += 1
            if mode != "strict_json":
                examples[mode].append({"path": name, "detail": error})
            if name.lower().endswith("manifest.json"):
                if not isinstance(data, dict):
                    findings.append({"severity": "needs_review", "code": "MANIFEST_UNPARSED", "path": name, "detail": error})
                    continue
                manifests.append({"path": name, "data": data})
                header = data.get("header", {})
                modules = data.get("modules", [])
                if not isinstance(header, dict) or not header.get("uuid"):
                    findings.append({"severity": "needs_review", "code": "MANIFEST_HEADER_UUID_MISSING", "path": name})
                if not isinstance(modules, list) or not modules:
                    findings.append({"severity": "needs_review", "code": "MANIFEST_MODULES_MISSING", "path": name})

        uuid_locations = collections.defaultdict(list)
        known_header_uuids = set()
        for rec in manifests:
            data = rec["data"]
            header = data.get("header", {})
            if isinstance(header, dict) and header.get("uuid"):
                uuid = str(header["uuid"]).lower()
                known_header_uuids.add(uuid)
                uuid_locations[uuid].append(rec["path"] + "#header")
            modules = data.get("modules", [])
            for module in modules if isinstance(modules, list) else []:
                if isinstance(module, dict) and module.get("uuid"):
                    uuid_locations[str(module["uuid"]).lower()].append(rec["path"] + "#module")
        for uuid, locations in uuid_locations.items():
            if len(locations) > 1:
                findings.append({"severity": "needs_review", "code": "DUPLICATE_UUID", "uuid": uuid, "locations": locations})

        manifest_summaries = []
        for rec in manifests:
            data = rec["data"]
            header = data.get("header", {}) if isinstance(data.get("header", {}), dict) else {}
            modules = data.get("modules", [])
            manifest_summaries.append({
                "path": rec["path"],
                "format_version": data.get("format_version"),
                "name": header.get("name"),
                "version": header.get("version"),
                "modules": [{"type": m.get("type"), "uuid": m.get("uuid"), "version": m.get("version"), "language": m.get("language")} for m in modules if isinstance(m, dict)] if isinstance(modules, list) else [],
                "dependencies": data.get("dependencies", []),
            })
            deps = data.get("dependencies", [])
            for dep in deps if isinstance(deps, list) else []:
                if isinstance(dep, dict) and dep.get("uuid") and str(dep["uuid"]).lower() not in known_header_uuids:
                    findings.append({"severity": "info", "code": "DEPENDENCY_UUID_NOT_IN_THIS_ARCHIVE", "path": rec["path"], "uuid": dep["uuid"], "note": "May be a separately installed pack; not necessarily an error."})

        report = {
            "archive": args.archive,
            "zip_integrity": "ok" if bad_member is None else "failed",
            "bad_member": bad_member,
            "file_count": len(infos),
            "uncompressed_bytes": expanded_bytes,
            "extensions": dict(sorted(counts.items())),
            "manifest_count": len(manifests),
            "manifests": manifest_summaries,
            "duplicate_archive_paths": duplicates[:MAX_REPORT_EXAMPLES],
            "unsafe_path_candidates": unsafe_paths[:MAX_REPORT_EXAMPLES],
            "findings": findings[:100],
            "examples": {key: value[:MAX_REPORT_EXAMPLES] for key, value in examples.items()},
            "limitations": [
                "Read-only static analysis; archive members are never extracted.",
                "JSON recovery modes are diagnostics only and do not prove Minecraft accepts a file.",
                "Version-aware Bedrock schema validation and in-game tests are not performed.",
                "Resource references, geometry/animation semantics, Script API compatibility, and subpack behavior require additional checks.",
            ],
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if bad_member is None else 1


if __name__ == "__main__":
    sys.exit(main())
