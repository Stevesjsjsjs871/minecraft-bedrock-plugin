# Minecraft Bedrock Engineer 1.7.2 — Skills-only maintenance and regression repair

## Release sequence
Plugin Creator current metadata was verified at 1.7.1 (`pluginrel_6ae5ace0dc7c81919fa7a302ed5b79e0`). This candidate advances one patch: 1.7.1 → 1.7.2.

## Changes
- Retires the old MCP-era package-integrity checker and registry-specific tests; the Skills-only package checker is the single release gate.
- Adds `legacy-source-migration` to govern safe extraction of reusable logic from historical code into local utilities, without activating remote services or backends.
- Repairs the Geometry & UV PNG test wrapper's module resolution.
- Fixes texture-generator CLI test parsing when the host injects Python startup diagnostics into stderr.
- Treats empty Cloudflare directories as inert placeholders while still failing if actual deployment files are present.
- Corrects version governance documentation to the live 1.7.1 base.

## Preservation and boundaries
- Both manifests retain the same plugin identity, Skills path and exact defaultPrompt array.
- USER scope and PRIVATE discoverability remain unchanged.
- Historical server source remains inert; this candidate does not create or configure MCP.
- Minecraft import, rendering, gameplay, multiplayer and Blockbench runtime checks: NOT RUN.
