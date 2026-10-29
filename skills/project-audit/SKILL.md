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
