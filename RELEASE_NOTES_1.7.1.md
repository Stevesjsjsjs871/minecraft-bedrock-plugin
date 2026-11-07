# Minecraft Bedrock Engineer 1.7.1 — Reference audit reliability and version correction

## Release sequence
Live Plugin Creator metadata was checked before editing: current release is 1.7.0 (`pluginrel_6ae5ab0ce4148191b4169ab76db11629`). The immediate patch successor is 1.7.1.

## Changes
- Synchronizes plugin.json, compatibility manifest, VERSION, README, CHANGELOG, release notes and VERSION_HISTORY to 1.7.1.
- Hardens reference archive inspection with ZIP CRC validation and hostile-entry handling.
- Adds tests for corrupt ZIPs, traversal paths, duplicate paths and comment-aware parsing.
- Preserves existing prompts, skill corpus, sample resources and the Skills-only/no-MCP architecture.

## Boundaries
- Legacy files with MCP-era names are retained as historical/inert materials pending a separate dependency-aware migration; no tool or backend is enabled by this update.
- No third-party reference archive contents are copied into the plugin.
- Runtime behavior inside Minecraft is not tested by this package update.
