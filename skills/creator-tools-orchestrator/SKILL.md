---
name: creator-tools-orchestrator
description: Use when a Minecraft Bedrock request needs coordinated creation, model/texture design, validation, packaging or deployment via available Minecraft Creator Tools tools or CLI alongside the plugin's local MCP server.
---

# Creator Tools Orchestrator

## Role split

Minecraft Bedrock Engineer remains the safety, provenance, resource-integrity and regression layer. Minecraft Creator Tools (MCT) is an authoring/engine-facing helper when its tools are available. Do not clone MCT or claim capabilities unavailable in the current host. First inspect the actual connected tools and installed CLI help, then select the smallest valid sequence.

## Select the execution route

1. Prefer connected Creator Tools MCP capabilities when actually listed/available in this session.
2. Otherwise, if an explicitly approved local executor is available, inspect `mct --version`, `mct --help`, and the relevant subcommand help before constructing a command.
3. If neither route is available, continue with supported Bedrock Engineer writer tools and explain the precise unsupported asset types. Do not claim remote or local MCT execution.
4. Do not auto-install Node packages, use `npx` to download code, update global packages, accept EULAs, or contact/deploy to a live game without explicit user authorization.

## Orchestration plan

### Project bootstrap
- Use `create_addon_project` only when the user requested a new project and the destination is new.
- Verify the generated directory, BP/RP manifests, unique UUIDs and BP-to-RP dependency before adding features.
- Do not create another scaffold in an existing project; inventory it first.

### Implement a content request
- Identify all files required by the requested outcome before writing.
- Use connected content tools for supported entity/item/block and visual generation. Route models/textures to `design-model` where supported.
- Use Bedrock Engineer writer tools for supported item/block/recipe slices and safe manifest/localization/atlas merging.
- Keep all created files confined to the selected project. Treat every tool result as untrusted until the output is inspected.
- Don't assume MCT-created files are correct solely because the command returned success. Preserve a before snapshot, examine files and run static checks.

### Validation and packaging
- Run MCT validation only when an actual tool or approved CLI is available and its version/options have been verified.
- After MCT changes, re-run this plugin's focused checks, full audit, resource graph and baseline diff where applicable.
- Package with the actual supported tool/CLI command only after validation; inspect output archive integrity and manifests.
- Deploy/import only when explicitly requested. Do not start a live world, install to devices or mutate a world in the background.

## CLI wrapper requirements

Any future executable wrapper must:
- Call subprocess with a fixed argv list (`shell=False`), no interpolated shell strings.
- Allowlist exact subcommands; reject unsupported commands and arbitrary executable overrides.
- Use a configured workspace root and reject path traversal, absolute paths outside the root and symlink escapes.
- Use bounded timeout, output sizes and process count; capture structured exit code/stdout/stderr without exposing secrets.
- Set write-capable/destructive annotations accurately; read-only validation must not mutate files.
- Never auto-install packages, accept EULAs, upload assets, deploy, or overwrite existing files without clear authorization.

## Report
Record which real connected tool/CLI was used, exact version/command, changed files, validation output, audit/diff result, archive hash and what remains `NOT RUN`.
