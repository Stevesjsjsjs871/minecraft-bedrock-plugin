---
name: visual-resource-pipeline
description: Use for Minecraft Bedrock entity/block visual assets, geometry, UVs, animations, textures and RP resource-link validation.
---

# Visual resource pipeline

Default reference baseline is Bedrock 1.26.50 unless the project specifies another version. Start with `skills-first-execution`; this is a workflow, not a remote tool suite. Do not call historical MCP tool names. Use bundled scripts only when a real executor can access them and their documented inputs.

## 1. Inventory and source
Inspect geometry, client entities, render controllers, materials, animations/controllers, atlas files, PNGs and localization. Record identifiers, texture dimensions and references. Use exact-version Mojang Samples and official Creator docs; record provenance. Do not execute scripts from third-party packs.

## 2. Geometry and UV
- Run `python skills/geometry-uv-engine/scripts/geometry_engine.py <geometry.geo.json>` for a static parse of the selected geometry identifier, bones/cubes, declared texture canvas, classic/per-face UV bounds and overlaps. Also inspect format version, parent hierarchy and pivots; these broader checks are not all emitted by the current CLI.
- Inspect classic box UV and supported per-face UV forms; check bounds, `uv_size`, rotations and intentional overlaps.
- Run `skills/geometry-uv-engine/scripts/geometry_engine.py` for standalone static geometry/UV bounds and overlap analysis; follow `geometry-uv-template-authoring` only as guidance because template rendering is not yet a standalone executable. Their previous server implementations are dormant migration sources; automatic UV audit/template generation is `NOT RUN` until standalone CLIs are migrated and tested.
- A generated UV guide is a separate reference image, never the entity production texture.
- Unsupported mesh forms must be reported as outside audit scope, not silently passed.

## 3. Texture authoring
The bundled `scripts/png_engine.py` is a standalone PNG structural validator. Run `python skills/visual-resource-pipeline/scripts/png_engine.py <texture.png>` to check signature, chunk CRCs, IDAT decompression, scanline sizes/filters and dimensions. Its focused tests are in `test_png_engine.py`. The bundled `scripts/generate_texture.py` is a deterministic standard-library PNG generator, not AI image synthesis. Inspect its `--help` and tests before execution. It supports implemented procedural styles only; do not claim it creates a hand-painted or semantically accurate skin. Preserve the original texture and write a distinct output unless overwrite was explicitly authorized.

For geometry-aware painting or reference transfer, follow `texture-painting-pipeline`, `uv-mapping-assistant`, `reference-mapping-review` and `reference-texture-transfer`. Use exact bone/cube/face selectors and explicit source crops. Require human review for semantic correspondence; geometric ranking is not semantic recognition. Validate source/output PNGs, dimensions, alpha, UV coverage and overlaps only where a real implementation is available; do not invoke retired server wrappers as tools.

## 4. Animation and render linkage
Verify client-entity aliases, geometry/material/texture declarations, render-controller references, animation aliases, controller states, transitions, Molang expressions and animated bone names. A syntactically valid animation is not proof that it plays in-game.

## 5. Texture/resource references
Inspect BP item/block definitions and RP atlases/localization. Resolve atlas keys to actual PNG paths and validate PNG decoding/dimensions. If the available auditor lacks a dedicated atlas mode, perform explicit file/reference checks; never claim a historical MCP texture-link auditor was called.

## 6. Output and limits
Report exact files/selectors, generated vs supplied assets, image hashes/dimensions, mapped/unmapped faces, overlap warnings, source provenance and tests. Deterministic pixel operations are 2D; they do not simulate 3D projection, renderer face orientation, lighting, mipmaps or seams. Minecraft import/rendering and Blockbench interoperability remain `NOT RUN` until tested.
