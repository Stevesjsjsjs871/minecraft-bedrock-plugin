# Release notes — 2.0.9

## Local utility review and archive intake hardening

- Reviewed all 90 registered Python files against Technical Guide 2.0 and refreshed the six-level execution registry and SHA-256 inventory.
- Hardened `skills/automated-validation/scripts/bedrock_audit.py` to reject unsafe raw ZIP member paths, case-insensitive duplicate names, symlink members and file/directory path collisions before CRC/decompression.
- Added five focused adversarial archive tests; archive safety suite now passes 17/17.
- Completed missing texture-painter registry metadata and corrected two false dependency failures for visual-reference analyzer local sibling imports.
- All 28 active Skills Python entry-point `--help` smoke checks return exit 0. Full Skills suite: 27/27 files, 500/500 tests PASS.
- Architecture: 28/28 PASS. Package integrity: 19 PASS / 0 FAIL / 1 WARN (34 inert historical `server/` files retained).

## Explicit limits

- CPython 3.13.5 local execution only. Installed ChatGPT-host script integration remains NOT TESTED.
- Minecraft Bedrock import, rendering and gameplay remain NOT RUN.
- Historical `server/` MCP source and tests remain inert and were not executed or deleted.
