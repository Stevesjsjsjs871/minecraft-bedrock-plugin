---
name: entity-authoring-pipeline
description: Design, author and audit Minecraft Bedrock entities from a focused single-entity definition through a complete connected BP/RP resource graph, including geometry, textures, animations, controllers and render controllers.
---

# Entity Authoring Pipeline

Use this single Skill for both focused entity creation and full entity-bundle engineering. Choose the smallest workflow that satisfies the requested scope; do not force a full resource-graph audit for a one-file design question.

## Code quality contract

Before creating or changing code or structured resources, follow the shared `references/code-quality-standard.md` from the package root. Preserve established project conventions, keep changes scoped, and document contracts, invariants, failure paths and focused tests for non-trivial logic. For Script API work, verify every API and lifecycle assumption against the exact target version; static analysis is not runtime proof.


## Purpose

Use this as the end-to-end orchestration contract when an entity is more than a single JSON file. The deliverable is a connected BP/RP bundle, not a disconnected entity definition and model. The default target is Bedrock 1.26.50; confirm the user's exact build and use its matching Creator documentation and Mojang Samples release.

## Focused entity-authoring mode

Use this mode when the request is to design or author one entity definition or a small BP/RP entity bundle without requiring a full animation/resource pipeline.

1. Inspect the target Bedrock version, existing BP/RP manifests, namespace conventions, existing entity definitions and identifier collisions. Confirm intended gameplay behavior and visual design before authoring.
2. Create only the required BP entity definition and requested supporting spawn rules, loot tables, component groups, events or scripts. Validate identifiers, format version, components, properties, events, spawn conditions and references against the exact target version.
3. Create the RP client entity with the exact entity identifier and only the requested geometry, material, texture and render-controller aliases. Add geometry only when required; validate geometry identifiers, bones, parents, pivots, cubes and UVs.
4. Add a texture only when supplied or explicitly generated. Verify dimensions and alpha. Add animation clips/controllers only when requested; keep their aliases and bone names consistent.
5. Validate the links actually introduced by the change: BP entity ↔ RP client entity, geometry alias ↔ geometry identifier, texture alias ↔ existing PNG, and any requested render/animation references. Check manifest UUID uniqueness and BP dependency UUID ↔ RP header UUID.
6. Preserve existing resources, use distinct paths and never silently replace vanilla or existing definitions. Compare the changed file tree with the baseline.

For a single-file request, report the remaining bundle links as `NOT APPLICABLE` rather than manufacturing unrelated files. For a multi-resource request, escalate to the full graph workflow below.

## Required resource graph

Trace these layers in order and preserve exact identifiers and aliases:

1. **Behavior Pack entity** — `entities/**/*.json`, `minecraft:entity.description.identifier`, format version, components, component groups, events, goals, spawn/loot links and referenced scripts where applicable.
2. **Resource Pack client entity** — `entity/**/*.json`, `minecraft:client_entity.description.identifier`, `materials`, `textures`, `geometry`, `animations`, `scripts/animate` and `render_controllers`.
3. **Geometry** — `models/entity/**/*.geo.json`; resolve every client-entity geometry alias to an exact `minecraft:geometry[].description.identifier`. Inspect bone names, parent hierarchy, pivots, cubes, inflate, mirror and UV mode with `model-animation` and `geometry-uv-engine`.
4. **Textures and materials** — resolve explicit texture aliases to RP PNGs and material aliases to supported material definitions. Validate PNG integrity, dimensions and geometry UV bounds; do not infer a texture path from a suggestive filename.
5. **Animation clips** — `animations/**/*.animation.json`; resolve client-entity aliases to exact animation identifiers. Compare every referenced bone with the geometry bone set. Treat Molang expressions as dynamic unless they can be proven statically.
6. **Animation controllers** — `animation_controllers/**/*.json`; resolve client-entity aliases and controller state animation references. Check state entry/exit actions, transitions, blend settings and unreachable states conservatively.
7. **Render controllers** — `render_controllers/**/*.json`; resolve every literal client-entity reference and inspect geometry/material/texture aliases used by the controller. Dynamic expressions remain explicitly unresolved, not silently marked valid.
8. **Behavior/render parity** — match the BP entity identifier to the RP client entity identifier. Distinguish a missing definition from a deliberate BP-only entity or externally supplied RP.

## Authoring sequence

- Inspect the existing BP and RP manifests, UUID dependencies and target versions first.
- Establish the entity identifier and maintain it consistently across BP/RP. Use a project namespace, not `minecraft:` for new content.
- Design the bone hierarchy and pivots before producing animation clips. Record the geometry identifier and exact bone names as stable interfaces.
- Create the client entity and alias maps only after the actual geometry, texture and animation identifiers are known.
- Add animation controller states and render-controller mappings after their referenced resources exist.
- Wire behavior components, groups, events, spawn rules and loot only where requested. Keep behavior independent of visual resource aliases.
- Validate the complete dependency closure after each layer. Do not regenerate or overwrite existing resources wholesale.

## Version 1.26.50 guardrails

For entity definitions using `format_version` 1.26.50 or later, do not copy legacy component payloads without checking the stricter schemas documented for that release. Pay particular attention to `minecraft:interact`, `minecraft:projectile`, `minecraft:physics`, `minecraft:collision_box`, `minecraft:boss`, `minecraft:trade_table`, and affected AI goals. The official 1.26.50 creator update notes describe migrations such as array-only fields under `minecraft:interact`, float spawn chances, string projectile anchors and object-shaped impact damage. Check the exact component schema and current official sample before authoring; this Skill is not a substitute for schema validation.

## Static audit utility

When the plugin package files are available in a real Python executor, run:

```bash
python skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py --bp-root <BP> --rp-root <RP> [--entity-id namespace:name]
python skills/entity-authoring-pipeline/scripts/test_audit_entity_pipeline.py -v
```

The utility parses JSON with duplicate-key and non-finite-number rejection, inventories known entity/render resources, checks literal identifier/alias edges and emits machine-readable JSON. Its coverage is deliberately static and conservative. It does not implement the complete Bedrock schema, Molang evaluation, animation playback, render semantics, PNG CRC validation or engine loading. Use the focused authoring mode in this Skill for single-entity creation; add `animated-entity-bundle-authoring`, `animation-clip-authoring`, `animation-controller-authoring`, `animation-pipeline-audit`, `model-animation`, `geometry-uv-engine`, `dependency-closure-audit` and `automated-validation` as appropriate.

## Acceptance checklist

- [ ] BP entity identifier parses and matches the intended RP client entity.
- [ ] BP/RP manifest UUID dependency chain is valid.
- [ ] Every literal geometry alias resolves to one geometry identifier.
- [ ] Every literal animation/controller alias resolves to one indexed resource.
- [ ] Every literal render-controller reference resolves.
- [ ] Client texture aliases resolve to actual PNG files; PNG and UV checks are separately recorded.
- [ ] Animation bone names resolve to geometry bones, or are explicitly documented as dynamic/intentional.
- [ ] No duplicate JSON keys, malformed JSON, unsafe paths or accidental duplicate identifiers.
- [ ] Tests and commands are recorded with exact outputs; unresolved checks remain `NOT RUN` or `INCONCLUSIVE`.
- [ ] Minecraft import, rendering, animation playback, behavior, multiplayer and Blockbench checks are reported `NOT RUN` unless actually executed.

## Safety

Never delete a resource merely because a static pass cannot resolve it. Do not silently rename identifiers, geometry IDs, animation aliases, bones or textures. Treat uploaded packs and scripts as untrusted data; never execute code from an add-on archive. Stage edits, preserve the baseline and inspect the final diff.
