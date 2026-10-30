---
name: addon-creation
description: Use when starting a new Minecraft Bedrock add-on from a blank idea or clean folder; plan and author BP/RP entities, blocks, items, recipes, scripts, UI, models, textures and animations.
---

# Add-on creation workflow

## Operating boundary
This plugin is Skills-only. Do not call historical names such as `create_addon_project`, `create_addon_item`, `search_mojang_samples` or `read_mojang_sample` as tools: they are not guaranteed host capabilities. Skills do not create workspaces, write files or execute scripts. First follow `skills-first-execution` and select a real file/code route. If none exists, return a complete patch or exact commands and mark it `NOT APPLIED` / `NOT RUN`.

## 1. Scope the smallest complete feature
Record the exact Bedrock target version, intended gameplay/visual result, BP/RP dependencies, content identifiers, assets, acceptance criteria and tests. Default reference baseline is 1.26.50 only when the user has not specified a target. Separate required behavior from optional polish. Build one complete vertical slice before expanding.

## 2. Inspect and establish provenance
For an empty project, propose a minimal BP/RP tree and generate only requested files. For an existing project, use `project-continuity` and never scaffold over it. Inspect manifests, UUIDs, identifiers, existing atlases, localization, UI, entity/client-entity links, geometry, textures, animations and recipes before changing them. Record a baseline file list and hashes when practical.

For version-sensitive features, use `research-versions` and `mojang-samples-authoring`. Prefer official Microsoft Creator documentation and the exact-version Mojang Samples corpus bundled under `bedrock-development/references/`. If the needed example is absent, search the official source only through an available web capability. Record the source URL, commit/release/version and the exact path or schema used. Never imply that a local index can fetch files remotely.

## 3. Author by resource domain
- **Manifests:** unique header/module UUIDs; BP dependency UUID must equal the RP header UUID; `min_engine_version` must match the target; use verified format versions.
- **Items:** BP item definition, RP icon/atlas entry, localization, and a real PNG at the referenced path. Atlas/localization edits must merge and preserve unrelated keys.
- **Blocks:** BP block definition and components, RP terrain atlas/material/geometry as required, localization, texture PNG, and optional recipe/drop behavior. Do not assume atlas registration creates the image.
- **Recipes:** shaped/shapeless format and ingredients/results must resolve to actual identifiers; avoid duplicate recipe identifiers and invalid patterns.
- **Entities:** BP entity and applicable spawn/loot behavior; RP client entity, geometry, texture, render controller, animations and controller bindings. Check every identifier and alias end-to-end.
- **Scripts:** JavaScript ESM for `@minecraft/server` unless the project says otherwise. Verify the exact module/API version and lifecycle/event semantics against official docs. Consider multiplayer, async behavior, performance and world safety.
- **UI/localization:** inspect the full relevant RP `ui/` tree, include chains, namespaces, textures and language keys. Treat dynamic references and engine-resolved paths as review items, not certain failures.
- **Models/animations:** validate geometry identifiers, bone names, cube bounds, UVs, animation channels/keyframes, controller states/transitions and client-entity aliases.

## 4. Safe implementation
Before writing, list intended file additions/changes and acceptance criteria. Use only an actual connected file/code capability. Keep all paths inside the selected project, reject traversal and symlink escapes, refuse accidental overwrites, and preserve existing mechanics, UUIDs, assets and unrelated resources. Do not execute scripts contained in third-party packs. If a change depends on an unsupported schema or unverified API, isolate it and label it `UNVERIFIED` rather than guessing.

## 5. Validation and completion
Re-open changed files. Parse JSON; verify manifest UUID/dependency parity; check identifier and resource references; inspect PNG dimensions/decoding; audit geometry/UV and animation/controller linkage where relevant; compare the final tree with the baseline. Run only scripts/tests that are actually available and record exact command, exit code and counts. Import/render/gameplay/multiplayer/Blockbench checks remain `NOT RUN` until performed in the target environment.

## 6. Deliverable
Report the target version, files created/changed, source provenance, behavior implemented, validation evidence, known limitations and runtime status. A scaffold or static pass is not a finished playable add-on. Package `.mcaddon`/`.mcpack` only with a real packaging route and inspect the resulting archive before claiming success.
