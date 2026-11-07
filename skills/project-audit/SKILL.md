---
name: project-audit
description: Use when auditing a Minecraft Bedrock add-on, reviewing a candidate release, diagnosing regressions, validating BP/RP archives, or producing a test report.
---

# Add-on Audit and Regression Guard

## Audit principles
An audit must be evidence-based, repeatable, and honest. Never say an audit passed without executing the checks and inspecting their results. Do not imply that static analysis proves runtime behavior.

## Procedure
1. Identify the baseline and candidate archive. If the baseline is unknown, say so and limit claims accordingly.
2. Test archive integrity and inspect actual root layout; identify BP and RP.
3. Parse JSON files. Syntax-check JavaScript using an appropriate available runtime/tool when possible.
4. Validate manifests: UUID uniqueness within expected scope, module types, version fields, BP/RP dependency linkage, and Script API module versions independently of pack version.
5. Check references across files: texture paths, geometry, animation clips, animation controllers, render controllers, materials, bone names, recipes/results, loot tables, localization keys, and other IDs relevant to the project.
6. Check structural consistency and likely content registration issues, including Creative inventory when the project uses it.
7. Compare candidate and baseline after carefully normalizing only legitimate version-dependent names. Report added, removed, and changed files. Do not normalize away meaningful differences.
8. Treat unexplained deletions or content changes as blockers until understood. Never auto-delete suspect recipes/resources.
9. Report findings with severity, evidence/path, impact, confidence, and suggested fix. Avoid presenting heuristic warnings as proven failures.
10. Rerun relevant tests after fixes and distinguish the original findings from remaining findings.

## Pre-runtime system-conflict pass
For any feature spanning more than one subsystem, do not stop after checking each file independently. Build a producer/consumer ledger and trace the full chain from registration and trigger through data/state changes to the visible/gameplay effect and cleanup. Compare identifiers, namespaces, value shapes, API/module versions, lifecycle assumptions, event registration count, state transitions, and reset/disposal paths across BP, RP, Script API, UI, entities, animations, recipes and loot as applicable. Record exact evidence at both ends of every disputed edge.

Explicitly test the static hypotheses: missing or duplicate producers, orphan consumers, conflicting definitions, incompatible data contracts, invalid literal state transitions, unreachable states, missing failure/cleanup paths, stale references after owner invalidation, and partial updates. Treat dynamic identifiers, computed keys, Molang, external packs and engine-managed registrations as unresolved—not automatically broken. If an AST/type checker or version-specific schema validator is unavailable, say so and do not substitute regex guesses as proof. Recheck changed edges and reverse dependents after fixes.

## Severity guidance
- BLOCKER: archive/manifest/dependency defect likely to prevent loading, or clearly destructive regression.
- HIGH: a strong indication that a requested core feature will fail.
- MEDIUM: likely functional defect or compatibility risk with a bounded workaround.
- LOW: maintainability, localization, performance, or consistency concern with limited immediate impact.
- INFO: observation requiring human/runtime review.

Use severity only where supported by evidence; include confidence when a check is heuristic.

## Runtime validation
If the Minecraft runtime is unavailable, mark in-game checks as NOT RUN. Provide scenario-specific tests with prerequisites, steps, expected outcome, failure indicators, and logs/screenshots to collect. For multiplayer mechanics, include both clients and cancellation/disconnect edge cases. For UI, cover scale/resolution/localization and open/close paths. For animation, cover triggers, interruption, first/third person if relevant, skin/resource-pack interactions, and cleanup.

## Output schema
- Scope and version assumptions.
- Baseline/candidate identity.
- Summary: pass/fail/not run counts.
- Findings grouped by severity with file paths and evidence.
- Files added/removed/changed.
- Checks performed and actual results.
- Runtime tests not performed.
- Release recommendation: ready for next test / hold / not enough evidence.

## Process gates and reviewer pass 2.1.9

Run the audit as a staged workflow, not as an unordered checklist:
1. **Scope gate:** freeze candidate/baseline hashes, target version, pack roots, requested coverage and acceptance criteria.
2. **Integrity gate:** verify archive safety, root layout and manifests before trusting semantic results.
3. **Dependency gate:** inventory registrations and typed references; follow forward and reverse dependencies for every in-scope feature.
4. **Behavior gate:** trace trigger → state/data → effect → cleanup, and inspect alternate branches, failure paths, boundaries and lifecycle.
5. **Independent challenge:** review each material finding and each claimed fix against both producer and consumer, alternate definitions, target-version behavior and regression risk.
6. **Final gate:** rerun affected checks, compare against baseline, inspect the exact final artifact and reconcile all criteria.

Use `workflow-execution-engine` for work-package ownership and stop/replan rules. Run independent read-only checks concurrently only when supported; serialize edits and final integration. A finding is not closed by editing code: it is closed only by evidence from a retest and the affected dependency closure.
