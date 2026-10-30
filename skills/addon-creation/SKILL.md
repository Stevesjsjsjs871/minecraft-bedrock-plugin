---
name: addon-creation
description: Plan a new Minecraft Bedrock add-on and author its BP/RP resources through real file capabilities or complete reviewable patches.
---

# Add-on Creation Workflow

## Operating boundary

This plugin is Skills-and-instructions-only. It does not provide a project scaffolder, remote sample-search service or built-in BP/RP file writer. Skills do not create workspaces, write files or execute scripts. Follow skills-first-execution and the capability matrix. If no real file/code route exists, return complete files or a patch and mark them NOT APPLIED / NOT RUN.

## 1. Scope the smallest complete feature

Record the exact Bedrock target version, gameplay/visual result, BP/RP dependencies, identifiers, assets, acceptance criteria and tests. Default reference baseline is 1.26.50 only when the user has not specified a target. Build one complete vertical slice before expanding.

## 2. Inspect and establish provenance

For an empty project, propose a minimal BP/RP tree and create files only through an authorized capability. For an existing project, use project-continuity and never scaffold over it. Inspect manifests, UUIDs, identifiers, atlases, localization, UI, entity/client-entity links, geometry, textures, animations and recipes before changing them.

Use research-versions and mojang-samples-authoring for version-sensitive features. Prefer official Microsoft Creator documentation and the exact-version Mojang Samples corpus. Inspect the local index and bundled sample files when mounted; otherwise use a real web capability. Record source URL, release/tag, commit or version, exact path and check date. Do not imply that a local index downloads remote content.

## 3. Author by resource domain

- Manifests: unique UUIDs, correct BP/RP dependency links, verified min_engine_version and format versions.
- Items: BP definition, RP icon/atlas entry, localization and an actual PNG at the referenced path.
- Blocks: BP definition/components, required RP resources, localization, texture and optional recipe/drop behavior.
- Entities: BP behavior, RP client entity, geometry, texture, materials/render controllers, animations/controllers and optional spawn/loot resources.
- UI: inventory JSON UI files, textures, fonts and literal references; distinguish unresolved dynamic references from proven missing files.
- Scripts: JavaScript ESM for @minecraft/server where appropriate; verify the exact module/API version and lifecycle/event semantics.

## 4. Validate and report

Parse changed JSON, reject duplicate keys where supported, validate UUIDs, identifiers, file paths and dependency links. Run only available standalone scripts. Return files changed or proposed, exact source provenance, static test evidence, unresolved assumptions and runtime status.

Minecraft import, rendering, gameplay, multiplayer and performance remain NOT RUN unless actually tested.
