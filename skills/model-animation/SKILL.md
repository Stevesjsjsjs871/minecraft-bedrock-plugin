---
name: model-animation
description: Use for Minecraft Bedrock geometry, Blockbench models, bone hierarchies, cube bounds, pivots, UVs, textures, animation clips/controllers, render controllers, attachables, and visual debugging.
---

# Bedrock Model, UV, Texture and Animation Engineering

## Evidence and target compatibility
- Default target is Minecraft Bedrock 1.26.50 unless the user specifies otherwise. Never infer support only from a newer sample or Java Edition format.
- Verify version-sensitive format/API assumptions against the official Creator documentation and a matching Mojang sample/release. Secondary reference: https://wiki.bedrock.dev/.
- Label conclusions `CONFIRMED`, `STATICALLY VERIFIED`, `RUNTIME TESTED`, `INFERRED`, or `NEEDS VERIFICATION`. A parseable JSON file is not proof of an engine-valid asset.

## Model intake and dependency graph
1. Identify the pack root, `manifest.json`, target resource category (entity, block, attachable, item-held geometry or player-related resource), and the exact file set before editing.
2. Build a reference graph rather than checking files in isolation: client entity -> geometry identifier(s), texture aliases/paths, render controllers, animations and animation controllers; geometry identifier -> geometry file; animation/controller identifiers -> definitions; script or entity references -> exported names. Report unresolved references with evidence and confidence.
3. Preserve original geometry identifiers, bone names, pivots, cube data, UV layout and references unless a requested feature requires changes. Do not replace detailed assets with placeholders.
4. Distinguish actual file paths (case and extension matter in packaged assets) from identifiers such as `geometry.foo`; do not pretend identifiers are paths.

## Geometry and bone checks
- Parse every geometry JSON and verify the expected top-level structure and geometry array/object shape before detailed checks.
- Check duplicate geometry identifiers; duplicate bone names within a geometry; parent names that do not resolve; self-parenting and hierarchy cycles; likely unreachable/orphan bones; and malformed pivot/rotation/vector shapes.
- Review cubes for `origin`, `size`, optional `pivot`/`rotation`, inflate, mirror and UV definitions. Flag negative or suspicious dimensions for review, not automatic correction.
- Confirm pivots and rotations are interpreted in the correct coordinate frame. Preserve intentional offsets; don't normalize values merely to make the model look conventional.
- Validate references to bone names in animations against actual geometry bones, while allowing deliberately dynamic or optional resources only when evidence explains them.

## UV and texture validation
- Resolve texture paths from the actual client-entity/attachable/block resource context and check that referenced files exist. Apply case-sensitive path checks in addition to normalized checks.
- Inspect texture dimensions, alpha channel, file type and obvious decode errors when image tools are available. Compare dimensions with geometry UV expectations where reliably inferable.
- Handle both supported UV representations conservatively; do not assume every face uses a two-number box. Flag missing, malformed or out-of-bounds UVs with exact geometry/bone/cube/face evidence where possible.
- Distinguish intentional transparent regions, mirrored faces, atlas use, and pixel-art seams from confirmed errors. Never repaint or regenerate a texture without user authorization if it would overwrite original art.
- Generated concept art is not a ready-to-import texture until size, transparency, UV mapping, palette, and seams have been checked.

## Animation and controller validation
For each animation definition:
- Validate JSON shape, identifier uniqueness, targeted bone names, channel value forms, keyframe time ordering/format, and clearly malformed numeric vectors.
- Check `loop`, `animation_length`, blend settings and keyframe interpolation conservatively; version-dependent syntax must be verified rather than rejected by guesswork.
- Resolve animation names referenced from client entities, animation controllers, scripts, and render controllers where applicable.

For animation controllers:
- Validate controller identifiers, state maps, initial/default state conventions, transition target states, animation/sound/particle references, and state references against actual definitions.
- Flag suspicious transition expressions and missing state names. Expressions may depend on Molang/runtime conditions; do not attempt to prove their runtime truth from static text alone.
- Look for conflicting animation ownership of the same bones/channels and define an interruption/priority test plan instead of automatically deleting a clip.

For render controllers:
- Validate identifier uniqueness; geometry, texture, and material alias keys; resolved aliases; and references to expected resource identifiers.
- Treat Molang expressions and engine-specific semantics as requiring docs/runtime verification unless they are directly proven invalid.

## Safe implementation workflow
1. Record baseline file list and hashes for model/animation-related files.
2. Make the narrowest patch and preserve unrelated asset data.
3. Re-run JSON parsing, structural checks, identifier/reference checks, texture path/decode checks, and baseline diff.
4. Inspect changed geometry/texture/animation visually when rendering tools exist. Otherwise say visual review was not available.
5. Package the full necessary BP/RP roots, then re-run archive integrity and path checks.

## Required report
Include: project/target version; files and identifiers examined; geometry and bone findings; texture/UV findings; animation/controller/reference findings; additions/removals/modifications; checks run and actual results; false-positive/heuristic caveats; exact in-game scenarios still needed. Mark Minecraft visual/runtime tests `NOT RUN` unless actually performed. Do not publish a release or silently delete assets.
