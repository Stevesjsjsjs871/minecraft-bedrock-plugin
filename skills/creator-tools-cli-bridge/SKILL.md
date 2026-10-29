---
name: creator-tools-cli-bridge
description: Use when the user wants Creator Tools CLI or validation/build commands run or integrated with Minecraft Bedrock Engineer; verify the actual installed MCT version and avoid unsafe implicit execution.
---

# Creator Tools CLI Bridge

## Execution truth
This skill describes a safe method, not proof that an executable or runtime is connected. Before attempting to execute a command, inspect the current host and available tools. If a real local executor is unavailable, do not imply the CLI ran. Give the exact commands and outputs needed from the user's machine.

## Preflight
1. Check whether a connected Creator Tools MCP tool provides the requested operation. Prefer it over a shell when available.
2. If a local CLI executor is available and authorized, run `mct --version` and `mct --help`. Inspect the specific subcommand help before any write.
3. Do not use `npx` to download or execute a package unless the user explicitly authorizes network/package installation. Do not modify global packages automatically.
4. Confirm the project root, target version and intended output path. Preserve the starting file inventory and hashes where practical.

## Command safety
- Use direct process arguments, never shell interpolation.
- Use only documented subcommands from the installed CLI version.
- Restrict paths to the selected workspace and reject traversal/symlinks.
- Apply an execution timeout and cap stdout/stderr before returning.
- Do not accept the EULA, start/deploy to a live game, alter worlds, or overwrite existing files without explicit user consent.

## Workflow
1. Inspect the project and manifests.
2. Plan the content and list the expected file changes before authoring.
3. Generate only with a tool proven available.
4. Inspect generated files and check the actual tool result.
5. Run focused Bedrock Engineer validation and broad audit/diff.
6. Package only after validation; then verify archive integrity and inventory.

## Report
Record actual CLI version, exact argv, exit code, bounded output and generated paths. Distinguish `NOT AVAILABLE`, `NOT RUN`, `FAILED` and `PASSED`. Never describe a planned command as executed.
