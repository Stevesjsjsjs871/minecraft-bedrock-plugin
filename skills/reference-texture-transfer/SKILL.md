---
name: reference-texture-transfer
description: Plan a reviewed 2D reference-crop to Bedrock cube-UV texture transfer without claiming an unavailable automatic painter.
---

# Reference Texture Transfer

## Capability boundary

The package does not contain an active reference-to-UV pixel-transfer script. This Skill prepares a deterministic, reviewable mapping plan; it does not write or modify a PNG. Do not describe retained legacy server code as an available painter.

## Inputs

- Exact Bedrock .geo.json and geometry identifier.
- Declared texture width and height.
- Reference PNG supplied by the user or accessible through an authorized image/file capability.
- Explicit integer source rectangles.
- Exact target bone, cube index and face selectors.
- Optional existing base texture and a new output path.

## Mapping plan

For each assignment, record a stable mapping ID and human-authored semantic label; source rectangle in reference-image pixels; target bone, cube index and face; rotation and flips; sampling and alpha/blend intent; overlap or shared-UV status; reviewer decision and unresolved uncertainty.

Use the standalone geometry engine to inspect supported cube-face UV bounds and the UV template renderer to produce a separate guide. Neither script infers semantic correspondences from a reference image.

## Safe workflow

1. Hash and preserve the original geometry, reference image and optional base texture when a real file executor is available.
2. Inspect the reference visually and select crops manually. If the image is not accessible, stop at a plan and mark mapping BLOCKED.
3. Validate each crop against the source image dimensions and each target against the selected geometry UV bounds.
4. Review shared or overlapping UV regions explicitly. Do not overwrite the source texture.
5. If an authorized external image editor or separately tested local transfer implementation is available, create a new output path and record the exact operation. Otherwise provide the mapping plan only.
6. Validate any produced PNG with the standalone PNG validator and compare its dimensions with the geometry texture canvas.

## Limits

No automatic 3D projection, semantic segmentation, UV unwrapping, face-orientation simulation or AI inpainting is provided by this Skill. Static bounds and PNG checks do not prove Bedrock rendering. Report Minecraft and Blockbench checks as NOT RUN until actually performed.
