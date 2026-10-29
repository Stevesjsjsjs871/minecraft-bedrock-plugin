---
name: release-quality-gate
description: Use before presenting or publishing a Minecraft Bedrock add-on or plugin release, especially when comparing before/after packs, running regression tests, measuring real-pack audit quality, or coordinating Creator Tools with this plugin.
---

# Release Quality Gate

## Objective

Build a reproducible evidence chain from candidate artifact to release recommendation. This workflow is a release gate, not a promise that the artifact is correct. Static audit, automated tests, Creator Tools validation and Minecraft runtime testing are separate evidence categories.

## Required inputs

Identify and record:
- Exact candidate archive and SHA-256.
- Optional known-good baseline archive and SHA-256.
- Target Minecraft Bedrock version and pack type (BP, RP, `.mcpack`, `.mcaddon`, `.mcworld`, or source directory staged by an approved tool).
- Plugin/analyzer version read from the package's `VERSION` file; never copy an old hard-coded version number from a historical command.
- Creator Tools version and command/result if Creator Tools is used.
- Runtime status: `NOT RUN`, `PARTIAL`, or `TESTED`, with tested platform, world settings and exact scenario when applicable.

## Gate sequence

1. **Input identity and safety.** Confirm each archive is the file that the user intended. Hash it before testing. Do not run scripts extracted from a submitted pack. Preserve original inputs byte-for-byte.
2. **Package and manifest checks.** Check ZIP/CRC integrity, canonical paths, duplicate members, manifests, UUID uniqueness, BP→RP dependency links, target engine version, JSON parseability and resource file structure. Separate hard errors from heuristics.
3. **Feature-focused checks.** Test the resources changed by the current task: item/block/recipe references, entity/client-entity links, geometry/texture/material references, animation/controller states, localization, UI and loot-table references when relevant.
4. **Baseline comparison.** Run `diff_packs` or the available baseline comparison. Investigate every new HIGH/BLOCKER finding, severity escalation, removed definition, and formerly resolved reference that becomes unresolved. Baseline removal is not automatically a defect, but it requires an explanation.
5. **Regression tests.** Run the complete MCP unit suite, benchmark evaluator suite, analyzer regression fixtures and report-schema checks using the commands recorded in the current project README/CI workflow. Preserve exact pass/fail/skip counts. A missing analyzer, skipped required fixture, stub, or failed dependency install is not a pass.
6. **Creator Tools validation.** When the actual tool/CLI is available, validate the candidate with the installed version. Record the exact command and result; do not say it ran if only instructions were produced. If it modifies files, audit the resulting files again and compare against the pre-validation snapshot.
7. **Real-pack benchmark.** Only score cases with independently reviewed labels and exact matching SHA-256 values. Validate both the manifest and reports against the shipped schema. Invalid/missing cases invalidate the run rather than silently dropping from the denominator. Report precision, recall, F1, per-rule counts, severity mismatches and case count separately. Synthetic fixtures are regression protection, not real-pack evidence.
8. **Runtime check.** When feasible, import the exact candidate into the target game build and test loading, resource rendering, intended gameplay and relevant multiplayer interactions. Capture the exact game build and scenario. If not performed, say `NOT RUN`.
9. **Decision.**
   - `HOLD`: any reproducible blocker/high defect, broken package/dependency, unsafe path, missing critical resource or failed mandatory test.
   - `REVIEW`: unresolved medium findings, uncertain references, partial coverage, mismatched benchmark provenance or runtime not tested for a runtime-sensitive change.
   - `READY FOR USER TEST`: required static tests pass, no unexplained severe regressions remain, and remaining runtime limitations are explicit.
   - Avoid calling something “release-ready” when required gates were skipped.

## Interpreting the tool boundary

The static analyzer uses conservative checks and heuristic resolution for some resource graph, UI, localization, and dynamic references. An unresolved edge is not automatically a confirmed engine defect. Conversely, a clean static report is not proof that the game can load or render the resource.

If Minecraft Creator Tools generated or changed the candidate, use this plugin's audit and diff afterward. This gives the workflows different responsibilities: Creator Tools can author/validate content; this plugin provides provenance, impact analysis, regression signals and explicit limitations. Do not make claims that MCT lacks a particular capability unless verified for the installed version.

## Report template

Include:
- Candidate name, SHA-256, target game version and tool versions.
- Gate-by-gate status with exact test counts and evidence locations.
- Baseline deltas and disposition of each severe/new finding.
- Real-pack benchmark results only when a valid reviewed corpus was actually scored.
- Creator Tools result and any files it changed.
- Runtime status and exact untested behaviors.
- Final recommendation (`HOLD`, `REVIEW`, or `READY FOR USER TEST`) and the remaining blocking action.
