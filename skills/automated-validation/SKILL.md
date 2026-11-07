---
name: automated-validation
description: Use to statically audit Minecraft Bedrock BP/RP projects and candidate archives, validate resource references and produce evidence-based reports.
---

# Automated validation workflow

## Capability boundary
Use `skills-first-execution` first. This skill does not expose an MCP wrapper or a hidden project filesystem. The primary bundled auditor is `scripts/bedrock_audit.py`; it can run only when a real code executor can access the script and the supplied project/archive. Otherwise prepare exact commands or a patch and mark execution `NOT RUN`.

## Input safety
- Identify the exact project root or candidate archive, target Bedrock version and BP/RP roots.
- Treat uploaded packs as untrusted data. Never execute scripts from them.
- Preserve source bytes; perform audits read-only and write reports separately.
- Reject path traversal, duplicate archive paths, symlink escapes, unreasonable archive expansion and ambiguous roots. The archive auditor pins one regular-file descriptor for SHA-256, ZIP/CRC inspection and member reads; it does not re-open the candidate path after the safety preflight.

## Audit sequence
1. Inspect ZIP structure/CRC and expected pack layout.
2. Parse `manifest.json` for every BP/RP; check format, UUID uniqueness, engine version and BP dependency → RP header UUID.
3. Parse JSON with duplicate-key detection where supported. Report exact path and JSON pointer/line when available.
4. Check identifiers, namespace consistency, file paths and references across blocks, items, entities, client entities, geometry, textures, atlases, render controllers, animations, animation controllers, recipes, loot tables, spawn rules and localization.
5. For RP UI, inventory all relevant `.json`, `.lang`, texture and include/namespace references. Do not treat dynamic references as confirmed missing without evidence.
6. For geometry/animation, verify geometry identifiers, bones, cube/UV bounds, texture dimensions, animation aliases, controller state references, transitions and client-entity bindings.
7. Classify findings by severity and confidence. Distinguish confirmed parse/reference errors from heuristics and unsupported resource shapes.
8. If a baseline is supplied, compare definitions and resource graph edges; explain removals and new regressions.
9. Validate the report against `references/report-schema.json` only when the schema validator is actually installed. Do not install dependencies silently.

## Pre-runtime cross-system contract pass
Run this pass whenever a requested feature crosses packs, resource types, scripts, UI, entities, animations, recipes, loot or lifecycle boundaries. For a broad audit, apply it to every detected feature chain; for a focused task, trace the changed feature and its reverse dependents. The existing reference graph is partial and must not be treated as a complete behavior model.

1. Build a **producer/consumer contract ledger** from actual source evidence. For each contract record: stable name/identifier, producer path and pointer, consumer path and pointer, value shape/type, namespace, lifecycle/availability condition, target version, and whether the value is literal, computed or external. Include identifiers, event names, component groups, properties, tags, scoreboard/storage keys, dynamic-property keys, script module/API dependencies, UI bindings/localization, recipes/results, loot references, entity/client-entity bindings, geometry/texture/animation aliases, controller states and manifest dependencies where present.
2. Trace each feature as an end-to-end chain: registration/definition → activation/trigger → state/data production → transformation → consumer/effect → cleanup/reset. Record every edge and exact evidence on both ends.
3. Check cross-system contracts: producer without consumer; consumer without an in-scope producer; spelling/case/namespace mismatch; incompatible value type/shape or enum; duplicate/conflicting registration; wrong pack/module dependency; target-version/API mismatch; impossible lifecycle ordering; stale state after despawn/reload/dimension change; missing cleanup; event handler registered more than once; and feature paths that terminate before the requested visible/gameplay effect.
4. Check state machines and event flows. Enumerate states, entry/exit actions, transitions, guards, reset paths and terminal states. Flag unreachable states, missing literal transition targets, contradictory guards only when statically provable, missing fallback/error states, duplicate transitions with conflicting effects, and state that can persist after its owner is gone. Treat Molang, dynamic expressions and tick scheduling as unresolved unless actually interpreted by a compatible validator.
5. Review script logic against the contract: input validation, null/undefined handling, boundary values, numeric units/ranges, asynchronous rejection, event duplication/re-entrancy, stale entity/block references, partial mutations, cancellation, cleanup and ordering. Use an available parser/type checker/linter only after verifying its presence and exact project configuration. Never execute add-on scripts as part of static analysis.
6. Reconcile specialist results against one shared graph and baseline. Two individually valid files can still disagree; record both endpoints of a conflict and the affected feature. Re-run affected contract edges after a fix, then run the broader dependency closure and baseline comparison.

### Contract finding confidence
- `HIGH`: both endpoints and the incompatibility are explicit in source, or a deterministic parser/check proves the violation.
- `MEDIUM`: one endpoint is explicit and the other is strongly inferred from a bounded, documented convention.
- `LOW`: dynamic names, expression evaluation, external packs, implicit loading order or incomplete indexing could explain the apparent mismatch.
- A missing producer in the candidate archive is not a confirmed defect if another installed pack, runtime registration, generated content or dynamic key can supply it. Mark the edge external/dynamic and request evidence.
- Never upgrade a finding solely because multiple heuristic scanners reported the same underlying guess. Deduplicate by contract edge and preserve the strongest source evidence.

## Script use
From the actual package root, inspect `python skills/automated-validation/scripts/bedrock_audit.py --help` before choosing arguments. Use bounded inputs and capture exact command, exit code and report path. `validate_report.py` can validate generated reports when its documented requirements are available. Do not invent arguments or claim a script ran if the package is not mounted.

## Result vocabulary
`PASS` means the check executed and passed; `FAIL` means it executed and found a failure; `PARTIAL` means bounded scan or unsupported shapes limited coverage; `BLOCKED` means required input/tool/dependency unavailable; `NOT RUN` means not executed. Always report coverage, skipped files, unsupported resource forms and runtime status. Static audit never proves Minecraft import, rendering or gameplay.
