---
name: regression-evals
description: Use when adding or changing Minecraft Bedrock Engineer audit rules, reference-graph behavior, report schemas, or skill routing; run repeatable synthetic fixtures and compare expected findings before release.
---

# Regression Evals

## Goal
Prevent improvements to the static analyzer from silently breaking existing behavior or increasing false positives. Treat the current release as the baseline and require expected outcomes for each fixture.

## Run
From this skill's `scripts` directory, run:

`python regression_tests.py --auditor ../../automated-validation/scripts/bedrock_audit.py`

Python 3 standard library only. Tests create temporary synthetic `.mcaddon`-like ZIP archives; they do not modify user projects, extract untrusted archives, or launch Minecraft. A test is only evidence for the encoded scenario, not a guarantee of engine behavior.

## Required cases
- Valid paired BP/RP manifests and valid JSON.
- A known geometry and animation reference that should resolve.
- A literal missing geometry reference that should remain visible as unresolved.
- Invalid JSON should produce a finding and a non-success result where the analyzer's contract specifies it.
- Unsafe archive paths should be rejected/reported.
- Report must contain tool version, checks, findings, file diff, runtime status and graph coverage metadata.
- Unknown/dynamic expressions must not be treated as confirmed missing literal identifiers.

## Change policy
When changing a rule, add a positive, negative and boundary fixture. Store the expected behavior in `references/test-matrix.md`. Do not weaken a test merely to make a release pass: update its expected result only when the rule's intended semantics and evidence have changed.

## Release gate
Report each test as PASS/FAIL/SKIP with the exact assertion. Do not claim the complete suite passed if the analyzer path was missing or any case was skipped. Do not equate static fixture success with an in-game test. Keep Minecraft runtime status `NOT RUN` unless an actual runtime test was performed.
