# Minecraft Bedrock Engineer 1.4.0

## Source and transport changes
- Aligns VERSION, plugin.json and Codex plugin metadata at 1.4.0.
- Registers the UV texture retarget MCP server in both MCP registries (16 server entries).
- Marks the core Python MCP server as embeddable behind an HTTP gateway while preserving STDIO.
- Adds Cloudflare Worker + Python Container deployment scaffolding under cloudflare/ and Dockerfile.

## Deployment gate
This branch is not yet deployable: the current Git tree does not contain three source modules referenced by both the registries and the Cloudflare container:
- server/entity_authoring_mcp.py
- server/animation_controller_mcp.py
- server/uv_texture_retarget_mcp.py

Do not deploy until these exact 1.4.0 source files and their dependent tests/assets are synchronized from the complete release archive, then run the full suite and a container build.

No production Worker deployment or Minecraft runtime test is claimed by this source update.
