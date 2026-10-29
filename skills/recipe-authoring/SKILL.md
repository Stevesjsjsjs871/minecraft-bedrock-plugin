---
name: recipe-authoring
description: Use when creating or troubleshooting shaped or shapeless Minecraft Bedrock crafting recipes for a new add-on, including ingredient/result references and target-version sample comparison.
---

# Minecraft Bedrock Recipe Authoring

## Workflow
1. Confirm the target Bedrock version and an existing linked BP/RP project scaffold.
2. Search/read the matching Mojang Samples recipe example before generating a new recipe. The bundled example is from the user-provided `bedrock-samples` 1.26.50.4 archive and uses `format_version` `1.20.10`; verify whether it fits any different target version.
3. Ensure all custom result and ingredient identifiers are already defined by item/block JSON files in the project's BP. Vanilla `minecraft:` identifiers are accepted as external references.
4. For a shapeless recipe, call `create_addon_recipe` with `recipe_type: "shapeless"` and a 1–9 item `ingredients` list. For a shaped recipe, use `recipe_type: "shaped"`, 1–3 equal-width pattern rows (up to 3 characters per row), and a `key_mapping` whose single uppercase letters/digits exactly match the non-space symbols in the pattern.
5. Inspect the generated file under `behavior_packs/<project>_BP/recipes/`. Check identifiers, result count (1–64), and recipe format. The tool refuses to overwrite existing files and performs static reference checks only.
6. Run the applicable static validations; import into Minecraft and craft with each intended ingredient arrangement before claiming it works. Keep runtime status `NOT RUN` until performed.

## Safety and limits
- The tool creates one recipe JSON only. It does not create missing items, blocks, textures, station logic, or custom recipe unlock systems.
- It does not overwrite recipes, follow symlinked pack roots, or accept custom IDs absent from this project's own BP definitions.
- Recipe unlocking, inventory consumption, shaped-grid semantics and multiplayer behavior still require in-game testing.
- Do not copy or redistribute vanilla assets from Mojang Samples without checking their license/EULA constraints.
