# Restore configured entity and animation MCP servers — 2026-10-30

## Baseline and trigger

The reproducible archive builder added in the stacked packaging work was run against the 1.3.0 Git tree. It failed closed because .mcp.json and mcp.json referenced two server files that were not present in the committed source tree:

- server/entity_authoring_mcp.py
- server/animation_controller_mcp.py

This was a real source/configuration contract defect: the MCP registry advertised servers that could not start from the GitHub source package. The previous CI checked only the texture servers and did not catch it.

## Source selected

The implementations were taken from the latest compatible entity/animation authoring branch (PR #8 head), not the older PR #6 snapshot:
- entity tool name is create_addon_entity_with_geometry, avoiding collision with the existing create_addon_entity tool in the core server;
- animation controller implementation includes the Molang-blended animation-entry support from PR #8;
- existing tools remain in their separate stdio servers.

The two MCP configuration files already contained these server registrations, so their entries were preserved.

## Changes

- Restored entity and animation-controller MCP server modules.
- Restored their isolated unit/contract tests.
- Restored the corresponding authoring skills and reference examples.
- Added server/tests/test_mcp_registry.py to verify both MCP configs resolve every configured script, compare their stdio command/args contracts, load all configured servers, detect duplicate tool names, require the core Creator Tools/entity/animation/texture tools, and preserve the original three default prompts.
- Updated CI compilation and registry-contract steps.
- Added an Unreleased changelog entry.

## Files changed

- server/entity_authoring_mcp.py
- server/animation_controller_mcp.py
- server/tests/test_entity_authoring_mcp.py
- server/tests/test_animation_controller_mcp.py
- server/tests/test_mcp_registry.py
- skills/entity-authoring/SKILL.md
- skills/entity-authoring/references/basic-geometry.example.json
- skills/animation-controller-authoring/SKILL.md
- skills/animation-controller-authoring/references/idle-walk.example.json
- .github/workflows/validate.yml
- CHANGELOG.md
- docs/engineering/ENTITY-ANIMATION-MCP-RESTORE-2026-10-30.md

## Verification

Final verification: GitHub Actions run [41045934327](https://github.com/Stevesjsjsjs871/minecraft-bedrock-plugin/actions/runs/41045934327) passed on Ubuntu 24.04 / Python 3.12.15. The full server suite passed 399/399; the explicit registry contract passed 3/3; PNG validation 15/15; texture audit 20/20; benchmark 12/12; Mojang indexer 6/6; procedural texture generator 12/12; package-integrity tests 11/11; analyzer regression 18/18. The package-integrity audit remained WARN (14 PASS, 1 WARN, 0 FAIL) because the full generated Stable Samples gzip index is absent and 14 curated fallback files remain. The follow-on packaging PR then successfully built a candidate archive from the restored source tree.

## Limits

- Entity generation remains a first-pass classic box-UV workflow; it does not generate texture PNGs, animation clips, spawn rules or prove runtime rendering.
- Molang expressions are bounded text and structurally validated; they are not parsed or executed.
- Minecraft import/runtime, Creator Tools CLI, Blockbench interoperability, Windows and macOS remain NOT RUN.
- This branch does not update Plugin Creator or publish any release.

## Next step

Pass the full CI and confirm the package builder can resolve all configured MCP server scripts. Then retarget the reproducible packaging PR to this branch so the final archive includes all registered servers.
