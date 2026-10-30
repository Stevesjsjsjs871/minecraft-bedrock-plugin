---
name: uv-mapping-assistant
description: Use to inspect Bedrock geometry UV regions and prepare explicit, reviewable mappings from reference image crops to exact cube faces.
---

# UV mapping workflow

This skill does not expose `build_uv_mapping_plan` or `map_reference_texture_to_uv` as live tools. Use the documented procedure with actual files/code capabilities or provide a reviewable mapping plan; never claim a historical MCP tool executed.

## Geometry inventory
Read the geometry JSON and select one unambiguous geometry identifier. Enumerate bones, cubes and supported faces. Record exact UV coordinates, integer pixel bounds, texture dimensions, mapping type, rotation metadata, out-of-bounds faces and overlap pairs. Flag unsupported mesh types.

## Source sheet
Inspect the reference PNG dimensions and hash. Define source rectangles explicitly as pixel coordinates. Each mapping must identify an exact target bone/cube/face selector; broad bone selectors are allowed only when the same crop is intentionally reused on all matching faces.

## Human review
For every assignment, record source crop, target selector, rationale, sampling method, quarter-turn rotation/flips, opacity and blend mode. Do not infer semantic correspondence automatically. Require explicit review for mirrored/shared UVs and any overlapping assignments.

## Transfer plan
Produce a table or JSON plan with geometry/reference hashes, source and target dimensions, exact selectors, source rectangles, mapped/unmapped coverage, overlap warnings and output path. Validate every crop and UV bound before writing. Preserve a supplied base texture and write a distinct output unless replacement is explicitly authorized.

## Completion checks
Validate output PNG decoding/dimensions/hash and rerun UV audits. Report partial coverage honestly. Static mapping does not simulate Bedrock 3D face orientation, rendering, seams or lighting; mark runtime `NOT RUN` until tested.
