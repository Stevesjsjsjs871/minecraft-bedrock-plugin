---
name: automated-validation
description: Use when a Minecraft Bedrock pack needs repeatable archive, manifest, geometry, bone, UV, texture-reference, animation, controller, resource graph, or baseline checks.
---

# Automated Validation 0.6.4

Run `python bedrock_audit.py candidate.mcaddon --report audit-report.json` or add `--baseline previous.mcaddon`. The helper is read-only and uses Python's standard library.

## Checks
- ZIP CRC integrity, unsafe/duplicate paths, JSON syntax, manifests, UUIDs and in-archive dependency context.
- Conservative geometry identifiers, bone hierarchy/transforms, cube/vector and UV structures.
- Selected animation definitions and literal cross-resource references.
- `reference_graph` with definitions, reference edges, status counts, source file and JSON pointer; common client-entity/attachable geometry, animation/controller references, texture path candidates, selected render-controller aliases, UI path candidates and heuristic localization keys.
- Baseline file-hash diffs, per-domain definition counts, explicit coverage metadata and runtime status.

## Interpretation and safety
- The helper is a static analyzer, not the Minecraft engine's complete validator. An unresolved reference may be external, dynamic, aliased or unsupported by the current indexer.
- Use exact paths/pointers and explain the check scope. Never turn a heuristic into a high-severity confirmed defect without evidence.
- The script does not extract archives, execute pack scripts, alter project files, or launch Minecraft.
- Never automatically delete or rewrite resources. Review all baseline removals.
- Mark Minecraft import, visual output and multiplayer tests `NOT RUN` unless actually performed.

## Regression gate
Run `python ../regression-evals/scripts/regression_tests.py --auditor bedrock_audit.py` (adjust the path for the working directory). Before release, run the regression-evals skill's five synthetic scenarios and report exact pass/fail/skip results. Do not claim the test suite passed if the analyzer was not found or a case was skipped.

## Output
Return archive identity and hashes, check statuses, findings with evidence, baseline delta, reference graph counts/edges, per-domain definition counts, explicit coverage metadata and runtime status. A parseable JSON file is not proof that a resource works in-game.
