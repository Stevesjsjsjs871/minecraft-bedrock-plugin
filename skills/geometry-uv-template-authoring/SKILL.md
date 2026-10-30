---
name: geometry-uv-template-authoring
description: Generate a labeled transparent PNG UV guide from supported Minecraft Bedrock cube geometry before painting or revising an entity texture.
---

# Geometry UV template authoring

Use the standalone `skills/geometry-uv-engine/scripts/uv_template_engine.py` renderer when a real Python executor can access the script and project files. It creates a separate transparent PNG guide and never edits geometry or the source texture.

```bash
python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --pixel-scale 4
python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --geometry-identifier geometry.example --pixel-scale 2 --max-pixels 16000000
```

## Input and safety

- Select a `.geo.json`; pass exact `description.identifier` when several geometries exist.
- The geometry description must declare positive integer `texture_width` and `texture_height`.
- The output path must end in `.png`; the renderer refuses to overwrite an existing file and uses exclusive creation after ensuring its parent directory exists.
- `pixel_scale` is an integer from 1 to 8. The default total pixel budget is 64 million pixels; tune `--max-pixels` explicitly if needed.
- The report includes output dimensions, source texture-canvas dimensions, pixel scale, number of regions, out-of-bounds count and SHA-256.

## Supported UV formats

- Classic box UV (`uv: [u, v]`) expands into six labeled face rectangles in the Bedrock box-net arrangement.
- Per-face cube UV supports north/south/east/west/up/down, optional `uv_size` and 0/90/180/270 rotations.
- Negative `uv_size` values are represented by their occupied positive rectangle; this static guide does not emulate face texture orientation or mirroring transform.
- Mesh UV projection (`poly_mesh`, `texture_meshes`) is not implemented and must not be fabricated.

## Review and limitations

- Inspect overlap regions carefully; mirrored/shared UVs may be intentional.
- Out-of-bounds rectangles are highlighted, not repaired.
- Labels are rasterized from a small built-in bitmap font and long bone names are truncated for legibility.
- The guide is not the production texture and is not registered in atlases or client-entity bindings.
- Minecraft renderer sampling, face orientation, lighting, mipmaps, seams and Blockbench import remain `NOT RUN` until tested.

Run renderer regression tests with:
```bash
python -m unittest skills.geometry_uv_engine.scripts.test_uv_template_engine -v
```

