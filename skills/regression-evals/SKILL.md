---
name: regression-evals
description: Use when changing analyzer rules, reference-graph behavior, report schemas or validation workflows; run synthetic regression fixtures and preserve expected findings.
---

# Regression evaluations

## Goal
Prevent static analyzer changes from silently breaking behavior or increasing false positives. Each rule change needs positive, negative and boundary fixtures, expected report fields and a test-matrix update.

## Run
From the package root:
```bash
python skills/regression-evals/scripts/regression_tests.py --auditor skills/automated-validation/scripts/bedrock_audit.py
python -m unittest discover -s skills/audit-benchmark/scripts -p 'test_*.py' -v
```
Inspect `--help` and dependency requirements before execution. The harness uses synthetic temporary archives; it does not inspect user packs or launch Minecraft. If `jsonschema` is unavailable, report schema validation `BLOCKED`; do not silently install dependencies.

## Required cases
- Valid paired BP/RP manifests and valid JSON.
- Geometry and animation references that resolve, plus literal missing references.
- Malformed JSON and unsafe archive paths.
- Dynamic/Molang expressions retained as dynamic rather than falsely reported as missing literal identifiers.
- Animation/controller state and bone-name checks with documented heuristic confidence.
- UI imports, namespace-qualified controls and localization edges with conservative path resolution.
- Conservative loot-table path/shape checks without executing loot data.
- Every emitted report validates against the shared report schema.
- Stable graph fields match the golden projection; domain filters respect explicit metadata.
- Reports include analyzer version, checks, findings, file deltas, runtime status and graph coverage metadata.

## Change policy
Add positive, negative and boundary fixtures for every rule change. Update `references/test-matrix.md`. Never weaken a test only to make a release pass; change expected semantics only with evidence.

## Release gate
Report PASS/FAIL/SKIP with assertion and exact command. Missing analyzer/schema, unavailable dependencies or skipped required fixtures prevent a pass. Synthetic success is not real-pack accuracy. Keep runtime `NOT RUN` unless the game was actually tested.
