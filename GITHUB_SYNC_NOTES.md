# GitHub source mirror

This branch mirrors the Minecraft Bedrock Engineer **1.5.11** source package.

- The repository is Skills-first; retired MCP and Cloudflare deployment configuration has been removed.
- Repository-only CI and ignore rules are retained.
- The plugin package's compressed Mojang sample index (`skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz`) is present in the Plugin Creator release but could not be transferred by the text-only source reader. It is intentionally not replaced with a fabricated index.
- The generated Python bytecode cache is excluded.
- The published plugin remains the authoritative complete package until the binary index is synchronized.

See the Plugin Creator release for the complete distributable package.
