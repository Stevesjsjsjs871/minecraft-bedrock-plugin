# Geometry & UV Engine scripts

## Geometry analyzer
```bash
python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json
python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json --geometry-identifier geometry.example --report uv-audit.json
```

## UV template renderer
```bash
python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --pixel-scale 4
python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --geometry-identifier geometry.example --pixel-scale 2 --max-pixels 16000000
```
The renderer creates a transparent PNG guide, labels each face by bone/cube/face, bounds memory with a pixel budget, and refuses to overwrite existing output files. It supports classic box and per-face cube UV only.

Run focused tests with:
```bash
python -m unittest discover -s skills/geometry-uv-engine/scripts -p 'test_*.py' -v
```

`png_engine.py` separately validates PNG integrity. Mesh projection, client-entity binding, actual PNG/canvas matching, Blockbench and game renderer behavior remain outside these CLIs.

`uv_template_engine.py` renders guides with a transparent canvas, a subtle texel grid and bitmap face labels. The current renderer uses rectangle bounds; it does not simulate Bedrock UV face orientation or mirror sampling.
