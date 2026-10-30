---
name: geometry-uv-engine
description: Run local Bedrock geometry UV audits and generate separate UV guide PNGs through a bounded CLI adapter.
---

# Geometry & UV Engine

This skill defines a workflow. It does not itself grant filesystem access or execute code. Run the bundled CLI only when a real local executor can access both the plugin package and the selected project.

## Current implementation boundary

The CLI adapter calls the existing, tested functions in the preserved geometry audit and template modules directly. It does not start an MCP transport. This is a transitional migration step: the geometry algorithms have not yet been extracted into a pure standalone library, so the adapter still depends on the legacy server source files and the shared PNG validator.

The existing MCP servers remain available in distributions that configure them. Do not remove or rename their tools as part of this CLI migration.

## Commands

Run from the package root, with the workspace directory supplied explicitly.

Read-only audit of every geometry file in the project's Resource Pack:

    python skills/geometry-uv-engine/scripts/geometry_uv_cli.py --workspace <workspace> audit --project <project-name>

Audit one geometry and an explicitly asserted PNG:

    python skills/geometry-uv-engine/scripts/geometry_uv_cli.py --workspace <workspace> audit --project <project-name> --geometry-path resource_packs/<project-name>_RP/models/entity/example.geo.json --texture-path resource_packs/<project-name>_RP/textures/entity/example.png

Generate a separate UV guide:

    python skills/geometry-uv-engine/scripts/geometry_uv_cli.py --workspace <workspace> template --project <project-name> --geometry-path resource_packs/<project-name>_RP/models/entity/example.geo.json --output-path resource_packs/<project-name>_RP/textures/uv_templates/example.png --geometry-id geometry.example --pixel-scale 4

The workspace must contain the project directory directly. The template command writes only a new PNG under textures/uv_templates; existing outputs are refused. The CLI reopens the generated PNG, validates its structure and dimensions, and verifies the SHA-256 returned by the template engine.

## Supported geometry coverage

- Classic box UV origins and per-face cube UV maps.
- Per-face north/south/east/west/up/down entries.
- Optional uv_size, negative-size flips and uv_rotation values 0, 90, 180 or 270 degrees.
- Declared texture_width and texture_height; an explicitly supplied PNG can provide a fallback canvas for one selected geometry in the audit path.
- Overlap and out-of-bounds reporting.

poly_mesh and texture_meshes are outside current cube-UV coverage. They must be reported as unsupported rather than treated as audited.

## Safety and result interpretation

- The audit is read-only.
- Geometry and production texture files are never changed by template generation.
- Project paths are confined to the selected workspace and Resource Pack.
- Symlink escapes, traversal, ambiguous geometry selection and output collisions are rejected.
- A generated guide is not a production texture, atlas entry, client-entity binding or renderer preview.
- PASS means the stated static checks passed; WARN means review is required; FAIL means an error finding exists; NOT RUN means runtime or visual verification was not performed.
- Minecraft import, renderer sampling, Blockbench interoperability and gameplay remain NOT RUN unless tested in the target environment.

## Official format reference

The Microsoft Learn geometry v1.21.0 reference documents cube UV objects, per-face mappings, uv_size, uv_rotation, texture canvas dimensions, and the poly_mesh / texture_meshes structures. The current implementation deliberately reports poly_mesh and texture_meshes as outside its supported cube-UV coverage.

Reference: https://learn.microsoft.com/en-us/minecraft/creator/reference/content/visualreference/geometry.v1.21.0?view=minecraft-bedrock-stable
