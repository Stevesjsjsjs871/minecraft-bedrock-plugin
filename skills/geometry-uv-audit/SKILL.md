---
name: geometry-uv-audit
description: Use when checking Minecraft Bedrock .geo.json cube UV mappings, texture canvas dimensions, and PNG integrity before visual testing.
---

# Geometry UV audit

Use `minecraft-bedrock-geometry-uv-auditor` and its read-only `audit_geometry_uvs` tool on an existing Bedrock Engineer project.

## Scope

- Scans one geometry JSON under `resource_packs/<project>_RP/models/entity/`, or recursively scans that directory when `geometry_path` is omitted.
- Supports classic box UV origins (`uv: [u, v]`) and alternate per-face UV maps (`north`, `south`, `east`, `west`, `up`, `down`) with optional `uv_size` and `uv_rotation`.
- Classic box UV bounds use the box layout rectangle: width `2 * (size.x + size.z)` and height `size.y + size.z`.
- Per-face default UV extents come from the corresponding cube dimensions: north/south = X×Y, east/west = Z×Y, up/down = X×Z. Explicit `uv_size` replaces those extents. UV rotations of 90°/270° swap the rectangle's width and height for bounds checks.
- Uses `texture_width` and `texture_height` declared in each geometry description. If they are absent, a PNG may be supplied for a single explicit geometry file and its validated dimensions become the fallback canvas.
- The optional `texture_path` is an explicit assertion by the caller that this PNG belongs to the selected geometry. The tool does not guess texture aliases by reading client-entity bindings.
- Supplied PNGs are deeply validated through `server/png_validation.py` (chunks, CRCs, IDAT decompression, scanline sizes and filters, Adam7).

## Example

```json
{
  "project_directory": "forest-addon",
  "geometry_path": "resource_packs/forest-addon_RP/models/entity/forest_guardian.geo.json",
  "texture_path": "resource_packs/forest-addon_RP/textures/entity/forest_guardian.png"
}
```

## Findings and limitations

- `UV_OUT_OF_BOUNDS` is an error when a rectangle exceeds the effective texture canvas.
- `TEXTURE_CANVAS_DIMENSION_MISMATCH` is a warning when actual PNG dimensions differ from the geometry's declared texture canvas; the audit still compares UVs against the declared canvas.
- A missing texture canvas means UV bounds cannot be proven unless an explicit valid PNG is supplied.
- `poly_mesh` and `texture_meshes` are reported as outside current cube-UV coverage rather than silently treated as audited.
- Static bounds checks do not validate texel content, visual alignment, UV orientation, material resolution, entity texture alias wiring, or runtime rendering. Import/visual tests remain `NOT RUN` until run in Minecraft.
- The tool is read-only. It never rewrites the geometry or changes atlas entries.
## UV template follow-up

After a clean audit, use the `geometry-uv-template-authoring` skill to create a separate labeled PNG guide for painting. The guide does not rewrite geometry or replace the actual texture.
