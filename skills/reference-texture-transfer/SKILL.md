---
name: reference-texture-transfer
description: Use when transferring parts of a user-provided or externally generated reference PNG onto explicitly selected Minecraft Bedrock geometry UV faces.
---

# Reference texture transfer

## Purpose

Use `map_reference_texture_to_uv` to map one or more rectangular crops from a 2D PNG reference onto selected bone/cube/face UV rectangles from a Bedrock `.geo.json`. This bridges a prepared reference sheet and the existing UV painter without inventing a 3D projection.

## File placement

- Geometry must live under `resource_packs/<project>_RP/models/entity/`.
- Reference PNG must be inside `resource_packs/<project>_RP/textures/`; a dedicated folder such as `textures/references/` is recommended.
- Optional base texture must live under `resource_packs/<project>_RP/textures/entity/` and match the geometry's declared `texture_width` and `texture_height` exactly.
- Output is a new PNG under `resource_packs/<project>_RP/textures/entity/`. Existing files are never overwritten.

## Mapping contract

Each mapping has:

- `selector`: at least one of `bone`, `cube_index`, or `face` (`north`, `south`, `east`, `west`, `up`, `down`). Use all three when targeting one exact face.
- `source_rect`: integer pixel rectangle `{ "x": 0, "y": 0, "width": 16, "height": 16 }` inside the reference PNG.
- Optional `rotation`: `0`, `90`, `180`, or `270`, plus `flip_x` / `flip_y`. Rotation is applied first, then the horizontal/vertical flips.
- `sampling`: `nearest` for pixel-art preservation or `bilinear` for smoother down/up-sampling. Bilinear sampling uses premultiplied alpha to avoid common transparent-edge color fringes.
- `opacity` and `blend_mode` (`over` or `replace`). `over` is source-over alpha compositing; `replace` copies the reference RGBA including its alpha after opacity scaling.

Mapping order is deterministic. If geometry UV islands overlap, or if multiple mappings select the same target region, the tool refuses by default. Set `allow_uv_overlap: true` only when sharing/ordered layering is intentional; later mappings win on shared texels.

## Important limitations

- The tool transfers caller-selected 2D source rectangles. It does not infer which parts of a character portrait correspond to 3D faces, automatically unwrap a model, generate artwork, or perform AI inpainting.
- `uv_rotation`, negative `uv_size`, UV mirroring and the engine's face-specific 3D sampling orientation are not simulated as a rendered 3D view. The transfer maps into the occupied texture-space rectangle; choose source orientation explicitly with `rotation` and flips.
- Source PNGs must be 8-bit, non-interlaced and supported by the installed PNG decoder. Fully validate inputs and outputs. Optional base textures must match the geometry canvas dimensions.
- `poly_mesh` and `texture_meshes` are outside the cube-face UV mapping scope.
- It does not add texture references to client entities or render controllers. Register/link the generated output explicitly, then run the geometry UV audit and texture-link checks where applicable.
- Static PNG/JSON checks do not prove Minecraft rendering. Import, visual inspection, mip/seam bleed and runtime remain `NOT RUN` until tested in the target game build.

## Recommended workflow

1. Inspect geometry and generate a labeled UV template.
2. Prepare a reference sheet with known, clearly separated source rectangles (AI-generated art may be used as an input, but must be reviewed and mapped explicitly).
3. Map one or more source rectangles to exact geometry bone/cube/face selectors; use `nearest` for pixel art and `bilinear` when soft resampling is intended.
4. Use the existing texture as `base_texture_path` when unmapped pixels must be preserved.
5. Review overlap warnings and the generated PNG; run geometry UV and resource-link audits.
6. Import into the exact Minecraft Bedrock target build and inspect every face. Record visual/runtime tests separately.

See `references/reference-transfer.example.json` for a compact example.
