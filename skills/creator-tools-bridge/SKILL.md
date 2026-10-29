---
name: creator-tools-bridge
description: Use when a Minecraft Bedrock task requires authoring or modifying content through Mojang's Minecraft Creator Tools CLI, while retaining Minecraft Bedrock Engineer for independent static audit and regression checks.
---

# Minecraft Creator Tools handoff

## Role boundary
Minecraft Bedrock Engineer supplies evidence-backed, read-only auditing, resource graphs, and baseline comparisons. It does not currently expose a packaged MCP tool that invokes the Creator Tools CLI. Do not claim that `scaffold_addon`, `scaffold_entity`, or an automatic writer exists in this release.

When a compatible local shell/execution environment and an already-installed, user-approved `mct` command are available, use Mojang's Creator Tools for authoring and this plugin for independent verification. If the environment exposes only this plugin's read-only MCP tools, explain the local CLI prerequisite instead of pretending to run it.

## Before invoking MCT
1. Check the installed CLI and its own help (`mct --version`, `mct --help`) instead of assuming commands or flags from another release.
2. Require an explicit project/output path from the user or an already-established project state. Resolve and display the intended target before any write operation; never write into an arbitrary current directory.
3. Do not install packages, run `npx` downloads, update global tools, or invoke network-dependent commands silently. Ask for explicit authorization to install or download dependencies.
4. Minecraft Creator Tools documents Node.js 22+ as a prerequisite for current releases. The user must review and accept the Minecraft EULA themselves where MCT requires it; never accept it on their behalf.
5. Prefer the narrowest relevant command and inspect `--help` for supported dry-run options. Do not use force/overwrite options unless the user explicitly authorizes overwriting identified files.

## Recommended flow
- For a new project, use the installed MCT creation workflow to scaffold a project, then inspect the resulting files and manifests before adding content.
- For an entity, item, or block, use the installed version's documented `create-*` or `add` workflow. Record the exact command and target directory.
- For edits to an existing project, preserve a baseline copy or version-control checkpoint first. Have MCT generate proposed content, then inspect the diff and run its validator where appropriate.
- After authoring, run Minecraft Bedrock Engineer's static archive audit, resource graph and `compare_baseline` on the candidate. Keep MCT diagnostics and this auditor's findings separate; disagreement requires review rather than silently preferring one result.
- Package only after the diff, manifest/dependency checks and resource references are reviewed. Mark Minecraft import/visual/gameplay tests `NOT RUN` unless actually performed.

## Safety contract for any future wrapper
A future packaged MCT wrapper must use fixed argv arrays (never shell-string concatenation), a strict command allowlist, a bounded working directory, path traversal protection, execution timeouts, bounded stdout/stderr, and structured errors. It must declare write-capable tools as destructive and separate read-only validation from write operations. It must never auto-install MCT, auto-accept the EULA, deploy to a live game, or overwrite files without explicit user authorization.

## Official references
- Creator Tools overview: https://learn.microsoft.com/en-us/minecraft/creator/documents/mctoolsoverview?view=minecraft-bedrock-stable
- Mojang repository: https://github.com/Mojang/minecraft-creator-tools
- CLI package and setup: https://www.npmjs.com/package/@minecraft/creator-tools
