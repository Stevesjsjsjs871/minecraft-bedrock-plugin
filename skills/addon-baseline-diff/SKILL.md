---
name: addon-baseline-diff
description: Use to compare a candidate Minecraft Bedrock add-on archive with its exact known-good baseline and produce regression evidence.
---

# Add-on Baseline Diff

## Purpose

Compare the candidate `.mcaddon` / `.mcpack` against the exact known-good baseline. This is the regression-preservation layer between implementation and delivery. It complements the structural audit: the audit checks a single build, while this tool identifies what changed between builds.

## Required input

- Baseline archive and SHA-256 from the last accepted candidate.
- New candidate archive and SHA-256.
- Exact target Minecraft version.
- Expected change scope or workbench milestone description.
- Use `--release-candidate` only when the candidate is intended to replace the previous pack in the user's Minecraft installation. Do not require a pack version bump for an intermediate workbench snapshot.
- Record the exact intended milestone delta (for example `WB-06 → WB-07`) before interpreting the report. A tool cannot decide whether a code change was intentional.

## Run

From the plugin root:

```bash
python skills/addon-baseline-diff/scripts/addon_baseline_diff.py <baseline.mcaddon> <candidate.mcaddon> --report <new-report.json>
```

For a candidate being delivered as a new installable release:

```bash
python skills/addon-baseline-diff/scripts/addon_baseline_diff.py <baseline.mcaddon> <candidate.mcaddon> --release-candidate --report <release-diff.json>
```

The command is read-only. It streams each ZIP member into bounded temporary parsing/checks, records SHA-256 by normalized pack-relative path, reports added/removed/modified files, parses manifests, compares pack identity, module UUID/version layout, `format_version`, `min_engine_version` and Script API dependencies, validates internal pack-dependency versions, checks visible/localized pack-title version parity for release candidates, strictly parses JSON where possible and checks JavaScript syntax with `node --check` when Node.js is available. It does not write into the source project or execute add-on code. Manifest and JSON parsing have explicit size limits; oversized JSON is reported as `REVIEW/NOT CHECKED`, not silently passed.

## Interpretation

- `PASS`: no blocking static findings and no unresolved deletions requiring review.
- `REVIEW`: files were removed, JSON was not strict JSON (possibly JSONC/comments), API/min-engine/manifest-format values changed, module UUID/layout changed, or the pack layout could not be normalized with certainty. Review each delta; removals are never assumed intentional.
- `FAIL`: unsafe archive paths, duplicate entries, corrupt data, invalid manifests, changed pack header identity, mismatched internal pack dependencies, module/header version mismatch, duplicate JSON keys, or JavaScript syntax errors.
- Pack-root folder renames are normalized to BP/RP roles when each role resolves unambiguously, preventing a harmless top-level folder rename from appearing as a full removal/addition.
- Built-in Script API dependency versions are tracked separately from add-on pack versions. They must not be bumped merely because the add-on version changed.
- Repeated module types are compared by their manifest position, not collapsed into one dictionary key. Any module-layout change remains visible for review.
- Strict JSON parse failures are review candidates rather than automatic engine incompatibility claims; Bedrock content may contain JSONC-like forms. Duplicate keys and non-finite constants are treated as definite failures.
- The tool reports static evidence only. Minecraft import, Content Log, gameplay, multiplayer and performance profiling remain `NOT RUN` until tested.

## Focused tests

From the plugin root:

```bash
python -m unittest discover -s skills/addon-baseline-diff/scripts -p 'test_*.py' -v
```

The suite covers path and symlink rejection, duplicate ZIP/JSON members, root-folder renames, BP/RP links, header/module version parity, repeated module types, UUID preservation, localized title keys (including keys without dots), stale translations, API dependency drift and JavaScript syntax failures.

## Release decision

Do not publish a changed add-on while unexplained resource removals or identity/dependency failures remain. Review every changed file against the intended workbench milestone. Never delete assets just because a scan considers them unreferenced. Attach both archive hashes and the diff report to the release evidence. A clean static delta is not a Minecraft runtime pass.

## Consolidated baseline regression workflow

This Skill also owns the procedural workflow formerly exposed as `addon-baseline-diff`. Use the existing comparator as the implementation; do not create a second diff algorithm. Require the exact known-good baseline archive and SHA-256, candidate archive and SHA-256, target Minecraft version, and written expected milestone delta before interpreting changes. Run the read-only comparator, classify additions/removals/modifications, inspect every removal and unresolved delta, and attach both hashes plus the machine-readable report. `PASS` is only a static archive-diff result; it does not establish a clean resource graph, Minecraft import, gameplay, multiplayer or performance result. Keep `project-audit` separate for broader single-project/resource-graph/behavior diagnosis and hand off to this comparator only for regression comparison.
