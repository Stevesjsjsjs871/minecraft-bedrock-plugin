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

The remote Worker does not execute the existing Python filesystem, archive, MCT CLI, texture, geometry, or animation audit handlers. Those remain available through the local Python MCP runtime. The remote gateway is being expanded in small TypeScript-native steps rather than pretending Python containers run on the Free plan.

## Deploy

Cloudflare Workers Free is sufficient for this gateway's current feature set.

1. In Workers & Pages, keep the GitHub-connected project and production branch `feat/cloudflare-workers-mcp`.
2. Add a Worker secret named `MCP_AUTH_TOKEN` (long random value). Never commit or share the secret in chat.
3. Trigger a new deployment from the latest commit.

No build command is required. Deploy command: `npx wrangler deploy`.

Endpoint after deployment: `https://<worker-subdomain>.workers.dev/mcp`

Health check: `GET https://<worker-subdomain>.workers.dev/health`

MCP requests use JSON-RPC over HTTP POST with the Bearer token. This implementation is stateless and does not require session storage.

## Legacy files

`Dockerfile` and `cloudflare/container/app.py` are retained for reference only; the Free Worker deployment does not build or invoke them.
