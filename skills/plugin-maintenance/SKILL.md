---
name: plugin-maintenance
description: Maintain Minecraft Bedrock Engineer as a combined Skills, local MCP, Creator Tools bridge and remote Worker package.
---

# Plugin maintenance

## Architecture invariants

- Preserve the stable plugin identity, both manifests, all 12 default prompts and their original first three entries.
- Keep the specialist Skills and standalone validators.
- Keep all 16 local STDIO MCP server registrations, their module files and focused tests. The workspace is scoped to `${PLUGIN_DATA}` through `MINECRAFT_BEDROCK_WORKSPACE`; reject path traversal and symlink escapes.
- Preserve the 19-tool core server and its Creator Tools bridge. MCT detection must never auto-install or download software.
- Keep the remote Cloudflare Worker as a separate Streamable HTTP gateway with four limited tools. It does not provide local filesystem, MCT, texture, geometry or animation execution.
- Never commit the Bearer token or place credentials in MCP configuration, headers, source or logs.
- Do not restore Spatial GUI.

## Maintenance loop

1. Read current Plugin Creator metadata/release ID, GitHub branch/PR chain, CI and prior development log.
2. Verify live MCP registrations and tool schemas from source and tests; distinguish local STDIO from the remote Worker.
3. Map every module's imports, paths, writes and tests before editing. Keep file operations inside the configured workspace and refuse overwrites.
4. Use exact-version Microsoft/Mojang docs and samples for Bedrock behavior; label runtime assumptions.
5. Make one small, testable change in a separate branch/PR. Do not rewrite large modules or merge without approval.
6. Run focused MCP protocol/registry tests, server tests, skill/package checks, Cloudflare contract/type checks and reproducible package checks where available.
7. Update README, CHANGELOG, VERSION, both manifests and release notes together. Confirm prompt parity.
8. Never publish a Plugin Creator release, deploy the Worker or publish a public release without explicit user approval.

## Evidence

Record exact commands, exit codes and counts. Static MCP handshake tests do not prove live ChatGPT connection, Worker availability, MCT CLI availability, Minecraft runtime, rendering or Blockbench behavior. Report untested areas as `NOT RUN`.
