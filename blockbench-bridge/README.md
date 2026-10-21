# Minecraft Bedrock Blockbench Bridge

A Blockbench plugin that adds editor-side helpers to the current project.

## Current features

- Create Bedrock Mob Blockout: makes a basic six-part humanoid starter model. If the project already contains elements, it asks before adding.
- Export Project Summary (JSON): exports counts and basic transforms from the current project for diagnostics.
- No remote JavaScript execution, network listener, or external connection.

## Install

1. Download minecraft_bedrock_mcp_bridge.js from this repository.
2. Open Blockbench and its Plugins dialog.
3. Use Load Plugin from File if your Blockbench version offers it, then select the JavaScript file.
4. Enable the plugin. Use the Tools menu to create a starter model or File > Export to export a project summary.

## Android note

Blockbench Web runs in the browser and cannot host a local Node.js MCP server itself. This plugin currently runs inside the editor and adds actions; it does not yet provide a live MCP connection from ChatGPT to Blockbench. A secure live bridge requires a separate transport and an MCP client that supports it.

## Limitations

- The blockout is a starter shape, not a finished textured mob.
- Project summary is not a full model backup.
- Check the target Bedrock format and test exported models in-game.
