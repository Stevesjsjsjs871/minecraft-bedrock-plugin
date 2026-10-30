# Minecraft Bedrock Engineer 1.5.13 — MCP restoration candidate

## Included
- 16 local STDIO MCP server registrations, with workspace isolation through `${PLUGIN_DATA}` and `MINECRAFT_BEDROCK_WORKSPACE`.
- Restored 19-tool core MCP server, including the Creator Tools CLI bridge.
- Restored the source-controlled Cloudflare Worker gateway and four-tool remote capability contract.
- MCP configuration validator, 16-process handshake test and server regression suite.
- Updated execution, maintenance, Creator Tools and package-integrity instructions.

## Boundaries
- The remote Worker is separately connected; this package contains no Bearer token or app credential.
- The remote Worker does not execute local Python handlers, write local project files or invoke MCT CLI.
- Local STDIO requires a host that supports process launch and Python 3.
- Minecraft import/render/gameplay and Blockbench interoperability remain NOT RUN unless separately tested.

## Release status
This is a GitHub source candidate only. Plugin Creator remains at 1.5.12 until the user explicitly approves an update. No Worker deployment, PR merge or public release is included.
