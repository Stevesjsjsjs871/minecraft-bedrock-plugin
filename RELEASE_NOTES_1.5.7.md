# Minecraft Bedrock Engineer 1.5.7

## Standalone PNG validation

Added a pure-Python PNG structural validation utility at `skills/visual-resource-pipeline/scripts/png_engine.py`. It checks file bounds, PNG signature, chunk boundaries and CRCs, IHDR legality, PLTE constraints, consecutive IDAT chunks, zlib stream completion, decompressed scanline lengths, filter values and Adam7 pass sizes.

Run:
```bash
python skills/visual-resource-pipeline/scripts/png_engine.py path/to/texture.png
python -m unittest discover -s skills/visual-resource-pipeline/scripts -p 'test_png_engine.py' -v
```

Eight synthetic tests pass locally. The validator does not render textures or establish Minecraft runtime compatibility. Existing legacy server modules remain preserved pending further dependency-aware migration.
