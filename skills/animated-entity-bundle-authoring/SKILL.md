---
name: animated-entity-bundle-authoring
description: Coordinate the manual creation and static review of a Minecraft Bedrock entity, geometry, animation clips and controller as one BP/RP feature.
---

# Animated Entity Bundle Authoring

## Purpose and capability boundary

Use this workflow when a new entity needs a coordinated first-pass model and animation system. It is a multi-file authoring recipe, not a one-call generator. The plugin does not contain an active entity-bundle writer or animation writer.

Use an actual authorized file capability if one is available. Otherwise return the complete proposed BP/RP files and mark them NOT APPLIED. Do not claim transactional writes, automatic rollback or server-side validation.

## Required inputs

- Existing BP and RP roots, or an explicitly approved new project layout.
- Exact target Bedrock version.
- Namespaced entity identifier and intended behavior.
- Explicit geometry, bone names, pivots, cubes and texture-canvas dimensions.
- Animation clip names, duration, loop intent, bone channels and keyframes.
- Controller states, initial state, transition destinations and reviewed Molang conditions.
- Texture and render-controller requirements.

## Planned resource set

Create only the resources required by the feature: BP entity definition; RP client entity; geometry/model JSON; required texture; render-controller JSON; animation clips; animation controller and client-entity aliases; optional spawn, loot, sound and localization resources.

## Manual workflow

1. Inventory the linked BP/RP manifests and all existing entity, geometry, animation and controller identifiers.
2. Confirm exact geometry bone names and cube indices before writing any animation channels.
3. Draft the geometry and client-entity references first; then define clip aliases and controller aliases consistently.
4. Author each resource as a separate proposed file. Preserve existing aliases and unrelated resources. Do not assume a generator will coordinate them.
5. Check JSON syntax, duplicate keys, identifiers, literal file paths, bone references, aliases and controller transition destinations using available local checks.
6. When the real executor can access the package and project, run the entity pipeline audit with the supplied BP/RP roots. Treat its output as a conservative static dependency report.
7. Re-open all changed files and compare the project tree with the baseline.

## Limits and handoff

The static audit does not execute Molang, validate every engine schema rule, render geometry or test animation interpolation/blending. It does not create a texture or prove the model is correctly UV-mapped. Minecraft import, spawn, rendering, controller transitions, multiplayer behavior and Blockbench interoperability remain NOT RUN until actually tested.

After the static stage, hand off to texture/UV review and an exact-target in-game test. Never describe the entity as a finished playable mob if those stages remain incomplete.
