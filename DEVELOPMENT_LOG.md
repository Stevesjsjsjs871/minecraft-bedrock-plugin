# Development log

## 2026-10-30 — PNG decoder validation for texture-atlas registration

### Recovered state
- Plugin Creator: minecraft-bedrock-engineer version 1.0.11, current release pluginrel_6ae3d2b1b6888191bf4727998f694e48 (private; not modified in this stage).
- GitHub main: 4eb35503095c735d725597bdb2f517f4bf188803, version 1.0.11.
- Latest main CI: run #103, success; run #102 also success.
- Existing draft PR #1 is still open, but its branch is 18 commits ahead and 2 behind main; its 1.0.10 integrated-server approach is superseded by the separate texture MCP server already present on main. It is not safe to merge as-is.
- Before this branch, the Plugin Creator texture MCP source and tests matched GitHub main byte-for-byte. Metadata/documentation drift exists: plugin.json and .codex-plugin/plugin.json differ in descriptions/keywords/interface metadata; README.md, CHANGELOG.md and visual-resource-pipeline/SKILL.md differ; mcp.json is semantically equal and .mcp.json is byte-for-byte equal. The three defaultPrompt entries are byte-for-byte equal. GitHub code search returned no TODO/FIXME matches and no open issues were found; this does not prove no informal TODOs exist outside the indexed default branch.
- The three original default prompts are present and unchanged in both manifests.

### Selected task and acceptance criteria
Harden register_texture_atlas so a PNG with valid chunk CRCs but invalid compressed image data cannot be registered. Accept only structurally valid PNG image streams whose decompressed byte count and scanline filter bytes match IHDR.

### Changes
- Extend server/texture_generator_mcp.py::_read_valid_png to validate legal IHDR color-type/bit-depth combinations, compression/filter/interlace methods, palette placement and bounds, consecutive IDAT chunks, zlib stream integrity, exact decompressed scanline length, and filter bytes 0–4. Adam7 pass dimensions are accounted for. It also accepts unused trailing bytes in the final IDAT chunk, as required by the W3C PNG specification, and rejects a lowercase reserved third chunk-name bit.
- Add three negative regression tests that rewrite IDAT data while recomputing the chunk CRC (invalid zlib stream, incorrect decompressed scanline length, invalid scanline filter byte), plus positive 5x5 RGBA Adam7 and unused-trailing-IDAT fixtures. The reader caps file reads at MAX_PNG_BYTES + 1 before rejecting oversized inputs.
- Preserve both stdio MCP servers, tool names, plugin identity and all default prompts.
- No Plugin Creator update or public release was made.

### Verification
- Pre-change baseline: GitHub Actions run #103 passed all configured checks on main (Python compile, MCP/unit suites, benchmark tests, Mojang sample-index tests, texture generator tests, package-integrity audit, analyzer regression and version/prompt consistency).
- Initial code/test commit d9ca200 passed run #106 (136 unit tests); documentation-only commits 5ab6fd3 and f5b801d passed runs #107 and #108. Final PNG compatibility commit 8a82953 passed run #109. Run #109 compiled all listed Python modules; passed 137 unit tests across five suites (98 MCP/server, 12 benchmark, 6 sample-index, 12 procedural texture, 9 package-integrity); passed all 18 analyzer regression cases; passed package-integrity audit and version/manifest/default-prompt/MCP-configuration consistency checks. All five new PNG cases passed: three negative CRC-valid corruptions and two positive fixtures (Adam7 and trailing IDAT bytes). Runs #104–#108 also passed on earlier heads.
- Reference basis: W3C PNG Specification (https://w3c.github.io/png/), especially IDAT concatenation/trailing-byte behavior, chunk naming and IHDR restrictions; Microsoft Learn custom block tutorial (https://learn.microsoft.com/en-us/minecraft/creator/documents/addcustomdieblock?view=minecraft-bedrock-stable) and item icon reference (https://learn.microsoft.com/en-us/minecraft/creator/reference/content/itemreference/examples/itemcomponents/minecraft_icon?view=minecraft-bedrock-stable) confirm the Bedrock atlas/key relationship.
- Minecraft import/rendering and Creator Tools CLI runtime: NOT RUN. GitHub Actions emitted non-failing Node.js 20 deprecation and Node punycode warnings.

### Git state
- PR #2 remains Draft and unmerged. Final code/test commit: 8a829534218e058e11faa2e8b7bb74dda1b1f680; main remains unchanged. Local uncommitted changes on the user's own workstation could not be inspected.
- PR #1 remains open and unmerged; do not merge its divergent 1.0.10 implementation without a fresh review.

### Risks and next step
- The new validator is static PNG-structure validation, not a full pixel reconstruction: it does not validate every ancillary-chunk semantic or every palette-index value. Minecraft's exact importer behavior still requires an in-game test.
- Residual file-operation risk: _atomic_update_json compares the existing atlas hash and then calls os.replace. The compare and replace are separate operations, so a non-cooperating external writer can still race in the narrow interval between them; path-based parent checks also are not a complete defense against a hostile directory swap. The next safety task is to harden this update path with a cross-platform, tested concurrency strategy before claiming strict lost-update protection.
- After that, reconcile the Plugin Creator/GitHub metadata and documentation drift without changing the three prompts, then review and clearly supersede draft PR #1.
