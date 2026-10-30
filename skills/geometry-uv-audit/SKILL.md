---
name: geometry-uv-audit
description: Use when checking Minecraft Bedrock .geo.json cube UV mappings, texture canvas dimensions, and PNG integrity before visual testing.
---

# Geometry UV audit

Use the standalone `skills/geometry-uv-engine/scripts/geometry_engine.py` CLI when a genuine Python executor can access the package and project files. This is a local script, not an online tool or hidden integration.

```bash
python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json
python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json --geometry-identifier geometry.example --report uv-audit.json
```

## Scope

- Reads `.geo.json`, rejects duplicate JSON keys and non-finite numeric values, and selects an exact `description.identifier` when necessary.
- Supports classic box UV origins (`uv: [u, v]`) and per-face cube maps (`north`, `south`, `east`, `west`, `up`, `down`).
- Classic box UV rectangle width is `2 * (size.x + size.z)` and height is `size.y + size.z`.
- Per-face default extents derive from cube axes; explicit `uv_size` is respected, and 90°/270° rotations swap extents for bounds calculations.
- Checks regions against the selected geometry description's declared `texture_width` and `texture_height`.
- Reports out-of-bounds regions as `FAIL` and positive-area overlaps as `WARN`; overlaps may represent intentional mirroring/reuse.

## Limitations

- The analyzer is static and cube-UV oriented. It does not resolve client-entity texture aliases or inspect PNG dimensions for geometry-canvas agreement.
- `poly_mesh` and `texture_meshes` projection are not implemented by this CLI.
- It does not render templates or modify geometry/textures. The legacy template renderer remains dormant pending migration.
- Minecraft import, face sampling, renderer orientation, Blockbench interoperability and runtime rendering remain `NOT RUN` until tested.
