#!/usr/bin/env python3
"""Validate and reconcile specialist Domain Results into one Work Order.

This deterministic local utility consumes JSON records. It never invokes Skills,
opens project files, executes add-on code, or infers that a domain ran. Inputs are
read-only; writing a Work Order requires an explicit --output path.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import uuid
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

REGISTRY_PATH = Path("skills/bedrock-engineer-core/references/domain-registry.json")
WORK_ORDER_SCHEMA_PATH = Path("skills/bedrock-engineer-core/references/work-order.schema.json")
DOMAIN_RESULT_SCHEMA_PATH = Path("skills/bedrock-engineer-core/references/domain-result.schema.json")
DOMAIN_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT RUN", "NOT APPLIED", "PARTIAL"}
EVIDENCE_STATUSES = {
    "PASS", "FAIL", "BLOCKED", "NOT RUN", "NOT APPLIED", "CONFIRMED_IN_SOURCE",
    "STATICALLY VERIFIED", "RUNTIME TESTED", "INFERRED", "UNVERIFIED", "PLANNED",
}
FILE_ACTIONS = {"added", "modified", "removed", "inspected"}
FILE_STATUSES = {"PLANNED", "APPLIED", "NOT APPLIED", "VERIFIED", "INSPECTED"}
FINDING_SEVERITIES = {"BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"}
FINDING_CONFIDENCE = {"CONFIRMED", "HIGH", "MEDIUM", "LOW", "INFERRED"}
CRITERION_STATUSES = {"MET", "NOT MET", "UNVERIFIED"}
RUNTIME_STATUSES = {"RUNTIME TESTED", "PARTIAL", "NOT RUN"}


class IntegrationError(ValueError):
    """Raised when an input record violates the integration contract."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IntegrationError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise IntegrationError(f"non-finite JSON number is not allowed: {value}")


def read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except IntegrationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrationError(f"cannot read valid JSON from {path}: {exc}") from exc


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise IntegrationError(f"{label} must be a non-empty string")
    return value


