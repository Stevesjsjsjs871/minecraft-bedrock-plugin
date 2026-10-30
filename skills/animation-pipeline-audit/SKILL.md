---
name: animation-pipeline-audit
description: Use when checking whether a Minecraft Bedrock entity's RP animation clips, animation-controller state machines, client-entity aliases, scripts.animate entries, geometry identifiers and model bone names form a consistent end-to-end graph.
---

# End-to-end entity animation pipeline audit

## Purpose

Use `audit_entity_animation_pipeline` after adding or changing animation clips, animation controllers or entity geometry. It performs a read-only cross-resource audit for one Resource Pack client entity; it does not generate or rewrite any files.

## What it checks

1. Confirms the selected project is an existing linked BP/RP scaffold and reads only within that project.
2. Inventories the entity's `description.animations`, `description.geometry` and `description.scripts.animate` references.
3. Indexes exact animation identifiers from RP `animations/`, controller identifiers from `animation_controllers/`, and geometry identifiers from `models/entity/`.
4. Detects missing, duplicated or ambiguous definitions and unresolved aliases.
5. Checks that each controller state's animation entries refer to aliases in this client entity and that transition destinations resolve to states in the same controller.
6. Checks nested controller references for cycles.
7. Compares clip bone names with the bones in every geometry variant declared by this client entity. Unknown names are warnings, not automatic proof of a broken pack; a clip may intentionally target a different geometry variant.
8. Performs bounded structural checks on clip lengths, channels, keyframe timestamps, numeric duplicate timestamps and discontinuous pre/post keyframes. JSON object property order is not treated as semantic keyframe order.

## Interpretation

- `HIGH` findings are exact missing/ambiguous resources, invalid graph references or unsafe/malformed inputs.
- `WARNING` findings include potential bone mismatches and suspicious controller cycles; consider the specific entity/geometry context before changing anything.
- `INFO` findings describe nonstandard or external/dynamic references that this static index cannot resolve.
- `analysis_complete=false` means a scan limit, unsafe path or parse failure reduced coverage. Do not treat a partial graph as a clean audit.
- Vanilla resources outside this RP may be external dependencies. Missing identifiers that share the client entity's namespace are reported as local missing resources; different-namespace and unqualified identifiers are conservatively reported as external/uncertain `INFO` references. This namespace heuristic is not proof of pack ownership.

## Limits

The audit does not evaluate Molang, infer dynamic resource names, execute scripts, render geometry, measure interpolation/blending, or launch Minecraft. It is not a complete engine schema validator. In-game behavior remains `NOT RUN` unless a real target-version test was performed.

## Required report

Report entity identifier, files scanned/parsed by category, resolved alias counts, controller state/transition counts, findings with exact paths and JSON pointers, `analysis_complete`, Molang status and Minecraft runtime status. Never delete a resource based solely on this audit.
