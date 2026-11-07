#!/usr/bin/env python3
"""Validate Minecraft Bedrock Engineer's Domain-Based Hybrid routing contracts.

This is a read-only, standard-library package checker. It does not load or execute
plugin Skills, bundled utilities, project scripts, or any legacy server source.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path("skills/bedrock-engineer-core/references/domain-registry.json")
WORK_ORDER_PATH = Path("skills/bedrock-engineer-core/references/work-order.schema.json")
DOMAIN_RESULT_PATH = Path("skills/bedrock-engineer-core/references/domain-result.schema.json")
PROJECT_STATE_SCHEMA_PATH = Path("skills/bedrock-engineer-core/references/project-state.schema.json")
PROJECT_STATE_PATH = Path("skills/bedrock-engineer-core/scripts/project_state.py")
PROJECT_STATE_TEST_PATH = Path("skills/bedrock-engineer-core/scripts/test_project_state.py")
PROJECT_STATE_SKILL_PATH = Path("skills/project-state-management/SKILL.md")
CHANGE_IMPACT_SCRIPT_PATH = Path("skills/bedrock-engineer-core/scripts/analyze_change_impact.py")
CHANGE_IMPACT_TEST_PATH = Path("skills/bedrock-engineer-core/scripts/test_analyze_change_impact.py")
CHANGE_IMPACT_SKILL_PATH = Path("skills/change-impact-analysis/SKILL.md")
CHANGE_IMPACT_SCHEMA_PATH = Path("skills/bedrock-engineer-core/references/change-impact.schema.json")
DOMAIN_PLANNER_PATH = Path("skills/bedrock-engineer-core/scripts/plan_domain_work.py")
DOMAIN_PLANNER_TEST_PATH = Path("skills/bedrock-engineer-core/scripts/test_plan_domain_work.py")
DOMAIN_INTEGRATOR_PATH = Path("skills/bedrock-engineer-core/scripts/integrate_domain_results.py")
DOMAIN_INTEGRATOR_TEST_PATH = Path("skills/bedrock-engineer-core/scripts/test_integrate_domain_results.py")
ARCHITECTURE_PATH = Path("ARCHITECTURE.md")
REQUIRED_ROUTES = {
    "conversation_files", "connected_workspace", "local_executor",
    "creator_tools_cli", "no_execution_route",
}
REQUIRED_WORK_ORDER_FIELDS = {
    "schema_version", "task", "project", "capability", "plan", "changes", "evidence", "status"
}
REQUIRED_DOMAIN_RESULT_FIELDS = {
    "domain_id", "status", "summary", "findings", "changed_files", "evidence", "limitations"
}


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "file is missing"
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"invalid UTF-8 JSON: {exc}"


def _frontmatter(path: Path) -> tuple[str | None, str | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, None, f"cannot read Skill: {exc}"
    if not text.startswith("---\n"):
        return None, None, "missing YAML frontmatter opener"
    end = text.find("\n---", 4)
    if end < 0:
        return None, None, "missing YAML frontmatter closer"
    header = text[4:end]
    name_match = re.search(r"(?m)^name:\s*([^\n#]+)\s*$", header)
    desc_match = re.search(r"(?m)^description:\s*(.+?)\s*$", header)
    if not name_match or not desc_match:
        return None, None, "frontmatter requires non-empty name and description"
    return name_match.group(1).strip().strip("'\""), desc_match.group(1).strip().strip("'\""), None


def _duplicate_enum_paths(value: Any, path: str = "$") -> list[str]:
    """Return JSON paths whose schema enum contains duplicate JSON values."""
    duplicates: list[str] = []
    if isinstance(value, dict):
        enum_values = value.get("enum")
        if isinstance(enum_values, list):
            encoded = [json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":")) for item in enum_values]
            if len(encoded) != len(set(encoded)):
                duplicates.append(path + ".enum")
        for key, child in value.items():
            duplicates.extend(_duplicate_enum_paths(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            duplicates.extend(_duplicate_enum_paths(child, f"{path}[{index}]"))
    return duplicates


def _has_cycle(graph: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, []):
            if visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def validate(package_root: Path) -> dict[str, Any]:
    root = package_root.resolve()
    checks: list[dict[str, str]] = []

    def check(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})

    registry_path = root / REGISTRY_PATH
    registry, error = _read_json(registry_path)
    check("registry-json", error is None, error or "domain registry parsed")
    if not isinstance(registry, dict):
        registry = {}

    architecture = registry.get("architecture") if isinstance(registry.get("architecture"), dict) else {}
    check(
        "architecture-identity",
        architecture.get("id") == "domain-based-hybrid" and architecture.get("integration_model") == "skills-only",
        "architecture must identify Domain-Based Hybrid with Skills-only integration",
    )
    boundary_text = " ".join(str(x).lower() for x in architecture.get("hard_boundaries", []))
    check(
        "no-mcp-boundary",
        "mcp" in boundary_text and "no mcp" in boundary_text and "backend" in boundary_text,
        "registry explicitly prohibits MCP and plugin-owned backend dependencies",
    )

    domains_raw = registry.get("domains") if isinstance(registry.get("domains"), list) else []
    domain_ids: list[str] = []
    domain_map: dict[str, dict[str, Any]] = {}
    assigned: list[str] = []
    domain_shape_ok = bool(domains_raw)
    for domain in domains_raw:
        if not isinstance(domain, dict):
            domain_shape_ok = False
            continue
        did = domain.get("id")
        skills = domain.get("skills")
        requires = domain.get("requires")
        if not isinstance(did, str) or not did or did in domain_map:
            domain_shape_ok = False
            continue
        if not all(isinstance(domain.get(k), str) and domain.get(k) for k in ("name", "purpose", "lead_skill")):
            domain_shape_ok = False
        if not isinstance(skills, list) or not skills or not all(isinstance(x, str) and x for x in skills):
            domain_shape_ok = False
            skills = []
        if not isinstance(requires, list) or not all(isinstance(x, str) for x in requires):
            domain_shape_ok = False
            requires = []
        if domain.get("lead_skill") not in skills:
            domain_shape_ok = False
        domain_ids.append(did)
        domain_map[did] = domain
        assigned.extend(skills)
    unique_domains = len(domain_ids) == len(set(domain_ids))
    unique_assignments = len(assigned) == len(set(assigned))
    check("domain-shape", domain_shape_ok and unique_domains, f"{len(domain_ids)} domains have unique IDs and required fields")
    check("unique-primary-membership", unique_assignments, "each Skill is assigned to at most one primary domain")

    skill_dirs = root / "skills"
    discovered_paths = sorted(skill_dirs.glob("*/SKILL.md")) if skill_dirs.exists() else []
    discovered: dict[str, Path] = {p.parent.name: p for p in discovered_paths}
    registered = set(assigned)
    discovered_names = set(discovered)
    missing = sorted(discovered_names - registered)
    stale = sorted(registered - discovered_names)
    check(
        "skill-coverage",
        not missing and not stale and bool(discovered),
        f"discovered={len(discovered_names)}, registered={len(registered)}, unregistered={missing}, missing_paths={stale}",
    )

    frontmatter_ok = True
    frontmatter_errors: list[str] = []
    for slug, path in discovered.items():
        name, description, fm_error = _frontmatter(path)
        if fm_error or name != slug or not description:
            frontmatter_ok = False
            frontmatter_errors.append(f"{slug}: {fm_error or f'name={name!r} does not match folder'}")
    check("skill-frontmatter", frontmatter_ok, "; ".join(frontmatter_errors) if frontmatter_errors else f"{len(discovered)} Skill frontmatter blocks match their folder names")

    dependency_ok = True
    graph: dict[str, list[str]] = {}
    dependency_errors: list[str] = []
    for did, domain in domain_map.items():
        reqs = domain.get("requires", [])
        graph[did] = reqs if isinstance(reqs, list) else []
        for req in graph[did]:
            if req not in domain_map or req == did:
                dependency_ok = False
                dependency_errors.append(f"{did}->{req}")
    check("domain-dependencies", dependency_ok, "; ".join(dependency_errors) if dependency_errors else "all domain dependency edges resolve")
    acyclic = dependency_ok and not _has_cycle(graph)
    check("domain-dependency-dag", acyclic, "domain dependency graph is acyclic" if acyclic else "domain dependency graph contains a cycle or invalid edge")

    profile_ok = True
    profile_errors: list[str] = []
    profiles = registry.get("workflow_profiles") if isinstance(registry.get("workflow_profiles"), dict) else {}
    for pname, profile in profiles.items():
        if not isinstance(profile, dict):
            profile_ok = False
            profile_errors.append(f"{pname}: profile is not an object")
            continue
        required = profile.get("required_domains", [])
        optional = profile.get("optional_domains", [])
        if not isinstance(required, list) or not isinstance(optional, list):
            profile_ok = False
            profile_errors.append(f"{pname}: domain lists must be arrays")
            continue
        if set(required) & set(optional):
            profile_ok = False
            profile_errors.append(f"{pname}: a domain is both required and optional")
        unknown = sorted((set(required) | set(optional)) - set(domain_map))
        if unknown:
            profile_ok = False
            profile_errors.append(f"{pname}: unknown domains {unknown}")
        gates = profile.get("delivery_gates", [])
        if not isinstance(gates, list) or not all(isinstance(x, str) and x for x in gates):
            profile_ok = False
            profile_errors.append(f"{pname}: invalid delivery gates")
    check("workflow-profiles", bool(profiles) and profile_ok, "; ".join(profile_errors) if profile_errors else f"{len(profiles)} workflow profiles reference known domains")

    routes = registry.get("capability_routes") if isinstance(registry.get("capability_routes"), list) else []
    route_ids = {r.get("id") for r in routes if isinstance(r, dict)}
    check("capability-routes", REQUIRED_ROUTES <= route_ids, f"required real-host/no-execution routes present; found={sorted(str(x) for x in route_ids)}")

    planner_path = root / DOMAIN_PLANNER_PATH
    planner_test_path = root / DOMAIN_PLANNER_TEST_PATH
    try:
        planner_text = planner_path.read_text(encoding="utf-8")
        planner_contract = all(token in planner_text for token in (
            "def resolve_domain_order(", "def build_work_order(", "_validate_work_order(",
            "no_execution_route", "runtime_status", "NOT RUN", "include_skills", "--include-skill",
        ))
        unsafe_imports = re.findall(
            r"(?im)^\s*(?:from|import)\s+(?:server|mcp(?:\.|\s)|subprocess|socket|requests|httpx|urllib)(?:\.|\s|$)",
            planner_text,
        )
        planner_ok = planner_contract and not unsafe_imports
    except (OSError, UnicodeDecodeError):
        planner_text = ""
        unsafe_imports = []
        planner_ok = False
    check(
        "domain-planner",
        planner_ok,
        "deterministic registry-to-Work-Order planner is present and has no legacy server/MCP or network/process imports"
        if planner_ok else "planner is missing, lacks required planning contracts, or imports a prohibited runtime/network dependency",
    )
    check(
        "domain-planner-tests",
        planner_test_path.is_file(),
        "focused domain planner test suite is present" if planner_test_path.is_file() else f"missing {DOMAIN_PLANNER_TEST_PATH}",
    )

    integrator_path = root / DOMAIN_INTEGRATOR_PATH
    integrator_test_path = root / DOMAIN_INTEGRATOR_TEST_PATH
    try:
        integrator_text = integrator_path.read_text(encoding="utf-8")
        integrator_contract = all(token in integrator_text for token in (
            "def integrate(", "def _detect_conflicts(", "--replace-domain",
            "criterion_results", "runtime_status", "CASE_COLLISION", "REMOVE_VS_WRITE",
        ))
        unsafe_integrator_imports = re.findall(
            r"(?im)^\s*(?:from|import)\s+(?:server|mcp(?:\.|\s)|subprocess|socket|requests|httpx|urllib)(?:\.|\s|$)",
            integrator_text,
        )
        integrator_ok = integrator_contract and not unsafe_integrator_imports
    except (OSError, UnicodeDecodeError):
        integrator_ok = False
        integrator_text = ""
        unsafe_integrator_imports = []
    check(
        "domain-result-integrator",
        integrator_ok,
        "Domain Result integrator exposes validation, replacement protection, conflict detection and acceptance/runtime aggregation without legacy/network/process imports"
        if integrator_ok else "integrator is missing, lacks required integration contracts, or imports a prohibited runtime/network dependency",
    )
    check(
        "domain-result-integrator-tests",
        integrator_test_path.is_file(),
        "focused Domain Result integration test suite is present" if integrator_test_path.is_file() else f"missing {DOMAIN_INTEGRATOR_TEST_PATH}",
    )
    integration_skill = root / "skills/domain-result-integration/SKILL.md"
    integration_skill_text = integration_skill.read_text(encoding="utf-8") if integration_skill.is_file() else ""
    integration_skill_ok = integration_skill.is_file() and "Domain Result" in integration_skill_text and "integrate_domain_results.py" in integration_skill_text
    check(
        "domain-result-integration-skill",
        integration_skill_ok,
        "Core orchestration has a Domain Result integration Skill" if integration_skill_ok else "missing or incomplete skills/domain-result-integration/SKILL.md",
    )

    state_script_path = root / PROJECT_STATE_PATH
    state_test_path = root / PROJECT_STATE_TEST_PATH
    try:
        state_script_text = state_script_path.read_text(encoding="utf-8")
        state_contract = all(token in state_script_text for token in (
            "def init_project(", "def inspect_project(", "def capture_project(",
            "def restore_revision(", "def recover_project(", "--expected-revision", "event_hash", "sha256",
            '\"project_files_changed\": False',
        ))
        unsafe_state_imports = re.findall(
            r"(?im)^\s*(?:from|import)\s+(?:server|mcp(?:\.|\s)|subprocess|socket|requests|httpx|urllib)(?:\.|\s|$)",
            state_script_text,
        )
        state_script_ok = state_contract and not unsafe_state_imports
    except (OSError, UnicodeDecodeError):
        state_script_ok = False
        state_script_text = ""
        unsafe_state_imports = []
    check(
        "project-state-manager",
        state_script_ok,
        "project state manager provides revision guards, immutable hash snapshots, event integrity and metadata-only restore without network/process imports"
        if state_script_ok else "project state manager is missing required contracts or imports a prohibited runtime/network/process dependency",
    )
    check(
        "project-state-manager-tests",
        state_test_path.is_file(),
        "focused project state test suite is present" if state_test_path.is_file() else f"missing {PROJECT_STATE_TEST_PATH}",
    )
    state_skill_path = root / PROJECT_STATE_SKILL_PATH
    state_skill_text = state_skill_path.read_text(encoding="utf-8") if state_skill_path.is_file() else ""
    state_skill_lower = state_skill_text.lower()
    state_skill_ok = state_skill_path.is_file() and "project_state.py" in state_skill_text and ".mbe/" in state_skill_text and "snapshot" in state_skill_lower and "never" in state_skill_lower
    check(
        "project-state-management-skill",
        state_skill_ok,
        "project continuity has operational instructions for the state utility and its non-rollback boundary" if state_skill_ok else "missing or incomplete project-state-management Skill",
    )

    for label, relative, required_fields in (
        ("work-order-schema", WORK_ORDER_PATH, REQUIRED_WORK_ORDER_FIELDS),
        ("domain-result-schema", DOMAIN_RESULT_PATH, REQUIRED_DOMAIN_RESULT_FIELDS),
    ):
        schema, schema_error = _read_json(root / relative)
        okay = schema_error is None and isinstance(schema, dict)
        if okay:
            props = schema.get("properties", {})
            req = set(schema.get("required", []))
            okay = required_fields <= req and isinstance(props, dict)
        duplicate_enums = _duplicate_enum_paths(schema) if okay else []
        if duplicate_enums:
            okay = False
        if okay and label == "work-order-schema":
            ref = schema.get("properties", {}).get("domain_results", {}).get("items", {}).get("$ref")
            okay = ref == "domain-result.schema.json" and (root / relative.parent / ref).is_file()
        detail = schema_error or (
            "duplicate enum values at: " + ", ".join(duplicate_enums) if duplicate_enums else
            "schema parsed, required fields present and local references resolve" if okay else
            f"schema contract or local reference invalid: {relative}"
        )
        check(label, bool(okay), detail)

    state_schema, state_schema_error = _read_json(root / PROJECT_STATE_SCHEMA_PATH)
    state_schema_ok = state_schema_error is None and isinstance(state_schema, dict)
    if state_schema_ok:
        state_required = {"schema_version", "project", "revision", "created_at", "updated_at", "latest_snapshot", "last_complete_snapshot", "records", "history", "last_event_hash", "integrity"}
        state_schema_ok = state_required <= set(state_schema.get("required", [])) and isinstance(state_schema.get("$defs"), dict)
        if _duplicate_enum_paths(state_schema):
            state_schema_ok = False
    check(
        "project-state-schema",
        bool(state_schema_ok),
        state_schema_error or ("project-state schema defines revision, evidence records, snapshots, history and integrity" if state_schema_ok else "project-state schema is missing required contract fields or contains duplicate enum values"),
    )
    impact_script_path = root / CHANGE_IMPACT_SCRIPT_PATH
    impact_test_path = root / CHANGE_IMPACT_TEST_PATH
    try:
        impact_text = impact_script_path.read_text(encoding="utf-8")
        impact_contract = all(token in impact_text for token in (
            "def analyze_project(", "def _walk_project(", "def _resolve_asset_path(",
            "--changed-path", "reverse", "UNRESOLVED_IDENTIFIER", "AMBIGUOUS_IDENTIFIER",
            "os.scandir", "DEFAULT_IGNORES", "--max-total-bytes",
        ))
        unsafe_impact_imports = re.findall(
            r"(?im)^\s*(?:from|import)\s+(?:server|mcp(?:\.|\s)|subprocess|socket|requests|httpx|urllib)(?:\.|\s|$)",
            impact_text,
        )
        impact_script_ok = impact_contract and not unsafe_impact_imports
    except (OSError, UnicodeDecodeError):
        impact_script_ok = False
        impact_text = ""
        unsafe_impact_imports = []
    check(
        "change-impact-analyzer",
        impact_script_ok,
        "change-impact analyzer provides bounded read-only dependency traversal and has no network/process/legacy runtime imports"
        if impact_script_ok else "change-impact analyzer is missing required contracts or imports a prohibited runtime/network/process dependency",
    )
    check(
        "change-impact-analyzer-tests",
        impact_test_path.is_file(),
        "focused change-impact analyzer test suite is present" if impact_test_path.is_file() else f"missing {CHANGE_IMPACT_TEST_PATH}",
    )
    impact_skill_path = root / CHANGE_IMPACT_SKILL_PATH
    impact_skill_text = impact_skill_path.read_text(encoding="utf-8") if impact_skill_path.is_file() else ""
    impact_skill_ok = impact_skill_path.is_file() and "analyze_change_impact.py" in impact_skill_text and "read-only" in impact_skill_text.lower() and "reverse" in impact_skill_text.lower()
    check(
        "change-impact-analysis-skill",
        impact_skill_ok,
        "audit domain has operational change-impact instructions and read-only boundaries" if impact_skill_ok else "missing or incomplete skills/change-impact-analysis/SKILL.md",
    )
    impact_schema, impact_schema_error = _read_json(root / CHANGE_IMPACT_SCHEMA_PATH)
    impact_schema_ok = impact_schema_error is None and isinstance(impact_schema, dict)
    if impact_schema_ok:
        required_impact_fields = {"schema_version", "project_root_name", "changed_paths", "impact", "summary", "coverage", "edges", "findings", "limitations"}
        impact_schema_ok = required_impact_fields <= set(impact_schema.get("required", [])) and isinstance(impact_schema.get("properties"), dict)
        if _duplicate_enum_paths(impact_schema):
            impact_schema_ok = False
    check(
        "change-impact-report-schema",
        bool(impact_schema_ok),
        impact_schema_error or ("change-impact report schema defines changed paths, impact closure, coverage, graph edges and findings" if impact_schema_ok else "change-impact report schema is missing required fields or has duplicated enum values"),
    )

    work_schema_for_link, _ = _read_json(root / WORK_ORDER_PATH)
    link_property = work_schema_for_link.get("properties", {}).get("project_state", {}) if isinstance(work_schema_for_link, dict) else {}
    link_ok = isinstance(link_property, dict) and link_property.get("type") == "object" and {"project_id", "revision", "state_path", "state_sha256"} <= set(link_property.get("required", []))
    check("work-order-project-state-link", link_ok, "Work Order supports an optional project ID/revision/checksum link" if link_ok else "Work Order project_state link contract is missing or incomplete")

    architecture_doc = root / ARCHITECTURE_PATH
    try:
        doc_text = architecture_doc.read_text(encoding="utf-8")
        doc_ok = "Domain-Based Hybrid" in doc_text and "Skills-only" in doc_text and "Task lifecycle" in doc_text and "Domain Result integration" in doc_text and "integrate_domain_results.py" in doc_text and "Project State Management" in doc_text and "project_state.py" in doc_text and "Change Impact Analysis" in doc_text and "analyze_change_impact.py" in doc_text
    except (OSError, UnicodeDecodeError):
        doc_ok = False
    check("architecture-document", doc_ok, "ARCHITECTURE.md describes the hybrid model and task lifecycle")

    failed = sum(c["status"] == "FAIL" for c in checks)
    return {
        "package": root.name,
        "architecture": architecture.get("id"),
        "summary": {
            "total_checks": len(checks),
            "passed": len(checks) - failed,
            "failed": failed,
            "domains": len(domain_ids),
            "registered_skills": len(registered),
            "discovered_skills": len(discovered),
            "workflow_profiles": len(profiles),
        },
        "checks": checks,
        "status": "FAIL" if failed else "PASS",
        "runtime_status": "NOT RUN",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", nargs="?", default=".")
    parser.add_argument("--json", dest="json_path", help="optional report output path")
    args = parser.parse_args(argv)
    report = validate(Path(args.package_root))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_path:
        Path(args.json_path).write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
