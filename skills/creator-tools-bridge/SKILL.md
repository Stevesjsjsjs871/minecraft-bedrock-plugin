---
name: creator-tools-bridge
description: Use when invoking the real local Minecraft Creator Tools CLI bridge exposed by the core MCP server.
---

# Minecraft Creator Tools CLI bridge

The local `minecraft-bedrock-engineer` STDIO server registers these Creator Tools bridge operations:

- Call `creator_tools_status` to detect the installed MCT CLI and report its path/version; this is read-only and never installs it.
- Call `creator_tools_catalog` to inspect capabilities exposed by the installed CLI; no download or installation.
- Call `validate_with_mct` to invoke the installed CLI's validation operation for an explicitly selected project and capture its actual result.
- Call `create_entity_with_mct` only when the user requested entity creation; it stages a supported handoff and merges validated new files after a clean diff.

## Safety and execution

1. Verify the live `minecraft-bedrock-engineer` MCP server and tool schemas before calling any bridge operation.
2. Start with `creator_tools_status`; if the CLI is absent, report `UNAVAILABLE`. Never install software, download executables, accept EULAs or invent CLI flags.
3. Inspect the exact CLI version and catalog before selecting a command. Do not assume capabilities from a different Creator Tools release.
4. For validation, capture the exact project path, command arguments, exit code and output. Keep plugin static-audit results separate from MCT results.
5. For entity creation, require the exact target project, template ID and entity slug; preserve existing files and refuse collisions. Re-inspect every staged output and report the diff.
6. The remote Cloudflare Worker does not invoke MCT CLI. This bridge is available only through the local STDIO server when the host exposes it.
7. Minecraft import, rendering, gameplay and Blockbench interoperability remain `NOT RUN` unless actually tested.
