---
name: reference-mapping-review
description: Prepare a human-reviewed mapping from visible reference-image crops to exact Minecraft Bedrock geometry UV faces.
---

# Reference Mapping Review

## Purpose and capability boundary

This is a manual review workflow. The package does not include an automatic image-region analyzer or a mapping-review service. Do not claim that the plugin detects semantic body parts or approves a transfer automatically.

## Required inputs

- A reference image supplied in the conversation or available through a real image-viewing capability.
- Exact target .geo.json and geometry identifier.
- Geometry UV inventory or a generated UV guide from the standalone renderer.
- Explicit source crop rectangles selected by a human.
- Exact bone, cube index and face selectors for each destination.

## Review procedure

1. Inspect the supplied reference image. If the image is unavailable to the current host, mark the review BLOCKED rather than inventing regions.
2. Give each proposed source crop a stable local label and record its pixel bounds.
3. Match each crop to one exact geometry bone, cube index and face: north, south, east, west, up or down.
4. Record source crop, destination selector, rotation, flips, sampling intent, opacity, overlap and human decision in a review table.
5. Mark uncertain mappings NEEDS REVIEW. Do not treat aspect ratio, area or color similarity as semantic confidence.
6. Use the standalone geometry engine and UV guide renderer only for their documented geometry/UV coverage. They do not analyze reference-image semantics.
7. Produce a transfer request or manual editing plan only. No texture is written by this Skill.

## Approval and limits

Every semantic assignment requires explicit human review. Shared UVs, mirrored faces, seams and face orientation must be reviewed against the actual geometry. Poly-mesh and texture-mesh formats are outside the documented cube-face workflow.

A review table is not a generated texture. Actual pixel transfer requires a real image editor or an independently implemented, tested local script. Minecraft face sampling, lighting, seams and rendering remain NOT RUN until tested in game.
