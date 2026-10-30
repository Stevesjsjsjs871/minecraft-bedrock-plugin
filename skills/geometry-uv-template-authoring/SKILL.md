---
name: geometry-uv-template-authoring
description: Use when preparing a labeled UV guide from a Bedrock geometry file before painting, reviewing or revising its entity texture.
---

# Geometry UV template authoring

Use `minecraft-bedrock-geometry-uv-template` and `generate_geometry_uv_template` for a separate UV guide image.

## Input contract

- Select one `.geo.json` file inside `resource_packs/<project>_RP/models/entity/`.
- If the file contains more than one `minecraft:geometry` entry, pass its exact `description.identifier` as `geometry_identifier`.
- The selected geometry must declare integer `texture_width` and `texture_height` (1–4096).
- Save the template only under `resource_packs/<project>_RP/textures/uv_templates/` with a new `.png` file name. Existing files are never overwritten.
- `pixel_scale` is the number of output pixels per UV texel (1–8; default 4). Large canvases may require a smaller scale to stay within the pixel budget.

## Mapping coverage

- Classic box UV (`uv: [u, v]`) is expanded into six labeled face regions using the Bedrock box-net arrangement. The DOWN face is shown as its occupied rectangle; the engine's V-flip is an orientation detail, not a different occupied area.
- Per-face UV objects support `north`, `south`, `east`, `west`, `up` and `down`, including negative `uv_size` flips, omitted `uv_size` defaults from cube dimensions, and `uv_rotation` 0/90/180/270.
- `poly_mesh` and `texture_meshes` are outside the template coverage and are reported rather than fabricated.

## Reading the report

- Out-of-bounds UVs are shown and reported; the tool clips drawing to the canvas but does not repair the source model.
- Overlap intersections are highlighted in magenta. A shared region may be intentional mirroring or texture reuse, so overlaps are warnings for review, not automatic errors.
- Fractional UV coordinates are noted; the PNG template rasterizes these at the selected pixel scale.
- The image is a transparent guide, not a painted/usable entity texture. It is not automatically registered in an atlas or connected to a client entity.
- Geometry and actual texture files are never edited. Minecraft sampling/orientation/render tests remain `NOT RUN` until imported into the target game.

## Recommended workflow

1. Run `audit_geometry_uvs` first to validate UV bounds and any explicitly associated PNG dimensions.
2. Generate the UV template and review highlighted overlaps and out-of-bounds regions.
3. Use the image as a guide. For explicit programmatic paint operations, use `paint_geometry_texture` with selectors for bone, cube index and/or face. Keep the output path separate from the source texture.
4. Run `audit_geometry_uvs` again with the resulting PNG explicitly supplied.
5. Run the texture-link auditor where block/item atlas links apply, then import the packs into the target Bedrock build for visual verification.

Official reference: [Bedrock geometry format 1.26.40](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/visualreference/geometry.v1.26.40?view=minecraft-bedrock-stable) and [Entity Modeling and Animation](https://learn.microsoft.com/en-us/minecraft/creator/documents/entitymodelingandanimation?view=minecraft-bedrock-stable).
