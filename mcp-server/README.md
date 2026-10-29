# Minecraft Bedrock Engineer MCP server — 0.6.7

This directory contains the seven-tool read-only stdio MCP server shipped with the private 0.6.7 plugin. It uses Python's standard library and the repository's static analyzer; no third-party MCP SDK is required.

## Tools
- `audit_pack` — full static audit report.
- `compare_baseline` — candidate-versus-baseline comparison.
- `get_resource_graph` — resource-reference graph, optionally filtered by domain.
- `validate_manifest` — manifest and dependency checks.
- `audit_geometry` — geometry, bone, cube and UV checks.
- `audit_animation` — animation/controller checks.
- `inspect_archive` — archive metadata and unsafe/duplicate path indicators without extraction.

All tools are read-only. Schemas reject unknown arguments; paths are confined to `MINECRAFT_BEDROCK_WORKSPACE`; archive size, uncompressed-size and entry-count limits are enforced. Pack scripts are never executed, archives are never extracted, and runtime status remains `NOT RUN`.

## Run locally
Requires Python 3.10+.

```bash
python -m py_compile mcp-server/server.py mcp-server/tests/test_server.py
python -m unittest discover -s mcp-server/tests -v
```

Set `MINECRAFT_BEDROCK_WORKSPACE` to an existing directory containing the archives you want to inspect. If unset, the server process's working directory is used.

## Integration status
This is a local stdio MCP server, **not a deployed remote endpoint**. The repository does not claim that it is connected to ChatGPT web/mobile. A remote integration requires a secured, stable HTTPS MCP endpoint and a separately configured host connection; no placeholder URL is provided.
