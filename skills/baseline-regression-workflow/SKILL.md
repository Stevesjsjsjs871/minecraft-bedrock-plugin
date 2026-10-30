---
name: baseline-regression-workflow
description: Compare a Minecraft Bedrock project with a preserved baseline using real file, hash and report capabilities.
---

# Baseline and Regression Workflow

## Capability boundary

This Skill defines a comparison procedure; it does not expose a built-in pack-diff tool. Use an actual local executor or connected file capability for inventories and hashes. If neither exists, provide a comparison plan and mark execution NOT RUN.

## Workflow

1. Preserve the original project or archive and record its SHA-256 before edits.
2. Capture a baseline file inventory, sizes and hashes where a real file capability permits.
3. Record BP/RP manifests, UUIDs, identifiers, resource references, scripts and known findings.
4. After changes, capture the same inventory and compare added, removed, modified and renamed paths.
5. Compare identifiers, UUID links, resource-reference edges, validation findings and report severity. Distinguish expected changes from regressions.
6. Investigate every removed or overwritten resource. Do not treat a static graph as complete when dynamic references or unsupported file formats remain.
7. Re-run the focused standalone validators and the broader audit appropriate to the change.
8. Preserve the baseline and final reports together with tool versions, commands and hashes.

## Required report

List baseline and candidate hashes, changed paths, added/removed resources, finding deltas, unresolved edges, tests actually run and runtime status. Do not claim a clean regression result if any scan is partial or BLOCKED.
