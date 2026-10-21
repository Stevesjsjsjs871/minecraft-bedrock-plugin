# Minecraft Bedrock Blockbench Bridge

This plugin connects a Blockbench tab to a local Termux MCP server over HTTP loopback.

## 1. Start Termux server

Update your checkout and install dependencies:

\`\`\`sh
cd "$HOME/minecraft-bedrock-plugin"
git pull
cd mcp-server
npm install
npm run check
npm start
\`\`\`

Keep Termux running. The server's MCP stdio transport and a local HTTP bridge run together. The bridge binds only to \`127.0.0.1:8765\`; it is not exposed to your Wi-Fi or the public internet.

## 2. Load the Blockbench plugin

Download \`minecraft_bedrock_mcp_bridge.js\` and load it through Blockbench's Plugins dialog if your browser version supports loading a local plugin file. The plugin polls the local bridge and currently supports:
- Reading a summary of the active project
- Creating a six-part starter humanoid blockout

## 3. Check connection

In Blockbench, open Tools → Check Termux Bridge. If the browser blocks local-network requests or reports a CORS/Private Network Access error, this browser build cannot use the loopback bridge directly; do not disable browser security. We will need a secure relay or another supported client path instead.

## Security

- Server binds to IPv4 loopback only.
- CORS is restricted to \`https://web.blockbench.net\`.
- Only fixed, allowlisted editor commands are implemented; no arbitrary code execution.
- This is an experimental bridge and has not yet been verified on every Android browser / Blockbench version.
