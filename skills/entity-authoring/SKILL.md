---
name: entity-authoring
description: Use to design and author a Minecraft Bedrock entity bundle across BP and RP files, including geometry, textures, client entity, render controllers and behavior references.
---

# Entity authoring workflow

This skill describes a file-authoring procedure; it does not provide a `create_addon_entity` tool. Follow `skills-first-execution` and use a real file/code route. Otherwise return complete files and mark them `NOT APPLIED`.

## Discovery
Inspect target version, pack manifests, namespace conventions, existing entities and identifier collisions. Search exact-version Mojang Samples and official Creator docs. Establish the required gameplay behavior and visual design before generating resources.

## Behavior Pack
Create only the required entity definition and supporting spawn rules, loot tables, component groups, events or scripts. Validate identifier, format version, components, properties, events, spawn conditions and references against the target version. Avoid copying unrelated vanilla behavior.

## Resource Pack
Create the client entity with exact entity identifier, geometry/material/texture aliases and render-controller bindings. Add geometry with a unique identifier, valid bones/parents/pivots/cubes and UVs. Add texture only when supplied or explicitly generated; verify canvas dimensions and alpha. Add animation clips/controllers only when requested and ensure aliases/states/transitions and animated bone names resolve.

## Bundle integrity
Check BP entity ↔ RP client entity identifier match, geometry identifier ↔ client alias, texture path ↔ file, render controller ↔ client binding, animation alias ↔ clip/controller, and any spawn/loot/script references. Check manifest UUID uniqueness and BP dependency UUID equals RP header UUID.

## Safety and tests
Preserve existing resources and use new distinct file paths. Do not overwrite existing definitions or silently replace vanilla entities. Validate JSON and references, then compare the file tree with baseline. In-game spawn, rendering, AI, animation playback, multiplayer and performance checks are `NOT RUN` until tested in the target game build.
