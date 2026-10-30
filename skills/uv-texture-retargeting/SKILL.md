---
name: uv-texture-retargeting
description: Convert a reviewed image reference into a Bedrock entity texture in one guarded operation by validating explicit source crops and exact geometry UV face selectors, planning the mapping, applying PNG transfer, and verifying the result.
---

# UV Texture Retargeting

Use `retarget_texture_to_entity` when a creator has a reference sheet and an existing Bedrock geometry and wants the reviewed texture mapping applied in one request.

## Required inputs

- Existing project directory.
- Exact `.geo.json` path and geometry identifier.
- Reference PNG already in the selected Resource Pack.
- New output PNG path under `textures/entity/`.
- One or more explicit source crop rectangles (`x`, `y`, `width`, `height`) mapped to exact geometry selectors (`bone`, `cube_index`, `face`).
- A short human-authored semantic label for every mapping.
- `approved: true` for every assignment and `review_confirmed: true` at the request level, set only after visual inspection.

Do not guess which pixels depict the head, torso, limbs, armor or other semantic parts. Use an image viewer and the geometry UV template/UV inventory to establish each crop and face mapping. The deterministic visual-reference analyzer is a region inventory aid; its geometric candidate scores are not semantic confidence.

## Execution sequence

1. The server hashes the geometry and reference files and verifies that they are safe, bounded project files.
2. It runs `analyze_visual_reference` for diagnostics and checks that the analyzed PNG hash matches the input hash.
3. It calls `build_uv_mapping_plan` with the reviewed assignments. The planner checks source rectangles, selector expansion, UV bounds, duplicate targets, overlaps and optional full coverage.
4. If the plan is not executable, the operation stops before writing.
5. It calls `map_reference_texture_to_uv` with the transfer request, creating a new PNG without overwriting any existing file.
6. It rechecks geometry/reference hashes, validates the output PNG, verifies dimensions against the geometry texture canvas and compares the output SHA-256 with the transfer result.

## Safety and scope

- Source geometry and reference PNG are read-only.
- Existing output paths are refused by the transfer engine.
- Overlap, layered assignments and full-coverage requirements are explicit controls. Keep overlap disabled unless the shared pixels are intentional.
- `review_confirmed` is an explicit approval gate, not a claim that the model recognized semantics automatically.
- Current support is for geometry cube UV formats understood by the existing UV tools. Unsupported mesh formats are not silently projected.
- This performs 2D texture-space transfer. It does not emulate Bedrock face sampling, lighting, normals, material rendering, mipmaps, seam bleed, animation or 3D projection.
- Minecraft import, in-game rendering, Blockbench interoperability and runtime behavior remain `NOT RUN` unless separately tested.

## Example

See `references/retarget-request.example.json`. Paths are illustrative and must be changed to files that exist in the active project.
