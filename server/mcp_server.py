#!/usr/bin/env python3
"""Read-only stdio MCP server for Minecraft Bedrock Engineer (stdlib only)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from archive_safety import (  # noqa: E402
    MAX_ARCHIVE_BYTES,
    MAX_ARCHIVE_MEMBERS,
    MAX_MEMBER_BYTES,
    MAX_UNCOMPRESSED_BYTES,
    validate_zip_limits,
)

VERSION_FILE = ROOT / "VERSION"
SERVER_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
MAX_MEMBERS_RETURNED = 2000
SUPPORTED_SUFFIXES = {".mcaddon", ".mcpack", ".mcworld", ".zip"}
AUDITOR = ROOT / "skills" / "automated-validation" / "scripts" / "bedrock_audit.py"

# Keep the priority workflow short and front-loaded for clients that expose it.
WORKFLOW_INSTRUCTIONS = (
    "Use inspect_archive for archive structure; audit_pack for static checks; "
    "diff_packs for concise file/finding/reference regressions; compare_baseline for full baseline reports; "
    "get_resource_graph for references; and validate_manifest/audit_geometry/audit_animation for focused checks. "
    "Cite paths/evidence, disclose coverage gaps, treat heuristics as unconfirmed, never claim in-game tests unless run, "
    "and never modify/delete files. Creation requires a separate approved MCT CLI; this MCP stays read-only."
)


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


_PATH = {"type": "string", "minLength": 1, "maxLength": 4096, "description": "Path to an archive inside the configured workspace; relative paths are recommended."}
_DOMAIN = {"type": "string", "enum": ["all", "geometry", "animations", "controllers", "textures", "ui", "localization"]}
TOOLS = [
    _tool("audit_pack", "Run all supported static checks against a Bedrock ZIP-compatible archive. Returns the full structured report; runtime remains NOT RUN.", {"candidate_path": _PATH}, ["candidate_path"]),
    _tool("compare_baseline", "Compare a candidate archive against a baseline and report additions, removals, modifications and audit findings.", {"candidate_path": _PATH, "baseline_path": _PATH}, ["candidate_path", "baseline_path"]),
    _tool("diff_packs", "Summarize changes between two Bedrock pack archives: file additions/removals/modifications, newly introduced findings, severity changes and unresolved resource-graph regressions. Read-only; no patch is applied.", {"candidate_path": _PATH, "baseline_path": _PATH}, ["candidate_path", "baseline_path"]),
    _tool("get_resource_graph", "Return the static resource reference graph. Choose a fixed domain or all; unresolved/dynamic references are not runtime proof.", {"archive_path": _PATH, "domain": _DOMAIN}, ["archive_path"]),
    _tool("validate_manifest", "Return manifest, UUID and dependency checks and related findings from the static report.", {"archive_path": _PATH}, ["archive_path"]),
    _tool("audit_geometry", "Return geometry, bone, cube, vector and UV checks/findings from the static report.", {"archive_path": _PATH}, ["archive_path"]),
    _tool("audit_animation", "Return animation/controller and related identifier checks/findings from the static report.", {"archive_path": _PATH}, ["archive_path"]),
    _tool("inspect_archive", "List archive metadata and unsafe/duplicate path indicators without extracting files or reading file payloads.", {"archive_path": _PATH}, ["archive_path"]),
]
TOOL_BY_NAME = {item["name"]: item for item in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    out: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        out["error"]["details"] = details
    return out


def _workspace_root() -> Path:
    raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    base = Path(raw).expanduser() if raw else Path.cwd()
    try:
        return base.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"Configured workspace does not exist: {base}") from exc



def _resolve_archive(raw: Any) -> Path:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 4096:
        raise ValueError("archive path must be a non-empty string no longer than 4096 characters")
    root = _workspace_root()
    value = Path(raw).expanduser()
    path = value if value.is_absolute() else root / value
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"archive path is unavailable: {raw}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("archive path resolves outside the configured workspace") from exc
    if not resolved.is_file():
        raise ValueError("archive path must identify a regular file")
    if resolved.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported archive extension {resolved.suffix!r}; expected one of {sorted(SUPPORTED_SUFFIXES)}")
    validate_zip_limits(resolved)
    return resolved


def _validate_arguments(name: str, args: Any) -> dict[str, Any]:
    if name not in TOOL_BY_NAME:
        raise ValueError(f"unknown tool {name!r}")
    if not isinstance(args, dict):
        raise ValueError("arguments must be a JSON object")
    schema = TOOL_BY_NAME[name]["inputSchema"]
    props = schema["properties"]
    extras = set(args) - set(props)
    missing = set(schema["required"]) - set(args)
    if extras:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extras))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    normalized: dict[str, Any] = {}
    for key, value in args.items():
        definition = props[key]
        if definition.get("type") == "string":
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            if len(value) < definition.get("minLength", 0) or len(value) > definition.get("maxLength", 1_000_000):
                raise ValueError(f"{key} has an invalid string length")
            if key == "domain" and value not in definition.get("enum", []):
                raise ValueError(f"domain must be one of {definition['enum']}")
        normalized[key] = value
    if name == "get_resource_graph" and "domain" not in normalized:
        normalized["domain"] = "all"
    return normalized


def _run_audit(candidate: Path, baseline: Path | None = None) -> dict[str, Any]:
    if not AUDITOR.is_file():
        raise RuntimeError(f"static analyzer was not found at {AUDITOR}")
    command = [sys.executable, str(AUDITOR), str(candidate)]
    if baseline is not None:
        command.extend(["--baseline", str(baseline)])
    try:
        proc = subprocess.run(
            command,
            cwd=str(_workspace_root()),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("static analysis exceeded the 120-second time limit") from exc
    except OSError as exc:
        raise RuntimeError(f"could not start static analyzer: {exc}") from exc
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"static analyzer did not return JSON (exit {proc.returncode}): {proc.stderr[-1000:]}") from exc
    if not isinstance(report, dict):
        raise RuntimeError("static analyzer returned a JSON value other than an object")
    # Preserve analyzer exit semantics as evidence; exit 1 can mean findings, not tool failure.
    report["execution"] = {
        "status": "completed_with_findings" if proc.returncode else "completed",
        "exit_code": proc.returncode,
        "mcp_server_version": SERVER_VERSION,
    }
    report["runtime_status"] = "NOT RUN"
    return report


def _finding_text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(key, "")) for key in ("title", "path", "evidence", "recommendation", "confidence")).lower()


def _select_report(report: dict[str, Any], kind: str) -> dict[str, Any]:
    checks = report.get("checks", [])
    findings = report.get("findings", [])
    if kind == "manifest":
        match = re.compile(r"manifest|uuid|dependenc", re.I)
        checks = [x for x in checks if match.search(str(x.get("name", "")) + " " + str(x.get("details", "")))]
        findings = [x for x in findings if match.search(_finding_text(x))]
    elif kind == "geometry":
        match = re.compile(r"geometry|bone|cube|uv|texture_width|texture_height", re.I)
        checks = [x for x in checks if match.search(str(x.get("name", "")) + " " + str(x.get("details", "")))]
        findings = [x for x in findings if match.search(_finding_text(x))]
    elif kind == "animation":
        match = re.compile(r"animation|controller", re.I)
        checks = [x for x in checks if match.search(str(x.get("name", "")) + " " + str(x.get("details", "")))]
        findings = [x for x in findings if match.search(_finding_text(x))]
    return {
        "status": "completed_with_findings" if findings else "completed",
        "candidate": report.get("candidate"),
        "checks": checks,
        "findings": findings,
        "coverage": (report.get("reference_graph") or {}).get("scope", {}).get("coverage", {}),
        "runtime_status": "NOT RUN",
        "analyzer_version": report.get("tool_version"),
        "mcp_server_version": SERVER_VERSION,
    }


def _filter_graph(graph: dict[str, Any], domain: str) -> dict[str, Any]:
    """Filter graph data by its explicit domain fields before using heuristics.

    When an edge has a target_domain, that declared domain is authoritative. This
    avoids cross-contamination such as a UI path containing the word "geometry"
    appearing in the geometry filter. Field-name heuristics are a fallback only
    for edges whose analyzer output has no target domain.
    """
    if domain == "all":
        return graph

    target_domains = {
        "geometry": {"geometry"},
        "animations": {"animation", "animations"},
        "controllers": {"animation_controllers", "render_controllers", "controllers", "controller"},
        "textures": {"texture", "textures"},
        "ui": {"ui", "ui_files"},
        "localization": {"localization", "localization_keys"},
    }
    accepted_targets = target_domains[domain]

    def norm(value: Any) -> str:
        return str(value or "").replace("\\", "/").strip().lower()

    def fallback_match(edge: dict[str, Any]) -> bool:
        kind = norm(edge.get("reference_kind"))
        value = norm(edge.get("referenced_value"))
        source = norm(edge.get("source_file"))
        pointer = norm(edge.get("source_pointer"))
        if domain == "geometry":
            return "geometry" in kind or value.startswith("geometry.") or "geometry" in pointer
        if domain == "animations":
            return ("animation" in kind and "controller" not in kind) or value.startswith("animation.") or "animations/" in pointer
        if domain == "controllers":
            return "controller" in kind or "controller" in value or "controller" in pointer
        if domain == "textures":
            return "texture" in kind or "textures/" in value or "texture" in pointer
        if domain == "ui":
            return "ui" in kind or "/ui/" in source or source.startswith("ui/") or "ui" in pointer
        if domain == "localization":
            return "localization" in kind or source.endswith((".lang", ".locres")) or "localization" in pointer
        return False

    def matches(edge: dict[str, Any]) -> bool:
        target = norm(edge.get("target_domain"))
        # Never let a heuristic override a known, different target domain.
        if target:
            return target in accepted_targets
        return fallback_match(edge)

    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict) and matches(edge)]
    definitions = graph.get("definitions", {})
    filtered_defs = {
        key: value for key, value in definitions.items()
        if key in accepted_targets
    }

    out = dict(graph)
    out["edges"] = edges
    out["edge_count"] = len(edges)
    out["definitions"] = filtered_defs
    counts: dict[str, int] = {}
    for edge in edges:
        state = str(edge.get("status", "unknown"))
        counts[state] = counts.get(state, 0) + 1
    out["status_counts"] = counts
    out["filter_domain"] = domain
    return out


def _inspect_archive(path: Path) -> dict[str, Any]:
    names: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    unsafe: list[str] = []
    file_count = 0
    entry_count = 0
    total_uncompressed = 0
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            raw = info.filename
            name = raw.replace("\\", "/")
            entry_count += 1
            file_count += 0 if info.is_dir() else 1
            total_uncompressed += info.file_size
            parts = Path(name).parts
            if name.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", name):
                unsafe.append(name)
            if name in seen:
                duplicates.append(name)
            seen.add(name)
            if len(names) < MAX_MEMBERS_RETURNED:
                names.append(name)
    return {
        "status": "completed",
        "archive": {"path": str(path), "size_bytes": path.stat().st_size, "is_zip": True},
        "member_count": file_count,
        "entry_count": entry_count,
        "uncompressed_bytes_declared": total_uncompressed,
        "members_truncated": entry_count > MAX_MEMBERS_RETURNED,
        "members": names,
        "duplicate_paths": sorted(set(duplicates)),
        "unsafe_paths": sorted(set(unsafe)),
        "payloads_read": False,
        "files_extracted": False,
        "mcp_server_version": SERVER_VERSION,
    }


_SEVERITY_RANK = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "BLOCKER": 4}
_UNRESOLVED_GRAPH_STATES = {"unresolved", "heuristic_unresolved", "ambiguous"}
_DIFF_SAMPLE_LIMIT = 100

def _finding_key(item: dict[str, Any]) -> tuple[str, str | None]:
    path = item.get("path")
    return str(item.get("title", "")), path if isinstance(path, str) else None

def _edge_key(edge: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return tuple(str(edge.get(key, "")) for key in (
        "source_file", "source_pointer", "reference_kind", "referenced_value", "target_domain"
    ))  # type: ignore[return-value]

def _sample(items: list[Any]) -> dict[str, Any]:
    return {"count": len(items), "items": items[:_DIFF_SAMPLE_LIMIT], "truncated": len(items) > _DIFF_SAMPLE_LIMIT}

def _summarize_pack_diff(comparison: dict[str, Any], baseline_report: dict[str, Any]) -> dict[str, Any]:
    """Build an actionable diff without writing files or treating heuristics as confirmed defects."""
    raw_diff = comparison.get("file_diff")
    candidate_graph = comparison.get("reference_graph")
    baseline_graph = baseline_report.get("reference_graph")
    if not isinstance(raw_diff, dict) or not isinstance(candidate_graph, dict) or not isinstance(baseline_graph, dict):
        raise RuntimeError("analyzer reports are missing file_diff or reference_graph required for diff_packs")

    file_diff = {}
    for bucket in ("added", "removed", "modified"):
        values = raw_diff.get(bucket, [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise RuntimeError(f"analyzer file_diff.{bucket} has an invalid shape")
        file_diff[bucket] = _sample(sorted(values))

    def scoped_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
        values = report.get("findings", [])
        if not isinstance(values, list):
            raise RuntimeError("analyzer findings has an invalid shape")
        # Baseline notes and inventory-level diffs are excluded from the static-rule comparison.
        excluded = {"File removed relative to baseline", "File changed relative to baseline"}
        return [f for f in values if isinstance(f, dict) and not str(f.get("title", "")).startswith("Baseline: ") and f.get("title") not in excluded]

    current_findings = scoped_findings(comparison)
    baseline_findings = scoped_findings(baseline_report)
    current_group: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
    baseline_group: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
    for item in current_findings:
        current_group.setdefault(_finding_key(item), []).append(item)
    for item in baseline_findings:
        baseline_group.setdefault(_finding_key(item), []).append(item)

    new_findings: list[dict[str, Any]] = []
    resolved_findings: list[dict[str, Any]] = []
    severity_escalations: list[dict[str, Any]] = []
    severity_deescalations: list[dict[str, Any]] = []
    all_finding_keys = set(current_group) | set(baseline_group)
    for key in sorted(all_finding_keys, key=lambda v: (v[0], v[1] or "")):
        old_items = sorted(baseline_group.get(key, []), key=lambda f: _SEVERITY_RANK.get(str(f.get("severity", "INFO")), -1))
        new_items = sorted(current_group.get(key, []), key=lambda f: _SEVERITY_RANK.get(str(f.get("severity", "INFO")), -1))
        shared = min(len(old_items), len(new_items))
        for item in new_items[shared:]:
            new_findings.append({k: item.get(k) for k in ("title", "path", "severity", "confidence", "evidence", "impact", "recommendation")})
        for item in old_items[shared:]:
            resolved_findings.append({k: item.get(k) for k in ("title", "path", "severity", "confidence", "evidence")})
        for old, new in zip(old_items[:shared], new_items[:shared]):
            old_rank = _SEVERITY_RANK.get(str(old.get("severity", "INFO")), -1)
            new_rank = _SEVERITY_RANK.get(str(new.get("severity", "INFO")), -1)
            if new_rank > old_rank:
                severity_escalations.append({"title": key[0], "path": key[1], "baseline": old.get("severity"), "candidate": new.get("severity")})
            elif new_rank >= 0 and old_rank > new_rank:
                severity_deescalations.append({"title": key[0], "path": key[1], "baseline": old.get("severity"), "candidate": new.get("severity")})

    def edges(report_graph: dict[str, Any]) -> list[dict[str, Any]]:
        values = report_graph.get("edges", [])
        if not isinstance(values, list) or not all(isinstance(edge, dict) for edge in values):
            raise RuntimeError("reference_graph.edges has an invalid shape")
        return values

    old_edges = edges(baseline_graph)
    new_edges = edges(candidate_graph)
    old_by_key: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    new_by_key: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for edge in old_edges:
        old_by_key.setdefault(_edge_key(edge), []).append(edge)
    for edge in new_edges:
        new_by_key.setdefault(_edge_key(edge), []).append(edge)

    new_unresolved: list[dict[str, Any]] = []
    regressed_edges: list[dict[str, Any]] = []
    for key, candidates in new_by_key.items():
        prior = old_by_key.get(key, [])
        prior_resolved = any(item.get("status") == "resolved" for item in prior)
        for edge in candidates:
            status = str(edge.get("status", ""))
            if status not in _UNRESOLVED_GRAPH_STATES:
                continue
            item = {
                "source_file": edge.get("source_file"),
                "source_pointer": edge.get("source_pointer"),
                "reference_kind": edge.get("reference_kind"),
                "referenced_value": edge.get("referenced_value"),
                "target_domain": edge.get("target_domain"),
                "status": status,
                "confidence": edge.get("confidence", "LOW"),
            }
            if prior_resolved:
                item["baseline_status"] = "resolved"
                regressed_edges.append(item)
            elif not prior:
                new_unresolved.append(item)

    candidate_severities = [str(f.get("severity", "INFO")) for f in current_findings]
    has_critical = any(level in ("BLOCKER", "HIGH") for level in candidate_severities)
    has_medium = "MEDIUM" in candidate_severities
    has_file_removals = bool(raw_diff.get("removed"))
    has_regression_edges = bool(regressed_edges)
    if has_critical:
        recommendation = "HOLD"
    elif has_medium or has_file_removals or has_regression_edges or new_findings:
        recommendation = "REVIEW"
    else:
        recommendation = "STATIC CHECKS PASSED — RUNTIME NOT VERIFIED"

    return {
        "status": "completed",
        "candidate": comparison.get("candidate"),
        "baseline": comparison.get("baseline"),
        "analysis_versions": {"candidate": comparison.get("tool_version"), "baseline": baseline_report.get("tool_version")},
        "file_diff": file_diff,
        "finding_delta": {
            "new": _sample(new_findings),
            "no_longer_reported": _sample(resolved_findings),
            "severity_escalations": _sample(severity_escalations),
            "severity_deescalations": _sample(severity_deescalations),
        },
        "reference_delta": {
            "new_unresolved": _sample(new_unresolved),
            "resolved_to_unresolved": _sample(regressed_edges),
        },
        "summary": {
            "files_added": len(raw_diff.get("added", [])),
            "files_removed": len(raw_diff.get("removed", [])),
            "files_modified": len(raw_diff.get("modified", [])),
            "new_findings": len(new_findings),
            "resolved_findings": len(resolved_findings),
            "severity_escalations": len(severity_escalations),
            "new_unresolved_references": len(new_unresolved),
            "reference_regressions": len(regressed_edges),
        },
        "recommendation": recommendation,
        "runtime_status": "NOT RUN",
        "mcp_server_version": SERVER_VERSION,
        "read_only": True,
        "sample_limit": _DIFF_SAMPLE_LIMIT,
    }


def call_tool(name: str, raw_args: Any) -> dict[str, Any]:
    try:
        args = _validate_arguments(name, raw_args)
        if name == "inspect_archive":
            path = _resolve_archive(args["archive_path"])
            return _inspect_archive(path)
        if name == "compare_baseline":
            candidate = _resolve_archive(args["candidate_path"])
            baseline = _resolve_archive(args["baseline_path"])
            return _run_audit(candidate, baseline)
        if name == "diff_packs":
            candidate = _resolve_archive(args["candidate_path"])
            baseline = _resolve_archive(args["baseline_path"])
            comparison = _run_audit(candidate, baseline)
            baseline_report = _run_audit(baseline)
            return _summarize_pack_diff(comparison, baseline_report)
        if name == "audit_pack":
            candidate = _resolve_archive(args["candidate_path"])
            return _run_audit(candidate)
        archive_arg = args["archive_path"]
        candidate = _resolve_archive(archive_arg)
        report = _run_audit(candidate)
        if name == "get_resource_graph":
            graph = report.get("reference_graph")
            if not isinstance(graph, dict):
                return _error("REPORT_SHAPE", "Analyzer report omitted reference_graph")
            return {"status": "completed", "candidate": report.get("candidate"), "reference_graph": _filter_graph(graph, args["domain"]), "runtime_status": "NOT RUN", "mcp_server_version": SERVER_VERSION}
        if name == "validate_manifest":
            return _select_report(report, "manifest")
        if name == "audit_geometry":
            return _select_report(report, "geometry")
        if name == "audit_animation":
            return _select_report(report, "animation")
        return _error("UNKNOWN_TOOL", f"unhandled tool {name!r}")
    except ValueError as exc:
        return _error("INVALID_ARGUMENT", str(exc))
    except TimeoutError as exc:
        return _error("TIMEOUT", str(exc))
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        return _error("ANALYSIS_FAILED", str(exc))
    except Exception as exc:  # Keep unexpected failures structured without leaking a stack trace.
        return _error("INTERNAL_ERROR", f"unexpected {type(exc).__name__}: {exc}")


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid JSON-RPC request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if not isinstance(method, str) or not isinstance(params, dict):
        return _jsonrpc_error(request_id, -32600, "Invalid method or params")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        requested = params.get("protocolVersion", "2025-03-26")
        supported = {"2024-11-05", "2025-03-26", "2025-06-18"}
        selected = requested if requested in supported else "2025-03-26"
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": selected,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-engineer", "version": SERVER_VERSION},
            "instructions": WORKFLOW_INSTRUCTIONS,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if not isinstance(name, str):
            payload = _error("INVALID_ARGUMENT", "tool name must be a string")
        else:
            payload = call_tool(name, args)
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": text}],
            "structuredContent": payload,
            "isError": payload.get("status") == "error",
        }}
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    # MCP stdio: one JSON-RPC message per line. stdout is protocol-only.
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_message(request)
        except json.JSONDecodeError:
            response = _jsonrpc_error(None, -32700, "Parse error")
        except Exception as exc:
            response = _jsonrpc_error(None, -32603, f"Internal error: {type(exc).__name__}")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
