---
name: mcp-integration
description: Select and safely use the local STDIO MCP server registry and the separately connected remote Bedrock gateway.
---

# MCP integration

## Local STDIO profile

The portable `mcp.json` and compatibility `.mcp.json` register 16 local processes for core authoring, archive inspection, Mojang sample search/read, pack graph/baseline diff, texture generation/auditing, entity authoring, animation, geometry/UV, painting and reference transfer/review.

The local workspace is `${PLUGIN_DATA}`; each process receives `MINECRAFT_BEDROCK_WORKSPACE=${PLUGIN_DATA}`. Verify the host-expanded path and live `tools/list` result before any write. Local STDIO requires a host that supports process launch and Python 3 on PATH.

The core server has 19 tools, including the Creator Tools CLI bridge. Call `creator_tools_status` first; if the CLI is absent, report `UNAVAILABLE`. MCT operations must never install or download software.

## Remote Worker profile

The separately connected endpoint is `https://minecraft-bedrock-plugin.msg2026.workers.dev/mcp`; health endpoint: `https://minecraft-bedrock-plugin.msg2026.workers.dev/health`.

It exposes exactly four tools: `bedrock_generate_manifest`, `bedrock_validate_manifest`, `bedrock_read_plugin_source` and `bedrock_plugin_capabilities`. It is read-only with respect to user projects and cannot invoke local Python handlers or Creator Tools CLI.

Authentication is Bearer-based and must be stored by the connected client. Never commit a token. The remote connection is managed separately from the plugin package; no app ID or credential is embedded here.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s server/tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s cloudflare/tests -p 'test_*.py' -v
```

A passing local registry handshake proves the server scripts answer MCP `initialize` and `tools/list`; it does not prove ChatGPT has connected to the Worker or that Minecraft runtime behavior works.
