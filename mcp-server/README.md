# Minecraft Bedrock Engineer MCP server

Read-only MCP adapter around the existing static analyzer. It exposes five focused tools:

- `audit_archive` — full report or concise summary.
- `compare_baseline` — candidate-versus-baseline file diff and findings.
- `get_resource_graph` — resource definitions, references and coverage metadata.
- `validate_manifest` — manifest-related checks and findings.
- `inspect_archive` — safe archive inventory without extraction.

## Safety model

- Every tool is annotated `readOnlyHint=true`, `destructiveHint=false`, and `idempotentHint=true`.
- Inputs are validated before the analyzer starts. Only regular `.mcaddon`, `.mcpack`, or `.zip` files up to 250 MiB are accepted; symbolic links are rejected.
- The analyzer is run as a subprocess with a 120-second timeout. Pack scripts are never executed and archives are never extracted.
- Tool results are structured JSON. Runtime status remains `NOT RUN`.
- MCP annotations are client hints, not an authorization boundary. Run this server only in a trusted environment and restrict filesystem/network access at the host/container level.

## Run locally

Requires Python 3.10+.

```bash
python -m venv .venv
# Linux/macOS
. .venv/bin/activate
python -m pip install -r mcp-server/requirements.txt
MBE_MCP_TRANSPORT=stdio python mcp-server/server.py
```

For local protocol testing, use an MCP client/Inspector configured for stdio with the command `python` and args `["mcp-server/server.py"]`. Set `MBE_MCP_TRANSPORT=stdio`.

## Run Streamable HTTP for deployment

```bash
python -m pip install -r mcp-server/requirements.txt
MBE_MCP_TRANSPORT=streamable-http MBE_MCP_HOST=0.0.0.0 MBE_MCP_PORT=8000 python mcp-server/server.py
```

Place behind a trusted HTTPS reverse proxy and configure authentication, request limits, timeouts and logs before exposing it publicly. Do not expose an unauthenticated service that can read arbitrary host files.

## Important: not yet connected to ChatGPT

This directory is the MCP server implementation, not a deployed endpoint. A portable plugin uses root `mcp.json` with a stable public HTTPS Streamable HTTP URL. That configuration must not be added with a fake URL. Public ChatGPT integration is incomplete until the server is deployed, security-reviewed, and registered in `mcp.json`; local stdio is for development/testing.

The server sends its shared workflow instructions during MCP initialization; the first 512 characters prioritize the tool call order and static-only limitation.
