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

Example texture-generation MCP arguments:

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

Example atlas-registration arguments:

```json
{
  "project_directory": "ruby-addon",
  "texture_type": "blocks",
  "texture_identifier": "ruby_ore",
  "texture_path": "resource_packs/ruby-addon_RP/textures/blocks/ruby_ore.png"
}
```

Texture generation remains procedural starter art, not AI image synthesis or UV-aware entity texture painting. Atlas registration does not create or edit the BP/RP block or item definitions that consume the key. Runtime/import/rendering checks remain `NOT RUN` unless executed in-game.

## Asset workflow

1. Inventory existing geometry, animation, animation-controller, render-controller, material and texture files. Locate definitions and references rather than guessing.
2. Search version-matched Mojang samples for relevant patterns and record source paths and compatibility evidence.
3. Use supported Creator Tools capabilities only when actually exposed by the host; do not fabricate a successful delegation.
4. Validate identifier/path consistency, geometry structure, bones, UVs, animation names and controller transitions with available static checks.
5. Compare against the baseline and report unresolved links, changed definitions, resource removals and severity changes.
6. Import into the target game when possible. Check missing textures, rendering, animation transitions and behavior; record the exact build/scenario.

## Asset discipline

- Follow user-provided references precisely; do not invent unrequested model or texture details.
- Do not delete unrelated geometry, bones, animations, controllers, textures or atlas entries.
- Distinguish generated assets, reference samples, existing assets and placeholders; preserve provenance/licensing boundaries.
- Mark all unexecuted runtime checks `NOT RUN`.
