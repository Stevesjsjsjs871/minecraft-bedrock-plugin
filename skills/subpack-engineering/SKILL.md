---
name: subpack-engineering
description: Use when creating or auditing Bedrock Resource Pack Subpacks, manifest settings, selectable modes, folder mappings and resource overrides.
---

# Subpack Engineering

## Inputs

Confirm target Bedrock build, RP root, manifest format, Subpack selection behavior the user expects, and the exact project baseline. Do not assume every historical manifest shape has identical semantics in the current game.

## Workflow

1. Parse `manifest.json` and inspect the actual schema/version fields controlling subpacks and settings. Verify the relevant structure against exact-version official Creator documentation or matching samples.
2. Enumerate declared `folder_name` values and compare them with real directory paths using exact case and safe relative-path rules.
3. Build a per-mode inventory of files and normalized relative resource paths. Identify resources overridden by multiple subpacks, missing declared folders, duplicate paths and folders not referenced by any declaration.
4. Check setting IDs, option values, defaults, ordering and localization keys against the manifest's actual structure. Do not invent field names or assume a particular client UI.
5. Compare resource trees across modes. Report which file each mode resolves to, whether an override is intentional, and any missing/ambiguous resource.
6. Preserve original content and inspect the final packaged archive if a real packaging route is available.

## Acceptance and output

Return manifest paths/format, declared settings/options, per-subpack inventory, duplicate/overridden resources, missing/orphan folders, localization results, baseline delta, tests and exact commands. Treat orphan folders as informational unless proven defective; never delete them automatically.

## Limits and safety

Use synthetic fixtures to test path/mapping logic. Do not copy third-party Subpack content. Static inventory cannot prove which option the game displays or loads. Selection UI, resource precedence and in-game behavior remain `NOT RUN` until tested in the exact target Bedrock client.
