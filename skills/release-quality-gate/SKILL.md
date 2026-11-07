---
name: release-quality-gate
description: Use to evaluate evidence and decide whether a Minecraft Bedrock add-on or Skills-only plugin candidate is ready for release.
---

# Release quality gate

## Objective
Create a traceable evidence chain from a precisely identified candidate to a release recommendation. A changed version number or a green synthetic test is not sufficient evidence of release readiness.

## Required inputs
Record candidate path/name and SHA-256, optional baseline path/hash, exact target Bedrock version, pack type, add-on release version, relevant tool versions, and runtime status. Do not rely on stale version numbers in historical instructions.

## Add-on gate sequence
1. **Identity and safety:** confirm candidate identity, hash it, inspect archive members and preserve the input. Never execute scripts from the candidate pack.
2. **Package integrity:** verify archive CRCs, canonical paths, duplicate members, expected BP/RP structure and bounded extraction.
3. **Manifest integrity:** parse all manifests; check UUID uniqueness, module UUID uniqueness, BP→RP dependency link, target engine version, pack/module version parity and supported format versions.
4. **Resource graph:** audit identifiers and references across BP/RP definitions, entity/client-entity, geometry, textures/atlases, render controllers, animations/controllers, recipes, loot/spawn rules, localization and relevant UI includes.
5. **Focused tests:** run tests for the changed domain first (entity bundle, geometry/UV, texture PNG stream, UI references, Script API, etc.). Then run the full available regression suite. Record exact commands, exit codes and counts.
6. **Baseline comparison:** when known-good baseline and candidate archives are available, run `skills/addon-baseline-diff/scripts/addon_baseline_diff.py <baseline> <candidate> --release-candidate --report <diff.json>`. Review additions, removals and modifications, header/module UUIDs, internal dependency versions, `format_version`, `min_engine_version`, Script API dependency drift and visible/localized title parity. Every unexplained removal requires review; the comparator never deletes resources. For an intermediate workbench snapshot, omit `--release-candidate`.
7. **Resource graph regression:** compare newly unresolved/ambiguous edges and removed definitions against the baseline. A path-looking string or unreferenced file alone is not proof of a defect or permission to delete.
8. **Benchmark evidence:** score real-pack precision/recall only with independently reviewed labels and exact artifact hashes. Synthetic fixtures test regression logic, not real-world quality.
9. **Runtime:** import the exact candidate into the target game build and test loading, rendering and relevant gameplay when possible. Record build/platform/scenario. Otherwise `NOT RUN`.
10. **Decision:** `HOLD` for reproducible blockers, broken package/dependencies or failed mandatory tests; `REVIEW` for unexplained removals, unresolved medium findings, partial coverage or missing runtime evidence on runtime-sensitive changes; `READY FOR USER TEST` only when required static gates pass and limitations are explicit.

## Skills-only plugin release
For this plugin itself, run the following from a full extracted package checkout:

```bash
python skills/bedrock-engineer-core/scripts/validate_domain_architecture.py .
python -m unittest discover -s skills/bedrock-engineer-core/scripts -p 'test_*.py' -v
python skills/bedrock-engineer-core/scripts/plan_domain_work.py --list-profiles
python skills/package-integrity/scripts/check_skills_package.py .
python skills/package-integrity/scripts/test_check_skills_package.py -v
```

Smoke-test all declared workflow profiles through `plan_domain_work.py`, and validate the resulting Work Orders against the shared schema. Confirm the planner only expands explicitly selected profiles and does not infer task intent, inspect projects, verify tools, invoke Skills or execute project code. Also run specialist script tests and sample-index tests that are actually present. Confirm version parity across `VERSION`, `plugin.json`, `.codex-plugin/plugin.json`, README heading and release notes. Confirm the domain registry covers every discovered `skills/*/SKILL.md` exactly once, all domain dependencies resolve without cycles, workflow profiles use known domain IDs, and both hand-off schemas are valid with no duplicate enum values. Confirm no Skill instructs the model to call unavailable tools. Retained legacy source must be marked dormant and not described as an active integration.

## Capability boundary
Use only tools actually exposed by the current host. For plugin updates, verify current release/source, build the overlay against that exact release, preserve omitted files, upload with a guarded release ID and read back the changed source. Skills are not execution tools. If package files cannot be mounted or a test cannot run, mark it `BLOCKED` or `NOT RUN`; do not substitute old test logs. Minecraft Creator Tools may be used only through a real connected capability or explicitly authorized local CLI, after checking its version/help.

## Report
Include candidate identity/hash, target version, architecture/domain validation, gate-by-gate status, exact test counts, baseline deltas, runtime status, known limitations and recommendation. Separate static checks, Creator Tools results and in-game verification.

## Consolidated release-quality-gate decision matrix

This Skill absorbs the concise `release-quality-gate` summary while retaining the full quality gate. Decision states remain `HOLD`, `REVIEW`, `READY FOR USER TEST` and `RELEASE READY`. Evaluate identity, archive integrity, manifests/dependencies, resource graph, focused/full tests, baseline delta, benchmarks where applicable, runtime/gameplay and Plugin Host evidence required by the declared release scope. A missing runtime or host check is `NOT RUN`/`BLOCKED`, not PASS; do not label the candidate `RELEASE READY` while required evidence is absent. This gate decides readiness; it does not build the artifact.
