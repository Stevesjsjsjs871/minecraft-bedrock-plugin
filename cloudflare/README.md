# Minecraft Bedrock Engineer — Cloudflare Workers MCP (1.4.0)

Architecture: MCP client -> Cloudflare Worker (/mcp, Bearer auth) -> Cloudflare Container -> original Python MCP modules.

The container adapter imports the existing 16 MCP modules and delegates tool calls to their original handlers. Local STDIO configuration remains intact.

Requirements: Workers Paid with Containers enabled, Docker, Node.js/npm and Wrangler 4.

From repository root:
```sh
npm install
npx wrangler secret put MCP_AUTH_TOKEN
npx wrangler deploy
```
Use a long random secret; never commit it. Endpoint: https://<worker-subdomain>.workers.dev/mcp

Health: GET /health. MCP: POST /mcp with Authorization: Bearer <token>. The adapter is stateless; workspace files are ephemeral unless persistent storage is separately configured. Static checks are not an in-game Minecraft test.
