---
name: regression-evals
description: Use when adding or changing Minecraft Bedrock Engineer audit rules, reference-graph behavior, report schemas, or skill routing; run repeatable synthetic fixtures and compare expected findings before release.
---

# Regression Evals 0.8.0

## Goal
Prevent changes to the static analyzer from silently breaking existing behavior or increasing false positives. Every rule change must have explicit expected outcomes, a golden graph projection where applicable, and a test-matrix entry as part of the release contract.

## Run
From the package root, run:

```bash
python skills/regression-evals/scripts/regression_tests.py --auditor skills/automated-validation/scripts/bedrock_audit.py
```

The harness creates temporary synthetic `.mcaddon`-like ZIP archives, checks the returned report shape and validates every report against `skills/automated-validation/references/report-schema.json` using JSON Schema Draft 2020-12. It does not extract user projects or launch Minecraft. Install `jsonschema` with `python -m pip install jsonschema` if needed.

## Required cases
- Valid paired BP/RP manifests and valid JSON.
- Geometry and animation references that should resolve.
- A literal missing geometry reference that stays unresolved.
- Malformed JSON reported with a non-success result where specified.
- Unsafe archive member paths reported without extraction.
- Dynamic/Molang-like expressions retained as dynamic rather than treated as confirmed missing literal identifiers.
- Animation bone targets absent from the in-archive geometry inventory are reported as INFO/LOW heuristics only.
- Literal animation-controller initial and transition state names are checked against each controller state map without evaluating Molang conditions.
- UI `ui_defs` imports are represented in the reference graph with heuristic path resolution; repeated imports and recognizable namespace-qualified control references have synthetic checks. Literal UI text localization uses are graph edges, with unresolved lookups remaining low-confidence.
- A conservative allowlist checks documented literal `minecraft:loot.table` component paths (and recognized string values) against in-archive loot-table files; item icon names remain aliases/heuristics and are not misclassified as missing texture files.
- Loot-table JSON gets conservative common-field checks for pools, entries, rolls and weights. Nested `type: loot_table` entries are indexed; resolved in-archive cycles are reported without executing loot data.
- Every emitted report validates against the shared report schema.
- The valid fixture matches `references/golden-graph.json` exactly on stable edge fields, edge count and status counts.
- Domain filters do not allow explicit target-domain metadata to be overridden by matching words in unrelated paths.
- Report includes tool version, checks, findings, file diff, runtime status, and graph coverage metadata.

## Additional benchmark harness tests

```bash
python -m unittest discover -s skills/audit-benchmark/scripts -p 'test_*.py' -v
```

These tests use temporary synthetic reports to validate scoring arithmetic, pending-label handling, SHA-256 enforcement, schema failures and tool-version pinning. They are tests of the evaluator, not evidence of real-pack accuracy.

## Change policy
When changing a rule, add positive, negative, and boundary fixtures. Add the invariant to `references/test-matrix.md`. Never weaken a test simply to make a release pass; alter an expected result only when intended semantics and evidence have changed.

## Release gate
Report each test as PASS/FAIL/SKIP with its assertion. The regression harness must not be reported as passing if the analyzer or schema is missing, `jsonschema` is unavailable, a fixture is skipped, or any emitted report fails validation. Static-fixture success is not an in-game test. Keep runtime status `NOT RUN` unless the game was actually launched and tested.


- The MCP `diff_packs` summary must preserve input archives, cap samples at 100 while retaining full counts, expose findings/severity/reference deltas, and keep runtime status `NOT RUN`.
