---
name: automated-validation
description: Use when a Minecraft Bedrock pack needs repeatable archive, manifest, geometry, bone, UV, texture-reference, animation, controller, resource graph, or baseline checks.
---

# Automated Validation 0.8.0

Run `python bedrock_audit.py candidate.mcaddon --report audit-report.json` or add `--baseline previous.mcaddon`. The analyzer is read-only and uses Python's standard library; it reads the analyzer version from package-root `VERSION` and imports the shared package-root `archive_safety.py` so CLI and MCP paths apply the same ZIP limits.

## Checks
- ZIP CRC integrity, unsafe/duplicate paths, JSON syntax, manifests, UUIDs and in-archive dependency context.
- Conservative geometry identifiers, bone hierarchy/transforms, cube/vector and UV structures.
- Selected animation definitions and literal cross-resource references.
- `reference_graph` with definitions, reference edges, status counts, source file and JSON pointer; common client-entity/attachable geometry, animation/controller references, texture path candidates, selected render-controller aliases, UI path candidates and heuristic localization keys.
- Baseline file-hash diffs, per-domain definition counts, explicit coverage metadata and runtime status.
- Literal animation-controller initial/transition state references; animation bone names compared to the global in-archive geometry inventory as INFO/LOW heuristic only.
- Partial UI/localization checks: common UI JSON shape and `ui_defs` entries/path candidates; repeated `ui_defs` entries; recognizable literal UI control/namespace references; duplicate keys within one `.lang` file; empty keys; literal `$key` lookups in UI `text` values; literal `minecraft:loot.table` component paths (plus recognized literal string values); common loot-table pool/entry/roll/weight shape checks; nested `type: loot_table` reference edges and resolved in-archive cycle detection. Item icon names remain alias heuristics rather than file paths. The graph includes heuristic `ui_defs` import edges and literal UI-to-localization-key edges. Missing/ambiguous UI paths, control names and localization lookups remain INFO/LOW heuristics.
- Bounded input limits applied before payload reads: 256 MiB compressed archive, 50,000 archive entries, 128 MiB per file, and 512 MiB cumulative declared uncompressed content.

## Report schema

Validate a saved report with `python validate_report.py audit-report.json`. This uses `references/report-schema.json` (JSON Schema Draft 2020-12) and requires `jsonschema`; install it with `python -m pip install jsonschema`. The regression harness validates every generated report against this same schema. Findings at MEDIUM severity lead to the `REVIEW` recommendation; BLOCKER/HIGH lead to `HOLD`.

## Evidence and benchmark discipline
- Static findings are hypotheses with evidence, not guarantees of game behavior. Include the exact archive SHA-256, source path, JSON Pointer where available, severity, confidence and limitations in the report or review notes.
- For measured quality claims, use the `audit-benchmark` skill and only reviewed real-pack cases. Do not report synthetic fixtures as real-world accuracy or omit failed/mismatched benchmark cases.
- This bundled MCP still has read-only archive tools. For creation or edits, use the `creator-tools-bridge` workflow only when the host exposes an approved local execution environment and an installed MCT CLI; do not claim this MCP itself writes files.

## Interpretation and safety
- The helper is a static analyzer, not the Minecraft engine's complete validator. An unresolved reference may be external, dynamic, aliased or unsupported by the current indexer. UI support does not validate all control bindings, UI rendering, localization fallback, or every version-specific schema.
- Use exact paths/pointers and explain the check scope. Never turn a heuristic into a high-severity confirmed defect without evidence.
- The script does not extract archives, execute pack scripts, alter project files, or launch Minecraft.
- Never automatically delete or rewrite resources. Review all baseline removals.
- Mark Minecraft import, visual output and multiplayer tests `NOT RUN` unless actually performed.

## Regression gate

Run `python ../regression-evals/scripts/regression_tests.py --auditor bedrock_audit.py` (adjust the path for the working directory). Before release, run all synthetic scenarios and report exact pass/fail/skip results. Do not claim the test suite passed if the analyzer was not found or a case was skipped.

## Output

Return archive identity and hashes, check statuses, findings with evidence, baseline delta, reference graph counts/edges, per-domain definition counts, explicit coverage metadata and runtime status. A parseable JSON file is not proof that a resource works in-game.
