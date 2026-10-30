---
name: baseline-regression-workflow
description: Use when comparing a changed Minecraft Bedrock add-on against a known-good version, reviewing file/resource deltas and detecting regressions before release.
---

# Baseline regression workflow

## Inputs
Candidate and known-good baseline archives/projects, SHA-256 hashes, target Bedrock version, expected feature scope and the exact analyzer version/configuration.

## Procedure
1. Hash both artifacts and verify any prior report hashes. Never label provenance verified when hashes differ.
2. Inspect archive safety and both BP/RP manifests.
3. Generate reports for baseline and candidate using the same available analyzer version and settings.
4. Compare file inventories, hashes, identifiers, findings, severity and resource-reference edges using a real local diff script or an explicit deterministic file comparison. Do not assume `diff_packs` exists as a callable tool.
5. Classify each delta as expected, generated noise, unexplained risk, intentional deletion requiring approval, or analyzer/rule-version drift.
6. Investigate new BLOCKER/HIGH findings, unexplained MEDIUM findings, missing resources, broken references and unexpected removals.
7. Verify unrelated files remain unchanged where preservation is expected. Valid JSON alone is not sufficient if the resource graph changed.
8. Apply only reviewed fixes to a staged candidate; preserve source inputs and rerun audit/comparison.
9. Report hashes, added/removed/modified files, finding/reference deltas, evidence and disposition of every material regression.

## Guardrails
A comparison request does not authorize rewriting the baseline. Never automatically delete assets or silence findings without inspecting their source. Newly unresolved edges are risk signals, not proof of gameplay failure. Runtime-sensitive content requires an in-game test.
