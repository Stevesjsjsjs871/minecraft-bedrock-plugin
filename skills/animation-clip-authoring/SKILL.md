---
name: animation-clip-authoring
description: Use when creating or auditing Minecraft Bedrock RP animation clips, bone transform channels, keyframes, aliases, and their client-entity or controller bindings.
---

# Bedrock Animation Clip Engineering

## Purpose and boundary

This Skill guides manual authoring and review of RP animation JSON. The current Skills-only package does not contain live `create_animation_clip` or `validate_animation_clip` tools. Do not call historical MCP names or claim that a generator ran. Use a real file/code route; otherwise provide a complete patch and mark it `NOT APPLIED`.

## Inputs and compatibility

Confirm the exact Bedrock target version/build, RP root, client-entity file, geometry identifier, animation identifier/namespace, intended alias, duration, looping behavior and requested motion. Inspect existing aliases and clips to avoid collisions. Read the target-version official Creator documentation and matching Mojang sample before relying on format-sensitive interpolation or `format_version` behavior. The bundled examples are reference data, not engine validation.

## Authoring workflow

1. Confirm the existing linked BP/RP project and authoritative baseline. Do not create a second scaffold.
2. Read the client entity's `description.animations`, `description.geometry` and `description.scripts.animate`. Choose a new, unique clip identifier and alias; do not remap an existing alias without explicit approval.
3. Inspect the selected geometry variant and exact bone names. Compare every animated bone against that geometry; mark intentional variant-specific names and unknown names for review.
4. Define the animation object using the target-version schema. Specify `animation_length`, looping behavior and only supported channels (`rotation`, `position`, `scale`). Rotation values use degrees and the documented axis order. Use finite numeric values or documented Molang expressions.
5. Keep keyframe timestamps within the clip duration and in the format/order required by the target version. Use only documented interpolation values and pre/post semantics. Do not assume cubic/bezier support from an unrelated sample or static checker.
6. Add the new `.animation.json` file under the RP `animations/` tree and update only the relevant client-entity alias map. Refuse collisions and preserve unrelated aliases.
7. Bind playback through a controller state or direct `scripts.animate` entry. If a controller owns playback, avoid a duplicate direct playback binding unless deliberately required.
8. Run JSON/duplicate-key checks and the available end-to-end entity graph audit: `python skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py --bp-root <BP> --rp-root <RP> [--entity-id namespace:name]`. That audit checks literal resource/alias relationships; it is not a complete animation schema or keyframe engine validator.
9. Compare against baseline, inspect exact diffs, and import into the exact game build to test movement, loop boundaries, interpolation, blending, priority, interruption and reload.

## Safety and limits

- Do not overwrite an existing clip or silently remap an alias.
- Keep every file inside the selected RP; reject traversal, symlink escapes, malformed JSON and duplicate keys.
- Molang is not evaluated by this workflow unless a real engine runtime evaluates it; report it as `NOT EVALUATED` for static checks.
- Static graph audit does not prove interpolation, blending, animation priority or renderer behavior.
- Do not hard-code generator-specific limits as Bedrock engine limits. Apply only limits evidenced by the exact tool/schema being used.

## Required report

Report target version, entity/geometry/animation identifiers, alias, clip duration and loop mode, animated bones/channels/keyframes, source used for version-sensitive semantics, files changed, static checks and exact results, baseline delta, unknown bone/alias findings, Molang status, and Minecraft runtime status (`NOT RUN` unless actually tested).

## Reference

See `references/idle-bob.example.json` for a minimal illustrative looped clip. Check the official animation documentation for the target view/version before copying its format or interpolation behavior.
