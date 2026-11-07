---
name: geometry-uv-engine
description: Use to audit Minecraft Bedrock geometry UVs, render UV template guides, or validate PNG assets; includes geometry-audit, template-authoring and PNG-check modes.
---

# Geometry & UV Engine

This skill defines a deterministic workflow, not a remote tool. It does not create filesystem access. Run bundled scripts only when a genuine local executor has access to the package and the project files. Never refer to retired MCP tools or imply that this skill itself executes code.

## Current implementation boundary

The current package ships standalone implementations for classic box UV and per-face UV inspection, overlap detection, bounds validation, template rasterization and PNG encoding. No retired server/protocol wrapper is required or included.

The standalone `scripts/geometry_engine.py` parses `.geo.json` and audits supported classic box/per-face cube UV rectangles, bounds and overlaps. `scripts/uv_template_engine.py` renders a labeled transparent PNG UV guide for those supported cube formats. `scripts/png_engine.py` validates PNG integrity. For explicit reference-crop mapping onto exact UV faces, use `skills/uv-texture-retargeting/scripts/reference_transfer.py` after reviewing `reference-mapping-review`; it is a separate deterministic local utility.

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

The static geometry parser and UV bounds/overlap analyzer, standalone UV template renderer, PNG validator and explicit reference-texture transfer core are available as local scripts with focused tests. The package contains no legacy server/protocol source tree. These scripts do not provide poly-mesh projections, client-entity texture binding, semantic portrait matching or actual renderer sampling.

## Consolidated modes: Geometry & UV

This Skill is the canonical entry for geometry/UV operations formerly exposed through `geometry-uv-engine` and `geometry-uv-engine`. Select only the required mode:

- **audit** — inspect `.geo.json`, geometry identifiers, cube bounds, face UV bounds, overlaps and supported geometry constraints; report findings without rewriting source.
- **render-template** — generate a separate labeled transparent UV guide PNG from supported geometry, using explicit output path, pixel scale and maximum-pixel budget.
- **png-check** — inspect PNG integrity, dimensions and hashes. PNG validity does not prove agreement with the intended texture canvas, face orientation or game renderer.

Implementation remains in this Skill's existing `geometry_engine.py`, `uv_template_engine.py` and `png_engine.py`; preserve their existing CLI contracts, tests and paths. The focused geometry, template and PNG suites are separate acceptance checks (10, 8 and 18 cases respectively). Poly-mesh/texture-mesh UV projection remains unsupported. Do not imply template rendering emulates Minecraft's renderer. Reference-image semantic mapping is outside this Skill and must use `uv-texture-retargeting` plus the separate human `reference-mapping-review` gate.
