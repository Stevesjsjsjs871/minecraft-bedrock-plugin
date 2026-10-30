# Geometry & UV Engine scripts

## Geometry analyzer

    python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json
    python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json --geometry-identifier geometry.example --report uv-audit.json

Checks supported cube UV bounds and overlaps without modifying geometry.

## UV template renderer

    python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --pixel-scale 4
    python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --canvas 64 32 --pixel-scale 2

The renderer writes a separate transparent RGBA8 PNG. The output parent must already exist, and the output file must not exist. Missing geometry canvas dimensions require the explicit --canvas WIDTH HEIGHT option. Bone-level mesh geometry is rejected because mesh projection is not implemented.

Safety limits: 2 MiB geometry JSON, 4096 texels per canvas axis, 4,194,304 output pixels and 32 MiB encoded PNG. These are tool limits, not Minecraft schema limits.

## Tests

    python -m unittest discover -s skills/geometry-uv-engine/scripts -p 'test_geometry_engine.py' -v
    python -m unittest discover -s skills/geometry-uv-engine/scripts -p 'test_uv_template_engine.py' -v

The renderer validates PNG chunks, CRCs, RGBA8 dimensions, decompressed scanlines and output SHA-256. Minecraft rendering, Blockbench interoperability and client-entity texture binding remain outside these CLIs.
