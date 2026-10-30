#!/usr/bin/env python3
"""Strict, offline integrity checks for a packaged Skills-only Minecraft Bedrock Engineer release."""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
from pathlib import Path
from typing import Any

from package_provenance import PackageSafetyError, scan_package, verify_provenance

EXPECTED_NAME = "minecraft-bedrock-engineer"
PROVENANCE_NAME = "BUILD_PROVENANCE.json"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

REQUIRED = [
    "VERSION", "README.md", "CHANGELOG.md", "plugin.json", ".codex-plugin/plugin.json",
    "skills/bedrock-engineer-core/SKILL.md", "skills/skills-first-execution/SKILL.md",
    "skills/skills-only-maintenance/SKILL.md", "skills/geometry-uv-engine/SKILL.md",
    "skills/geometry-uv-engine/scripts/geometry_engine.py",
    "skills/geometry-uv-engine/scripts/test_geometry_engine.py",
    "skills/geometry-uv-engine/scripts/uv_template_engine.py",
    "skills/geometry-uv-engine/scripts/test_uv_template_engine.py",
    "skills/visual-resource-pipeline/scripts/png_engine.py",
    "skills/visual-resource-pipeline/scripts/test_png_engine.py",
    "skills/package-integrity/scripts/package_provenance.py",
    "skills/package-integrity/scripts/check_skills_package.py",
    "skills/package-integrity/scripts/test_check_skills_package.py",
    "skills/package-integrity/scripts/build_skills_package.py",
    "skills/package-integrity/scripts/test_build_skills_package.py",
]
LEGACY_MCP_FILES = [".mcp.json", "mcp.json"]
LEGACY_DEPLOYMENT_FILES = ["Dockerfile", "wrangler.toml", "package.json"]
FORBIDDEN_ACTIVE_CALLS = [
    "create_addon_project", "create_addon_item", "create_addon_block", "create_addon_recipe",
    "create_addon_entity", "search_mojang_samples", "read_mojang_sample", "audit_texture_links", "diff_packs",
]
ORIGINAL_DEFAULT_PROMPTS = [
    "Create a Minecraft Bedrock add-on from scratch or extend my existing project. Work from files I provide or an actually connected workspace, preserve existing mechanics and assets, and produce complete BP/RP files with validation evidence.",
    "Audit this Bedrock add-on or candidate release. Check archive integrity, BP/RP manifests and dependency links, JSON/JavaScript, resource references, identifiers, and regressions. Provide exact paths, evidence and severity; do not delete resources.",
    "Research this Minecraft Bedrock feature for the exact target version. Prioritize official Creator documentation and matching Mojang samples, verify API and format compatibility, compare implementations, cite sources, and implement only when requested.",
]


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def read_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=_reject_constant,
    )


def interface(manifest: dict, compat: bool) -> dict:
    value = manifest.get("interface", {}) if compat else manifest.get("extensions", {}).get("com.openai", {}).get("interface", {})
    return value if isinstance(value, dict) else {}


def skill_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, None, "missing opening YAML frontmatter"
    end = text.find("\n---", 4)
    if end < 0:
        return None, None, "missing closing YAML frontmatter"
    block = text[4:end]
    name = re.search(r"(?m)^name:\s*([^\n#]+)\s*$", block)
    desc = re.search(r"(?m)^description:\s*(.+?)\s*$", block)
    if not name or not desc:
        return None, None, "frontmatter requires non-empty name and description"
    return name.group(1).strip().strip("\"'"), desc.group(1).strip().strip("\"'"), None


