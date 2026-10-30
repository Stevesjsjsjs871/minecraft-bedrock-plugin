# Minecraft Bedrock Engineer — 1.0.12

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
