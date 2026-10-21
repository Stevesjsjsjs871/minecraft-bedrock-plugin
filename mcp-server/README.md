# Minecraft Bedrock MCP Server (Android / Termux)

A local Model Context Protocol (MCP) server with read-only static-analysis tools for Minecraft Bedrock add-ons. It does **not** execute add-on JavaScript, launch Minecraft, or claim that an in-game test passed.

## Tools

- `validate_manifest_json` — validate JSON text and basic Bedrock manifest fields.
- `validate_manifest_file` — read and validate a local `manifest.json`.
- `inspect_pack_directory` — list a BP/RP folder and report manifest issues and common folder hints.
- `compare_pack_versions` — compare two three-part version arrays.
- `inspect_blockbench_model_json` / `inspect_blockbench_model_file` — inspect .bbmodel elements, texture metadata, outliner UUIDs, duplicate UUIDs and suspicious coordinates.
- `validate_bedrock_geometry_json` — check exported geometry identifiers, bones, parents and cube bounds.
- `inspect_png_texture_file` — read PNG dimensions and bit-depth metadata.
- `validate_json_file` — parse arbitrary local JSON and report top-level structure.

## Install on Android

1. Install Termux from a trusted source such as F-Droid or the official Termux GitHub releases. Avoid mixing Termux and add-on apps from different sources.
2. Open Termux and run:

   ```sh
   pkg update
   pkg upgrade
   pkg install nodejs-lts git
   termux-setup-storage
   ```

3. Clone the existing project and install dependencies:

   ```sh
   cd ~
   git clone https://github.com/Stevesjsjsjs871/minecraft-bedrock-plugin.git
   cd minecraft-bedrock-plugin/mcp-server
   npm install
   npm run check
   ```

4. Start the MCP server:

   ```sh
   npm start
   ```

The server uses **stdio** transport. It is not a website and does not open a network port. Keep it running only when an MCP client launches it as a child process. A mobile app cannot automatically connect to this process unless that app supports local stdio MCP servers and allows configuring a command.

## Android file access

After `termux-setup-storage`, shared storage is normally available under `~/storage/shared`. Example:

```sh
node -e "console.log(require('node:fs').existsSync(process.env.HOME + '/storage/shared'))"
```

Grant Android storage permission if prompted. Then call `inspect_pack_directory` with the actual extracted pack folder path, for example `/data/data/com.termux/files/home/storage/shared/Download/MyBehaviorPack`. The exact path depends on where you saved and extracted the pack.

## Example MCP client configuration

For a client that supports local stdio MCP servers, use the path to the Termux Node binary and server file. Determine the Node path with `which node` inside Termux. Example shape (replace paths with your actual values):

```json
{
  "mcpServers": {
    "minecraft-bedrock": {
      "command": "/data/data/com.termux/files/usr/bin/node",
      "args": ["/data/data/com.termux/files/home/minecraft-bedrock-plugin/mcp-server/server.js"]
    }
  }
}
```

Not every Android or ChatGPT client supports launching local MCP servers. ChatGPT's remote MCP connection requires a reachable HTTPS server; this local stdio implementation alone does not make the server publicly reachable. Do not expose a phone service to the internet without adding authentication and a secure remote transport.

## Blockbench workflow

1. Save or export the project as a `.bbmodel` file.
2. Call `inspect_blockbench_model_file` with the real path, or use `inspect_blockbench_model_json` with its JSON text.
3. Export Bedrock geometry JSON from Blockbench and pass its contents to `validate_bedrock_geometry_json`.
4. Use `inspect_png_texture_file` to check texture dimensions. This tool does not decode image pixels or edit textures.

## More utilities

The server is designed to grow into a read-only developer toolkit first: diagnostics before any destructive repair tools. Future candidates include safe ZIP/.mcpack/.mcaddon inventory, cross-file reference checks, animation-controller validation, and packaging checks.

## Limitations

- Validation is heuristic and covers common manifest fields, not every Bedrock schema rule.
- Directory inspection skips symbolic links and caps results at 500 files by default.
- It does not unpack ZIP, `.mcpack`, or `.mcaddon` archives yet; extract the archive first.
- It does not modify files, execute user scripts, or test in-game behavior.
