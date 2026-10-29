---
name: baseline-regression-workflow
description: Use when comparing a changed Minecraft Bedrock add-on against a known-good previous version, especially after Creator Tools generation, multi-file content changes or before preparing a release.
---

# Baseline Regression Workflow

## Purpose
Answer what actually changed and whether the change introduced detectable regressions. This is not a runtime guarantee and does not automatically make changes safe.

## Inputs
- Candidate archive or project staged with an approved tool.
- Known-good baseline archive/report whenever available.
- Expected feature and the files it is allowed to change.
- Target Bedrock version.
- Exact audit/analyzer version from package `VERSION`.

## Procedure
1. Hash both candidate and baseline. Refuse to label provenance verified if a report hash does not match its corresponding artifact.
2. Run archive safety checks and inspect candidate/baseline manifests.
3. Generate current analyzer reports for both artifacts using the same analyzer version and configuration.
4. Run the available `diff_packs` or baseline comparison. Summarize added, removed and changed files, new/no-longer-reported findings, severity changes and reference-graph edges that became unresolved.
5. Classify each change:
   - expected and explained by the requested feature;
   - expected generated noise (justify);
   - unexplained potentially dangerous change;
   - intentional deletion requiring user approval;
   - static-analysis difference caused by rule/version drift.
6. Investigate all new BLOCKER/HIGH findings, unexplained MEDIUM findings, missing resources and previously resolved references becoming unresolved. Check removals and manifest/UUID changes separately.
7. Verify unrelated files are unchanged where strict preservation is expected. If the generator reformats a broad tree, don't treat "valid JSON" alone as sufficient.
8. Apply only requested, reviewed fixes. Preserve source inputs; write to a staged candidate and rerun audit/diff afterward.
9. Produce a compact evidence report with exact file counts/hashes and the disposition of every material regression.
10. Decide `HOLD`, `REVIEW`, or `READY FOR USER TEST` based on recorded evidence. Runtime-sensitive content cannot be marked release-ready solely on static checks.

## Output
- Baseline and candidate SHA-256.
- Files added/removed/modified and expected-change allowlist.
- Finding/severity/reference-edge deltas.
- Exact checks and pass/fail/skip counts.
- Unresolved issues and runtime status.
- Recommendation and next action.

## Guardrails
A user request to compare versions does not imply permission to rewrite the baseline. Never automatically delete assets or "fix" a finding without inspecting its source. Newly unresolved resource edges are risk signals, not automatic proof of gameplay failure.
