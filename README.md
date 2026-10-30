# Minecraft Bedrock Engineer — 1.1.1

## 1.1.1: animation-controller state machines

- Adds the dedicated `minecraft-bedrock-animation-controller-authoring` stdio MCP server.
- Adds `create_animation_controller`, which creates an RP animation-controller JSON with a defined initial state, bounded states, animation aliases, transitions and Molang commands.
- Binds the new controller to an existing RP client entity by adding an alias in `description.animations` and registering that alias in `description.scripts.animate` without removing unrelated entries.
- Adds read-only `validate_animation_controller` to check controller structure, state targets, alias references, controller binding and `scripts.animate` registration.
- Checks the linked BP/RP scaffold, JSON duplicate keys, path containment, symlinks, existing controller IDs, output collisions and client-entity concurrent changes. It refuses to overwrite a controller file.
- Molang checks are text-shape validation only. Minecraft import, expression evaluation, animation blending and runtime transitions remain `NOT RUN`.

## 1.1.0: first-pass custom entity authoring

- Adds the dedicated `minecraft-bedrock-entity-authoring` stdio MCP server with `create_addon_entity`.
- Creates four coordinated resources in an existing linked BP/RP scaffold: BP entity definition, RP client entity, Bedrock geometry model and render controller.
- Accepts an explicit bone/cube model definition with parent hierarchy, pivots, classic box UVs, optional cube transforms and locators. Checks duplicate/missing/cyclic bones, finite vectors, cube limits and UV bounds.
- Validates the scaffold's BP/RP manifests and dependency, checks identifier collisions, confines writes to the selected project, rejects symlinks and existing destinations, and rolls back partial file creation.
- Texture PNGs, animation clips/controllers and spawn rules are not fabricated. Minecraft import/spawn/render tests remain `NOT RUN`.

## 1.0.14: full PNG stream audit and bounded scan budgets

- The read-only `audit_texture_links` tool validates decompressed PNG scanlines, legal color/depth combinations, PLTE/tRNS placement, consecutive IDAT chunks, bounded zlib output, filter bytes and Adam7 passes.
- Adds reusable `server/png_validation.py`, validation caching and explicit per-audit limits. Results report `analysis_complete` and scan metrics.
- Adds regression coverage for corrupt zlib streams, scanline/filter errors, indexed/Adam7 PNGs, cache reuse and incomplete scans. Runtime remains `NOT RUN`.

## Earlier texture pipeline

- 1.0.13 introduced the read-only BP/RP texture-link auditor.
- 1.0.12 strengthened PNG data validation and safe atlas updates.
- 1.0.11 added safe block/item atlas registration.
- 1.0.10 added the separate procedural PNG texture generator.

The original MCP server, plugin identity, permissions, default prompts and existing tools are preserved. Minecraft runtime remains `NOT RUN` unless explicitly reported otherwise.
