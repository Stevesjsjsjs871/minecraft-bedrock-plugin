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
- Reject path traversal, duplicate archive paths, symlink escapes, unreasonable archive expansion and ambiguous roots.

## Audit sequence
1. Inspect ZIP structure/CRC and expected pack layout.
2. Parse `manifest.json` for every BP/RP; check format, UUID uniqueness, module UUID uniqueness, engine version and BP dependency → RP header UUID.
3. Parse JSON with duplicate-key detection where supported. Report exact path and JSON pointer/line when available.
4. Check identifiers, namespace consistency, file paths and references across blocks, items, entities, client entities, geometry, textures, atlases, render controllers, animations, animation controllers, recipes, loot tables, spawn rules and localization.
5. For RP UI, inventory all relevant `.json`, `.lang`, texture and include/namespace references. Do not treat dynamic references as confirmed missing without evidence.
6. For geometry/animation, verify geometry identifiers, bones, cube/UV bounds, texture dimensions, animation aliases, controller state references, transitions and client-entity bindings.
7. Classify findings by severity and confidence. Distinguish confirmed parse/reference errors from heuristics and unsupported resource shapes.
8. If a baseline is supplied, compare definitions and resource graph edges; explain removals and new regressions.
9. Validate the report against `references/report-schema.json` only when the schema validator is actually installed. Do not install dependencies silently.

## Script use
From the actual package root, inspect `python skills/automated-validation/scripts/bedrock_audit.py --help` before choosing arguments. Use bounded inputs and capture exact command, exit code and report path. `validate_report.py` can validate generated reports when its documented requirements are available. Do not invent arguments or claim a script ran if the package is not mounted.

## Result vocabulary
`PASS` means the check executed and passed; `FAIL` means it executed and found a failure; `PARTIAL` means bounded scan or unsupported shapes limited coverage; `BLOCKED` means required input/tool/dependency unavailable; `NOT RUN` means not executed. Always report coverage, skipped files, unsupported resource forms and runtime status. Static audit never proves Minecraft import, rendering or gameplay.
