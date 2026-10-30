---
name: animation-clip-authoring
description: Use when creating, editing, or auditing Minecraft Bedrock RP animation clips, including bone rotation/position/scale channels, keyframes, animation aliases, and linking animation clips to an entity's animation controller.
---

# Bedrock Animation Clip Engineering

## Purpose and relationship to controllers

Animation clips contain the raw time-based transform data for model bones. Animation controllers are state machines that decide when clips play. Keep these responsibilities separate:

- `animations/<slug>.animation.json` defines the clip and its bone keyframes.
- The client entity's `description.animations` maps a short alias to the full `animation.namespace.name` identifier.
- An animation controller state references that short alias in its `animations` list. When a controller owns playback, do not also add the alias to `scripts.animate` unless direct playback is independently intended.

Default target is Bedrock 1.26.50 unless the user states otherwise. Confirm version-sensitive conventions with the corresponding official Creator documentation and Mojang sample release.

## Authoring workflow

1. Confirm an existing linked BP/RP project and the intended RP client-entity JSON. Never create a second scaffold or replace an existing entity.
2. Inspect the entity's `description.animations` and `description.geometry` maps. Choose unique aliases; do not remap an alias already used by another resource.
3. Inspect the target geometry and exact bone names. Bedrock matches animation bone names to geometry bones; unrecognized names are ignored by the engine, so report them as warnings rather than silently assuming they work.
4. Define animation length, looping behavior, and required bone channels (`rotation`, `position`, `scale`). Keep values to numeric scalars/vectors or bounded Molang text. Rotation values use degrees, in X/Y/Z order.
5. Define keyframes in strictly increasing time order, within the clip's declared duration. Use either a single `value`, or both `pre` and `post` for a discontinuous keyframe. Do not invent cubic/bezier interpolation: the built-in static authoring contract currently targets supported linear keyframing and explicit pre/post values.
6. Use `create_animation_clip` to write a new RP clip and register its alias in `description.animations`. The tool refuses output/identifier collisions, unsafe paths, invalid manifests and invalid keyframe data. It leaves `scripts.animate` and controller files unchanged.
7. Reference the new alias in an existing animation controller state, or choose direct playback through `scripts.animate` when there is no controller. Validate the controller after any binding change.
8. Run `validate_animation_clip`, the broader resource graph and pack audit. Check that model geometry, animation identifiers, aliases and controller references resolve.
9. Import into the target Bedrock build and verify actual movement, loop boundaries, interpolation, blending, animation priority and controller transitions.

## Tool constraints

- `create_animation_clip` writes one new file under RP `animations/` and updates one existing client entity's `description.animations` map.
- `validate_animation_clip` is read-only.
- The current generator emits `format_version: 1.8.0` and supports `rotation`, `position`, and `scale` channels with numeric or text-bounded Molang values.
- Keyframe times must be finite, nonnegative, strictly increasing and no later than `animation_length`.
- Limits are intentional: 64 bones, 128 keyframes per channel, 512 total keyframes, 600 seconds per clip, and 512 characters per Molang expression.
- Geometry lookup is static. Ambiguous or unavailable geometry is reported as such; missing bone names are warnings because engine behavior ignores unmatched bone names.
- Molang receives printable-string and length checks only. It is not parsed, evaluated or executed by the plugin.
- Existing output files and animation identifiers are never overwritten. The operation is workspace-confined, rejects symlinks/path traversal, detects concurrent client-entity changes and removes the new clip if the alias update fails.

## Required report

Report target game version, project/entity/animation identifiers, alias, duration, loop setting, bones/channels/keyframes, geometry match and unknown-bone warnings, files created/updated, exact static checks, Molang limitations, and runtime status. Use `NOT RUN` for Minecraft runtime unless the target game was genuinely launched and tested.

## Reference

See `references/idle-bob.example.json` for a minimal looped two-keyframe clip. The official reference describes the animation hierarchy, aliases, transforms and pre/post keyframes: https://learn.microsoft.com/en-us/minecraft/creator/documents/animations/animationsoverview?view=minecraft-bedrock-stable
