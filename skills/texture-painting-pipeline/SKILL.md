---
name: texture-painting-pipeline
description: Use when creating or revising a Minecraft Bedrock entity texture from its actual geometry UV mapping, preserving an optional source PNG and applying explicit pixel-art operations.
---

# Geometry-aware texture painting pipeline

Use `minecraft-bedrock-texture-painter` and `paint_geometry_texture` after confirming the selected `.geo.json` and the exact canvas dimensions.

## What the tool does

The tool extracts UV rectangles from the selected geometry using the same region parser as `generate_geometry_uv_template`. It supports classic box UV and per-face UV rectangles, then applies ordered deterministic pixel operations selected by bone, cube index, and/or face. Operations are `fill`, `border`, `checker`, `stripes`, `gradient`, and seeded `noise`.

The result is a **new** RGBA8 PNG. The source geometry and source texture are never modified. If `source_texture_path` is supplied, its 8-bit non-interlaced pixels are decoded and used as the starting canvas; unpainted pixels and their alpha remain unchanged. Supported source color types are grayscale, RGB, indexed/palette, grayscale-alpha, and RGBA. Interlaced and 16-bit source PNGs are rejected rather than silently altered. Without a source PNG, the canvas starts transparent unless `background_color` is provided.

## Input contract

- `project_directory`: existing project directory directly under `MINECRAFT_BEDROCK_WORKSPACE`.
- `geometry_path`: project-relative path under `resource_packs/<project>_RP/models/entity/`.
- `geometry_identifier`: required when the file contains multiple geometries, or when one identifier is duplicated.
- `source_texture_path`: optional existing PNG under the same Resource Pack `textures/entity/` directory. Its dimensions must exactly equal geometry `texture_width` and `texture_height`.
- `output_path`: a new PNG under the Resource Pack `textures/entity/` directory; existing outputs are refused.
- `operations`: 1–128 ordered operations. Each `selector` must name at least one of `bone`, `cube_index`, or `face`; every selector must match at least one supported UV region.

Example operation:

```json
{
  "selector": {"bone": "head", "face": "north"},
  "mode": "gradient",
  "color": "#26384D",
  "secondary_color": "#8BA6BA",
  "axis": "y",
  "opacity": 255,
  "blend_mode": "over"
}
```

`blend_mode: over` alpha-composites onto the current canvas; `replace` writes the operation's RGBA values directly. Pattern operations use the face rectangle's texture-space coordinates. `border` paints the border and leaves its interior unchanged unless `secondary_color` is supplied, in which case the interior receives that color.

## Safety and interpretation

- UV rectangles outside the declared canvas cause a hard refusal; the tool does not clip or rewrite the geometry.
- UV overlaps require explicit `allow_uv_overlap: true`. This is a conscious opt-in because later paint operations may overwrite pixels shared by mirrored or intentionally reused faces.
- Per-face negative `uv_size` and rotations are represented by the occupied rectangle; the tool does not simulate the engine's face sampling orientation or apply a 3D projection.
- Fractional UV boundaries are handled by pixel-center coverage. The report does not claim engine-identical rasterization for fractional coordinates.
- PNG integrity is validated before decode and after encode. Decoding is dependency-free and limited to 8-bit non-interlaced PNGs.
- Output paths are Resource-Pack-confined, symlinks/traversal are refused, and output creation uses exclusive no-overwrite semantics.
- This is deterministic structured 2D painting, not AI image synthesis, UV-aware generative inpainting, a Blockbench editor, or a 3D renderer. The caller must explicitly specify palette/patterns. Generated imagery still needs asset-specific art direction and visual review.
- Runtime texture sampling, material effects, UV orientation and entity rendering in Minecraft remain `NOT RUN` until tested in the target game build.

## Recommended workflow

1. Run `audit_geometry_uvs` on the geometry and explicitly linked source texture.
2. Produce `generate_geometry_uv_template` to inspect region labels, overlaps and canvas fit.
3. Use `paint_geometry_texture` with a source PNG and targeted operations; keep a separate output path.
4. Re-run `audit_geometry_uvs` against the actual output texture to confirm dimensions and UV bounds.
5. Run `audit_texture_links` when block/item atlases are involved; entity texture aliases still need their own client-entity reference check.
6. Import into the exact target Bedrock build and visually inspect face orientation, mirrored regions, transparency, mip/edge bleeding and material behavior. Record runtime as `NOT RUN` until performed.

## Official reference

Bedrock geometry documents per-face UVs through the six named cube faces and `uv_size`; see [geometry 1.19.30](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/visualreference/geometry.v1.19.30?view=minecraft-bedrock-stable) and the [geometry 1.19.30 schema](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/schemasreference/schemas/minecraftschema_geometry_1.19.30?view=minecraft-bedrock-stable). These references describe the geometry UV mapping structure; they do not guarantee the painter's preview will match runtime sampling for every format feature.
