---
name: geometry-uv-engine
description: Inspect Bedrock geometry cube layouts and UV face bounds and generate reproducible UV guide images from supported geometry formats.
---

# Geometry & UV Engine

This skill defines a deterministic workflow, not a remote tool. It does not create filesystem access. Run bundled scripts only when a genuine local executor has access to the package and the project files. Never refer to retired MCP tools or imply that this skill itself executes code.

## Current implementation boundary

Existing legacy sources contain reusable algorithms for classic box UV and per-face UV inspection, overlap detection, bounds validation, template rasterization and PNG encoding. They remain preserved in `server/` as dormant migration sources until dependencies are separated and legacy tests are adapted. This skill does not advertise those old wrappers as active callable integrations.

The standalone `scripts/geometry_engine.py` parses `.geo.json` and audits supported classic box/per-face cube UV rectangles, bounds and overlaps. `scripts/uv_template_engine.py` renders a labeled transparent PNG UV guide for those supported cube formats. `scripts/png_engine.py` validates PNG integrity.

## Safe geometry/UV audit procedure

1. Establish target Bedrock version and project root. Inventory `.geo.json`, client-entity bindings, render controllers and explicitly associated textures.
2. Parse JSON with duplicate-key detection; reject non-finite numbers. Select exact `description.identifier` when multiple geometries exist in one file.
3. For each bone and cube, record identifiers, cube index, origin, size and declared texture canvas. Check numeric types, finiteness and dimension validity.
4. For classic box UV origins, compute the occupied box-net rectangle: width `2 * (size.x + size.z)` and height `size.y + size.z`.
5. For per-face maps, inspect north/south/east/west/up/down. Default dimensions come from cube axes; honor explicit `uv_size` and 90/270-degree UV rotations when calculating occupied bounds. Preserve the distinction between signed flips and rectangle extent.
6. Report UV bounds, overlaps and fractional coordinates independently. Shared/mirrored UV regions are warnings for review, not automatic defects.
7. Mark `poly_mesh` and `texture_meshes` as outside current cube-UV coverage. Do not silently pass them.
8. Generate a separate labeled guide using `python skills/geometry-uv-engine/scripts/uv_template_engine.py input.geo.json output.png --pixel-scale 4`. Existing output files are refused; geometry and source textures remain read-only.
9. Validate each generated PNG and record SHA-256, dimensions and byte length.
10. Report exact path, geometry identifier, bone/cube/face selector, expected rectangle, canvas, severity and limitations.

## Output status vocabulary

- `PASS`: supported static checks completed with no finding at the selected severity.
- `WARN`: overlap, fractional coordinates, unsupported mesh format or ambiguous association requires review.
- `FAIL`: invalid structure, non-finite coordinate or UV rectangle provably outside the selected canvas.
- `NOT RUN`: unavailable project files, executor, game import, renderer sampling, Blockbench interoperability or runtime verification.

## Migration status

The static geometry parser and UV bounds/overlap analyzer are migrated into a standalone CLI with focused tests. The standalone renderer is migrated with a focused test suite. The legacy server source remains preserved for dependency-aware cleanup. The renderer does not provide poly-mesh projections, client-entity texture binding, PNG-to-canvas matching or actual renderer sampling.