def check(root: Path) -> dict:
    root = Path(root).absolute()
    checks: list[dict[str, str]] = []

    def add(check_id: str, status: str, message: str) -> None:
        checks.append({"id": check_id, "status": status, "message": message})

    try:
        records, hygiene_violations = scan_package(root)
        add("package-hygiene", "FAIL" if hygiene_violations else "PASS", "; ".join(hygiene_violations[:20]) if hygiene_violations else f"{len(records)} regular files; no symlinks, bytecode, cache directories or special files")
    except PackageSafetyError as exc:
        records = []
        add("package-hygiene", "FAIL", str(exc))
        return report(root, checks)

    missing = [path for path in REQUIRED if not (root / path).is_file()]
    add("required-files", "FAIL" if missing else "PASS", "Missing: " + ", ".join(missing) if missing else f"All {len(REQUIRED)} required package files exist")
    if missing:
        ok, message = verify_provenance(root, records)
        add("provenance-integrity", "PASS" if ok else "FAIL", message)
        return report(root, checks)

    try:
        root_manifest = read_json(root / "plugin.json")
        compat_manifest = read_json(root / ".codex-plugin/plugin.json")
        version_file = (root / "VERSION").read_text(encoding="utf-8").strip()
    except Exception as exc:
        add("manifest-parse", "FAIL", f"Unable to read manifests/version: {type(exc).__name__}: {exc}")
        return report(root, checks)
    add("manifest-parse", "PASS", "Both plugin manifests parse as strict JSON objects")
    if not isinstance(root_manifest, dict) or not isinstance(compat_manifest, dict):
        add("manifest-shape", "FAIL", "Both manifests must be JSON objects")
        return report(root, checks)

    versions = [root_manifest.get("version"), compat_manifest.get("version"), version_file]
    semver_ok = all(isinstance(value, str) and SEMVER.fullmatch(value) for value in versions)
    same_version = len(set(versions)) == 1
    add("version-parity", "PASS" if semver_ok and same_version else "FAIL", f"Version markers: root={versions[0]!r}, compatibility={versions[1]!r}, VERSION={versions[2]!r}")
    identities = [root_manifest.get("name"), compat_manifest.get("name")]
    add("plugin-identity", "PASS" if identities == [EXPECTED_NAME, EXPECTED_NAME] else "FAIL", f"Plugin identities: {identities!r}")

    root_prompts = interface(root_manifest, False).get("defaultPrompt")
    compat_prompts = interface(compat_manifest, True).get("defaultPrompt")
    prompt_ok = isinstance(root_prompts, list) and isinstance(compat_prompts, list) and len(root_prompts) >= 3 and root_prompts == compat_prompts and all(isinstance(item, str) and item.strip() for item in root_prompts)
    original_ok = prompt_ok and root_prompts[:3] == ORIGINAL_DEFAULT_PROMPTS
    add("default-prompt-parity", "PASS" if prompt_ok else "FAIL", "Default prompts match exactly" if prompt_ok else "Root and compatibility default prompts differ or are invalid")
    add("original-default-prompts", "PASS" if original_ok else "FAIL", "The three original default prompts are preserved verbatim and in order" if original_ok else "The first three default prompts differ from the original contract")

    skill_paths = [root_manifest.get("skills"), compat_manifest.get("skills")]
    add("skills-path", "PASS" if skill_paths == ["./skills", "./skills"] and (root / "skills").is_dir() else "FAIL", f"Skill paths: {skill_paths!r}")

    mcp_refs = []
    for label, manifest in (("root", root_manifest), ("compatibility", compat_manifest)):
        if "mcpServers" in manifest:
            mcp_refs.append(label + ".mcpServers")
    mcp_files = [name for name in LEGACY_MCP_FILES if (root / name).exists()]
    add("skills-only-boundary", "PASS" if not mcp_refs and not mcp_files else "FAIL", "No MCP manifests/configuration are present" if not mcp_refs and not mcp_files else f"Unexpected MCP configuration: {mcp_refs + mcp_files!r}")

    deployment = [name for name in LEGACY_DEPLOYMENT_FILES if (root / name).exists()]
    if (root / "cloudflare").exists():
        deployment.append("cloudflare/")
    add("obsolete-deployment", "PASS" if not deployment else "FAIL", "No retired Cloudflare/container deployment scaffolding" if not deployment else f"Retired deployment artifacts remain: {deployment!r}")

    skills = sorted((root / "skills").rglob("SKILL.md"))
    skill_names: dict[str, str] = {}
    bad_skills: list[str] = []
    for path in skills:
        try:
            name, description, error = skill_frontmatter(path)
        except Exception as exc:
            bad_skills.append(f"{path.relative_to(root)}: {type(exc).__name__}")
            continue
        if error:
            bad_skills.append(f"{path.relative_to(root)}: {error}")
            continue
        if name in skill_names:
            bad_skills.append(f"duplicate skill name {name!r}: {skill_names[name]} and {path.relative_to(root)}")
        else:
            skill_names[name] = str(path.relative_to(root))
        if not description:
            bad_skills.append(f"{path.relative_to(root)}: empty description")
    add("skill-inventory", "PASS" if skills and not bad_skills else "FAIL", f"Discovered {len(skills)} skills / {len(skill_names)} unique names" + ("; " + "; ".join(bad_skills[:12]) if bad_skills else "; frontmatter valid and names unique"))

    stale = []
    for path in skills:
        body = path.read_text(encoding="utf-8")
        for tool in FORBIDDEN_ACTIVE_CALLS:
            if re.search(r"(?i)\b(?:call|invoke)\s+`" + re.escape(tool) + r"`", body):
                stale.append(f"{path.relative_to(root)} invokes {tool}")
        if re.search(r"(?i)actual MCP registry|MCP connection|MCP unit suite", body):
            stale.append(f"{path.relative_to(root)} contains active MCP release instructions")
    add("skill-tool-boundary", "PASS" if not stale else "FAIL", "No stale calls to retired tools in skill instructions" if not stale else "; ".join(stale[:20]))

    readme = (root / "README.md").read_text(encoding="utf-8")
    readme_heading = re.search(r"(?m)^# Minecraft Bedrock Engineer — (\S+)\s*$", readme)
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    changelog_heading = re.search(r"(?m)^##\s+(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)(?:\s|$)", changelog)
    add("readme-version", "PASS" if readme_heading and versions[0] == readme_heading.group(1) else "FAIL", f"README heading version: {readme_heading.group(1) if readme_heading else 'missing'}")
    add("changelog-version", "PASS" if changelog_heading and versions[0] == changelog_heading.group(1) else "FAIL", f"Newest CHANGELOG heading version: {changelog_heading.group(1) if changelog_heading else 'missing'}")
    readme_arch = "Skills-and-instructions-only" in readme and ("does not use MCP" in readme or "No MCP server" in readme)
    add("readme-architecture", "PASS" if readme_arch else "FAIL", "README documents the intentional Skills-only architecture" if readme_arch else "README must explicitly document the Skills-only/no-MCP architecture")

    geometry_script = root / "skills/geometry-uv-engine/scripts/geometry_engine.py"
    geometry_test = root / "skills/geometry-uv-engine/scripts/test_geometry_engine.py"
    geometry_text = geometry_script.read_text(encoding="utf-8") if geometry_script.is_file() else ""
    geometry_contract = all(token in geometry_text for token in ("analyze_geometry", "duplicate JSON key", "UV_OUT_OF_BOUNDS", "UV_OVERLAP", "--geometry-identifier"))
    geometry_ok = geometry_script.is_file() and geometry_test.is_file() and geometry_contract
    add("geometry-engine", "PASS" if geometry_ok else "FAIL", "Standalone geometry/UV analyzer, test suite and expected static-analysis contract are present")

    template_script = root / "skills/geometry-uv-engine/scripts/uv_template_engine.py"
    template_test = root / "skills/geometry-uv-engine/scripts/test_uv_template_engine.py"
    template_text = template_script.read_text(encoding="utf-8") if template_script.is_file() else ""
    template_contract = all(token in template_text for token in ("extract_regions", "render_template", "encode_png", "max_pixels", "xb"))
    template_ok = template_script.is_file() and template_test.is_file() and template_contract
    add("uv-template-engine", "PASS" if template_ok else "FAIL", "Standalone transparent UV template renderer, pixel budget, exclusive output creation and focused tests are present")

    png_script = root / "skills/visual-resource-pipeline/scripts/png_engine.py"
    png_test = root / "skills/visual-resource-pipeline/scripts/test_png_engine.py"
    png_ok = png_script.is_file() and png_test.is_file()
    add("png-engine", "PASS" if png_ok else "FAIL", "Canonical PNG validator and focused tests are present")

    sample_root = root / "skills/bedrock-development/references/mojang-samples-1.26.50.4"
    index_meta = sample_root / "INDEX_METADATA.json"
    index_path = sample_root / "mojang-samples-index.json.gz"
    try:
        meta = read_json(index_meta)
        with gzip.open(index_path, "rb") as stream:
            payload = stream.read(64 * 1024 * 1024 + 1)
        if len(payload) > 64 * 1024 * 1024:
            raise ValueError("decompressed Mojang index exceeds 64 MiB safety limit")
        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs, parse_constant=_reject_constant)
        count = len(decoded) if isinstance(decoded, list) else len(decoded.get("entries", decoded.get("files", []))) if isinstance(decoded, dict) else 0
        expected_count = meta.get("indexed_count")
        ok = bool(payload) and (not expected_count or count == expected_count)
        if count == 0:
            ok = False
            detail = "Compressed sample index is empty; full sample corpus must be retained"
        else:
            detail = f"Gzip/JSON valid; indexed entries={count}, metadata expected={expected_count}"
        add("mojang-index-integrity", "PASS" if ok else "FAIL", detail)
    except Exception as exc:
        add("mojang-index-integrity", "FAIL", f"Sample index verification failed: {type(exc).__name__}: {exc}")
    add("png-engine-tests", "PASS" if png_test.is_file() else "FAIL", "Focused PNG validator test file present" if png_test.is_file() else "PNG validator tests are missing")

    provenance_ok, provenance_message = verify_provenance(root, records, versions[0] if isinstance(versions[0], str) else None)
    add("provenance-integrity", "PASS" if provenance_ok else "FAIL", provenance_message)
    return report(root, checks)


def report(root: Path, checks: list[dict[str, str]]) -> dict:
    failed = sum(item["status"] == "FAIL" for item in checks)
    warnings = sum(item["status"] == "WARN" for item in checks)
    return {
        "package": root.name,
        "checks": checks,
        "summary": {"total": len(checks), "passed": sum(item["status"] == "PASS" for item in checks), "failed": failed, "warnings": warnings},
        "status": "FAIL" if failed else "PASS",
        "runtime_status": "NOT RUN",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", nargs="?", default=".")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args(argv)
    result = check(Path(args.package_root))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_path:
        output = Path(args.json_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
    print(rendered)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
