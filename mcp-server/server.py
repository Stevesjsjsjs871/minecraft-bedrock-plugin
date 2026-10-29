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

SERVER_VERSION = "0.6.7"
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 50_000
MAX_MEMBERS_RETURNED = 2000
SUPPORTED_SUFFIXES = {".mcaddon", ".mcpack", ".mcworld", ".zip"}
ROOT = Path(__file__).resolve().parents[1]
AUDITOR = ROOT / "skills" / "automated-validation" / "scripts" / "bedrock_audit.py"

# Keep the priority workflow short and front-loaded for clients that expose it.
WORKFLOW_INSTRUCTIONS = (
    "Use audit_pack for a general audit; compare_baseline for regressions; "
    "get_resource_graph for reference questions; and validate_manifest, audit_geometry, "
    "or audit_animation for focused checks. Results are static evidence only. "
    "Never claim runtime verification unless performed; never modify or delete pack files."
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
    size = resolved.stat().st_size
    if size > MAX_ARCHIVE_BYTES:
        raise ValueError(f"archive exceeds the {MAX_ARCHIVE_BYTES}-byte size limit")
    if not zipfile.is_zipfile(resolved):
        raise ValueError("file is not a valid ZIP-compatible archive")
    try:
        with zipfile.ZipFile(resolved) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_MEMBERS:
                raise ValueError(
                    f"archive member count {len(entries)} exceeds the {MAX_ARCHIVE_MEMBERS}-entry limit"
                )
            declared_uncompressed = sum(info.file_size for info in entries if not info.is_dir())
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError(f"archive central directory is invalid: {exc}") from exc
    if declared_uncompressed > MAX_UNCOMPRESSED_BYTES:
        raise ValueError(f"archive declares {declared_uncompressed} uncompressed bytes; limit is {MAX_UNCOMPRESSED_BYTES}")
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
    if domain == "all":
        return graph
    needles = {
        "geometry": ("geometry",),
        "animations": ("animation",),
        "controllers": ("controller",),
        "textures": ("texture",),
        "ui": ("ui",),
        "localization": ("localization", "lang", "locres"),
    }[domain]
    edges = []
    for edge in graph.get("edges", []):
        text = " ".join(str(edge.get(k, "")) for k in ("reference_kind", "kind", "referenced_domain", "domain", "referenced_value", "source_path", "source")).lower()
        if any(n in text for n in needles):
            edges.append(edge)
    definitions = graph.get("definitions", {})
    filtered_defs = {
        key: value for key, value in definitions.items()
        if any(n in key.lower() for n in needles)
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
