---
name: recipe-authoring
description: Use when creating or troubleshooting shaped or shapeless Minecraft Bedrock crafting recipes and validating ingredient/result references against the target version.
---

# Minecraft Bedrock recipe authoring

## Workflow
1. Confirm target Bedrock version and BP root. For an existing project, inspect its manifests and recipe conventions before editing.
2. Inspect the bundled `bedrock-samples` 1.26.50.4 recipe example and its provenance. It uses `format_version` `1.20.10`; verify compatibility for any other target using official Creator documentation and matching samples.
3. Ensure every custom ingredient/result identifier resolves to an existing BP item/block definition. Treat `minecraft:` identifiers as vanilla references only when documented for the target version.
4. For shapeless recipes, create an `ingredients` list within the documented count/shape limits. For shaped recipes, use 1–3 equal-width rows (maximum 3 symbols per row), map each non-space symbol exactly once, and verify every key resolves.
5. Write one recipe JSON to the correct BP `recipes/` folder using a real file capability. If none exists, provide the complete file and mark it `NOT APPLIED`. Never assume `create_addon_recipe` is an available tool.
6. Validate JSON, `format_version`, recipe identifier/type, ingredient/result identifiers and count. Check duplicate recipe identifiers and output path collisions.
7. Test unlock behavior, crafting-grid arrangements, inventory consumption and multiplayer behavior in the target game before claiming runtime success.

## Safety and limits
- Recipe authoring does not create missing items, blocks, textures, station logic or custom unlock systems.
- Preserve existing recipes and unrelated files; do not overwrite without explicit authorization.
- Do not copy or redistribute vanilla assets from Mojang Samples without checking license/EULA constraints.
- Static validation is not a crafting test. Mark runtime `NOT RUN` until performed.
