---
name: uv-mapping-assistant
description: Use when preparing explicit texture-reference assignments for Minecraft Bedrock geometry UV faces and validating transfer coverage before writing a texture.
---

# UV Mapping Assistant

## Purpose

Use the `minecraft-bedrock-uv-mapping-assistant` MCP server and `build_uv_mapping_plan` to inventory the supported cube-face UVs of one Bedrock `.geo.json`, resolve explicit source-sheet rectangles to exact face selectors, and prepare a validated `transfer_request` for `map_reference_texture_to_uv`.

The assistant does not infer semantic correspondence from a portrait or illustration. A person must decide which source crop belongs on which face, or supply a reference sheet whose labeled parts and rectangle coordinates are known.

## Inputs

- `project_directory`: one existing project under `MINECRAFT_BEDROCK_WORKSPACE`.
- `geometry_path`: project-relative path under `resource_packs/<project>_RP/models/entity/`.
- `geometry_identifier`: exact identifier for one geometry entry in the file.
- `reference_image_path`: standard 8-bit non-interlaced PNG under the RP `textures/` tree.
- `output_path`: new PNG path under `textures/entity/`. Its parent directory must exist and the file must not already exist.
- `source_assignments`: ordered entries. Each entry has a selector (`bone`, `cube_index`, and/or `face`) and a source crop rectangle. Optional transfer fields include quarter-turn rotation, flips, nearest/bilinear sampling, opacity, and `over`/`replace` blend mode.

A broad selector such as `{ "bone": "head" }` intentionally applies the same source rectangle to every supported face on that bone. Prefer exact bone/cube/face selectors when the six visible sides need different image regions.

## Review the plan

The response includes:

- A stable region ID for every supported target face.
- Exact UV bounds, pixel bounding rectangle, normalized coordinates, classic/per-face mapping type and `uv_rotation` metadata.
- Source image dimensions/hash and optional base texture size.
- Expanded assignments using exact selectors, plus mapped/unmapped coverage.
- UV overlap pairs and warnings.
- A `transfer_request` validated against the downstream `map_reference_texture_to_uv` tool's input contract.

`plan_status` is:
- `ready`: complete coverage, no unaccepted overlap and transfer request passes static contract validation.
- `partial`: unmapped faces remain but `require_full_coverage` was not requested. Unmapped regions stay transparent unless an optional base texture is supplied.
- `needs_review`: full coverage was required but not reached, or UV overlap was found without explicit acceptance. In this case, `transfer_request` is `null`; the unapproved data is available only as `draft_transfer_request` for review.

UV overlap can be intentional (for mirrored/shared texture regions). It is not automatically an error. The downstream transfer uses one `allow_uv_overlap` switch for overlapping geometry regions and ordered duplicate assignments; only enable it after reviewing the reported pairs.

## Execute the transfer

1. Review the inventory, assignment expansion, uncovered regions and overlap pairs.
2. Pass the returned `transfer_request` unchanged to `map_reference_texture_to_uv`.
3. Inspect the produced PNG; run `audit_geometry_uvs` with the explicit geometry and output texture paths.
4. Link the generated texture to the client entity/render controller separately if needed. The transfer tool does not rewrite entity definitions.
5. Import the pack into the exact target Minecraft Bedrock build and inspect faces, orientation, transparency and seams. Static planning does not prove renderer behavior.

## Scope and safety

- Read-only: the assistant never writes project files.
- Requires a unique geometry identifier; ambiguous geometry entries are rejected.
- Validates reference/base PNG decoding, source rectangle bounds, base canvas size, UV bounds, assignment coverage, path containment, symlinks and destination collisions.
- Cube face UVs only. `poly_mesh` and `texture_meshes` are outside the current plan.
- Fractional UV coordinates are reported as exact floating bounds plus conservative integer pixel bounds. Review rasterization when a geometry intentionally uses fractional UVs.
- Rotation metadata is preserved for review but this tool does not simulate Bedrock's 3D face sampling orientation. No AI semantic segmentation, UV unwrapping or 3D rendering is performed.
- Mark Minecraft import, rendering, material and runtime checks `NOT RUN` until actually tested.

See `references/guardian-mapping-plan.example.json` for an explicit source-sheet mapping request.
