---
name: texture-painting-pipeline
description: Plan Minecraft Bedrock entity texture work against geometry UVs while preserving source images and distinguishing real generators from unavailable painters.
---

# Texture Painting Pipeline

## Capability boundary

The package does not include a geometry-aware texture painter. The bundled texture generator creates only the deterministic procedural styles implemented by its script; it is not a semantic skin painter, image inpainting system or reference-transfer engine.

Use an actual authorized image editor or file/code capability only when it is available. Otherwise return a paint plan, pixel map or reviewable output specification and mark image editing NOT APPLIED.

## Inputs and preflight

Identify the exact .geo.json, geometry identifier, texture canvas dimensions, base PNG, desired output path, target version and intended visual result. Preserve the original texture. Use the standalone geometry audit and UV guide renderer to inspect supported cube-face layouts when a real executor can access them.

## Planning workflow

1. Inventory geometry bones/cubes and supported UV faces.
2. Record texture dimensions and verify that the base PNG matches the declared canvas.
3. Define intended edits in texture-space coordinates and map each region to exact geometry selectors.
4. Mark shared/mirrored UVs and overlaps for explicit review.
5. Separate user-authored semantic decisions from geometric bounds calculations.
6. If the procedural generator is suitable, inspect its current help and supported styles before use. Do not describe its output as hand-painted or semantically accurate.
7. If an external editor is used, write a distinct output file, preserve the source and record the editor/version and changed-file hashes.

## Completion checks

Validate output PNG integrity and dimensions with the standalone PNG validator. Re-run geometry and resource-link checks where applicable. Report pixel coverage and unresolved regions honestly.

Static texture-space work does not simulate Bedrock 3D face orientation, lighting, mipmaps, seam bleed or materials. Minecraft rendering and Blockbench inspection remain NOT RUN until actually performed.
