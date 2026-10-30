---
name: entity-authoring
description: Use when creating a new Minecraft Bedrock custom entity bundle, including BP entity definitions, RP client entities, geometry JSON, render controllers, bone hierarchies, cube UVs, and the first import-validation plan.
---

# Minecraft Bedrock Entity Authoring

## Scope and evidence
- Default target: Minecraft Bedrock 1.26.50 unless the user selects another version.
- Prefer version-matched Mojang samples and official Creator documentation for components, format versions, and resource identifiers.
- Distinguish `STATICALLY VERIFIED` from `RUNTIME TESTED`. JSON parsing and reference checks do not prove the entity imports, spawns, animates, or renders in Minecraft.
- Do not claim a texture or animation exists unless its file is present and its identifier/path resolves.

## `create_addon_entity_with_geometry_with_geometry`
Use the dedicated `create_addon_entity_with_geometry_with_geometry` MCP tool only on an existing project created by `create_addon_project`. It creates four coordinated files:
1. `behavior_packs/<project>_BP/entities/<slug>.json`
2. `resource_packs/<project>_RP/entity/<slug>.entity.json`
3. `resource_packs/<project>_RP/models/entity/<slug>.geo.json`
4. `resource_packs/<project>_RP/render_controllers/<slug>.render_controllers.json`

The tool derives the entity namespace from the project directory (`forest-addon` -> `forest_addon`) and links the entity, geometry, and render-controller identifiers across the files. It validates the existing BP/RP manifest dependency and does not overwrite existing files.

## Geometry input contract
- `geometry.bones` contains 1–64 bones. Bone names are unique, begin with a letter, and use letters, digits, or underscores.
- Each bone requires a three-number `pivot`; it may reference one existing `parent`, contain up to 64 cubes, and define named three-number `locators`.
- The parent graph must be complete and acyclic. Preserve intentional pivots and hierarchy; do not flatten the skeleton.
- Each cube requires `origin`, non-negative `size` (not all zero), and a two-integer box-UV origin. Optional `pivot`, `rotation`, `mirror`, and `inflate` are supported.
- The box UV rectangle is checked against `texture_width` and `texture_height`. This validates the classic box-UV form only; per-face UV maps, poly meshes, and Blockbench project files are not accepted by this first version.
- Bounds, vector values, cube count, bone count, and total geometry input are bounded to limit invalid or abusive writes.

An example input is included at `references/basic-geometry.example.json`.

## Texture and animation follow-up
- The generated client entity references `textures/entity/<namespace>/<slug>` but the tool intentionally does not fabricate a PNG. Supply a correctly UV-mapped PNG at the returned path or use the procedural texture tool only for a suitable placeholder.
- No animation clip or animation controller is created. Add these separately after the bone names and required movement are agreed.
- Add a spawn rule only when biome, spawn conditions, weight, and group size are specified; `is_spawnable` is not proof that natural spawning is configured.

## Required validation
1. Parse all four generated JSON files and confirm their identifiers agree.
2. Check bone parent references, cycles, cube UV bounds, and texture-path existence.
3. Validate BP and RP manifests remain linked; compare the file list before and after the operation.
4. Import the packs in the exact target game build. Test `/summon <namespace>:<slug>`, entity collision/health, geometry visibility, texture alignment, lighting/material behavior, and spawn egg behavior if enabled.
5. Mark Minecraft import, spawning, and visual tests `NOT RUN` until actually performed.


## Backward compatibility
The existing core MCP tool `create_addon_entity_with_geometry` remains available for its original input contract. Use `create_addon_entity_with_geometry_with_geometry` when supplying an explicit bone/cube geometry definition.
