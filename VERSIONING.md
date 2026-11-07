# Versioning — Minecraft Bedrock Engineer plugin package

This file governs the Minecraft Bedrock Engineer Plugin Creator package, not add-ons developed with it. For the user's Bedrock add-on version, visible in-game title and BP/RP `manifest.json` updates, use `skills/addon-versioning/SKILL.md` and `ADDON_VERSIONING.md`.

Plugin Creator metadata and its current-release marker are authoritative. `VERSION`, both plugin manifests, README heading, changelog and release notes must agree. The attached-release endpoint can include unpublished releases; do not call every historical attachment a publicly published release.

## New plugin-package sequence

Use exactly three numeric components, each 0–9. Increment PATCH through 9, then carry into MINOR; when MINOR is 9, carry into MAJOR:

- `1.0.8 → 1.0.9`
- `1.0.9 → 1.1.0`
- `1.1.9 → 1.2.0`
- `1.9.9 → 2.0.0`
- `2.0.0 → 2.0.1`

Never create a new plugin package version with a component `10` or above. Historical legacy releases are immutable. For a legacy PATCH overflow, carry into the next MINOR (`1.5.12 → 1.6.0`); do not rewrite the historic string. Stop for a MAJOR above 9 or when no successor exists.

## Current project sequence

Live Plugin Creator metadata was refreshed on 2026-11-07: current version `2.1.11`, release ID `pluginrel_6aef522dcae48191bd5d00fe0d8d1593`, USER scope, PRIVATE discoverability. The next candidate is `2.3.0` based on the verified 2.2.0 archive. It is not published. Refresh live metadata again immediately before any update and use the exact observed release ID as the guarded precondition.

## Candidate discipline

Do not bump for every internal edit. Accumulate coherent plugin changes and allocate a candidate only after tests are prepared. Preserve every default prompt exactly, including type, strings and order. Keep historical history immutable and add a new row for the new candidate. A successful Plugin Creator update must be followed by metadata/source read-back.

## CLI

```bash
python skills/version-governance/scripts/version_governance.py next 1.9.6
python skills/version-governance/scripts/version_governance.py validate 1.9.7
python skills/version-governance/scripts/test_version_governance.py -v
```
