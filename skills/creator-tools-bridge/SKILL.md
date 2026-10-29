---
name: creator-tools-bridge
description: Use when creating a Minecraft Bedrock add-on from scratch or extending one through Mojang's Minecraft Creator Tools MCP/CLI, with Minecraft Bedrock Engineer providing independent static audits and regressions.
---

# Minecraft Creator Tools integration

## Capability boundary
Minecraft Bedrock Engineer now has a local `create_addon_project` MCP tool that writes a new linked BP/RP starter scaffold inside the configured workspace. It does not create gameplay content, textures, models, animations, or Script API code. The eight analysis tools remain read-only. Do not claim that an automatic MCT CLI subprocess wrapper is part of this plugin.

When an actual Creator Tools MCP tool or approved local `mct` CLI is available in the host, use its supported creation and validation commands for the requested content. If only the local scaffold/audit server is available, explain which files can be generated and which authoring capability is missing; never pretend a model, entity, texture, or code file was created.

## Before invoking MCT
1. Inspect available tools or the installed CLI help (`mct --version`, `mct --help`, and the relevant command's `--help`). Don't assume names/options from another release.
2. For a new project, create the clean BP/RP scaffold first with `create_addon_project`, then verify the output. Supply a new single directory name, not a path.
3. Require an explicit project/output path or established project state before any write operation. Never write into an arbitrary current directory or overwrite an existing file without explicit authorization.
4. Do not install packages, run `npx` downloads, update global tools, or invoke network-dependent commands silently. Ask for authorization before installing/downloading dependencies.
5. Current Creator Tools documentation lists Node.js 22+ as a prerequisite. The user must review and accept the Minecraft EULA themselves when MCT requires it; never accept it on their behalf.
6. Prefer the narrowest relevant command. Use only actual dry-run/safe options confirmed by the installed version.

## Recommended flow
- New project: scaffold -> agree first feature -> create only the related content -> validate -> audit -> compare -> package.
- Use MCT content tools for supported new mobs/items/blocks and model design when those specific tools are actually available.
- Use the CLI for whole-project validation, fixes, rendering, packaging or deployment only where supported by the installed version and explicit authorization.
- After authoring, run Minecraft Bedrock Engineer's static audit/resource graph/baseline comparison. Keep MCT diagnostics and local analyzer findings separate; disagreements require review.
- Mark Minecraft import, visual output and gameplay/multiplayer tests `NOT RUN` unless they actually occurred.

## Requirements for any future wrapper
Use fixed argv arrays, never shell-string concatenation; allowlist commands; constrain operations to an approved workspace; reject path traversal and symlinks; impose timeouts and bounded stdout/stderr; return structured errors; mark writing tools as write-capable; separate read-only checks from writes; and never auto-install MCT, accept the EULA, deploy to a live game, or overwrite files without user authorization.

## Official references
- Creator Tools overview: https://learn.microsoft.com/en-us/minecraft/creator/documents/mctoolsoverview?view=minecraft-bedrock-stable
- Manifest reference: https://learn.microsoft.com/en-us/minecraft/creator/reference/content/addonsreference/packmanifest?view=minecraft-bedrock-stable
- Mojang repository: https://github.com/Mojang/minecraft-creator-tools
- CLI package: https://www.npmjs.com/package/@minecraft/creator-tools
