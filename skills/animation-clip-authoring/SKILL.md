---
name: animation-clip-authoring
description: Design and manually author Minecraft Bedrock RP animation clip JSON with verified bone names, keyframes and client-entity aliases.
---

# Bedrock Animation Clip Engineering

## Capability boundary

This Skill provides format guidance and a review workflow. The package has no active animation-clip writer or dedicated clip validator. Do not claim that a script automatically writes a clip or updates a client entity. Use an actual authorized file capability or return the complete JSON files and mark them NOT APPLIED.

## Relationship to controllers

- An RP animation file defines time-based transforms for model bones.
- The client entity's animation map exposes aliases for animation and controller identifiers.
- A controller state references the intended animation aliases.
- Direct playback and controller-owned playback must not be mixed accidentally. Verify the intended binding against exact-version documentation.

## Authoring workflow

1. Confirm the linked BP/RP project, exact target version and intended client-entity JSON.
2. Inventory existing geometry identifiers, bone names and animation aliases. Choose new unique identifiers; never remap an existing alias without explicit approval.
3. Confirm every animated bone exists in the selected geometry. Report missing or differently cased bone names.
4. Define clip length, looping intent, channels and keyframes. Keep keyframe times within the declared duration and in the format/order supported by the target version.
5. Verify rotation units, vector ordering, interpolation and pre/post semantics against matching official Creator documentation and Mojang Samples. Do not invent interpolation modes or rely on examples from another version.
6. Produce the animation JSON and the necessary client-entity alias changes as separate reviewable edits. Preserve unrelated aliases and controller bindings.
7. Parse the JSON and run the entity pipeline audit when its actual script and project roots are accessible. The audit is a resource-graph check, not a complete animation-schema or Molang validator.
8. Re-open the output and compare it with the baseline.

## Required report

List the clip identifier, target geometry, bone coverage, channels, duration, loop intent, alias changes, static checks, unresolved assumptions and runtime status.

Minecraft import, animation playback, interpolation, blending, controller transitions and multiplayer behavior remain NOT RUN until tested in the exact target Bedrock build.
