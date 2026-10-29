# Development log

## 2026-10-30 — PNG decoder validation for texture-atlas registration

### Recovered state
- Plugin Creator: minecraft-bedrock-engineer version 1.0.11, current release pluginrel_6ae3d2b1b6888191bf4727998f694e48 (private; not modified in this stage).
- GitHub main: 4eb35503095c735d725597bdb2f517f4bf188803, version 1.0.11.
- Latest main CI: run #103, success; run #102 also success.
- Existing draft PR #1 is still open, but its branch is 18 commits ahead and 2 behind main; its 1.0.10 integrated-server approach is superseded by the separate texture MCP server already present on main. It is not safe to merge as-is.
- The current Plugin Creator texture MCP source and tests match GitHub main byte-for-byte. Some manifest, MCP metadata and skill documentation files differ; this drift is recorded for a separate follow-up.
- The three original default prompts are present and unchanged in both manifests.

### Selected task and acceptance criteria
Harden register_texture_atlas so a PNG with valid chunk CRCs but invalid compressed image data cannot be registered. Accept only structurally valid PNG image streams whose decompressed byte count and scanline filter bytes match IHDR.

### Changes
- Extend server/texture_generator_mcp.py::_read_valid_png to validate legal IHDR color-type/bit-depth combinations, compression/filter/interlace methods, palette placement and bounds, consecutive IDAT chunks, zlib stream integrity, exact decompressed scanline length, and filter bytes 0–4. Adam7 pass dimensions are accounted for.
- Add three negative regression tests that rewrite IDAT data while recomputing the chunk CRC (invalid zlib stream, incorrect decompressed scanline length, invalid scanline filter byte), plus a positive 5x5 RGBA Adam7 fixture covering all seven passes.
- Preserve both stdio MCP servers, tool names, plugin identity and all default prompts.
- No Plugin Creator update or public release was made.

### Verification
- Pre-change baseline: GitHub Actions run #103 passed all configured checks on main (Python compile, MCP/unit suites, benchmark tests, Mojang sample-index tests, texture generator tests, package-integrity audit, analyzer regression and version/prompt consistency).
- New branch/PR CI: pending at time of commit creation.
- Minecraft import/rendering and Creator Tools CLI runtime: NOT RUN.

### Risks and next step
- The new validator is static PNG-structure validation; Minecraft's exact importer behavior still requires an in-game test.
- Next: reconcile the Plugin Creator/GitHub metadata drift without changing the three prompts, then retire or clearly supersede draft PR #1 after review.
