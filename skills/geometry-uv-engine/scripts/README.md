# Geometry & UV Engine scripts

## Geometry analyzer

```bash
python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json
python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json --geometry-identifier geometry.example --report uv-audit.json
```

Parses a `.geo.json`, selects an exact geometry identifier when needed, checks classic/per-face cube UV extents against the declared canvas and reports overlaps as review warnings. Mesh UV projection and entity/render binding checks are outside scope.

## UV template renderer

```bash
python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --pixel-scale 4
python skills/geometry-uv-engine/scripts/uv_template_engine.py path/to/entity.geo.json path/to/uv-guide.png --geometry-identifier geometry.example --pixel-scale 2 --max-pixels 16000000
```

Renders a separate transparent PNG guide with a subtle texel grid and bone/cube/face labels. The renderer refuses to overwrite output files and enforces pixel-scale and total-pixel limits. It supports classic box and per-face cube UV rectangles; it does not emulate renderer face orientation or mirrored sampling.

## PNG validation

Use the canonical validator at `skills/visual-resource-pipeline/scripts/png_engine.py`:

```bash
python skills/visual-resource-pipeline/scripts/png_engine.py path/to/uv-guide.png
```

## Tests

Run the focused suites from the plugin root:

```bash
python -m unittest discover -s skills/geometry-uv-engine/scripts -p 'test_*.py' -v
python -m unittest discover -s skills/visual-resource-pipeline/scripts -p 'test_*.py' -v
```

Minecraft rendering, Blockbench interoperability, mesh projection, client-entity binding and texture-to-canvas matching remain outside these standalone CLIs.
