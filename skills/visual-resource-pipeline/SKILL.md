---
name: visual-resource-pipeline
description: Use when creating or validating Minecraft Bedrock textures, geometry, animation, and connected Resource Pack assets.
---

# Visual Resource Pipeline

Default target is Minecraft Bedrock 1.26.50. Prefer bundled version-matched Mojang samples and official Creator documentation. Keep the dependency chain coherent: BP definition -> RP client entity or atlas -> geometry/textures/controllers/animations -> localization and recipe/behavior references. Preserve existing assets and reject path traversal and unintended overwrites. Distinguish static validation from in-game tests; mark runtime NOT RUN.

## Procedural texture generator

`scripts/generate_texture.py` is the deterministic standard-library RGBA PNG writer. It supports `pixel_noise`, `checker`, `stripes`, `solid`, `vertical_gradient`, `horizontal_gradient`, `brick`, `stone_noise`, `ore_veins`, and `wood_grain`; width/height are capped at 1024 each and 1,048,576 total pixels.

The separate `minecraft-bedrock-texture-generator` stdio MCP server exposes two tools:

- `generate_texture` creates a deterministic RGBA PNG inside an existing project's `resource_packs/<project>_RP/textures/` directory. It requires existing parent folders, refuses symlinked paths and existing destinations, validates style/color/dimensions, then fully validates the written PNG before reporting success. Results include the file hash.
- `register_texture_atlas` registers an existing PNG in `textures/terrain_texture.json` (`texture_type: "blocks"`) or `textures/item_texture.json` (`texture_type: "items"`). It validates legal IHDR combinations, chunk bounds/order/CRCs, consecutive IDAT chunks, bounded zlib decompression, exact scanline lengths and filter bytes (including Adam7 interlace). It preserves unrelated atlas entries and rejects duplicate JSON keys and conflicting identifiers.

Atlas registration serializes this tool's read/modify/write cycles with a per-atlas exclusive lock. A lock already present causes an `ATLAS_BUSY` result. A possible stale lock is deliberately not removed automatically: inspect it and remove it only after confirming no texture-tool process is still running. Atlas JSON is atomically replaced after validation.

## Texture-link auditor

The separate `minecraft-bedrock-texture-link-auditor` stdio MCP server exposes the read-only `audit_texture_links` tool. Pass one existing project directory directly under `MINECRAFT_BEDROCK_WORKSPACE` (the same project layout created by `create_addon_project`). It scans:

- `behavior_packs/<project>_BP/blocks/**/*.json` for `minecraft:material_instances` texture keys.
- `behavior_packs/<project>_BP/items/**/*.json` for `minecraft:icon` in string, `texture`, or `textures.default` form.
- `resource_packs/<project>_RP/textures/terrain_texture.json` and `item_texture.json` for the corresponding atlas entries.
- The PNG file paths referenced by each atlas entry, including project containment, chunk ordering/CRCs, legal IHDR/PLTE/tRNS metadata, consecutive IDAT chunks, bounded zlib decompression, exact scanline lengths/filter bytes and Adam7 passes.

The auditor uses `server/png_validation.py` for full image-stream checks. It catches PNGs whose chunk CRCs are valid but whose compressed IDAT data is broken or decodes to an invalid scanline layout. Repeated PNG paths are checked once per audit; atlas entry count, unique PNG count and aggregate PNG bytes have explicit safety budgets. The report exposes `analysis_complete`, `atlas_keys_checked`, `unique_png_files_inspected` and `png_bytes_inspected`. A false `analysis_complete` means a safety budget or unsafe/missing scan directory prevented full coverage. Unused entries are warnings because content may be referenced dynamically or outside the scanned BP block/item folders. The scan is read-only and never edits, repairs or deletes project files.

Example audit MCP arguments:

```json
{
  "project_directory": "ruby-addon"
}
```

The auditor follows the documented static link shapes; it cannot infer runtime-generated references or guarantee Minecraft rendering. It reports `runtime_status: "NOT RUN"`.

## Example texture generation

```json
{
  "project_directory": "ruby-addon",
  "output_path": "resource_packs/ruby-addon_RP/textures/blocks/ruby_ore.png",
  "width": 16,
  "height": 16,
  "style": "ore_veins",
  "base_color": "#55545A",
  "accent_color": "#9A5CDA",
  "seed": 14
}
```

## Geometry UV guide generation

Before external texture painting, use `minecraft-bedrock-geometry-uv-auditor.audit_geometry_uvs` to check the model and any explicitly linked PNG. Then use `minecraft-bedrock-geometry-uv-template.generate_geometry_uv_template` to create a separate transparent face-labeled UV guide under `resource_packs/<project>_RP/textures/uv_templates/`. It expands classic box UVs, supports per-face UV rectangles and rotations, and marks possible UV intersections in magenta. Review intersections as possible intentional mirrored/shared texture regions, not automatic errors.

The guide is not the entity texture and is not automatically bound to a client entity or registered in an atlas. Never replace the model texture with the guide. Review the returned face-region map to map each label back to its bone/cube. See `skills/geometry-uv-template-authoring/SKILL.md` for the full input contract and limitations.

## Asset workflow

1. Inventory existing geometry, animation, animation-controller, render-controller, material and texture files. Locate definitions and references rather than guessing.
2. Search version-matched Mojang samples for relevant patterns and record source paths and compatibility evidence.
3. Use supported Creator Tools capabilities only when actually exposed by the host; do not fabricate a successful delegation.
4. Validate identifier/path consistency, geometry structure, bones, UVs, animation names and controller transitions with available static checks.
5. Compare against the baseline and report the file list before and after, changed definitions, resource removals and severity changes.
6. Run `audit_texture_links` after adding or changing item/block textures and atlas entries. Resolve errors before packaging; treat unused entries as review warnings, not automatic deletion candidates.
7. For entity texture work, run `audit_geometry_uvs`, generate a separate UV guide, paint the actual PNG at the declared canvas size, then re-run the geometry and texture-link audits.
8. Import into the target game when possible. Check missing textures, rendering, animation transitions and behavior; record the exact build/scenario.

## Asset discipline

- Follow user-provided references precisely; do not invent unrequested model or texture details.
- Do not delete unrelated geometry, bones, animations, controllers, textures or atlas entries.
- Distinguish generated assets, reference samples, existing assets and placeholders; preserve provenance/licensing boundaries.
- Mark all unexecuted runtime checks `NOT RUN`.

## Geometry-aware texture painting

For entity textures, use `minecraft-bedrock-texture-painter` / `paint_geometry_texture` after UV audit and template review. The tool maps explicit bone/cube/face selectors to regions extracted from `.geo.json` and paints an existing or transparent canvas with fill, border, checker, stripes, gradient or seeded noise operations. It writes a distinct PNG, keeps a supplied source image's unpainted pixels/alpha, requires exact geometry texture dimensions and refuses out-of-bounds UVs. Overlaps require an explicit opt-in.

This feature is deterministic 2D pixel painting, not AI texture synthesis or a 3D render preview. It does not simulate face sampling orientation, Molang/material lighting, or engine rendering. See `skills/texture-painting-pipeline/SKILL.md` for the full contract and example.
