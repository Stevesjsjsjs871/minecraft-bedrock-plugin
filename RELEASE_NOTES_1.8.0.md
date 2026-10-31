# Minecraft Bedrock Engineer 1.8.0

## Highlights

- Adds a standalone local reference-texture transfer tool that maps manually reviewed PNG crops onto explicit Bedrock geometry UV face selectors.
- Supports classic box and per-face cube UV regions, nearest/bilinear sampling, rotation, flips, opacity, over/replace compositing, and optional base texture preservation.
- Validates PNG chunk integrity, supported color/depth/interlace modes, source crop bounds, geometry canvas, UV overlap, duplicate mapping selections and texel budgets.
- Writes to a new output path exclusively and records SHA-256 hashes and a structured JSON report.
- Expands the package-integrity gate to require the transfer CLI/tests and reject legacy server/MCP imports from the new local utility.
- Aligns specialist skill documentation with real standalone implementation and clearly labels Minecraft runtime/rendering tests as not run.

## Architecture and compatibility

Skills-and-instructions-only remains the active plugin architecture. The new utility is local Python code and does not add a remote service, MCP configuration, registry, or plugin-owned backend. Existing plugin identity, scope, discoverability and the exact 12 default prompts are preserved. Historical server sources remain inert; broad deletion is deferred until each dependency cluster is migrated and tested.

## Validation

Validation evidence is recorded in the release work report. Static tests do not prove successful import or rendering in Minecraft; Bedrock runtime and Blockbench checks remain `NOT RUN` unless performed separately.
