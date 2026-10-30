---
name: creator-tools-cli-bridge
description: Use only when the user explicitly authorizes an installed local Minecraft Creator Tools CLI workflow.
---

# Local CLI bridge

No CLI is bundled or implied by this skill. Before any command, verify that the current environment actually has the executable, read its version and help, and confirm the project path and intended operation. Do not install packages, download binaries, accept licenses/EULAs, deploy or overwrite without explicit user authorization.

Use a dry-run or read-only validation mode when available. For writes, snapshot affected files and refuse ambiguous paths or collisions. Capture exact command, exit code and output. Re-audit all changed files and compare the tree to the snapshot. If the CLI is missing or not accessible, mark `BLOCKED` and provide instructions; never call a fictitious MCP wrapper.
