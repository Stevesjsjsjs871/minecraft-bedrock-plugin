#!/usr/bin/env python3
"""Strict, offline integrity checks for a packaged Skills-only Minecraft Bedrock Engineer release."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
from collections import Counter
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
    "skills/package-integrity/scripts/compare_plugin_sources.py",
    "skills/package-integrity/scripts/test_compare_plugin_sources.py",
    "skills/bedrock-development/scripts/restore_mojang_index.py",
    "skills/bedrock-development/scripts/test_restore_mojang_index.py",
    "skills/audit-benchmark/requirements.txt",
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
    if compat:
        value = manifest.get("interface", {})
    else:
        extensions = manifest.get("extensions")
        if not isinstance(extensions, dict):
            return {}
        provider = extensions.get("com.openai")
        if not isinstance(provider, dict):
            return {}
        value = provider.get("interface", {})
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
        if hygiene_violations:
            # Do not read package paths after discovering symlinks or special files.
            return report(root, checks)
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
    same_version = all(value == versions[0] for value in versions)
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
        if not isinstance(meta, dict):
            raise ValueError("INDEX_METADATA.json must be an object")
        required_meta = {"source_archive", "target_version", "zip_sha256", "entry_count", "indexed_count", "declared_uncompressed_bytes", "category_counts"}
        missing_meta = sorted(required_meta - meta.keys())
        if missing_meta:
            raise ValueError("index metadata is missing: " + ", ".join(missing_meta))
        if not isinstance(meta["source_archive"], str) or not meta["source_archive"] or Path(meta["source_archive"]).name != meta["source_archive"]:
            raise ValueError("index metadata source_archive must be a filename")
        if not isinstance(meta["target_version"], str) or not meta["target_version"]:
            raise ValueError("index metadata target_version is invalid")
        if not isinstance(meta["zip_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", meta["zip_sha256"]):
            raise ValueError("index metadata zip_sha256 is invalid")
        for field in ("entry_count", "indexed_count", "declared_uncompressed_bytes"):
            if type(meta[field]) is not int or meta[field] < 0:
                raise ValueError(f"index metadata {field} must be a non-negative integer")
        expected_categories = meta["category_counts"]
        if not isinstance(expected_categories, dict) or any(not isinstance(key, str) or type(value) is not int or value < 0 for key, value in expected_categories.items()):
            raise ValueError("index metadata category_counts is invalid")
        with gzip.open(index_path, "rb") as stream:
            payload = stream.read(64 * 1024 * 1024 + 1)
        if len(payload) > 64 * 1024 * 1024:
            raise ValueError("decompressed Mojang index exceeds 64 MiB safety limit")
        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs, parse_constant=_reject_constant)
        if not isinstance(decoded, dict):
            raise ValueError("Mojang index payload must be an object")
        stats = decoded.get("archive_stats")
        entries = decoded.get("entries")
        if not isinstance(stats, dict) or not isinstance(entries, list):
            raise ValueError("Mojang index archive_stats/entries are missing or malformed")
        actual_categories = Counter(item.get("category") for item in entries if isinstance(item, dict) and isinstance(item.get("category"), str))
        stats_ok = (
            decoded.get("archive_file_name") == meta["source_archive"]
            and decoded.get("archive_sha256") == meta["zip_sha256"]
            and decoded.get("target_version") == meta["target_version"]
            and all(type(stats.get(field)) is int for field in ("entry_count", "indexed_count", "declared_uncompressed_bytes"))
            and stats.get("entry_count") == meta["entry_count"]
            and stats.get("indexed_count") == meta["indexed_count"]
            and stats.get("declared_uncompressed_bytes") == meta["declared_uncompressed_bytes"]
            and len(entries) == meta["indexed_count"]
        )
        category_ok = dict(sorted(actual_categories.items())) == dict(sorted(expected_categories.items()))
        index_size = index_path.stat().st_size
        expected_index_bytes = meta.get("index_file_bytes")
        size_ok = index_size <= 16 * 1024 * 1024 and (expected_index_bytes is None or (type(expected_index_bytes) is int and index_size == expected_index_bytes))
        expected_index_sha = meta.get("index_sha256")
        index_sha_ok = expected_index_sha is None or (
            isinstance(expected_index_sha, str)
            and re.fullmatch(r"[0-9a-f]{64}", expected_index_sha) is not None
            and hashlib.sha256(index_path.read_bytes()).hexdigest() == expected_index_sha
        )
        source_asset_ok = True
        if any(key in meta for key in ("source_release_tag", "source_asset_name", "source_asset_url")):
            tag, asset, url = meta.get("source_release_tag"), meta.get("source_asset_name"), meta.get("source_asset_url")
            source_asset_ok = (
                isinstance(tag, str) and isinstance(asset, str) and asset == meta["source_archive"]
                and isinstance(url, str)
                and url == f"https://github.com/Mojang/bedrock-samples/releases/download/{tag}/{asset}"
            )
        ok = bool(payload) and stats_ok and category_ok and size_ok and index_sha_ok and source_asset_ok
        detail = (
            f"Official archive hash/name, target version, {len(entries)} indexed entries, "
            f"{stats.get('entry_count')} ZIP entries, category counts, compressed size/hash "
            + ("match pinned metadata" if ok else "do not match pinned metadata")
        )
        add("mojang-index-integrity", "PASS" if ok else "FAIL", detail)
    except Exception as exc:
        add("mojang-index-integrity", "FAIL", f"Sample index verification failed: {type(exc).__name__}: {exc}")
    add("png-engine-tests", "PASS" if png_test.is_file() else "FAIL", "Focused PNG validator test file present" if png_test.is_file() else "PNG validator tests are missing")

    benchmark_requirements = (root / "skills/audit-benchmark/requirements.txt").read_text(encoding="utf-8")
    benchmark_dependency_ok = re.search(r"(?m)^jsonschema==4\.26\.0\s*$", benchmark_requirements) is not None
    add("benchmark-schema-dependency", "PASS" if benchmark_dependency_ok else "FAIL", "Pinned jsonschema 4.26.0 dependency is declared for Draft 2020-12 validation" if benchmark_dependency_ok else "audit-benchmark requires a pinned jsonschema==4.26.0 dependency")

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
