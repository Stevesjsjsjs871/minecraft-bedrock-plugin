#!/usr/bin/env python3
"""Offline structural and contract audit for a Minecraft Bedrock Engineer package.

The checker is intentionally static: it does not launch Minecraft, connect to an
MCP host, download references, execute pack scripts, or extract archives.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_PLUGIN_NAME = "minecraft-bedrock-engineer"
REQUIRED_FILES = (
    "plugin.json",
    ".codex-plugin/plugin.json",
    "VERSION",
    "mcp.json",
    ".mcp.json",
    "README.md",
    "archive_safety.py",
    "server/mcp_server.py",
    "server/tests/test_mcp_server.py",
    "skills/automated-validation/scripts/bedrock_audit.py",
    "skills/automated-validation/scripts/validate_report.py",
    "skills/automated-validation/references/report-schema.json",
    "skills/regression-evals/scripts/regression_tests.py",
    "skills/audit-benchmark/scripts/evaluate_benchmark.py",
    "skills/audit-benchmark/scripts/test_evaluate_benchmark.py",
    "skills/bedrock-development/scripts/index_mojang_samples.py",
    "skills/bedrock-development/scripts/test_index_mojang_samples.py",
    "skills/bedrock-development/references/mojang-samples-1.26.50.4/INDEX_METADATA.json",
    "skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _prompt(manifest: dict[str, Any], *, compatibility: bool) -> Any:
    if compatibility:
        interface = manifest.get("interface")
        return interface.get("defaultPrompt") if isinstance(interface, dict) else None
    extensions = manifest.get("extensions")
    if not isinstance(extensions, dict):
        return None
    openai = extensions.get("com.openai")
    if not isinstance(openai, dict):
        return None
    interface = openai.get("interface")
    return interface.get("defaultPrompt") if isinstance(interface, dict) else None


def _semver(value: Any) -> bool:
    return isinstance(value, str) and SEMVER_RE.fullmatch(value) is not None


def _server_config(path: Path, check_id: str, checks: list[dict[str, str]]) -> dict[str, Any] | None:
    try:
        data = _read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        checks.append({"id": check_id, "status": "FAIL", "message": f"Cannot parse {path.name}: {exc}"})
        return None
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict) or not servers:
        checks.append({"id": check_id, "status": "FAIL", "message": f"{path.name} must contain a non-empty mcpServers object"})
        return None
    server = servers.get(EXPECTED_PLUGIN_NAME)
    if not isinstance(server, dict):
        checks.append({"id": check_id, "status": "FAIL", "message": f"{path.name} has no {EXPECTED_PLUGIN_NAME!r} server"})
        return None
    args = server.get("args")
    if server.get("type") != "stdio":
        checks.append({"id": check_id, "status": "FAIL", "message": f"{path.name} server transport must remain stdio"})
    elif not isinstance(server.get("command"), str) or not server["command"].strip():
        checks.append({"id": check_id, "status": "FAIL", "message": f"{path.name} server command must be a non-empty string"})
    elif not isinstance(args, list) or not any(
        isinstance(arg, str) and "server/mcp_server.py" in arg.replace("\\", "/") for arg in args
    ):
        checks.append({"id": check_id, "status": "FAIL", "message": f"{path.name} args must reference server/mcp_server.py"})
    else:
        checks.append({"id": check_id, "status": "PASS", "message": f"{path.name} contains a stdio server reference to server/mcp_server.py"})
    return server


def _frontmatter(text: str) -> tuple[str | None, str | None]:
    if not text.startswith("---\n"):
        return None, None
    end = text.find("\n---", 4)
    if end < 0:
        return None, None
    block = text[4:end]
    name_match = re.search(r"(?m)^name:\s*([^\n#]+?)\s*$", block)
    description_match = re.search(r"(?m)^description:\s*(.+?)\s*$", block)
    return (
        name_match.group(1).strip().strip("\"'") if name_match else None,
        description_match.group(1).strip().strip("\"'") if description_match else None,
    )


def _literal_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _registry_audit(server_path: Path, checks: list[dict[str, str]]) -> dict[str, Any]:
    try:
        source = server_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(server_path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        checks.append({"id": "mcp-python-syntax", "status": "FAIL", "message": f"Cannot parse MCP server Python: {exc}"})
        return {"tool_count": 0, "tool_names": [], "duplicate_names": [], "missing_handlers": [], "schema_errors": []}

    assignments = []
    call_tool_func = None
    helper_tool_func = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TOOLS" for t in node.targets):
            assignments.append(node.value)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "call_tool":
                call_tool_func = node
            elif node.name == "_tool":
                helper_tool_func = node

    names: list[str] = []
    schema_errors: list[str] = []
    writer_readonly_errors: list[str] = []
    writer_names = {"create_addon_project", "create_addon_item", "create_addon_block", "create_addon_recipe"}
    if len(assignments) != 1 or not isinstance(assignments[0], (ast.List, ast.Tuple)):
        schema_errors.append("Expected one statically declared TOOLS list")
    else:
        for entry in assignments[0].elts:
            if not isinstance(entry, ast.Call) or _literal_string(entry.func) is not None:
                schema_errors.append("TOOLS entries must be calls to _tool(...) or equivalent literal tool factories")
                continue
            if not isinstance(entry.func, ast.Name) or entry.func.id != "_tool" or not entry.args:
                schema_errors.append("TOOLS entries must call _tool(name, description, properties, required, ...)")
                continue
            name = _literal_string(entry.args[0])
            if name is None:
                schema_errors.append("Tool name must be a literal string")
                continue
            names.append(name)
            if len(entry.args) < 4:
                schema_errors.append(f"{name}: expected name, description, properties and required arguments")
                continue
            if _literal_string(entry.args[1]) is None:
                schema_errors.append(f"{name}: description must be a non-empty literal string")
            if not _literal_string(entry.args[1]):
                schema_errors.append(f"{name}: description is empty")
            props_node, required_node = entry.args[2], entry.args[3]
            if isinstance(props_node, ast.Dict) and isinstance(required_node, (ast.List, ast.Tuple)):
                prop_names = {k.value for k in props_node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                req_names = {e.value for e in required_node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                unknown_required = sorted(req_names - prop_names)
                if unknown_required:
                    schema_errors.append(f"{name}: required fields not in properties: {unknown_required}")
            elif not isinstance(required_node, (ast.List, ast.Tuple)):
                schema_errors.append(f"{name}: required must be a literal list or tuple")
            kwargs = {kw.arg: kw.value for kw in entry.keywords if kw.arg}
            read_only_false = isinstance(kwargs.get("read_only"), ast.Constant) and kwargs["read_only"].value is False
            if name in writer_names and not read_only_false:
                writer_readonly_errors.append(f"{name} must explicitly be write-capable (read_only=False)")
            if name not in writer_names and read_only_false:
                writer_readonly_errors.append(f"{name} is marked write-capable but is not in the write-tool allowlist")

    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        schema_errors.append(f"Duplicate registered tool names: {duplicates}")
    handlers: set[str] = set()
    if call_tool_func:
        for node in ast.walk(call_tool_func):
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "name":
                for comparator in node.comparators:
                    literal = _literal_string(comparator)
                    if literal:
                        handlers.add(literal)
    missing_handlers = sorted(set(names) - handlers)
    undocumented_dispatch = sorted(handlers - set(names))
    if missing_handlers:
        schema_errors.append(f"Registered tools missing from call_tool dispatch: {missing_handlers}")
    if undocumented_dispatch:
        schema_errors.append(f"call_tool dispatch mentions unregistered names: {undocumented_dispatch}")

    closed_schema_factory = False
    annotation_factory = False
    if helper_tool_func:
        for node in ast.walk(helper_tool_func):
            if not isinstance(node, ast.Dict):
                continue
            pairs = {}
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    pairs[key.value] = value
            if {"properties", "required", "additionalProperties"}.issubset(pairs):
                closed_value = pairs["additionalProperties"]
                if isinstance(closed_value, ast.Constant) and closed_value.value is False:
                    closed_schema_factory = True
            expected_annotation_keys = {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}
            if expected_annotation_keys.issubset(pairs):
                annotation_factory = True
    if not closed_schema_factory:
        schema_errors.append("Shared MCP schema factory must explicitly set additionalProperties=False")
    if not annotation_factory:
        schema_errors.append("Shared MCP tool factory must emit readOnlyHint/destructiveHint/idempotentHint/openWorldHint")
    if schema_errors:
        checks.append({"id": "mcp-tool-registry", "status": "FAIL", "message": "; ".join(schema_errors)})
    else:
        checks.append({"id": "mcp-tool-registry", "status": "PASS", "message": f"Found {len(names)} unique registered tools; dispatch is complete and shared schema/annotation contracts are present"})
    if not closed_schema_factory:
        checks.append({"id": "mcp-schema-factory", "status": "FAIL", "message": "Shared MCP schema factory does not enforce a closed properties object"})
    elif not annotation_factory:
        checks.append({"id": "mcp-schema-factory", "status": "FAIL", "message": "Shared MCP tool factory omits required safety annotations"})
    else:
        checks.append({"id": "mcp-schema-factory", "status": "PASS", "message": "Shared MCP factory explicitly closes tool schemas and emits all four safety annotations"})
    if writer_readonly_errors:
        checks.append({"id": "mcp-write-annotations", "status": "FAIL", "message": "; ".join(writer_readonly_errors)})
    elif set(names) >= writer_names:
        checks.append({"id": "mcp-write-annotations", "status": "PASS", "message": "Four write-capable tools are explicitly marked; other registered tools are not incorrectly marked write-capable"})
    else:
        checks.append({"id": "mcp-write-annotations", "status": "WARN", "message": "One or more expected authoring tools are absent; check API compatibility before release"})
    return {
        "tool_count": len(names),
        "tool_names": sorted(names),
        "duplicate_names": duplicates,
        "missing_handlers": missing_handlers,
        "schema_errors": schema_errors,
    }


def _index_audit(root: Path, checks: list[dict[str, str]], *, deep: bool) -> dict[str, Any] | None:
    base = root / "skills/bedrock-development/references/mojang-samples-1.26.50.4"
    metadata_path = base / "INDEX_METADATA.json"
    index_path = base / "mojang-samples-index.json.gz"
    try:
        metadata = _read_json(metadata_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        checks.append({"id": "sample-index-metadata", "status": "FAIL", "message": f"Cannot parse sample-index metadata: {exc}"})
        return None
    sha = metadata.get("zip_sha256")
    target_version = metadata.get("target_version")
    indexed_count = metadata.get("indexed_count")
    entry_count = metadata.get("entry_count")
    if not SHA256_RE.fullmatch(sha or "") or not isinstance(target_version, str) or not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", target_version):
        checks.append({"id": "sample-index-metadata", "status": "FAIL", "message": "Metadata needs a four-part target_version and a 64-character lowercase ZIP SHA-256"})
        return None
    if not isinstance(indexed_count, int) or not isinstance(entry_count, int) or indexed_count < 1 or entry_count < indexed_count:
        checks.append({"id": "sample-index-metadata", "status": "FAIL", "message": "Metadata entry/index counts are missing or inconsistent"})
        return None
    checks.append({"id": "sample-index-metadata", "status": "PASS", "message": f"Sample provenance metadata is structurally valid ({target_version}; indexed {indexed_count}/{entry_count} entries)"})
    if not deep:
        checks.append({"id": "sample-index-content", "status": "WARN", "message": "Deep compressed-index validation skipped by option"})
        return {"target_version": target_version, "indexed_count": indexed_count, "entry_count": entry_count, "zip_sha256": sha}
    try:
        with gzip.open(index_path, "rt", encoding="utf-8") as stream:
            index = json.load(stream)
    except (OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        checks.append({"id": "sample-index-content", "status": "FAIL", "message": f"Compressed sample index is unreadable: {exc}"})
        return None
    if not isinstance(index, dict):
        checks.append({"id": "sample-index-content", "status": "FAIL", "message": "Compressed sample index root must be a JSON object"})
        return None
    actual_entries = index.get("entries")
    stats = index.get("archive_stats")
    actual_count = len(actual_entries) if isinstance(actual_entries, list) else None
    bad_paths = []
    duplicate_paths = []
    seen: set[str] = set()
    malformed_entries = []
    if isinstance(actual_entries, list):
        for pos, entry in enumerate(actual_entries):
            if not isinstance(entry, dict):
                malformed_entries.append(str(pos))
                continue
            path = entry.get("path")
            category = entry.get("category")
            if not isinstance(path, str) or not path or "\\" in path or "\x00" in path or PurePosixPath(path).is_absolute() or any(part in {"", ".", ".."} for part in path.split("/")):
                bad_paths.append(str(path)[:120])
            if isinstance(path, str):
                if path in seen:
                    duplicate_paths.append(path[:120])
                seen.add(path)
            if not isinstance(category, str) or not category:
                malformed_entries.append(f"{pos}:missing category")
            size = entry.get("size_bytes")
            if not isinstance(size, int) or size < 0:
                malformed_entries.append(f"{pos}:invalid size")
            digest = entry.get("sha256", "")
            if digest and (not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)):
                malformed_entries.append(f"{pos}:invalid sha256")
    else:
        malformed_entries.append("entries is not a list")
    archive_sha = index.get("archive_sha256") if isinstance(index, dict) else None
    if actual_count != indexed_count:
        malformed_entries.append(f"indexed_count metadata {indexed_count} != index entries {actual_count}")
    if isinstance(stats, dict):
        if stats.get("entry_count") != entry_count:
            malformed_entries.append(f"archive_stats.entry_count {stats.get('entry_count')} != metadata {entry_count}")
        if stats.get("indexed_count") != indexed_count:
            malformed_entries.append(f"archive_stats.indexed_count {stats.get('indexed_count')} != metadata {indexed_count}")
    else:
        malformed_entries.append("archive_stats is not an object")
    if archive_sha != sha:
        malformed_entries.append("sample index archive_sha256 disagrees with INDEX_METADATA.json")
    if index.get("target_version") != target_version:
        malformed_entries.append("sample index target_version disagrees with INDEX_METADATA.json")
    if bad_paths or duplicate_paths or malformed_entries:
        details = []
        if bad_paths: details.append(f"unsafe paths sample={bad_paths[:3]}")
        if duplicate_paths: details.append(f"duplicate paths sample={duplicate_paths[:3]}")
        if malformed_entries: details.append(f"contract errors sample={malformed_entries[:5]}")
        checks.append({"id": "sample-index-content", "status": "FAIL", "message": "; ".join(details)})
    else:
        checks.append({"id": "sample-index-content", "status": "PASS", "message": f"Compressed index validated: {actual_count} unique canonical entries; provenance hash/version match"})
    return {"target_version": target_version, "indexed_count": indexed_count, "entry_count": entry_count, "zip_sha256": sha}


def audit_package(root: Path, *, deep_index: bool = True, strict_files: bool = True) -> dict[str, Any]:
    root = root.expanduser().resolve()
    checks: list[dict[str, str]] = []
    def add(code: str, status: str, message: str) -> None:
        checks.append({"id": code, "status": status, "message": message})

    missing = [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]
    if missing:
        add("required-files", "FAIL" if strict_files else "WARN", f"Missing required package files: {missing}")
    else:
        add("required-files", "PASS", f"All {len(REQUIRED_FILES)} required package files exist")
    if not root.is_dir():
        add("package-root", "FAIL", f"Package root is not a directory: {root}")
        return _report(root, checks, {}, None)

    try:
        root_manifest = _read_json(root / "plugin.json")
        compat_manifest = _read_json(root / ".codex-plugin/plugin.json")
        version_file = (root / "VERSION").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        add("manifest-parse", "FAIL", f"Cannot read version/manifests: {exc}")
        return _report(root, checks, {}, None)
    if not isinstance(root_manifest, dict) or not isinstance(compat_manifest, dict):
        add("manifest-parse", "FAIL", "Root and compatibility manifests must be JSON objects")
        return _report(root, checks, {}, None)
    add("manifest-parse", "PASS", "Root and compatibility manifests parse as UTF-8 JSON objects")

    versions = [root_manifest.get("version"), compat_manifest.get("version"), version_file]
    identities = [root_manifest.get("name"), compat_manifest.get("name")]
    if any(not _semver(v) for v in versions):
        add("version-markers", "FAIL", f"All version markers must use strict SemVer; found {versions}")
    elif len(set(versions)) != 1:
        add("version-markers", "FAIL", f"Version markers disagree: root={versions[0]}, compatibility={versions[1]}, VERSION={versions[2]}")
    else:
        add("version-markers", "PASS", f"Version markers agree at {versions[0]}")
    if identities != [EXPECTED_PLUGIN_NAME, EXPECTED_PLUGIN_NAME]:
        add("plugin-identity", "FAIL", f"Plugin identity changed or mismatched: {identities}")
    else:
        add("plugin-identity", "PASS", f"Both manifests retain {EXPECTED_PLUGIN_NAME}")

    root_prompt = _prompt(root_manifest, compatibility=False)
    compat_prompt = _prompt(compat_manifest, compatibility=True)
    def valid_prompt(value: Any) -> bool:
        if isinstance(value, str): return bool(value.strip())
        if isinstance(value, list): return 1 <= len(value) <= 3 and all(isinstance(p, str) and p.strip() for p in value)
        return False
    if not valid_prompt(root_prompt) or not valid_prompt(compat_prompt):
        add("default-prompts", "FAIL", "Both manifests need a string prompt or an array of 1–3 non-empty strings")
    elif root_prompt != compat_prompt:
        add("default-prompts", "FAIL", "Root and compatibility default prompts differ in type, value or order")
    else:
        add("default-prompts", "PASS", "Root and compatibility default prompts match exactly")

    compat_skills = compat_manifest.get("skills")
    compat_mcp = compat_manifest.get("mcpServers")
    if compat_skills != "./skills":
        add("compatibility-references", "FAIL", f"Compatibility manifest skill path should remain ./skills; found {compat_skills!r}")
    elif compat_mcp != "./.mcp.json" or not (root / ".mcp.json").is_file():
        add("compatibility-references", "FAIL", f"Compatibility MCP path should remain ./.mcp.json; found {compat_mcp!r}")
    else:
        add("compatibility-references", "PASS", "Compatibility manifest retains the skills and MCP configuration paths")

    _server_config(root / ".mcp.json", "local-mcp-config", checks)
    _server_config(root / "mcp.json", "portable-mcp-config", checks)

    skill_files = sorted((root / "skills").rglob("SKILL.md")) if (root / "skills").is_dir() else []
    if not skill_files:
        add("skill-inventory", "FAIL", "No skills/*/SKILL.md files found")
    else:
        skill_names: list[str] = []
        skill_errors: list[str] = []
        for skill_file in skill_files:
            try:
                text = skill_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                skill_errors.append(f"{skill_file.relative_to(root)}: unreadable ({exc})")
                continue
            name, description = _frontmatter(text)
            if not name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                skill_errors.append(f"{skill_file.relative_to(root)}: invalid/missing YAML frontmatter name")
            else:
                skill_names.append(name)
            if not description or len(description) < 12:
                skill_errors.append(f"{skill_file.relative_to(root)}: missing or too-short YAML frontmatter description")
        dup_skills = sorted({name for name in skill_names if skill_names.count(name) > 1})
        if dup_skills:
            skill_errors.append(f"duplicate skill names: {dup_skills}")
        if skill_errors:
            add("skill-inventory", "FAIL", "; ".join(skill_errors[:8]))
        else:
            add("skill-inventory", "PASS", f"Checked {len(skill_files)} skill files; frontmatter names/descriptions are present and names are unique")

    server = root / "server/mcp_server.py"
    registry = _registry_audit(server, checks) if server.is_file() else {"tool_count": 0, "tool_names": [], "duplicate_names": [], "missing_handlers": [], "schema_errors": ["server source missing"]}
    index = None
    if (root / "skills/bedrock-development/references/mojang-samples-1.26.50.4/INDEX_METADATA.json").is_file():
        index = _index_audit(root, checks, deep=deep_index)

    readme_path = root / "README.md"
    if readme_path.is_file() and len(versions) >= 3 and _semver(versions[0]):
        try:
            first = readme_path.read_text(encoding="utf-8").splitlines()[0]
            if re.match(r"^#\s+Minecraft Bedrock Engineer\s+—\s+\d+\.\d+\.\d+", first) and versions[0] not in first:
                add("readme-version", "WARN", f"README heading is stale ({first!r}); expected current release {versions[0]}")
            else:
                add("readme-version", "PASS", "README heading does not contradict the current release version")
        except (OSError, UnicodeDecodeError, IndexError):
            add("readme-version", "WARN", "README heading could not be checked")

    return _report(root, checks, registry, index)


def _report(root: Path, checks: list[dict[str, str]], registry: dict[str, Any], index: dict[str, Any] | None) -> dict[str, Any]:
    fails = sum(c["status"] == "FAIL" for c in checks)
    warns = sum(c["status"] == "WARN" for c in checks)
    status = "FAIL" if fails else ("WARN" if warns else "PASS")
    return {
        "checker": "minecraft-bedrock-engineer-package-integrity",
        "checker_version": "1.0.6",
        "package_root": str(root),
        "status": status,
        "summary": {"checks": len(checks), "passed": sum(c["status"] == "PASS" for c in checks), "warnings": warns, "failures": fails},
        "checks": checks,
        "mcp_registry": registry,
        "mojang_samples_index": index,
        "runtime_status": "NOT RUN",
    }


def fix_readme_heading(root: Path) -> None:
    """Replace only the recognized README heading version, preserving other bytes as text."""
    manifest_path = root / "plugin.json"
    readme_path = root / "README.md"
    version = _read_json(manifest_path).get("version")
    if not _semver(version):
        raise ValueError("plugin.json does not contain a strict SemVer version")
    readme = readme_path.read_text(encoding="utf-8")
    lines = readme.splitlines(keepends=True)
    if not lines or not re.match(r"^#\s+Minecraft Bedrock Engineer\s+—\s+\d+\.\d+\.\d+", lines[0]):
        raise ValueError("README first line is not the expected Minecraft Bedrock Engineer version heading; no change made")
    replacement = f"# Minecraft Bedrock Engineer — {version}"
    newline = "\n" if lines[0].endswith("\n") else ""
    lines[0] = replacement + newline
    readme_path.write_text("".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", nargs="?", default=str(Path(__file__).resolve().parents[3]), help="Package directory (defaults to this plugin root)")
    parser.add_argument("--skip-deep-index", action="store_true", help="Check index metadata but do not decompress and inspect the full sample index")
    parser.add_argument("--allow-incomplete", action="store_true", help="Report missing core files as warnings; useful only for synthetic fixtures")
    parser.add_argument("--fix-readme-heading", action="store_true", help="Safely replace only a stale first-level README version heading")
    args = parser.parse_args(argv)
    root = Path(args.package_root).expanduser().resolve()
    if args.fix_readme_heading:
        try:
            fix_readme_heading(root)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            print(json.dumps({"status": "FAIL", "error": f"README heading fix failed: {exc}"}, ensure_ascii=False))
            return 2
    report = audit_package(root, deep_index=not args.skip_deep_index, strict_files=not args.allow_incomplete)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
