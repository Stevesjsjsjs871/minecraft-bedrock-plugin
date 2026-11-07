---
name: domain-result-integration
description: Use after specialist domains have completed work to validate their Domain Results, reconcile file changes, detect cross-domain conflicts, assess acceptance criteria and update one shared Work Order.
---

# Domain Result Integration

## Purpose

Core owns final reconciliation. Specialist domains do not independently declare the whole Work Order complete. Each domain returns a record matching `skills/bedrock-engineer-core/references/domain-result.schema.json`; Core integrates those records against the same Work Order and selected-domain set.

## Required hand-off

Use `skills/bedrock-engineer-core/references/domain-result.example.json` as a shape example, not evidence for a real project. Each Domain Result must include `domain_id`, `status`, `summary`, `findings`, `changed_files`, `evidence` and `limitations`. Optional fields include `runtime_status`, exact `criterion_results` and registered `next_domains`.

Report only observed work. `changed_files` means a concrete file action; planned work must be marked explicitly. `MET` and `NOT MET` acceptance claims require evidence. Unresolved criteria are `UNVERIFIED`.

## Integration procedure

1. Preserve the original Work Order identity, baseline, constraints, selected domains and acceptance criteria.
2. Validate every result against schema and registry. Reject unknown/unselected domains, duplicate results, undeclared criteria, unsafe paths, duplicate path claims within one domain and unsupported statuses.
3. Merge by domain ID. Replacing an existing result requires explicit replacement instruction.
4. Reconcile changed files and evidence. An inspected action is not a write; planned placeholders are superseded only by explicit reports.
5. Detect case-insensitive path collisions, removal versus add/modify, inconsistent actions, overlapping writes and producer/consumer contract conflicts. Do not silently choose a version.
6. Aggregate each acceptance criterion as `MET`, `NOT MET`, `CONFLICT` or `UNVERIFIED`. A met claim requires evidence; conflicting claims never pass.
7. Recompute Work Order state. `COMPLETE` requires every selected domain `PASS`, no unresolved file conflicts or high/blocker findings, and every criterion `MET`. A blocked domain/blocker conflict means `BLOCKED`; unresolved work remains `PARTIAL` or `IN_PROGRESS`.
8. Aggregate runtime separately. Static checks never imply Minecraft runtime success.
9. Reopen the integrated Work Order and report missing domains, conflicts, criterion dispositions, evidence and runtime limitations.
10. Run `outcome-quality-assessment` on the integrated result and exact final artifact. Keep dimension scores, criterion statuses and readiness gates separate. A `COMPLETE` Work Order does not automatically mean `READY`; the quality gate can still return `REVIEW` or `HOLD`.

## Optional local utility

When a real executor and package checkout are available:

```bash
python skills/bedrock-engineer-core/scripts/integrate_domain_results.py \
  --package-root . --work-order work-order.json \
  --result domain-results/bp-rp.json \
  --result domain-results/audit.json \
  --output work-order.integrated.json
```

The script is a local JSON utility, not a plugin tool or background service. It reads inputs without modifying them; existing output requires `--overwrite`. Use `--replace-domain <domain_id>` to replace an existing result. Exit `0` means integrated Work Order `COMPLETE`, `1` valid but incomplete/review/blocked, `2` input/contract error. If unavailable, reconcile manually and do not claim the script ran.

## Safety

- Never resolve conflicts by silently choosing one domain's file version.
- Never delete an unreferenced or disputed asset as an integration side effect.
- Never convert missing results, failed checks or runtime `NOT RUN` into `PASS`.
- Preserve target version, baseline, constraints and user-approved preservation list.
- Quality scoring cannot override a failed critical criterion or readiness hard gate.
