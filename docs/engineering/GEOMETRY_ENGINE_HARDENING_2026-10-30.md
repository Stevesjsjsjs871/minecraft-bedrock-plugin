# Standalone geometry analyzer hardening — 2026-10-30

## Source state

- Base branch: fix/cloudflare-profile-contract-and-ci-20261030
- Base commit: 92353c6debb6f1f4eb2c6dac649c8f161ce26abd
- Current Plugin Creator release inspected: 1.5.10, Release ID pluginrel_6ae4ad7132e48191be6d353396338ede.
- Plugin Creator 1.5.10 contains an initial standalone geometry analyzer, but the analyzer has unbounded file/overlap work, silently assumes a 64x32 canvas, accepts non-integer schema values, checks mesh fields at the wrong JSON level, and overwrites report files.
- No Plugin Creator files were changed.

## Changes

- Add a hardened dependency-free geometry analyzer and CLI.
- Require exact geometry selection when multiple geometry entries exist; reject duplicate identifiers.
- Enforce input, bone, cube, region, canvas and overlap-comparison safety limits.
- Treat absent texture canvas dimensions as unknown (WARN), not as an invented 64x32 default.
- Require integer texture dimensions and integer uv_rotation values.
- Detect poly_mesh and texture_meshes on bones, matching the official geometry schema.
- Use a bounded sweep-line overlap algorithm and report truncation explicitly.
- Reject symlinked geometry input and refuse to overwrite an existing JSON report.
- Isolate test-only PNG shims so later tests load the real shared validator.
- Preserve existing MCP server tools and all default prompts.

## Official reference checked

Microsoft Learn, Visuals Documentation — minecraft:geometry.v1.21.0, last updated 2026-03-05:
https://learn.microsoft.com/en-us/minecraft/creator/reference/content/visualreference/geometry.v1.21.0?view=minecraft-bedrock-stable

The schema places poly_mesh and texture_meshes on bones; per-face uv_rotation is an integer with values 0, 90, 180 or 270; texture_width and texture_height are integer properties.

## Validation plan

- Compile geometry engine and tests.
- Run the standalone geometry engine unit tests.
- Run full server regression tests and existing analyzer/texture/package suites.
- Run package/manifest/MCP consistency checks.
- Minecraft runtime, visual rendering and Blockbench interoperability remain NOT RUN.

## Risks / limits

- The analyzer covers classic box and per-face cube UV bounds/overlaps only.
- It does not parse poly_mesh/texture_meshes projections, client-entity texture bindings, separate PNG/canvas associations or renderer behavior.
- The visual UV template renderer remains in the preserved legacy server module and is not migrated here.
