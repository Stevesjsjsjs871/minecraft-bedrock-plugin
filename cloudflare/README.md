# Minecraft Bedrock Engineer — unified remote MCP

## Current architecture

The Cloudflare Worker is now an authenticated **HTTP proxy**, not a second implementation of a reduced toolset:

- ChatGPT MCP endpoint: `POST /mcp` on the Worker.
- Worker validates the public `MCP_AUTH_TOKEN`.
- Worker forwards the unchanged JSON-RPC request to the Python MCP backend.
- Python backend validates a separate `MCP_BACKEND_TOKEN`.
- Python backend imports all 16 original MCP modules and builds `tools/list` directly from their `TOOLS` declarations. Tool calls dispatch to the original module handlers.
- Health endpoint: `GET /health` on both services.

This avoids maintaining a hand-written, incomplete TypeScript copy of the tool registry. Existing local STDIO configuration remains unchanged.

## Required deployment topology

The Python backend must run as a persistent HTTPS container service. The repository root `Dockerfile` builds it and starts `cloudflare/container/app.py`.
The backend initializes `MINECRAFT_BEDROCK_WORKSPACE` to `/data/workspace` when it is not supplied and creates the directory at startup. Mount a persistent volume at `/data` (or configure `MINECRAFT_BEDROCK_WORKSPACE` to a persistent mounted directory) before using write-capable tools; otherwise project files may be lost when the container is replaced.

The Cloudflare Worker Free plan does not execute this Python container. Deploy the container to a Python/Docker-capable host first, then configure the Worker to proxy to it. The backend URL must be a public HTTPS base URL, for example `https://your-service.example`; the Worker appends `/mcp`.

Do not expose the backend without `MCP_BACKEND_TOKEN`. The backend refuses to start if this token is missing and requires it for every POST to `/mcp`. Its `/health` endpoint is intentionally public and read-only.

## Secrets

Configure these as **Workers Builds secrets** (the deploy helper transfers them to Worker runtime secrets without printing values):

- `MCP_AUTH_TOKEN`: public ChatGPT-to-Worker bearer token, at least 32 characters.
- `MCP_BACKEND_URL`: HTTPS base URL of the Python container.
- `MCP_BACKEND_TOKEN`: independent Worker-to-backend bearer token, at least 32 characters.

Configure `MCP_BACKEND_TOKEN` as an environment secret on the Python container as well. Generate independent random values for the two tokens. Never commit them or paste them into chat.

The deploy helper aborts if any required value is missing. It writes a temporary secrets file outside the repository, deploys with Wrangler, and removes the file.

## Verification sequence

1. Check backend `GET /health`; it should report the module and tool counts.
2. Check Worker `GET /health`; `backend_configured` must be `true`.
3. Send MCP `initialize` to Worker `POST /mcp`.
4. Send `tools/list`; verify the returned tool names match the union of the 16 Python modules.
5. Call representative read-only, generation and audit tools. Only then test write-capable tools inside a disposable project.
6. Confirm the ChatGPT custom MCP connection and invoke it in a chat using `@`.

## Security and limits

- Worker and backend use separate bearer credentials.
- The backend requires authentication for all MCP POST requests; only the read-only health check is public.
- The backend enforces an 8 MiB request-body limit.
- The Worker enforces a 1 MiB request-body limit in its current configuration. Large ZIP/image requests may therefore need a later, deliberate limit increase after evaluating Worker platform limits.
- Worker-to-backend requests time out after 30 seconds. Long-running tools may require asynchronous job handling in a future iteration.
- Static audits are not Minecraft runtime verification. Do not claim in-game validation unless performed in the target game.

## Status

The unified proxy and authenticated Python adapter are implemented on the development branch. They are **not deployed or live-verified yet**. A Docker-capable backend host and its secrets are still required. The Cloudflare Free Worker alone cannot run the Python modules.
