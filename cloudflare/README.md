# Minecraft Bedrock Engineer — Cloudflare Workers Free MCP Gateway

## Architecture

The remote endpoint is a stateless Cloudflare Worker. It does **not** use Cloudflare Containers, Durable Objects, paid storage, a Docker runtime, or a paid external API.

- MCP HTTP endpoint: `POST /mcp`
- Health endpoint: `GET /health`
- Authentication: `Authorization: Bearer <MCP_AUTH_TOKEN>`
- Source reference reads: public GitHub repository, restricted to `server/` and `skills/` paths.
- Local MCP: the existing Python STDIO servers remain unchanged and retain the full local toolset.

## Free remote toolset (current phase)

- `bedrock_generate_manifest` — generate a BP/RP manifest with fresh UUIDs.
- `bedrock_validate_manifest` — static manifest structure/UUID/version checks.
- `bedrock_read_plugin_source` — read bounded source/reference files from this repository.
- `bedrock_plugin_capabilities` — report the preserved local modules and remote limitations.

By default, the Worker retains its four lightweight TypeScript tools. To expose the complete Python toolset remotely, deploy a separate Python MCP backend and configure Worker settings `MCP_BACKEND_URL` (HTTPS MCP endpoint) and `MCP_BACKEND_TOKEN` (a long random backend-only secret). The Worker authenticates ChatGPT using `MCP_AUTH_TOKEN`, then proxies MCP JSON-RPC requests to the Python backend with the separate backend token. The Python adapter checks that token before dispatching to the preserved Python modules. Do not reuse the public Worker token as the backend token.

The Python backend must run `cloudflare/container/app.py` with the original plugin source mounted at `/app/plugin` (or set `PLUGIN_ROOT`), dependencies installed, and `MCP_BACKEND_TOKEN` configured as a runtime secret. The backend must have a publicly reachable HTTPS endpoint. This repository change adds the authenticated proxy path; it does not provision the Python hosting service automatically. Until the backend is deployed and both Worker settings are configured, the Worker continues to use its four-tool fallback.

## Deploy

Cloudflare Workers Free can host the proxy, but a separate reachable Python host is required for the full toolset.

1. In Workers & Pages, keep the GitHub-connected project and production branch `feat/cloudflare-workers-mcp`.
2. In Workers Builds → Settings → Variables and secrets, add a **Secret** named `MCP_AUTH_TOKEN` with a long random value (at least 32 characters). Workers Builds secrets are build-time only and are not automatically available to the running Worker.
3. Set the Workers Builds **Deploy command** to `node cloudflare/deploy-with-secrets.mjs`. This helper creates a temporary secrets file outside the repository, invokes `wrangler deploy --secrets-file`, and removes the temporary file.
4. When the Python backend is ready, also configure `MCP_BACKEND_URL` and `MCP_BACKEND_TOKEN` as Worker settings, then trigger a new deployment from the latest commit.

Do not commit or share the secret in chat. The deploy helper fails before deployment if `MCP_AUTH_TOKEN` is absent or shorter than 32 characters.

Endpoint after deployment: `https://<worker-subdomain>.workers.dev/mcp`

Health check: `GET https://<worker-subdomain>.workers.dev/health`

MCP requests use JSON-RPC over HTTP POST with the Bearer token. This implementation is stateless and does not require session storage.

## Legacy files

`Dockerfile` and `cloudflare/container/app.py` are retained for reference only; the Free Worker deployment does not build or invoke them.
