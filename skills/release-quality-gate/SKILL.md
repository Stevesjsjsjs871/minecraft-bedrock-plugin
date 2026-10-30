---
name: release-quality-gate
description: Use before presenting or publishing a Minecraft Bedrock Engineer or add-on release; establish reproducible package, regression, compatibility and runtime evidence.
---

# Release quality gate

## Objective
Create a traceable evidence chain from a precisely identified candidate to a release recommendation. A changed version number or a green synthetic test is not sufficient evidence of release readiness.

## Required inputs
Record candidate path/name and SHA-256, optional baseline path/hash, exact target Bedrock version, pack type, current plugin version from `VERSION` and both manifests, relevant tool versions, and runtime status. Do not rely on stale version numbers in historical instructions.

## Gate sequence
1. **Identity and safety:** confirm candidate identity, hash it, inspect archive members and preserve the input. Never execute scripts from the candidate pack.
2. **Package integrity:** verify archive CRCs, canonical paths, duplicate members, expected BP/RP structure and bounded extraction.
3. **Manifest integrity:** parse all manifests; check UUID uniqueness, module UUID uniqueness, BP→RP dependency link, target engine version and supported format versions.
4. **Resource graph:** audit identifiers and references across BP/RP definitions, entity/client-entity, geometry, textures/atlases, render controllers, animations/controllers, recipes, loot/spawn rules, localization and relevant UI includes.
5. **Focused tests:** run tests for the changed domain first (entity bundle, geometry/UV, texture PNG stream, UI references, script API, etc.). Then run the full available regression suite. Record exact commands, exit codes and counts.
6. **Baseline comparison:** review all new HIGH/BLOCKER findings, severity escalations, removed definitions and broken edges. Every intentional removal needs a reason. Do not delete resources merely because they appear unused in a static scan.
7. **Benchmark evidence:** score real-pack precision/recall only with independently reviewed labels and exact artifact hashes. Synthetic fixtures test regression logic, not real-world quality.
8. **Runtime:** import the exact candidate into the target game build and test loading, rendering and relevant gameplay when possible. Record build/platform/scenario. Otherwise `NOT RUN`.
9. **Decision:** `HOLD` for reproducible blockers, broken package/dependencies or failed mandatory tests; `REVIEW` for unresolved medium findings, partial coverage or missing runtime evidence on runtime-sensitive changes; `READY FOR USER TEST` only when required static gates pass and limitations are explicit.

## Skills-only plugin release
For this plugin itself, run `skills/package-integrity/scripts/check_skills_package.py .` and `test_check_skills_package.py -v` from a real extracted package checkout. Also run the specialist script tests and sample-index tests that are actually present. Confirm version parity across `VERSION`, `plugin.json`, `.codex-plugin/plugin.json`, README heading and release notes. Confirm that no skill instructs the model to call unavailable tools. Retained legacy source must be explicitly marked dormant and must not be described as an active integration.

## Capability boundary
Use only tools actually exposed by the current host. Skills are not execution tools. If package files cannot be mounted or a test cannot run, mark it `BLOCKED` or `NOT RUN`; do not substitute old test logs. Minecraft Creator Tools may be used only through a real connected capability or explicitly authorized local CLI, after checking its version/help.

## Report
Include candidate identity/hash, target version, gate-by-gate status, exact test counts, baseline deltas, runtime status, known limitations and recommendation. Separate static checks, Creator Tools results and in-game verification.
