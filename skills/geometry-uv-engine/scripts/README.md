# Geometry & UV Engine scripts

The local CLI adapter exposes the existing read-only geometry UV audit and the separate UV template generator without starting an MCP transport.

Run from the plugin package root:

    python skills/geometry-uv-engine/scripts/geometry_uv_cli.py --workspace <workspace> audit --project <project-name>

    python skills/geometry-uv-engine/scripts/geometry_uv_cli.py --workspace <workspace> template --project <project-name> --geometry-path resource_packs/<project-name>_RP/models/entity/example.geo.json --output-path resource_packs/<project-name>_RP/textures/uv_templates/example.png

The workspace contains the project directory directly. The CLI requires the preserved server geometry modules and server/png_validation.py. It uses only Python standard-library code plus those bundled modules; no third-party package installation is required.

The adapter is transitional, not a complete pure-library extraction. Its commands call the existing geometry functions directly. The old MCP servers and their tool names remain unchanged.

The audit is read-only. Template generation creates a new guide PNG, refuses overwrite, validates the generated PNG and checks its SHA-256. It does not change geometry or production textures. poly_mesh and texture_meshes remain outside cube-UV coverage. Minecraft runtime and visual verification are NOT RUN.
