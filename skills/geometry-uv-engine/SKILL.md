---
name: geometry-uv-engine
description: Analyze Bedrock geometry cube UV mappings with bounded static checks for canvas bounds, overlaps, and unsupported mesh coverage.
---

# Geometry & UV Engine

This is a local, dependency-free static analyzer for Bedrock .geo.json geometry files. It does not create filesystem access by itself; run it only when a real local executor can access the plugin package and the selected project file.

## Commands

    python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json
    python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json --geometry-identifier geometry.example --report uv-audit.json
    python -m unittest discover -s skills/geometry-uv-engine/scripts -p 'test_*.py' -v

The analyzer reads one geometry file and emits a JSON report. It never edits geometry or textures. A report file is created only if the target does not already exist.

## Supported static coverage

- Classic box UV origins, using the box-net occupied rectangle width 2 × (size.x + size.z) and height size.y + size.z.
- Per-face cube UV maps for north, south, east, west, up and down.
- Per-face default extents from cube axes; explicit uv_size; negative-size flips; integer uv_rotation values 0, 90, 180 and 270.
- Geometry selection by exact description.identifier.
- Duplicate JSON key and non-finite number rejection.
- Texture canvas bounds when both texture_width and texture_height are explicitly declared as positive integers.
- Positive-area overlap detection with a bounded sweep-line comparison budget.
- Bone-level poly_mesh and texture_meshes are reported as outside cube-UV coverage.

## Important limits

- Missing texture_width/texture_height are not silently replaced with an assumed 64×32 canvas. The analyzer returns WARN and marks bounds_checked false.
- A local safety limit of 4096 texels per canvas dimension, 2 MiB per JSON file, 6000 cubes/regions, and 250,000 overlap comparisons is enforced. These are analyzer resource limits, not additional claims about the Bedrock schema.
- Overlap is a warning because mirrored or shared UV regions can be intentional.
- poly_mesh and texture_meshes are not analyzed; their presence is reported as unsupported.
- The analyzer does not resolve client-entity texture aliases, validate a separate PNG against the geometry canvas, rasterize a UV template, or render the model.
- Minecraft import, visual sampling, Blockbench interoperability and gameplay remain NOT RUN until tested in the target environment.

## Relationship to existing tools

The existing MCP geometry auditor and template renderer remain unchanged in distributions that configure them. This script is a separate local utility and does not start an MCP transport. The template renderer is not yet migrated into a standalone script.

## Official format reference

The Microsoft Learn geometry v1.21.0 reference documents per-face UV objects, uv_size, integer uv_rotation values, integer texture_width/texture_height, and bone-level poly_mesh / texture_meshes properties:

https://learn.microsoft.com/en-us/minecraft/creator/reference/content/visualreference/geometry.v1.21.0?view=minecraft-bedrock-stable
