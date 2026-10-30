# UV template renderer hardening — 2026-10-30

## Source state

- GitHub base PR: #18, head commit e09d1fdc6ef6a3278995ec143c0d9bc5c5cc6e69.
- PR #18 workflow run 41076073453 completed successfully; the geometry analyzer suite passed 28/28 and the server regression suite passed 359/359.
- Current Plugin Creator release re-read before this audit: 1.5.12, Release ID pluginrel_6ae4b2ea22f88191a00187713b7e9b91.
- Plugin Creator is Skills-only. Its current standalone uv_template_engine.py was inspected, but not modified.
- The current renderer has an oversized 64,000,000-pixel default, follows resolved input/output paths, can create parent directories, does not verify its encoded PNG or on-disk bytes, assumes the geometry analyzer always supplies a canvas, and can walk extremely long Bresenham lines for extreme UV coordinates.
- The renderer also emits a guide for cube UVs even when bone-level mesh UV data exists, which can make an incomplete result look complete.

## Changes

- Add a standalone uv_template_engine.py on top of PR #18's bounded geometry analyzer.
- Require declared texture dimensions or an explicit --canvas WIDTH HEIGHT override.
- Refuse bone-level poly_mesh and texture_meshes rather than silently omitting mesh UV regions.
- Preserve mirror and negative uv_size information as review metadata; do not claim exact renderer face orientation.
- Clip rectangle lines to the output canvas before rasterization.
- Cap output at 4,194,304 pixels and 32 MiB encoded PNG; callers cannot raise the hard cap.
- Validate PNG signature, chunk order, CRCs, RGBA8 IHDR, decompressed scanline length and filter bytes.
- Create output exclusively in an existing parent directory, refuse symlinks/overwrites, read the file back, and verify SHA-256.
- Add focused regression tests and wire compilation/tests into GitHub Actions.
- Update the geometry/UV skill and script README with actual limits and unsupported cases.

## Official reference checked

Microsoft Learn, Visuals Documentation — minecraft:geometry.v1.21.0, last updated 2026-03-05:
https://learn.microsoft.com/en-us/minecraft/creator/reference/content/visualreference/geometry.v1.21.0?view=minecraft-bedrock-stable

The reference documents per-face UV objects, clockwise uv_rotation values, texture dimensions, mirror behavior, and bone-level poly_mesh / texture_meshes. It does not define negative uv_size orientation; the renderer therefore marks such regions for human review rather than claiming exact face sampling.

## Validation plan

- Compile geometry_engine.py, uv_template_engine.py and both focused test modules.
- Run geometry analyzer tests and UV renderer/PNG safety tests independently.
- Run the full server, texture, indexer, package and capability-contract suites through the existing workflow.
- Verify the new output PNG by parsing its chunks, CRCs, IHDR and decompressed scanlines, then read it back and compare SHA-256.
- Minecraft runtime, Blockbench interoperability, visual face orientation and texture binding remain NOT RUN.

## Scope and safety

- This is a GitHub-only stacked draft based on PR #18.
- Existing MCP registrations, project IDs and all three original default prompts remain untouched.
- Plugin Creator 1.5.12 was read for source audit only. No Plugin Creator mutation, release creation, deployment or public release was performed.
- PR #18 must be reviewed/merged before this dependent PR; do not merge this branch independently of its base.


## Post-CI security review

The first PR CI run (GitHub Actions run 41079643776) completed successfully, including the renderer test step. A follow-up code review identified that PNG validation called zlib flush after a bounded decompress. That could permit additional buffered output beyond the expected scanline budget for a malicious compressed stream supplied to the public validator.

The validator now requires the bounded decompress call itself to reach the exact expected output and the zlib end marker; it no longer calls flush. The caller-supplied max_pixels argument is also constrained by the same hard 4,194,304-pixel cap. Added regression cases cover decompression overrun, truncated zlib streams, hard-cap override attempts, and line clipping across / outside the canvas.

The workflow must be rerun on the updated HEAD before this follow-up can be called verified.
