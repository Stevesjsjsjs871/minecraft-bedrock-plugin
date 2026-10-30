# GitHub source mirror

This branch contains the maintained Minecraft Bedrock Engineer **1.5.11 Skills-first source**.

- Removed all retired `server/` MCP wrappers and server tests from this repository.
- Removed the legacy package-integrity checker that validates the retired server/registry architecture; the active Skills-only checker and tests remain.
- Removed MCP/Cloudflare deployment configuration and obsolete deployment scaffolding in the preceding sync.
- Kept release history and changelog entries as historical records; they are not active code.
- Repository CI and ignore rules are maintained for the Skills-first scripts.

## Binary reference data

The compressed Mojang Samples index (`skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz`, 1,128,413 bytes) is present in the Plugin Creator release but was not readable through its text-source API. The binary archive download endpoint was not reachable from the current file-transfer runtime. It is not replaced with a fabricated or partial index. The GitHub mirror is therefore source-complete except for this one binary index; the Plugin Creator release remains the authoritative complete distribution.
