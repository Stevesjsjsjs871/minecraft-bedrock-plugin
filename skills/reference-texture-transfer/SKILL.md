---
name: reference-texture-transfer
description: Use when transferring reviewed reference PNG crops onto explicitly selected Minecraft Bedrock geometry UV faces with a deterministic local script.
---

# Reference texture transfer

This skill describes a bundled local Python utility. It is not a hosted service and does not create filesystem access. Run it only when a real executor can access the package and the user's project. It does not use MCP, a registry, a remote backend, or network access.

## Inputs and safety

Use a JSON request based on `references/reference-transfer.example.json`. Set `project_directory` to one lowercase kebab-case directory directly below the executor workspace. Geometry, source PNG, optional base PNG and output must be project-relative POSIX paths. The project must contain `resource_packs/<project>_RP/manifest.json`; outputs must be under an existing project folder and are created exclusively (never overwritten).

Choose the exact `geometry_identifier` when the file contains multiple geometries. Each mapping requires a selector with one or more of `bone`, `cube_index`, and `face` (`north`, `south`, `east`, `west`, `up`, `down`) plus an integer `source_rect` crop. Review semantic correspondence yourself; the script does not identify which portrait region belongs on which model face.

Optional transforms are `rotation` (`0`, `90`, `180`, `270`), `flip_x`, `flip_y`; sampling is `nearest` or `bilinear`; blend mode is `over` or `replace`; opacity is `0..255`. Transform order is rotation followed by horizontal/vertical flips. A supplied base texture is preserved outside selected regions and must match the geometry texture canvas exactly.

UV overlaps and duplicate target selections fail by default. Set `allow_uv_overlap: true` only for intentionally shared UVs or ordered layering that has been reviewed. Static tool validation does not prove visual orientation or runtime correctness.

## Run

From the package root:

```bash
python skills/reference-texture-transfer/scripts/reference_transfer.py <request.json> --workspace <workspace-directory> --report <report.json>
```

The script is dependency-free and uses only the Python standard library. It returns structured JSON with status, geometry/canvas, input and output SHA-256, mapping coverage, texel budget, warnings and explicit runtime status. To test:

```bash
cd skills/reference-texture-transfer/scripts
python -m pytest -q
```

## Supported scope and limitations

- Supports classic box UV and per-face cube UV for six faces; unsupported mesh types are reported, not projected.
- Handles PNG 8-bit non-interlaced color types 0, 2, 3, 4 and 6; rejects unsupported depth/interlace or invalid CRC/chunk/scanline data.
- Applies explicit 2D source crops to texture-space rectangles. It does not infer semantic matches, unwrap geometry, generate artwork, simulate 3D projection, determine renderer face orientation, link textures to client entities, or verify seams/mipmaps.
- Static PNG/JSON checks do not prove Minecraft rendering. Import, Blockbench inspection and game runtime remain `NOT RUN` until actually performed.

## Workflow

1. Audit geometry UVs and render a transparent UV guide.
2. Prepare a reviewed reference image and manually define crops/selectors.
3. Use a copy of the base texture when untouched pixels must remain.
4. Run the transfer, inspect the report and resulting PNG; then rerun UV/resource-link audits.
5. Import into the exact Bedrock build and visually inspect every face; report runtime evidence separately.
