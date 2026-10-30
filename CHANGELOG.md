# Plugin package changelog

## 1.1.1 — Animation-controller state machines
- Adds `minecraft-bedrock-animation-controller-authoring` as a dedicated stdio MCP server.
- Adds `create_animation_controller` to generate RP state-machine JSON from an initial state, state animation aliases, transition destinations/conditions, optional entry/exit commands and blend durations.
- Binds the controller into an existing client entity using `description.animations` and `description.scripts.animate`, preserving unrelated client entity resources.
- Adds read-only `validate_animation_controller` for state/transition/reference/binding checks.
- Enforces linked scaffold manifests, workspace confinement, safe RP paths, symlink and duplicate-JSON rejection, animation alias existence and no-overwrite behavior. The two-file authoring operation cleans up its new controller if updating the entity fails.
- Molang text is bounded but not parsed or executed. Minecraft runtime behavior remains NOT RUN.

## 1.1.0 — First-pass custom entity authoring
- Adds the `minecraft-bedrock-entity-authoring` stdio MCP server and `create_addon_entity` tool.
- Creates linked BP entity, RP client entity, geometry and render-controller JSON from an explicit bounded bone/cube model input.
- Validates bone names and parent graphs, finite coordinates, classic box-UV bounds, project manifests, entity identifier uniqueness and path safety.
- Refuses output collisions and symlinks; rolls back the files created by the operation if a write fails partway through.
- Does not fabricate textures, animations, animation controllers or spawn rules. Minecraft import/spawn/render testing remains NOT RUN.

## 1.0.14 — Full PNG stream validation and bounded texture audit
- Adds shared `server/png_validation.py` to validate PNG chunks/CRCs, legal IHDR/PLTE/tRNS rules, consecutive IDAT chunks, bounded zlib decompression, exact scanline sizes/filter bytes and Adam7 passes.
- Upgrades `audit_texture_links` to validate decompressed PNG scanlines and catches valid-CRC but corrupt compressed image data.
- Caches repeated PNG validation and applies per-audit limits for atlas entries, unique PNG files and aggregate bytes; reports `analysis_complete` and scan metrics.
- Auditor remains read-only; runtime validation remains NOT RUN.

## 1.0.13 — Read-only BP/RP texture-link audit
- Adds `audit_texture_links`, scanning BP block/item JSON through matching RP atlases to referenced PNG files.
- Reports missing keys/files, malformed or duplicate-key JSON, invalid atlas paths, corrupt PNGs, unsafe symlinks and unused atlas entries.
- Uses bounded scans and remains read-only, workspace-confined and runtime-unverified.

## 1.0.12 — PNG validation and atlas write safety
- Validates PNG image data, legal IHDR metadata, chunk ordering, consecutive IDAT data, bounded scanline sizes, filter methods and Adam7.
- Validates generated PNGs, serializes atlas updates with exclusive locks and rejects duplicate JSON keys.
- Static validation only; Minecraft import/rendering remains NOT RUN.

## 1.0.11 — Safe texture-atlas registration
- Adds `register_texture_atlas` for block and item Resource Pack textures.
- Preserves unrelated atlas entries and refuses conflicts, corrupt PNGs, unsafe paths and concurrent changes.

## 1.0.10 — Dedicated procedural texture MCP tool
- Adds the separate `minecraft-bedrock-texture-generator` stdio MCP server with `generate_texture`.
- Generates bounded RGBA PNG starter textures using deterministic procedural styles; it is not AI image synthesis or UV-aware painting.
