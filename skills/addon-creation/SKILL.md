---
name: addon-creation
description: Use when the user wants to start a Minecraft Bedrock add-on from a blank idea or clean folder, plan the first feature, scaffold BP/RP, and implement new entities, blocks, items, recipes, scripts, UI, models, textures, or animations.
---

# Add-on Creation from Scratch

## Goal
Turn a user's idea into a working Minecraft Bedrock add-on incrementally. The default target is Bedrock 1.26.50 unless the user specifies another version. Start with a clean project scaffold, implement a small vertical slice, validate it, and only then expand. This is the primary path for new projects; use the existing-project safety path only when source files already exist.

## Capability selection
1. For a genuinely new project, call `create_addon_project` with a new single directory name, a display name, a short description, and the exact target game version. It creates a linked Behavior Pack and Resource Pack scaffold under the configured workspace. Never choose an existing or arbitrary nested target.
2. Inspect the tool's actual output and both generated manifests. Check that the BP dependency UUID equals the RP header UUID, all manifest/module UUIDs differ, and `min_engine_version` matches the requested target.
3. For one simple custom item in a fresh scaffold, use `create_addon_item` after reading the Mojang item example; it creates the BP item definition, RP atlas mapping and localization entry, but does not generate a PNG. It refuses collisions and pre-existing atlas/localization files rather than merging them. Treat scaffolding and content authoring as separate operations. The scaffold tool does not create gameplay content. For item creation in a clean scaffold, use `create_addon_item`; for blocks, entities or models, prefer an actually available Mojang Creator Tools MCP capability. For whole-project work, validation, rendering, or packaging, use a locally available, user-approved MCT CLI only after checking `mct --help` and the installed version. Do not claim a capability or tool is available unless it is listed in the active host.
4. Use available authorized file-writing tools to implement the generated files when present. If the host cannot edit files, be transparent and produce a patch/archive artifact or precise file contents instead of claiming changes were applied.

## Convert idea into a build plan
Record: (a) gameplay/visual goal, (b) target Bedrock version, (c) content types, (d) pack dependencies and expected import order, (e) assets that must be generated or provided, (f) acceptance criteria, and (g) tests. For a large idea, split it into milestones such as minimal playable behavior, resource visuals, animation, UI/localization, polish, and packaging. Implement the smallest complete first milestone rather than creating many unconnected placeholders.

## Version-aware engineering
- Before authoring a new resource, search `search_mojang_samples` for a nearby example in the same domain and read a curated example with `read_mojang_sample`. Verify exact-version differences instead of copying vanilla files wholesale. Pair with the `mojang-samples-authoring` skill for provenance and licensing limits.
- Research version-sensitive formats and APIs against official Creator documentation and matching Mojang samples. Record source links and the exact version represented by each source; do not mix a current sample with an older target without checking compatibility.
- Use JavaScript ESM for new `@minecraft/server` code unless the project's toolchain or user requirements say otherwise. Do not guess API versions: verify them for the target game before adding manifest dependencies.
- Keep Behavior Pack and Resource Pack UUIDs unique, and link them only through the actual generated UUIDs. Never reuse one UUID for multiple manifest objects.
- Entity work must consider BP entity definitions, spawn rules/loot where applicable, RP client entity, geometry, texture, render controller and animation/controller references. Only add the files needed for the selected feature.
- Block/item work must verify format versions, identifiers, components, icon/texture mappings, localization and Creative catalog exposure as applicable.
- Script work must consider module type/version, imports, async behavior, player/entity lifecycle, multiplayer correctness and performance.
- UI/localization support varies by format and version. Treat ambiguous paths and dynamic keys as review items, not proven defects.

## Implement, validate, iterate
1. Before each milestone, list intended files and acceptance criteria.
2. Generate content using validated schemas or version-matched examples; don't fabricate undocumented properties.
3. Parse all JSON, validate manifest dependency links and UUID uniqueness, check cross-resource references and identifier consistency, and run relevant static audits.
4. When possible run Mojang Creator Tools validation or its relevant specialist tools, keeping its diagnostics distinct from this plugin's audit results.
5. Compare the change set to the previous milestone. Explain unexpected deletions/additions; do not silently delete unknown resources.
6. Package as `.mcaddon`/`.mcpack` only when the required tooling is available and the structure has been inspected.
7. Report static checks, MCT checks, and game runtime checks separately. Mark import/render/gameplay/multiplayer behavior `NOT RUN` unless actually tested.

## Safety and source control
- `create_addon_project` is a write operation; it only creates a brand-new child directory in the configured workspace and refuses an existing target. Never use it to edit an existing project.
- Do not install dependencies, download remote executables, accept the Minecraft EULA, deploy into a live world, or overwrite files without the required user authorization.
- For existing projects, preserve mechanics, UUIDs, recipes, assets, and unrelated files; inspect before editing. For new projects, creating the initial structure is expected, but avoid generating unrequested filler content.
- Do not label a generated scaffold as a finished add-on. It is the start of a project until actual behavior and resource assets have been implemented and tested.

## Official references
- Creator Tools overview: https://learn.microsoft.com/en-us/minecraft/creator/documents/mctoolsoverview?view=minecraft-bedrock-stable
- Manifest reference: https://learn.microsoft.com/en-us/minecraft/creator/reference/content/addonsreference/packmanifest?view=minecraft-bedrock-stable
- Comprehensive pack contents: https://learn.microsoft.com/en-us/minecraft/creator/documents/comprehensivepackcontents?view=minecraft-bedrock-stable
- Mojang Creator Tools: https://github.com/Mojang/minecraft-creator-tools


## Multiple custom items

For subsequent items in the same scaffold, `create_addon_item` merges new entries into an existing valid item atlas and `en_US.lang` while preserving unrelated entries. Check key collisions, malformed content and every existing texture file before proceeding. It fails closed on ambiguous localization/atlas state rather than discarding user data. Item definitions alone do not create textures; create or supply the PNG and verify it at the exact RP path before packaging.


## First custom block

Use `create_addon_block` for a basic custom block BP definition plus its RP terrain texture atlas mapping. Search/read the version-labelled Mojang block example first, inspect the generated fields against the desired Bedrock version, then provide a PNG at the reported RP path. The tool merges only valid existing terrain atlases and rejects key collisions; it does not create the texture, recipes, drops, custom geometry, or gameplay logic. Test import and rendering in the target game before claiming completion.


## Crafting recipes (0.9.0)

Use `create_addon_recipe` once the result item/block definitions exist. Use `shapeless` with an `ingredients` list for shapeless recipes, or `shaped` with 1–3 equal-width pattern rows and a `key_mapping` for each used A–Z/0–9 symbol. Ingredients and result identifiers must use `namespace:name` form; custom identifiers must resolve to existing item/block definitions in the same BP, while `minecraft:` identifiers are accepted as vanilla references. The generator writes one BP recipe file and refuses collisions. It does not create new ingredient items, blocks, or textures. Check its JSON and target-version example, then test the recipe in Minecraft; static creation leaves runtime `NOT RUN`.
