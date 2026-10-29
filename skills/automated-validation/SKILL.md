---
name: automated-validation
description: Use when a Minecraft Bedrock project needs repeatable archive, manifest, geometry, bone, UV, texture-reference, animation, controller, resource-graph, or baseline checks after creation or modification.
---

# Automated Validation

Run `python skills/automated-validation/scripts/bedrock_audit.py candidate.mcaddon --report audit-report.json` or add `--baseline previous.mcaddon`. The analyzer is read-only, uses Python's standard library, and shares bounded ZIP limits with the local MCP wrapper through package-root `archive_safety.py`.

## Checks
- ZIP CRC integrity, unsafe/duplicate paths, JSON syntax, manifests, UUIDs and in-archive dependency context.
- Conservative geometry identifiers, bone hierarchy/transforms, cube/vector and UV structures.
- Selected animation definitions and literal cross-resource references.
- A resource-reference graph with source paths/pointers, target domains and resolution statuses, including common entity/attachable geometry, animation/controller, texture, UI and localization references.
- Baseline file-hash diffs, definition counts, explicit coverage metadata and runtime status.
- Partial UI/localization checks, selected loot-table structure and recursive in-archive loot-table reference checks. Heuristic/dynamic references remain lower-confidence review items.
- Bounded input limits are applied before reading ZIP payloads; these are resource-safety limits, not Minecraft format limits.

## Report schema and interpretation

Validate reports with `python skills/automated-validation/scripts/validate_report.py report.json` where the JSON Schema dependency is available. A schema-valid report is structurally consistent, not proof that content works in-game. Static findings are hypotheses with evidence, not guarantees of engine behavior. Include archive SHA-256, source paths and JSON Pointers where available, severity, confidence, coverage and limitations.

## New-project workflow

`create_addon_project` creates only a new linked Behavior Pack/Resource Pack scaffold and its state/readme files. After content has actually been authored, use this analyzer for static validation. It does not audit a project directory directly; package or stage an archive using an available approved tool before calling archive audit tools. Don't treat an empty scaffold as a finished add-on and don't claim gameplay checks that were not run.

## Regression gate

Use `skills/regression-evals/scripts/regression_tests.py --auditor skills/automated-validation/scripts/bedrock_audit.py` when the real analyzer and its dependencies are present. Report exact pass/fail/skip results. Do not claim a suite passed if the analyzer is a stub, missing, or any required case was skipped.

## Safety

The analyzer does not execute pack scripts, alter project files, launch Minecraft or deploy to a live world. Never automatically delete or rewrite resources. Review baseline removals. Mark Minecraft import, visual output and gameplay/multiplayer tests `NOT RUN` unless actually performed.
