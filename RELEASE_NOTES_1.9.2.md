# Minecraft Bedrock Engineer 1.9.2

## Version-aware compatibility and migration workflow

- Adds a specialist compatibility skill separating game build, pack/JSON format versions, Script API dependencies, manifest minimum engine versions, experiments and Creator Tools versions.
- Adds explicit compatibility states for supported, experimental, beta, deprecated, removed, unknown and not applicable.
- Requires exact-version official documentation and matching Mojang Samples provenance before migration recommendations.
- Adds conservative schema-migration rules: no automatic global `format_version` bumps, exact affected-file coverage, and explicit runtime-test boundaries.
- Adds a dated 1.26.50 reference covering stricter entity validation, `minecraft:interact` and projectile schema changes, released block features and stable Script API module versions.
- Adds four focused regression tests.

## Validation

- Focused skill tests: 4 passed.
- Python syntax compilation: passed.
- Manifest/default-prompt parity: passed (12 prompts unchanged).
- Full package checker: not run against the complete original source tree in this task.
- Minecraft runtime/import/render/gameplay tests: NOT RUN.

Preserves plugin identity, USER scope, PRIVATE discoverability and all existing default prompts.
