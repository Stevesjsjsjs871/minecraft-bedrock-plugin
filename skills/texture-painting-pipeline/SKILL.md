---
name: texture-painting-pipeline
description: Use to plan and perform geometry-aware Bedrock texture painting with explicit UV selectors, deterministic pixel operations and source preservation.
---

# Texture painting pipeline

This is a Skills-only workflow. Do not call historical `paint_geometry_texture` or other MCP tool names as if they were active integrations. The deterministic painter is a bounded local utility at `skills/texture-painting-pipeline/scripts/texture_painter.py`. It is not a ChatGPT-host Tool; run it only when a real local executor can access both the package and project. Otherwise prepare the exact paint plan or produce an asset through an actually available image/file capability.

## Inputs and preflight
Identify the exact `.geo.json`, target texture dimensions, base PNG (if any), output path, selected bones/cubes/faces, operations and colors. Validate geometry identifier, cube/face UV bounds, texture canvas, source PNG decoding and path containment. Refuse ambiguous selectors, symlink escapes and unintended overwrites.

## Operation planning
Specify each operation in deterministic order: target selector, fill/border/checker/stripes/gradient/noise operation, palette, opacity/blend and seed where applicable. Preserve untouched pixels and alpha when a base texture is supplied. For overlaps, report exact pairs and require explicit approval before painting shared regions. The local utility supports `fill`, `border`, `checker`, `stripes`, `gradient` and deterministic `noise`; it enforces a 128-operation cap, bounded PNG/JSON sizes, UV region/texel budgets, path containment, symlink checks and exclusive output creation. Use `skills/texture-painting-pipeline/references/texture-painting-request.example.json` as the request shape and `python skills/texture-painting-pipeline/scripts/texture_painter.py --help` for CLI arguments.

## Reference transfer
Use `reference-mapping-review` before transferring semantic regions. Bind the review to exact reference and geometry hashes; require explicit human-approved labels, crops and face selectors. Never infer that a portrait region maps to a particular 3D face solely from geometric similarity. When a local executor is available, the deterministic utility is `skills/uv-texture-retargeting/scripts/reference_transfer.py`; supply a JSON request based on `skills/uv-texture-retargeting/references/reference-transfer.example.json`. It preserves pixels outside mapped regions when a matching base texture is provided, refuses overwrite, checks PNG integrity and UV overlap, and reports SHA-256. Run `python skills/uv-texture-retargeting/scripts/reference_transfer.py --help` for the CLI contract.

## Validation
Check output PNG signature/chunks/decompression, dimensions, alpha and SHA-256; rerun UV bounds/overlap checks; inspect a visual preview if available. Write a separate output unless replacement was expressly requested. Record every mapped/unmapped region.

## Limitations
The painter is a standalone local script, not an installed Skill executor. Its supported PNG codec is limited to 8-bit non-interlaced PNG color types 0/2/3/4/6. These are deterministic 2D pixel operations, not semantic AI texture synthesis or 3D projection. They do not prove Bedrock face orientation, seams, lighting, mip behavior or renderer output. Mark Minecraft import/rendering `NOT RUN` until tested.
