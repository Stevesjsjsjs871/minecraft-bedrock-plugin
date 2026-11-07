#!/usr/bin/env python3
"""Build a deterministic Work Order from the Domain-Based Hybrid registry.

This planner only expands declared workflow/domain dependencies and emits a JSON
work record. It does not classify natural language, inspect projects, invoke
Skills, access a workspace, execute project scripts, or persist state unless an
explicit output path is supplied.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path("skills/bedrock-engineer-core/references/domain-registry.json")
WORK_ORDER_SCHEMA_PATH = Path("skills/bedrock-engineer-core/references/work-order.schema.json")
DOMAIN_RESULT_SCHEMA_PATH = Path("skills/bedrock-engineer-core/references/domain-result.schema.json")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON from {path}: {exc}") from exc


def _require_text(value: str | None, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _registry_domains(registry: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    raw = registry.get("domains")
    if not isinstance(raw, list) or not raw:
        raise ValueError("registry.domains must be a non-empty array")
    domain_map: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    skill_owner: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each registry domain must be an object")
        domain_id = item.get("id")
        if not isinstance(domain_id, str) or not domain_id.strip():
            raise ValueError("each domain requires a non-empty id")
        if domain_id in domain_map:
            raise ValueError(f"duplicate domain id: {domain_id}")
        skills = item.get("skills")
        requires = item.get("requires")
        if not isinstance(skills, list) or not skills or not all(isinstance(x, str) and x.strip() for x in skills):
            raise ValueError(f"domain {domain_id} has an invalid skills array")
        if not isinstance(requires, list) or not all(isinstance(x, str) and x.strip() for x in requires):
            raise ValueError(f"domain {domain_id} has an invalid requires array")
        if len(set(requires)) != len(requires):
            raise ValueError(f"domain {domain_id} has duplicate dependency edges")
        for skill in skills:
            if skill in skill_owner:
                raise ValueError(f"Skill {skill!r} has multiple primary domains: {skill_owner[skill]} and {domain_id}")
            skill_owner[skill] = domain_id
        lead = item.get("lead_skill")
        if lead not in skills:
            raise ValueError(f"domain {domain_id} lead_skill must belong to that domain")
        domain_map[domain_id] = item
        order.append(domain_id)
    known = set(domain_map)
    for domain_id, item in domain_map.items():
        for requirement in item["requires"]:
            if requirement not in known:
                raise ValueError(f"domain {domain_id} requires unknown domain {requirement!r}")
            if requirement == domain_id:
                raise ValueError(f"domain {domain_id} cannot require itself")
    return domain_map, order


def resolve_domain_order(
    registry: dict[str, Any], profile_name: str, include_domains: list[str] | None = None
) -> list[str]:
    """Return the stable topological dependency closure for a workflow profile."""
    profiles = registry.get("workflow_profiles")
    if not isinstance(profiles, dict) or profile_name not in profiles:
        known = sorted(profiles) if isinstance(profiles, dict) else []
        raise ValueError(f"unknown workflow profile {profile_name!r}; available: {', '.join(known)}")
    profile = profiles[profile_name]
    if not isinstance(profile, dict):
        raise ValueError(f"workflow profile {profile_name!r} must be an object")
    required = profile.get("required_domains")
    optional = profile.get("optional_domains", [])
    if not isinstance(required, list) or not required or not all(isinstance(x, str) for x in required):
        raise ValueError(f"workflow profile {profile_name!r} has invalid required_domains")
    if not isinstance(optional, list) or not all(isinstance(x, str) for x in optional):
        raise ValueError(f"workflow profile {profile_name!r} has invalid optional_domains")
    if len(set(required)) != len(required) or len(set(optional)) != len(optional):
        raise ValueError(f"workflow profile {profile_name!r} contains duplicate domain entries")
    overlap = sorted(set(required) & set(optional))
    if overlap:
        raise ValueError(f"workflow profile {profile_name!r} marks domains both required and optional: {overlap}")

    architecture = registry.get("architecture")
    if not isinstance(architecture, dict) or architecture.get("id") != "domain-based-hybrid" or architecture.get("integration_model") != "skills-only":
        raise ValueError("registry must identify the Domain-Based Hybrid / Skills-only architecture")
    domain_map, registry_order = _registry_domains(registry)
    unknown_optional = sorted(set(optional) - set(domain_map))
    if unknown_optional:
        raise ValueError(f"workflow profile references unknown optional domains: {unknown_optional}")
    selected_optional = include_domains or []
    if len(set(selected_optional)) != len(selected_optional):
        raise ValueError("--include-domain values must be unique")
    invalid = sorted(set(selected_optional) - set(optional))
    if invalid:
        raise ValueError(
            f"domains {invalid} are not optional for profile {profile_name!r}; "
            "only explicitly declared optional domains can be added"
        )
    unknown_required = sorted(set(required) - set(domain_map))
    if unknown_required:
        raise ValueError(f"workflow profile references unknown required domains: {unknown_required}")

    requested = list(required) + selected_optional
    registry_rank = {domain_id: index for index, domain_id in enumerate(registry_order)}
    state: dict[str, int] = {}  # 0/unseen, 1/visiting, 2/done
    ordered: list[str] = []
    stack: list[str] = []

    def visit(domain_id: str) -> None:
        marker = state.get(domain_id, 0)
        if marker == 2:
            return
        if marker == 1:
            start = stack.index(domain_id) if domain_id in stack else 0
            cycle = stack[start:] + [domain_id]
            raise ValueError("domain dependency cycle: " + " -> ".join(cycle))
        if domain_id not in domain_map:
            raise ValueError(f"selected domain {domain_id!r} is not present in the registry")
        state[domain_id] = 1
        stack.append(domain_id)
        dependencies = sorted(domain_map[domain_id]["requires"], key=lambda x: registry_rank.get(x, 10**9))
        for dependency in dependencies:
            visit(dependency)
        stack.pop()
        state[domain_id] = 2
        ordered.append(domain_id)

    for domain_id in requested:
        visit(domain_id)

    # A dependency may be required even if it is not directly named in the
    # profile. Profile optionality controls only user-added domains, not the
    # dependencies required to make a selected domain coherent.
    return ordered


def _validate_work_order(
    work_order: dict[str, Any], registry: dict[str, Any], package_root: Path
) -> None:
    """Validate the generated envelope against the package's declared contract."""
    schema_path = package_root / WORK_ORDER_SCHEMA_PATH
    result_schema_path = package_root / DOMAIN_RESULT_SCHEMA_PATH
    schema = _read_json(schema_path) if schema_path.is_file() else None
    result_schema = _read_json(result_schema_path) if result_schema_path.is_file() else None
    if not isinstance(schema, dict) or not isinstance(result_schema, dict):
        raise ValueError("work-order and domain-result schemas must be present in the package")
    required = set(schema.get("required", []))
    if not required.issubset(work_order):
        raise ValueError(f"generated Work Order is missing schema fields: {sorted(required - set(work_order))}")
    properties = schema.get("properties", {})
    if set(work_order) - set(properties):
        raise ValueError(f"generated Work Order contains unknown root fields: {sorted(set(work_order) - set(properties))}")
    if work_order.get("schema_version") != "1.0.0":
        raise ValueError("unsupported Work Order schema version")

    task = work_order.get("task")
    if not isinstance(task, dict) or not all(isinstance(task.get(k), str) and task[k].strip() for k in ("request", "language", "task_type")):
        raise ValueError("Work Order task requires request, language and task_type text")
    project = work_order.get("project")
    if not isinstance(project, dict) or not all(isinstance(project.get(k), str) and project[k].strip() for k in ("name", "source_of_truth")):
        raise ValueError("Work Order project requires name and source_of_truth")
    if project.get("target_game_version") is not None and not isinstance(project.get("target_game_version"), str):
        raise ValueError("target_game_version must be a string or null")
    for field in ("pack_roots", "constraints", "preserve"):
        if not isinstance(project.get(field, []), list) or not all(isinstance(x, str) for x in project.get(field, [])):
            raise ValueError(f"project.{field} must be an array of strings")
    if "acceptance_criteria" in task and (not isinstance(task["acceptance_criteria"], list) or not all(isinstance(x, str) for x in task["acceptance_criteria"])):
        raise ValueError("task.acceptance_criteria must be an array of strings")
    baseline = project.get("baseline")
    if baseline is not None:
        if not isinstance(baseline, dict) or not isinstance(baseline.get("artifact"), str) or not isinstance(baseline.get("verified"), bool):
            raise ValueError("baseline requires artifact text and a verified boolean")
        digest = baseline.get("sha256")
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[A-Fa-f0-9]{64}", digest)):
            raise ValueError("baseline sha256 must contain exactly 64 hexadecimal characters")

    capability = work_order.get("capability")
    route_ids = {item.get("id") for item in registry.get("capability_routes", []) if isinstance(item, dict)}
    if not isinstance(capability, dict) or capability.get("route") not in route_ids or not isinstance(capability.get("verified"), bool):
        raise ValueError("capability requires a registered route and a verified boolean")
    if not isinstance(capability.get("available_tools", []), list) or not all(isinstance(x, str) for x in capability.get("available_tools", [])):
        raise ValueError("capability.available_tools must be an array of strings")
    if not isinstance(capability.get("limitations", []), list) or not all(isinstance(x, str) for x in capability.get("limitations", [])):
        raise ValueError("capability.limitations must be an array of strings")

    plan = work_order.get("plan")
    if not isinstance(plan, dict) or set(plan) != {"selected_domains", "ordered_skills", "steps"}:
        raise ValueError("plan must contain selected_domains, ordered_skills and steps only")
    if not isinstance(plan["selected_domains"], list) or len(set(plan["selected_domains"])) != len(plan["selected_domains"]):
        raise ValueError("plan.selected_domains must be a unique array")
    if not isinstance(plan["ordered_skills"], list) or not all(isinstance(x, str) for x in plan["ordered_skills"]):
        raise ValueError("plan.ordered_skills must be a string array")
    if not isinstance(plan["steps"], list):
        raise ValueError("plan.steps must be an array")
    for step in plan["steps"]:
        if not isinstance(step, dict) or not isinstance(step.get("id"), str) or not isinstance(step.get("action"), str):
            raise ValueError("each plan step requires id and action strings")
        if step.get("status") not in {"PLANNED", "PASS", "FAIL", "BLOCKED", "NOT RUN", "PARTIAL", "NOT APPLIED"}:
            raise ValueError(f"invalid plan step status: {step.get('status')!r}")
        if step.get("owner_domain") is not None and step.get("owner_domain") not in plan["selected_domains"]:
            raise ValueError(f"step owner domain is not selected: {step.get('owner_domain')!r}")

    changes = work_order.get("changes")
    if not isinstance(changes, dict) or not isinstance(changes.get("files"), list):
        raise ValueError("changes.files must be an array")
    evidence = work_order.get("evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("items"), list) or evidence.get("runtime_status") not in {"RUNTIME TESTED", "PARTIAL", "NOT RUN"}:
        raise ValueError("evidence requires items and a valid runtime_status")
    allowed_evidence_statuses = {"PASS", "FAIL", "BLOCKED", "NOT RUN", "NOT APPLIED", "CONFIRMED_IN_SOURCE", "STATICALLY VERIFIED", "RUNTIME TESTED", "INFERRED", "UNVERIFIED", "PLANNED"}
    for item in evidence["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("check"), str) or item.get("status") not in allowed_evidence_statuses:
            raise ValueError("each evidence item requires a check and registered status")
    if work_order.get("status") not in {"PLANNED", "IN_PROGRESS", "COMPLETE", "PARTIAL", "BLOCKED"}:
        raise ValueError("invalid Work Order status")
    domain_results = work_order.get("domain_results", [])
    if not isinstance(domain_results, list):
        raise ValueError("domain_results must be an array")
    result_required = set(result_schema.get("required", []))
    for result in domain_results:
        if not isinstance(result, dict) or not result_required.issubset(result):
            raise ValueError("each domain result must satisfy the Domain Result required fields")


def build_work_order(
    registry: dict[str, Any], *, profile_name: str, request: str, project_name: str,
    source_of_truth: str, target_game_version: str | None = None,
    task_type: str | None = None, language: str = "ru", include_domains: list[str] | None = None,
    include_skills: list[str] | None = None,
    acceptance_criteria: list[str] | None = None, capability_route: str = "no_execution_route",
    capability_verified: bool = False, available_tools: list[str] | None = None,
    capability_limitations: list[str] | None = None, pack_roots: list[str] | None = None,
    baseline_artifact: str | None = None, baseline_sha256: str | None = None,
    baseline_verified: bool = False, constraints: list[str] | None = None,
    preserve: list[str] | None = None, package_root: Path = Path("."),
) -> dict[str, Any]:
    """Create a Work Order; all selections and capability claims are caller-supplied."""
    request = _require_text(request, "request")
    project_name = _require_text(project_name, "project_name")
    source_of_truth = _require_text(source_of_truth, "source_of_truth")
    language = _require_text(language, "language")
    ordered_domains = resolve_domain_order(registry, profile_name, include_domains)
    domain_map, _ = _registry_domains(registry)
    profile = registry["workflow_profiles"][profile_name]
    delivery_gates = profile.get("delivery_gates", [])
    if not isinstance(delivery_gates, list) or not all(isinstance(x, str) and x.strip() for x in delivery_gates):
        raise ValueError(f"workflow profile {profile_name!r} has invalid delivery_gates")

    route_ids = {item.get("id") for item in registry.get("capability_routes", []) if isinstance(item, dict)}
    if capability_route not in route_ids:
        raise ValueError(f"capability route {capability_route!r} is not declared in the registry")
    if baseline_sha256 and not baseline_artifact:
        raise ValueError("baseline_sha256 requires baseline_artifact")
    if baseline_verified and not baseline_artifact:
        raise ValueError("baseline_verified requires baseline_artifact")
    if not isinstance(capability_verified, bool) or not isinstance(baseline_verified, bool):
        raise ValueError("capability_verified and baseline_verified must be booleans")
    if baseline_sha256 and not re.fullmatch(r"[A-Fa-f0-9]{64}", baseline_sha256):
        raise ValueError("baseline_sha256 must contain exactly 64 hexadecimal characters")

    # Every selected domain contributes its entry/lead Skill only. Specialist
    # Skills are opt-in so a profile does not silently load every Skill in each
    # domain; the caller/Core adds only those relevant to this task.
    extra_skills = include_skills or []
    if len(set(extra_skills)) != len(extra_skills):
        raise ValueError("--include-skill values must be unique")
    skill_owner = {skill: domain_id for domain_id, domain in domain_map.items() for skill in domain["skills"]}
    unknown_skills = sorted(set(extra_skills) - set(skill_owner))
    if unknown_skills:
        raise ValueError(f"unknown Skills requested: {unknown_skills}")
    unselected_skill_domains = sorted({skill_owner[skill] for skill in extra_skills} - set(ordered_domains))
    if unselected_skill_domains:
        raise ValueError(f"requested Skills belong to domains that are not selected: {unselected_skill_domains}")
    lead_skills = {domain_map[domain_id]["lead_skill"] for domain_id in ordered_domains}
    duplicate_leads = sorted(set(extra_skills) & lead_skills)
    if duplicate_leads:
        raise ValueError(f"lead Skills are already included by their domains: {duplicate_leads}")

    ordered_skills: list[str] = []
    steps: list[dict[str, Any]] = []
    for domain_id in ordered_domains:
        domain = domain_map[domain_id]
        ordered_skills.append(domain["lead_skill"])
        ordered_skills.extend(skill for skill in extra_skills if skill_owner[skill] == domain_id)
        steps.append({
            "id": f"domain:{domain_id}",
            "action": f"{domain['lead_skill']}: {domain['purpose']}",
            "status": "PLANNED",
            "owner_domain": domain_id,
        })
    for index, gate in enumerate(delivery_gates, start=1):
        steps.append({
            "id": f"gate:{index:02d}",
            "action": gate,
            "status": "PLANNED",
            "owner_domain": None,
        })

    baseline = None
    if baseline_artifact:
        baseline = {
            "artifact": baseline_artifact,
            "sha256": baseline_sha256,
            "verified": bool(baseline_verified),
        }
    task_kind = _require_text(task_type or profile_name, "task_type")
    work_order = {
        "schema_version": "1.0.0",
        "task": {
            "request": request,
            "language": language,
            "task_type": task_kind,
            "acceptance_criteria": list(acceptance_criteria or []),
        },
        "project": {
            "name": project_name,
            "source_of_truth": source_of_truth,
            "target_game_version": target_game_version,
            "pack_roots": list(pack_roots or []),
            "baseline": baseline,
            "constraints": list(constraints or []),
            "preserve": list(preserve or []),
        },
        "capability": {
            "route": capability_route,
            "verified": bool(capability_verified),
            "available_tools": list(available_tools or []),
            "limitations": list(capability_limitations or []),
        },
        "plan": {
            "selected_domains": ordered_domains,
            "ordered_skills": ordered_skills,
            "steps": steps,
        },
        "changes": {"files": []},
        "domain_results": [],
        "evidence": {
            "items": [{
                "check": "work-order-created",
                "status": "PLANNED",
                "command": None,
                "exit_code": None,
                "details": "Planning only. No project files were inspected or changed by this utility; specialist work has not run.",
            }],
            "runtime_status": "NOT RUN",
        },
        "status": "PLANNED",
    }
    _validate_work_order(work_order, registry, Path(package_root).resolve())
    return work_order


def _write_output(path: Path, payload: str, overwrite: bool) -> None:
    path = path.expanduser()
    if not path.parent.exists() or not path.parent.is_dir():
        raise ValueError(f"output directory does not exist: {path.parent}")
    if path.exists() and not overwrite:
        raise ValueError(f"output already exists (pass --overwrite to replace): {path}")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not overwrite:
            raise ValueError(f"output already exists (pass --overwrite to replace): {path}")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", default=".", help="plugin package root (default: current directory)")
    parser.add_argument("--profile", help="workflow profile ID from domain-registry.json")
    parser.add_argument("--list-profiles", action="store_true", help="list declared workflow profiles and exit")
    parser.add_argument("--request", help="user request text; this utility does not classify it")
    parser.add_argument("--task-type", help="explicit task type (defaults to profile ID)")
    parser.add_argument("--language", default="ru")
    parser.add_argument("--project-name")
    parser.add_argument("--source-of-truth", help="for example: attached archive / connected workspace / user description")
    parser.add_argument("--target-game-version", help="exact target Bedrock version; omitted means unknown")
    parser.add_argument("--include-domain", action="append", default=[], help="add a profile-declared optional domain (repeatable)")
    parser.add_argument("--include-skill", action="append", default=[], help="add one specialist Skill from a selected domain (repeatable)")
    parser.add_argument("--acceptance", action="append", default=[], help="acceptance criterion (repeatable)")
    parser.add_argument("--capability-route", default="no_execution_route")
    parser.add_argument("--capability-verified", action="store_true", help="caller confirms the selected route is available")
    parser.add_argument("--tool", action="append", default=[], help="verified available tool name (repeatable)")
    parser.add_argument("--limitation", action="append", default=[], help="known capability limitation (repeatable)")
    parser.add_argument("--pack-root", action="append", default=[], help="project pack root (repeatable)")
    parser.add_argument("--baseline-artifact")
    parser.add_argument("--baseline-sha256")
    parser.add_argument("--baseline-verified", action="store_true")
    parser.add_argument("--constraint", action="append", default=[])
    parser.add_argument("--preserve", action="append", default=[])
    parser.add_argument("--output", type=Path, help="write the Work Order JSON to this path")
    parser.add_argument("--overwrite", action="store_true", help="allow replacing an existing --output file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        root = Path(args.package_root).resolve()
        registry = _read_json(root / REGISTRY_PATH)
        if not isinstance(registry, dict):
            raise ValueError("domain registry root must be a JSON object")
        if args.list_profiles:
            profiles = registry.get("workflow_profiles", {})
            if not isinstance(profiles, dict):
                raise ValueError("registry.workflow_profiles must be an object")
            print(json.dumps({name: {
                "required_domains": profile.get("required_domains", []),
                "optional_domains": profile.get("optional_domains", []),
            } for name, profile in profiles.items()}, ensure_ascii=False, indent=2))
            return 0
        if not args.profile or not args.request or not args.project_name or not args.source_of_truth:
            parser.error("planning requires --profile, --request, --project-name and --source-of-truth")
        order = build_work_order(
            registry,
            profile_name=args.profile,
            request=args.request,
            task_type=args.task_type,
            language=args.language,
            project_name=args.project_name,
            source_of_truth=args.source_of_truth,
            target_game_version=args.target_game_version,
            include_domains=args.include_domain,
            include_skills=args.include_skill,
            acceptance_criteria=args.acceptance,
            capability_route=args.capability_route,
            capability_verified=args.capability_verified,
            available_tools=args.tool,
            capability_limitations=args.limitation,
            pack_roots=args.pack_root,
            baseline_artifact=args.baseline_artifact,
            baseline_sha256=args.baseline_sha256,
            baseline_verified=args.baseline_verified,
            constraints=args.constraint,
            preserve=args.preserve,
            package_root=root,
        )
        rendered = json.dumps(order, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            _write_output(args.output, rendered, args.overwrite)
        sys.stdout.write(rendered)
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
