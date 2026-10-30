---
name: creator-tools-bridge
description: Use when coordinating this Skills-only workflow with an actually connected Minecraft Creator Tools capability or an explicitly authorized local CLI.
---

# Optional Creator Tools bridge

This is an optional coordination procedure, not an integration. Do not call historical Creator Tools MCP names or assume that a tool exists because this skill mentions Creator Tools.

1. Inspect the active host's actual connected capabilities. If no Creator Tools capability is listed, report `UNAVAILABLE` and continue with native file/code workflows or a patch.
2. For a local CLI, require explicit user authorization and inspect the installed version and `--help` first. Do not install software, download executables, accept EULAs, deploy, or modify a live world without explicit approval.
3. Identify exactly which files Creator Tools will read/write. Snapshot the project and preserve unrelated files.
4. Run only the requested operation. Capture the exact command/tool name, version, arguments and result.
5. Re-inspect changed files, compare against the snapshot, run this plugin's available static audits and explain any deltas.
6. Separate Creator Tools diagnostics from this plugin's checks. Mark game import/render/runtime `NOT RUN` unless actually tested.

If the capability is absent or fails, do not invent a successful delegation. Provide the exact manual steps or a complete patch.
