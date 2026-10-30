# Geometry & UV Engine scripts

The standalone geometry analyzer uses only Python's standard library.

    python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json
    python skills/geometry-uv-engine/scripts/geometry_engine.py path/to/entity.geo.json --geometry-identifier geometry.example --report uv-audit.json

Run focused regression tests from the repository root:

    python -m unittest discover -s skills/geometry-uv-engine/scripts -p 'test_*.py' -v

The report path must be new; existing files are never overwritten. Geometry files must be regular non-symlink files and no larger than the analyzer's 2 MiB input limit.

Missing texture canvas dimensions produce WARN and leave bounds unchecked; the analyzer does not assume a default canvas. poly_mesh and texture_meshes are reported as unsupported. UV template rasterization, PNG/canvas association and Minecraft rendering remain outside this CLI.
