---
name: audit-benchmark
description: Use when measuring Minecraft Bedrock Engineer audit quality against independently reviewed real add-on packs, validating benchmark metadata, or calculating evidence-backed precision and recall.
---

# Real-pack audit benchmark

## Purpose
Measure whether the static auditor finds the reviewed issues it claims to check, and how often it emits findings that reviewers do not confirm. Do not substitute synthetic regression fixtures for a real-pack benchmark.

## Dataset rules
- Keep original `.mcaddon`, `.mcpack`, `.mcworld`, and `.zip` files outside the plugin repository by default. Do not redistribute packs unless their license or explicit permission allows it.
- Record the SHA-256 of the exact artifact tested, source/provenance URL when available, retrieval date, license/permission state, target Bedrock version, pack type, and independent label-review notes.
- Only cases marked `label_status: reviewed` are scored. A reviewer must exhaustively label the finding titles listed in `scored_rules` for that case; unreviewed rules are out of scope, not assumed correct or wrong.
- Expected findings are matched by exact `(title, path)` signatures. Rule-title changes require a deliberate benchmark migration; do not quietly re-label old results.
- Every scored case's local artifact must hash to the manifest SHA-256. Every report must pass the shipped report JSON Schema and its candidate SHA-256 must match that same manifest hash. An invalid or mismatched report invalidates the run; do not omit failures and average the remaining cases.
- Report aggregate and per-rule precision, recall, F1, number of scored cases, and severity mismatches separately. Do not call these metrics overall “accuracy”: the benchmark does not count true negatives and measures only explicitly reviewed rule classes.
- Separate static structural facts from runtime claims. Record game/runtime verification as `NOT_RUN`, `PARTIAL`, or `TESTED`; never infer runtime correctness from a static audit.

## Workflow
1. Build a local benchmark manifest using `references/benchmark-manifest.example.json` as a schema-compatible starting point. Populate real cases only after the artifact and source are actually inspected.
2. Label expected findings independently, ideally with two reviewers for high-impact rules. Include a short evidence note for every expected finding and document disagreements.
3. Put the exact local artifacts in a private `artifacts/` directory using each case's `artifact_filename`. Run the current auditor for each exact artifact and save the JSON report as `<case_id>.json` in a separate local reports directory.
4. Install the pinned Draft 2020-12 validator with `python -m pip install -r skills/audit-benchmark/requirements.txt`, then run `python skills/audit-benchmark/scripts/evaluate_benchmark.py --dataset path/to/benchmark.json --artifacts-dir path/to/artifacts --reports-dir path/to/reports --expected-tool-version 0.7.8` from the package root. If the dependency cannot be installed, report the benchmark as NOT RUN; do not treat missing schema validation as a pass. Remove the expected-version option only when intentionally evaluating multiple tool versions together.
5. Preserve the evaluator output, dataset manifest, tool version, report hashes and reviewer notes together. Before comparing releases, rerun the same artifact corpus and avoid changing labels mid-comparison.

## Interpretation
- Real-pack benchmark results are not available merely because the harness exists. Do not publish percentages until a real, labeled corpus has been run.
- A benchmark miss can be caused by analyzer behavior, rule-title drift, path normalization, or an incomplete label. Inspect each mismatch before assigning blame.
- A pack downloaded from the internet is not automatically redistributable. The benchmark may retain local-only hashes and labels without packaging the original file.
- Synthetic tests still protect known regressions; benchmark results complement them and do not replace runtime testing.
