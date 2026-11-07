# Release Notes — 2.0.4

## Skills-only maintenance hardening

- Adds the standalone `texture-painter` utility to `texture-painting-pipeline` for explicit deterministic pixel operations on selected geometry UV regions, including fill, border, checker, stripes, gradient and seeded noise.
- Adds regression coverage for source preservation, alpha handling, UV selectors, overlap controls, bounds, path safety and bounded PNG handling.
- Strengthens package-integrity checks against nested MCP configuration files and renamed protocol adapters, with negative fixtures to prevent false-positive Skills-only acceptance.
- Extends reference texture transfer regression coverage for transforms, filtering, alpha, layering, overlaps, invalid mappings, path collisions and symlink inputs.
- Adds hardened file-opening checks for archive and image inputs, including no-follow semantics where supported.
- Updates the six-level Python script registry and tool evidence to distinguish local development execution from plugin-host integration.

## Verification and limitations

- Local Skills test suite: 473/473 test executions passed in the development environment.
- Focused texture painter suite: 26/26 passed.
- Reference transfer suite: 28/28 passed.
- ZIP safety suite: 8/8 passed.
- Package checker suite: 25/25 passed.
- Strict Skills-only release gate remains BLOCKED while historical files under `server/` remain in the package. Those files are retained as inert migration material because several contain useful domain logic; no legacy server was activated or removed in this release candidate.
- ChatGPT-host skill/script execution, Minecraft import/render/gameplay and Blockbench integration were not verified in this development session.
