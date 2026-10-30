---
name: texture-painting-pipeline
description: Use to plan and perform geometry-aware Bedrock texture painting with explicit UV selectors, deterministic pixel operations and source preservation.
---

# Texture painting pipeline

This is a Skills-only workflow. Do not call historical `paint_geometry_texture` or other MCP tool names as if they were active integrations. If an actual code executor and a supported local script are available, inspect the script contract before running; otherwise produce a precise paint plan or output asset through an available image/file capability.

## Inputs and preflight
Identify the exact `.geo.json`, target texture dimensions, base PNG (if any), output path, selected bones/cubes/faces, operations and colors. Validate geometry identifier, cube/face UV bounds, texture canvas, source PNG decoding and path containment. Refuse ambiguous selectors, symlink escapes and unintended overwrites.

## Operation planning
Specify each operation in deterministic order: target selector, fill/border/checker/stripes/gradient/noise operation, palette, opacity/blend and seed where applicable. Preserve untouched pixels and alpha when a base texture is supplied. For overlaps, report exact pairs and require explicit approval before painting shared regions.

## Reference transfer
Use `reference-mapping-review` before transferring semantic regions. Bind the review to exact reference and geometry hashes; require explicit human-approved labels, crops and face selectors. Never infer that a portrait region maps to a particular 3D face solely from geometric similarity.

## Validation
Check output PNG signature/chunks/decompression, dimensions, alpha and SHA-256; rerun UV bounds/overlap checks; inspect a visual preview if available. Write a separate output unless replacement was expressly requested. Record every mapped/unmapped region.

## Limitations
These are deterministic 2D pixel operations, not semantic AI texture synthesis or 3D projection. They do not prove Bedrock face orientation, seams, lighting, mip behavior or renderer output. Mark Minecraft import/rendering `NOT RUN` until tested.
