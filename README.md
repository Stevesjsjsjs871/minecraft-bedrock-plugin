# Minecraft Bedrock Engineer — 1.0.14

## Unreleased: entity geometry and animation-controller authoring

This branch adds two dedicated stdio MCP servers while retaining the existing core MCP server and all of its tools, including the Minecraft Creator Tools bridge.

- `create_addon_entity` remains available with its original core-server contract.
- `create_addon_entity_with_geometry` creates a coordinated BP entity, RP client entity, geometry and render controller from explicit bounded bone/cube input.
- `create_animation_controller` creates an RP animation-controller state machine and binds it to an existing client entity.
- `validate_animation_controller` performs read-only structural and client-entity linkage checks.
- The animation authoring input prefers ordered transition arrays. The legacy object-map shorthand remains accepted; generated Bedrock JSON always uses the ordered array form.

### Scope and limitations

- Entity geometry currently supports classic box UV only. Per-face UV maps, poly meshes and Blockbench project files are not accepted by this first implementation.
- The entity tool does not create a texture PNG or animation clips. It reports the expected texture path; supply and validate the actual PNG separately.
- Animation transition strings receive bounded text validation only. Molang is not parsed or executed.
- Static JSON/reference checks do not prove pack import, spawning, rendering or animation behavior. Minecraft runtime remains `NOT RUN` until tested in the target game build.

Official references:
- [Creating New Entity Types](https://learn.microsoft.com/en-us/minecraft/creator/documents/introductiontoaddentity?view=minecraft-bedrock-stable)
- [Animation Controllers Reference](https://learn.microsoft.com/en-us/minecraft/creator/documents/animations/animationcontroller?view=minecraft-bedrock-stable)
- [Geometry Reference](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/visualreference/geometry.v1.19.30?view=minecraft-bedrock-stable)

---

## 1.0.14: full PNG stream audit and bounded scan budgets

- The read-only `audit_texture_links` tool now validates the decompressed PNG scanline stream, not only chunk CRCs and IHDR metadata. It checks legal color/depth combinations, PLTE/tRNS placement, consecutive IDAT chunks, bounded zlib output, exact scanline sizes, filter bytes and Adam7 passes.
- Adds a reusable `server/png_validation.py` validator shared by the texture audit implementation, with explicit file/byte/dimension/pixel limits and symlink-safe file reads.
- Caches validation for repeated PNG paths and caps atlas entries, unique PNG files and aggregate PNG bytes per audit. Results include `analysis_complete`, atlas keys checked, unique PNGs inspected and bytes inspected.
- Adds regression cases for valid-CRC but corrupt zlib streams, scanline/filter errors, indexed/Adam7 PNGs, cache reuse and incomplete budgeted scans. The audit remains read-only; Minecraft runtime remains `NOT RUN`.


## 1.0.13: read-only BP/RP texture-link audit

- Adds `audit_texture_links`, a dedicated read-only MCP tool that follows texture references from BP block/item definitions to the matching RP atlas and then to the actual PNG files.
- Checks `minecraft:material_instances` block texture keys, both supported item icon forms (`texture` and `textures.default`), atlas key presence, texture-path containment, PNG signatures/chunk CRCs and dimensions.
- Reports malformed/duplicate-key JSON, missing atlas keys, missing/corrupt PNGs, unsafe symlinks and unused atlas entries as structured findings with file paths and severity.
- Uses bounded scans and file sizes, skips symlinked directories, and never edits project files. Runtime/import/rendering remains `NOT RUN`.

## 1.0.12: deeper PNG validation and safer atlas updates

- Validates PNG image data, not only chunk CRCs: legal IHDR combinations, chunk ordering, contiguous IDAT data, bounded zlib decompression, exact scanline lengths and filter bytes. Supports standard color types and Adam7 interlace.
- Validates the procedural generator's PNG before reporting success.
- Serializes atlas read/modify/write operations with an exclusive per-atlas lock, refuses busy locks and never automatically removes a possible stale lock.
- Rejects duplicate JSON object keys in existing atlases rather than silently discarding earlier entries.
- Adds regression coverage for malformed PNG streams, decompression expansion, invalid filters, Adam7/indexed PNGs, duplicate atlas keys and lock lifecycle.

## 1.0.11: safe texture-atlas registration

- Adds `register_texture_atlas` alongside the procedural `generate_texture` MCP tool.
- Registers existing PNGs in the Bedrock block (`textures/terrain_texture.json`) or item (`textures/item_texture.json`) atlas while preserving unrelated entries.
- Validates PNG chunk bounds and CRCs, dimensions, project/Resource Pack containment, atlas shape, and symlink safety; refuses conflicting texture identifiers and concurrent atlas changes.
- Does not alter BP/RP item or block definitions. Those definitions must use the registered texture identifier; Minecraft runtime remains `NOT RUN`.

## 1.0.10: dedicated procedural texture MCP tool

- Registers a separate `minecraft-bedrock-texture-generator` stdio MCP server with the `generate_texture` tool, preserving the existing MCP server and its tools.
- Generates real RGBA PNGs inside an existing project's Resource Pack `textures/` folder, using the existing ten-style procedural generator.
- Enforces workspace/project containment, canonical relative POSIX paths, existing parent directories, no symlinked parents, size bounds and no-overwrite behavior.
- Adds an independent JSON-RPC/MCP contract test suite. Generated assets are procedural starter textures, not AI image synthesis, UV-aware painting, or proof of Minecraft rendering.

The original MCP server, plugin identity, permissions, main MCP entry, audit/reference tools and all three default prompts are preserved. Minecraft runtime remains `NOT RUN`.
