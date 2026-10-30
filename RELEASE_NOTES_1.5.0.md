# 1.5.0 — Skills-first, MCP-free package

- Removed MCP server declarations from the plugin manifest.
- Removed `.mcp.json` and `mcp.json` package configuration.
- Removed skills that only described MCP tool invocation and MCP registry/contract testing.
- Kept the existing Bedrock authoring, geometry, animation, texture, audit, UI, sample-reference and validation skills.
- Added a Skills-first core workflow that prohibits pretending unavailable remote tools or project-file access exist.
- Preserved legacy Python server source files as dormant code for possible future extraction into a protocol-independent engine; they are not exposed by this package.

## Important limitation

This change removes the plugin's MCP connection. It does not guarantee that ChatGPT will display the plugin in the `@` picker: app registration, account eligibility and host availability are controlled separately by ChatGPT. Skills do not themselves provide remote file execution.