def _string_list(value: Any, label: str, *, unique: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise IntegrationError(f"{label} must be an array of strings")
    if unique and len(value) != len(set(value)):
        raise IntegrationError(f"{label} must not contain duplicates")
    return value


def _safe_relative_path(value: Any, label: str) -> str:
    path = _text(value, label).strip()
    if "\x00" in path or "\\" in path:
        raise IntegrationError(f"{label} must use a safe relative POSIX path: {path!r}")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise IntegrationError(f"{label} must not be absolute: {path!r}")
    raw_parts = path.split("/")
    parts = PurePosixPath(path).parts
    if not parts or any(part in {"", ".", ".."} for part in raw_parts):
        raise IntegrationError(f"{label} contains an unsafe path segment: {path!r}")
    return path


def _domain_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    domains = registry.get("domains")
    if not isinstance(domains, list) or not domains:
        raise IntegrationError("registry.domains must be a non-empty array")
    index: dict[str, dict[str, Any]] = {}
    for domain in domains:
        if not isinstance(domain, dict):
            raise IntegrationError("each registry domain must be an object")
        domain_id = _text(domain.get("id"), "domain.id")
        if domain_id in index:
            raise IntegrationError(f"duplicate registry domain id: {domain_id}")
        skills = _string_list(domain.get("skills"), f"domain {domain_id}.skills", unique=True)
        lead_skill = _text(domain.get("lead_skill"), f"domain {domain_id}.lead_skill")
        if lead_skill not in skills:
            raise IntegrationError(f"domain {domain_id} lead_skill is not a member of its skills list")
        index[domain_id] = domain
    return index


def _validate_work_order(work_order: Any, registry: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    if not isinstance(work_order, dict):
        raise IntegrationError("Work Order root must be a JSON object")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise IntegrationError("Work Order schema properties must be an object")
    unknown = sorted(set(work_order) - set(properties))
    missing = sorted(set(schema.get("required", [])) - set(work_order))
    if unknown:
        raise IntegrationError(f"Work Order has unsupported top-level fields: {unknown}")
    if missing:
        raise IntegrationError(f"Work Order is missing required fields: {missing}")
    if work_order.get("schema_version") != "1.0.0":
        raise IntegrationError("Work Order schema_version must be '1.0.0'")

    task = work_order.get("task")
    if not isinstance(task, dict):
        raise IntegrationError("Work Order task must be an object")
    task_allowed = set(schema.get("properties", {}).get("task", {}).get("properties", {}))
    if set(task) - task_allowed:
        raise IntegrationError(f"Work Order task has unsupported fields: {sorted(set(task) - task_allowed)}")
    _text(task.get("request"), "task.request")
    _text(task.get("language"), "task.language")
    _text(task.get("task_type"), "task.task_type")
    criteria = _string_list(task.get("acceptance_criteria", []), "task.acceptance_criteria", unique=True)

    project = work_order.get("project")
    if not isinstance(project, dict):
        raise IntegrationError("Work Order project must be an object")
    project_allowed = set(schema.get("properties", {}).get("project", {}).get("properties", {}))
    if set(project) - project_allowed:
        raise IntegrationError(f"Work Order project has unsupported fields: {sorted(set(project) - project_allowed)}")
    _text(project.get("name"), "project.name")
    _text(project.get("source_of_truth"), "project.source_of_truth")

    # A project-state link is optional, but when present it must be a complete,
    # safe integrity reference. The state manager refreshes it after mutations.
    state_link = work_order.get("project_state")
    if state_link is not None:
        if not isinstance(state_link, dict):
            raise IntegrationError("Work Order project_state must be an object when present")
        state_link_schema = schema.get("properties", {}).get("project_state", {})
        link_properties = state_link_schema.get("properties", {}) if isinstance(state_link_schema, dict) else {}
        link_allowed = set(link_properties) if isinstance(link_properties, dict) else set()
        if not link_allowed or set(state_link) - link_allowed:
            raise IntegrationError("Work Order project_state has unsupported fields or schema is incomplete")
        required_link_fields = set(state_link_schema.get("required", []))
        if required_link_fields - set(state_link):
            raise IntegrationError("Work Order project_state is missing required fields")
        project_id = _text(state_link.get("project_id"), "project_state.project_id")
        try:
            if str(uuid.UUID(project_id)) != project_id.lower():
                raise ValueError("non-canonical UUID")
        except (ValueError, AttributeError) as exc:
            raise IntegrationError("project_state.project_id must be a canonical UUID") from exc
        revision = state_link.get("revision")
        if type(revision) is not int or revision < 1:
            raise IntegrationError("project_state.revision must be an integer >= 1")
        state_path = _safe_relative_path(state_link.get("state_path"), "project_state.state_path")
        if state_path != ".mbe/project-state.json":
            raise IntegrationError("project_state.state_path must identify .mbe/project-state.json")
        state_hash = _text(state_link.get("state_sha256"), "project_state.state_sha256")
        if not re.fullmatch(r"[a-f0-9]{64}", state_hash):
            raise IntegrationError("project_state.state_sha256 must be a lowercase SHA-256 digest")
        snapshot_id = state_link.get("latest_snapshot_id")
        snapshot_hash = state_link.get("latest_snapshot_sha256")
        if (snapshot_id is None) != (snapshot_hash is None):
            raise IntegrationError("project_state latest snapshot ID and hash must both be null or both be present")
        if snapshot_id is not None:
            if not isinstance(snapshot_id, str) or not re.fullmatch(r"snapshot-[a-f0-9]{32}", snapshot_id):
                raise IntegrationError("project_state.latest_snapshot_id has an invalid format")
            if not isinstance(snapshot_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", snapshot_hash):
                raise IntegrationError("project_state.latest_snapshot_sha256 must be a lowercase SHA-256 digest")

    capability = work_order.get("capability")
    if not isinstance(capability, dict):
        raise IntegrationError("Work Order capability must be an object")
    capability_allowed = set(schema.get("properties", {}).get("capability", {}).get("properties", {}))
    if set(capability) - capability_allowed:
        raise IntegrationError(f"Work Order capability has unsupported fields: {sorted(set(capability) - capability_allowed)}")
    route_ids = {
        item.get("id") for item in registry.get("capability_routes", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if capability.get("route") not in route_ids or not isinstance(capability.get("verified"), bool):
        raise IntegrationError("Work Order capability must have a registered route and boolean verified flag")

    plan = work_order.get("plan")
    if not isinstance(plan, dict):
        raise IntegrationError("Work Order plan must be an object")
    plan_allowed = set(schema.get("properties", {}).get("plan", {}).get("properties", {}))
    if set(plan) - plan_allowed:
        raise IntegrationError(f"Work Order plan has unsupported fields: {sorted(set(plan) - plan_allowed)}")
    domain_map = _domain_index(registry)
    selected = _string_list(plan.get("selected_domains"), "plan.selected_domains", unique=True)
    if not selected:
        raise IntegrationError("plan.selected_domains must not be empty")
    unknown_domains = sorted(set(selected) - set(domain_map))
    if unknown_domains:
        raise IntegrationError(f"Work Order selects unknown domains: {unknown_domains}")
    ordered_skills = _string_list(plan.get("ordered_skills"), "plan.ordered_skills")
    if len(ordered_skills) != len(set(ordered_skills)):
        raise IntegrationError("plan.ordered_skills contains duplicate Skills")
    for skill in ordered_skills:
        if not any(skill in domain.get("skills", []) for domain in domain_map.values()):
            raise IntegrationError(f"Work Order references an unregistered Skill: {skill}")
    steps = plan.get("steps")
    if not isinstance(steps, list):
        raise IntegrationError("plan.steps must be an array")
    step_ids: set[str] = set()
    step_allowed = set(schema.get("properties", {}).get("plan", {}).get("properties", {}).get("steps", {}).get("items", {}).get("properties", {}))
    for step in steps:
        if not isinstance(step, dict):
            raise IntegrationError("each Work Order plan step must be an object")
        if set(step) - step_allowed:
            raise IntegrationError(f"Work Order plan step has unsupported fields: {sorted(set(step) - step_allowed)}")
        step_id = _text(step.get("id"), "plan step.id")
        _text(step.get("action"), f"plan step {step_id}.action")
        if step_id in step_ids:
            raise IntegrationError(f"duplicate Work Order step id: {step_id}")
        step_ids.add(step_id)
        if step.get("status") not in {"PLANNED", "PASS", "FAIL", "BLOCKED", "NOT RUN", "PARTIAL", "NOT APPLIED"}:
            raise IntegrationError(f"plan step {step_id} has invalid status")
        owner = step.get("owner_domain")
        if owner is not None and owner not in selected:
            raise IntegrationError(f"plan step {step_id} belongs to an unselected domain {owner!r}")

    changes = work_order.get("changes")
    if not isinstance(changes, dict) or not isinstance(changes.get("files"), list):
        raise IntegrationError("Work Order changes.files must be an array")
    change_allowed = set(schema.get("properties", {}).get("changes", {}).get("properties", {}).get("files", {}).get("items", {}).get("properties", {}))
    for item in changes["files"]:
        if not isinstance(item, dict):
            raise IntegrationError("each Work Order change record must be an object")
        if set(item) - change_allowed:
            raise IntegrationError(f"Work Order change record has unsupported fields: {sorted(set(item) - change_allowed)}")
        _safe_relative_path(item.get("path"), "changes.files.path")
        if item.get("action") not in FILE_ACTIONS:
            raise IntegrationError("Work Order change record has invalid action")
        if item.get("status") not in FILE_STATUSES:
            raise IntegrationError("Work Order change record has invalid status")

    evidence = work_order.get("evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("items"), list):
        raise IntegrationError("Work Order evidence must contain an items array")
    evidence_allowed = set(schema.get("properties", {}).get("evidence", {}).get("properties", {}))
    if set(evidence) - evidence_allowed:
        raise IntegrationError(f"Work Order evidence has unsupported fields: {sorted(set(evidence) - evidence_allowed)}")
    evidence_item_allowed = set(schema.get("properties", {}).get("evidence", {}).get("properties", {}).get("items", {}).get("items", {}).get("properties", {}))
    if evidence.get("runtime_status") not in RUNTIME_STATUSES:
        raise IntegrationError("Work Order evidence.runtime_status is invalid")
    _string_list([item.get("check") for item in evidence["items"] if isinstance(item, dict)], "evidence check names")
    for item in evidence["items"]:
        if not isinstance(item, dict) or item.get("status") not in EVIDENCE_STATUSES:
            raise IntegrationError("Work Order evidence item has an invalid shape/status")
        if set(item) - evidence_item_allowed:
            raise IntegrationError(f"Work Order evidence item has unsupported fields: {sorted(set(item) - evidence_item_allowed)}")

    if work_order.get("status") not in {"PLANNED", "IN_PROGRESS", "COMPLETE", "PARTIAL", "BLOCKED"}:
        raise IntegrationError("Work Order status is invalid")
    return domain_map, selected, criteria


def validate_domain_result(
    result: Any, *, registry: dict[str, Any], result_schema: dict[str, Any],
    selected_domains: list[str], acceptance_criteria: list[str],
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise IntegrationError("each Domain Result must be a JSON object")
    properties = result_schema.get("properties", {})
    allowed = set(properties) if isinstance(properties, dict) else set()
    unknown = sorted(set(result) - allowed)
    required = set(result_schema.get("required", []))
    missing = sorted(required - set(result))
    if unknown:
        raise IntegrationError(f"Domain Result has unsupported fields: {unknown}")
    if missing:
        raise IntegrationError(f"Domain Result is missing required fields: {missing}")

    domain_id = _text(result.get("domain_id"), "domain_id")
    domains = _domain_index(registry)
    if domain_id not in domains:
        raise IntegrationError(f"Domain Result references unknown domain: {domain_id}")
    if domain_id not in selected_domains:
        raise IntegrationError(f"Domain Result domain is not selected in the Work Order: {domain_id}")
    if result.get("status") not in DOMAIN_STATUSES:
        raise IntegrationError(f"Domain Result {domain_id} has invalid status")
    _text(result.get("summary"), f"Domain Result {domain_id}.summary", allow_empty=True)

    findings = result.get("findings")
    if not isinstance(findings, list):
        raise IntegrationError(f"Domain Result {domain_id}.findings must be an array")
    for finding in findings:
        if not isinstance(finding, dict):
            raise IntegrationError(f"Domain Result {domain_id} finding must be an object")
        finding_allowed = {"severity", "message", "confidence", "path", "pointer", "recommended_action"}
        if set(finding) - finding_allowed:
            raise IntegrationError(f"Domain Result {domain_id} finding has unsupported fields: {sorted(set(finding) - finding_allowed)}")
        if not {"severity", "message", "confidence"}.issubset(finding):
            raise IntegrationError(f"Domain Result {domain_id} finding lacks severity/message/confidence")
        if finding.get("severity") not in FINDING_SEVERITIES or finding.get("confidence") not in FINDING_CONFIDENCE:
            raise IntegrationError(f"Domain Result {domain_id} finding has invalid severity/confidence")
        _text(finding.get("message"), f"Domain Result {domain_id} finding.message")
        for key in ("path", "pointer", "recommended_action"):
            if key in finding and finding[key] is not None and not isinstance(finding[key], str):
                raise IntegrationError(f"Domain Result {domain_id} finding.{key} must be text or null")
        if finding.get("path"):
            _safe_relative_path(finding["path"], f"Domain Result {domain_id} finding.path")

    changed_files = result.get("changed_files")
    if not isinstance(changed_files, list):
        raise IntegrationError(f"Domain Result {domain_id}.changed_files must be an array")
    seen_files: set[str] = set()
    normalized_files: list[dict[str, Any]] = []
    for item in changed_files:
        if not isinstance(item, dict):
            raise IntegrationError(f"Domain Result {domain_id} changed_files item must be an object")
        if set(item) - {"path", "action", "status"}:
            raise IntegrationError(f"Domain Result {domain_id} changed_files item has unsupported fields: {sorted(set(item) - {'path', 'action', 'status'})}")
        path = _safe_relative_path(item.get("path"), f"Domain Result {domain_id} changed_files.path")
        if path in seen_files:
            raise IntegrationError(f"Domain Result {domain_id} reports the same path more than once: {path}")
        seen_files.add(path)
        action = item.get("action")
        if action not in FILE_ACTIONS:
            raise IntegrationError(f"Domain Result {domain_id} changed_files item has invalid action")
        status = item.get("status")
        if status is None:
            status = "INSPECTED" if action == "inspected" else (
                "NOT APPLIED" if result.get("status") in {"NOT APPLIED", "NOT RUN", "BLOCKED"} else "APPLIED"
            )
        if status not in FILE_STATUSES:
            raise IntegrationError(f"Domain Result {domain_id} changed_files item has invalid status")
        normalized_files.append({"path": path, "action": action, "status": status})

    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        raise IntegrationError(f"Domain Result {domain_id}.evidence must be an array")
    normalized_evidence: list[dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, dict):
            raise IntegrationError(f"Domain Result {domain_id} evidence item must be an object")
        if set(item) - {"check", "status", "details"}:
            raise IntegrationError(f"Domain Result {domain_id} evidence item has unsupported fields: {sorted(set(item) - {'check', 'status', 'details'})}")
        check = _text(item.get("check"), f"Domain Result {domain_id} evidence.check")
        status = item.get("status")
        if status not in EVIDENCE_STATUSES:
            raise IntegrationError(f"Domain Result {domain_id} evidence item has invalid status")
        details = item.get("details", "")
        if not isinstance(details, str):
            raise IntegrationError(f"Domain Result {domain_id} evidence.details must be text")
        normalized_evidence.append({"check": check, "status": status, "details": details})

    limitations = _string_list(result.get("limitations"), f"Domain Result {domain_id}.limitations")
    next_domains = _string_list(result.get("next_domains", []), f"Domain Result {domain_id}.next_domains", unique=True)
    unknown_next = sorted(set(next_domains) - set(domains))
    if unknown_next:
        raise IntegrationError(f"Domain Result {domain_id} suggests unknown next domains: {unknown_next}")

    runtime_status = result.get("runtime_status", "NOT RUN")
    if runtime_status not in RUNTIME_STATUSES:
        raise IntegrationError(f"Domain Result {domain_id}.runtime_status is invalid")

    criterion_results = result.get("criterion_results", [])
    if not isinstance(criterion_results, list):
        raise IntegrationError(f"Domain Result {domain_id}.criterion_results must be an array")
    seen_criteria: set[str] = set()
    normalized_criteria: list[dict[str, Any]] = []
    for item in criterion_results:
        if not isinstance(item, dict):
            raise IntegrationError(f"Domain Result {domain_id} criterion result must be an object")
        if set(item) - {"criterion", "status", "evidence"}:
            raise IntegrationError(f"Domain Result {domain_id} criterion result has unsupported fields: {sorted(set(item) - {'criterion', 'status', 'evidence'})}")
        criterion = _text(item.get("criterion"), f"Domain Result {domain_id} criterion")
        if criterion not in acceptance_criteria:
            raise IntegrationError(f"Domain Result {domain_id} reports a criterion not declared in the Work Order: {criterion!r}")
        if criterion in seen_criteria:
            raise IntegrationError(f"Domain Result {domain_id} reports criterion more than once: {criterion!r}")
        seen_criteria.add(criterion)
        status = item.get("status")
        if status not in CRITERION_STATUSES:
            raise IntegrationError(f"Domain Result {domain_id} criterion {criterion!r} has invalid status")
        ev = _string_list(item.get("evidence", []), f"Domain Result {domain_id} criterion evidence")
        if status in {"MET", "NOT MET"} and not any(entry.strip() for entry in ev):
            raise IntegrationError(f"Domain Result {domain_id} criterion {criterion!r} requires evidence for {status}")
        normalized_criteria.append({"criterion": criterion, "status": status, "evidence": ev})

    normalized = dict(result)
    normalized["changed_files"] = normalized_files
    normalized["evidence"] = normalized_evidence
    normalized["next_domains"] = next_domains
    normalized["runtime_status"] = runtime_status
    normalized["criterion_results"] = normalized_criteria
    return normalized


def _load_result_inputs(paths: list[Path]) -> list[Any]:
    incoming: list[Any] = []
    for path in paths:
        value = read_json(path)
        if isinstance(value, list):
            incoming.extend(value)
        else:
            incoming.append(value)
    return incoming


def _detect_conflicts(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_exact: dict[str, list[tuple[str, str]]] = defaultdict(list)
    by_folded: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for result in results:
        domain_id = result["domain_id"]
        for item in result["changed_files"]:
            path, action = item["path"], item["action"]
            by_exact[path].append((domain_id, action))
            by_folded[path.casefold()][path].add(domain_id)

    conflicts: list[dict[str, Any]] = []
    for folded, spellings in sorted(by_folded.items()):
        if len(spellings) > 1:
            paths = sorted(spellings)
            domains = sorted({domain for owners in spellings.values() for domain in owners})
            conflicts.append({
                "code": "CASE_COLLISION",
                "severity": "BLOCKER",
                "path": paths[0],
                "paths": paths,
                "domain_ids": domains,
                "message": f"Different paths collide case-insensitively: {', '.join(paths)}",
            })

    for path, claims in sorted(by_exact.items()):
        domains = sorted({domain for domain, _ in claims})
        mutating = [(domain, action) for domain, action in claims if action != "inspected"]
        mutating_domains = sorted({domain for domain, _ in mutating})
        actions = {action for _, action in mutating}
        if len(mutating_domains) < 2:
            continue
        if "removed" in actions and actions & {"added", "modified"}:
            conflicts.append({
                "code": "REMOVE_VS_WRITE",
                "severity": "BLOCKER",
                "path": path,
                "domain_ids": mutating_domains,
                "message": f"One domain removes {path} while another adds or modifies it",
            })
        elif len(actions) > 1:
            conflicts.append({
                "code": "ACTION_CONFLICT",
                "severity": "HIGH",
                "path": path,
                "domain_ids": mutating_domains,
                "message": f"Domains report different write actions for {path}: {', '.join(sorted(actions))}",
            })
        else:
            conflicts.append({
                "code": "OVERLAPPING_WRITE",
                "severity": "HIGH",
                "path": path,
                "domain_ids": mutating_domains,
                "message": f"Multiple domains report writing {path}; patch-level overlap cannot be resolved from file-level hand-offs",
            })
    return conflicts


def _aggregate_criteria(results: list[dict[str, Any]], criteria: list[str]) -> list[dict[str, Any]]:
    claims: dict[str, list[tuple[str, str, list[str]]]] = defaultdict(list)
    for result in results:
        for item in result.get("criterion_results", []):
            claims[item["criterion"]].append((result["domain_id"], item["status"], item["evidence"]))
    output: list[dict[str, Any]] = []
    for criterion in criteria:
        rows = claims.get(criterion, [])
        statuses = {status for _, status, _ in rows}
        if not rows:
            status = "UNVERIFIED"
        elif "MET" in statuses and "NOT MET" in statuses:
            status = "CONFLICT"
        elif "NOT MET" in statuses:
            status = "NOT MET"
        elif "UNVERIFIED" in statuses:
            status = "UNVERIFIED"
        else:
            status = "MET"
        output.append({
            "criterion": criterion,
            "status": status,
            "domain_ids": sorted({domain for domain, _, _ in rows}),
            "evidence": list(dict.fromkeys(e for _, _, ev in rows for e in ev)),
        })
    return output


def _merge_changes(existing: list[dict[str, Any]], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    reported_paths: set[str] = set()
    for result in results:
        domain_id = result["domain_id"]
        for item in result["changed_files"]:
            reported_paths.add(item["path"])
            reports[(item["path"], item["action"])].append((domain_id, item["status"]))

    merged: list[dict[str, Any]] = []
    for item in existing:
        # Replace only a planned placeholder. Preserve prior applied/verified
        # Work Order records because they may represent manual or earlier work
        # not repeated by the current specialist hand-offs.
        if item.get("path") in reported_paths and item.get("status") == "PLANNED":
            continue
        merged.append(dict(item))

    for (path, action), rows in sorted(reports.items()):
        statuses = {status for _, status in rows}
        if "NOT APPLIED" in statuses:
            status = "NOT APPLIED"
        elif "PLANNED" in statuses:
            status = "PLANNED"
        elif "VERIFIED" in statuses:
            status = "VERIFIED"
        elif "INSPECTED" in statuses:
            status = "INSPECTED"
        else:
            status = "APPLIED"
        owners = ", ".join(sorted({domain for domain, _ in rows}))
        merged.append({
            "path": path,
            "action": action,
            "status": status,
            "reason": f"Domain Result hand-off from: {owners}",
        })
    return merged


def _aggregate_runtime(results: list[dict[str, Any]]) -> str:
    if not results:
        return "NOT RUN"
    states = {result.get("runtime_status", "NOT RUN") for result in results}
    if states == {"RUNTIME TESTED"}:
        return "RUNTIME TESTED"
    if states == {"NOT RUN"}:
        return "NOT RUN"
    return "PARTIAL"


def integrate(
    work_order: Any, incoming_results: list[Any], *, registry: dict[str, Any],
    work_order_schema: dict[str, Any], result_schema: dict[str, Any],
    replace_domains: list[str] | None = None,
) -> dict[str, Any]:
    domain_map, selected, acceptance = _validate_work_order(work_order, registry, work_order_schema)
    if not isinstance(work_order.get("domain_results", []), list):
        raise IntegrationError("Work Order domain_results must be an array")

    existing_results = [
        validate_domain_result(item, registry=registry, result_schema=result_schema,
                               selected_domains=selected, acceptance_criteria=acceptance)
        for item in work_order.get("domain_results", [])
    ]
    existing_by_domain: dict[str, dict[str, Any]] = {}
    for item in existing_results:
        did = item["domain_id"]
        if did in existing_by_domain:
            raise IntegrationError(f"Work Order already contains duplicate Domain Results for {did}")
        existing_by_domain[did] = item

    replacements = replace_domains or []
    if len(replacements) != len(set(replacements)):
        raise IntegrationError("--replace-domain values must be unique")
    unknown_replacements = sorted(set(replacements) - set(selected))
    if unknown_replacements:
        raise IntegrationError(f"--replace-domain references unselected domains: {unknown_replacements}")
    absent_replacements = sorted(set(replacements) - set(existing_by_domain))
    if absent_replacements:
        raise IntegrationError(f"--replace-domain requested domains without an existing result: {absent_replacements}")

    normalized_incoming = [
        validate_domain_result(item, registry=registry, result_schema=result_schema,
                               selected_domains=selected, acceptance_criteria=acceptance)
        for item in incoming_results
    ]
    incoming_ids = [item["domain_id"] for item in normalized_incoming]
    if len(incoming_ids) != len(set(incoming_ids)):
        raise IntegrationError("incoming Domain Results contain duplicate domain_id values")
    for did in incoming_ids:
        if did in existing_by_domain and did not in replacements:
            raise IntegrationError(f"Domain Result for {did} already exists; use --replace-domain {did} to replace it")
    if set(replacements) - set(incoming_ids):
        raise IntegrationError(f"--replace-domain has no incoming replacement result for: {sorted(set(replacements) - set(incoming_ids))}")

    merged_by_domain = dict(existing_by_domain)
    for result in normalized_incoming:
        merged_by_domain[result["domain_id"]] = result
    results = [merged_by_domain[did] for did in selected if did in merged_by_domain]

    conflicts = _detect_conflicts(results)
    criteria = _aggregate_criteria(results, acceptance)
    missing_domains = [did for did in selected if did not in merged_by_domain]
    domain_statuses = [{"domain_id": did, "status": merged_by_domain[did]["status"]}
                       for did in selected if did in merged_by_domain]
    next_domains = list(dict.fromkeys(
        domain for result in results for domain in result.get("next_domains", [])
        if domain not in merged_by_domain
    ))

    blocker_conflict = any(conflict["severity"] == "BLOCKER" for conflict in conflicts)
    blocker_finding = any(
        finding.get("severity") == "BLOCKER"
        for item in results for finding in item.get("findings", [])
    )
    blockers = blocker_conflict or blocker_finding
    domain_blocked = any(item["status"] == "BLOCKED" for item in results)
    high_findings = any(
        finding.get("severity") == "HIGH"
        for item in results for finding in item.get("findings", [])
    )
    failed_or_incomplete = any(item["status"] in {"FAIL", "PARTIAL", "NOT RUN", "NOT APPLIED"} for item in results)
    criterion_review = any(item["status"] != "MET" for item in criteria)
    all_reported_pass = len(results) == len(selected) and all(item["status"] == "PASS" for item in results)
    no_conflicts = not conflicts
    complete = all_reported_pass and no_conflicts and not criterion_review and not high_findings

    if blockers or domain_blocked:
        work_status = "BLOCKED"
        integration_status = "BLOCKED"
    elif complete:
        work_status = "COMPLETE"
        integration_status = "COMPLETE"
    elif not results:
        work_status = "PLANNED"
        integration_status = "PLANNED"
    elif failed_or_incomplete or conflicts or criterion_review or high_findings:
        work_status = "PARTIAL"
        integration_status = "REVIEW"
    elif missing_domains:
        work_status = "IN_PROGRESS"
        integration_status = "IN_PROGRESS"
    else:
        work_status = "PARTIAL"
        integration_status = "REVIEW"

    runtime_status = _aggregate_runtime(results)
    work_order = json.loads(json.dumps(work_order))
    work_order["domain_results"] = results
    work_order["changes"]["files"] = _merge_changes(work_order["changes"]["files"], results)
    work_order["evidence"]["runtime_status"] = runtime_status
    for result in results:
        for evidence_item in result.get("evidence", []):
            work_order["evidence"]["items"].append({
                "check": f"{result['domain_id']}:{evidence_item['check']}",
                "status": evidence_item["status"],
                "command": None,
                "exit_code": None,
                "details": evidence_item.get("details", ""),
            })
    status_by_domain = {item["domain_id"]: item["status"] for item in domain_statuses}
    step_map = {
        "PASS": "PASS", "FAIL": "FAIL", "BLOCKED": "BLOCKED", "NOT RUN": "NOT RUN",
        "NOT APPLIED": "NOT APPLIED", "PARTIAL": "PARTIAL",
    }
    for step in work_order["plan"]["steps"]:
        owner = step.get("owner_domain")
        if owner in status_by_domain:
            step["status"] = step_map[status_by_domain[owner]]

    work_order["status"] = work_status
    reported = len(results)
    missing_count = len(missing_domains)
    summary = (
        f"Integrated {reported}/{len(selected)} selected domain results; "
        f"{len(conflicts)} file conflict(s); {sum(x['status'] == 'MET' for x in criteria)}/{len(criteria)} "
        "acceptance criterion/criteria met."
    )
    work_order["integration"] = {
        "status": integration_status,
        "summary": summary,
        "domain_coverage": {
            "expected": len(selected),
            "reported": reported,
            "missing": missing_domains,
        },
        "domain_statuses": domain_statuses,
        "acceptance": criteria,
        "conflicts": conflicts,
        "next_domains": next_domains,
        "runtime_status": runtime_status,
    }
    return work_order


def _atomic_write(path: Path, payload: str, overwrite: bool) -> None:
    path = path.expanduser()
    if not path.parent.exists() or not path.parent.is_dir():
        raise IntegrationError(f"output directory does not exist: {path.parent}")
    if path.exists() and not overwrite:
        raise IntegrationError(f"output already exists (pass --overwrite to replace): {path}")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not overwrite:
            raise IntegrationError(f"output already exists (pass --overwrite to replace): {path}")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", default=".", help="plugin package root containing registry and schemas")
    parser.add_argument("--work-order", required=True, type=Path, help="input Work Order JSON")
    parser.add_argument("--result", action="append", default=[], type=Path,
                        help="Domain Result JSON file or JSON array file; repeat for multiple inputs")
    parser.add_argument("--replace-domain", action="append", default=[],
                        help="explicitly replace an existing result for this selected domain")
    parser.add_argument("--output", type=Path, help="write reconciled Work Order to a new path")
    parser.add_argument("--overwrite", action="store_true", help="allow replacing an existing --output file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = Path(args.package_root).resolve()
        registry = read_json(root / REGISTRY_PATH)
        work_schema = read_json(root / WORK_ORDER_SCHEMA_PATH)
        result_schema = read_json(root / DOMAIN_RESULT_SCHEMA_PATH)
        if not isinstance(registry, dict) or not isinstance(work_schema, dict) or not isinstance(result_schema, dict):
            raise IntegrationError("registry and schemas must be JSON objects")
        work_order = read_json(args.work_order)
        incoming = _load_result_inputs(args.result)
        integrated = integrate(
            work_order, incoming, registry=registry,
            work_order_schema=work_schema, result_schema=result_schema,
            replace_domains=args.replace_domain,
        )
        rendered = json.dumps(integrated, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            _atomic_write(args.output, rendered, args.overwrite)
        sys.stdout.write(rendered)
        return 0 if integrated["status"] == "COMPLETE" else 1
    except IntegrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
