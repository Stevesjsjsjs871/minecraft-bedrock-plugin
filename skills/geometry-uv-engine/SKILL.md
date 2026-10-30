---
name: geometry-uv-engine
description: Analyze Bedrock geometry cube UV mappings and generate bounded, validated transparent UV guide PNGs from supported geometry formats.
---

# Geometry & UV Engine

This is a local, dependency-free static analyzer and UV guide renderer. It does not create filesystem access by itself; run the scripts only when a real local executor can access the plugin package and selected project files.

## Commands

    python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json
    python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json --geometry-identifier geometry.example --report uv-audit.json
    python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --pixel-scale 4
    python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --canvas 64 32 --pixel-scale 2
    python -m unittest discover -s skills/geometry-uv-engine/scripts -p 'test_*.py' -v

## Supported static coverage

- Classic box UV origins expanded into the six standard cube-face rectangles.
- Per-face UV maps for north, south, east, west, up and down.
- Per-face default extents, explicit uv_size and integer uv_rotation values 0, 90, 180 and 270.
- Explicit texture canvas dimensions; if geometry omits them, rendering requires a user-supplied --canvas WIDTH HEIGHT override.
- UV bounds, labels and a transparent texel grid.
- PNG chunk CRC, RGBA8 layout, decompressed scanline length and filter-byte validation.
- Exclusive output creation, on-disk SHA-256 verification and no-overwrite behavior.
- Bounded output memory and line clipping so extreme UV coordinates cannot cause unbounded raster loops.

## Important limits

- The renderer refuses geometry containing bone-level poly_mesh or texture_meshes rather than producing an incomplete guide.
- The official geometry schema documents uv_size as texel extents but does not define negative-size orientation. Negative values are shown as a normalized occupied rectangle with flip metadata and a review warning; confirm face orientation in Blockbench and the target Bedrock runtime.
- Bone/cube mirror flags are preserved as review metadata; the PNG is a UV-coordinate guide, not a renderer-accurate face-orientation simulation.
- UV overlaps and out-of-bounds regions remain visible in the guide and are reported; a generated guide does not make invalid geometry valid.
- The renderer does not resolve client-entity texture aliases, compare the PNG to a separately supplied texture, project mesh UVs, or render the 3D model.

## Resource and filesystem safety

- Geometry JSON is limited by the geometry analyzer's 2 MiB input cap.
- Canvas dimensions are limited to 4096 texels per axis by the analyzer.
- Output is limited to 4,194,304 pixels and 32 MiB encoded PNG.
- Existing output files, dangling symlinks and symlinked geometry inputs are refused.
- The output parent directory must already exist.
- These are local tool safety limits, not additional Minecraft format limits.

## Validation boundary

Static geometry analysis and PNG self-validation do not prove Minecraft import, face orientation, texture binding, rendering, gameplay, multiplayer behavior or Blockbench interoperability. Mark those as NOT RUN unless tested in the target environment.

## Official format reference

Microsoft Learn, Visuals Documentation — minecraft:geometry.v1.21.0 (last updated 2026-03-05): per-face UV, uv_rotation, texture dimensions, mirror, poly_mesh and texture_meshes properties.

https://learn.microsoft.com/en-us/minecraft/creator/reference/content/visualreference/geometry.v1.21.0?view=minecraft-bedrock-stable
