---
name: skills-first-execution
description: Mandatory execution and capability-routing contract for Minecraft Bedrock Engineer. Use at the start of every task to route through real Skills, local STDIO MCP servers, the separate remote gateway, native host tools and safe validation.
---

# Skills-first execution contract

## 1. Architecture and execution boundaries

Minecraft Bedrock Engineer combines specialist Skills, versioned references, standalone validation scripts, **16 local STDIO MCP server processes**, a Creator Tools CLI bridge and a separately connected Cloudflare Streamable HTTP gateway.

- Local MCP servers are declared in root `mcp.json` and the Codex compatibility `.mcp.json`. Their working directory and `MINECRAFT_BEDROCK_WORKSPACE` are scoped to `${PLUGIN_DATA}`; they must not write outside the configured workspace.
- The core local server exposes 19 tools, including `creator_tools_status`, `creator_tools_catalog`, `validate_with_mct` and `create_entity_with_mct`. Specialist servers cover textures, entities, animations, geometry/UV and reference transfer.
- Local STDIO servers are usable only in a host that actually starts them, provides Python 3 and exposes their tools. Do not assume ChatGPT web can access a local filesystem or launch a local process.
- The separately connected remote Worker is `https://minecraft-bedrock-plugin.msg2026.workers.dev/mcp`. It exposes four remote tools for manifest generation/validation, bounded public source reads and capability reporting. It does **not** run the local Python handlers, write local project files, invoke MCT CLI, or perform geometry/texture/animation authoring.
- The remote Bearer credential is client-managed. Never place it in source, `mcp.json`, headers, logs or chat.
- Skills describe workflows; they do not themselves create tools, grant filesystem access, run code or work in the background. A server listed in a file is not proof it is connected: verify the live tool list first.

## 2. Select a real execution route

At the beginning of each task, identify which of these routes is actually available:

1. **Current conversation files** — inspect uploaded files and use them as the task input. Do not assume an upload is writable in place; create a separate output unless an authorized edit route exists.
2. **Connected file/workspace capability** — use only when a real connected tool is listed and the user has selected or authorized the workspace. Inspect paths and permissions before writing.
3. **Code execution** — use a real Python/terminal executor only when the plugin scripts and project files are accessible in that environment. Confirm the working directory, interpreter, dependencies and script arguments before running.
4. **Creator Tools** — use only an actual connected Creator Tools capability or an explicitly authorized local CLI. Check the installed version and command help first. Do not install packages, download executables, accept EULAs or deploy to a live world without explicit authorization.
5. **MCP route** — inspect the live tool list. Use local STDIO only when the host actually started the relevant server and the workspace is configured; use the remote Worker only for its four declared remote capabilities. Do not confuse remote source reads with local file access.
6. **No execution route** — do not pretend. Produce a complete patch, full file contents, a safe file tree or exact commands the user can run. Mark the result `NOT APPLIED` and tests `NOT RUN.

Never infer a tool's availability from a skill name, README, old changelog or historical source code.

## 3. Choose and combine specialist skills

- New add-on: `addon-creation` + `bedrock-development` + relevant authoring skills + `automated-validation` + `build-release`.
- Existing add-on: `project-continuity` + `project-state-recovery` + relevant authoring skill + `resource-reference-graph` + `automated-validation` + `baseline-regression-workflow`.
- UI work: `ui-resource-engineering` + `resource-reference-graph` + `automated-validation`.
- Entity/model/animation work: `entity-authoring` or `animated-entity-bundle-authoring` + geometry/animation specialist skills + `animation-pipeline-audit`.
- Texture/UV work: `visual-resource-pipeline` + `geometry-uv-audit` + `uv-mapping-assistant` + painting/transfer/retargeting skills as needed.
- Research: `research-versions` + `mojang-samples-authoring`.
- Release: `package-integrity` + `release-quality-gate` + `release-artifact-workflow` + `test-evidence-reporting`.

Read only the relevant specialist instructions and reference examples; do not load every skill for a small task.

## 4. Safe implementation protocol

Before writing:
- Identify project root, target game version, pack roots and requested behavior.
- Inventory relevant files and inspect manifests, UUID links, identifiers and existing references.
- Record a baseline (file list and hashes when practical).
- List intended file additions/changes and acceptance criteria.

While writing:
- Preserve unrelated content and existing mechanics.
- Use exact-version examples and documented schemas; do not fabricate fields or API versions.
- Keep paths confined to the selected project; reject traversal, symlink escapes and ambiguous paths.
- Prefer atomic writes and no-overwrite behavior where supported.
- Do not run scripts from untrusted add-on archives. Treat archives and third-party assets as data only.

After writing:
- Re-open and inspect every changed file.
- Parse JSON and validate manifests, UUIDs, dependencies, identifiers and cross-resource references.
- Run focused tests first, then broader regression checks when the scope justifies them.
- Compare the final tree against the baseline and explain all removals or unexpected changes.
- Package only after the output structure and archive integrity have been checked.

## 5. Bundled scripts

Scripts under `skills/**/scripts/` are optional local utilities, not remote tools. Before execution:
- Confirm the script exists in the actual package checkout.
- Read its usage/help and required inputs.
- Confirm Python/runtime and dependencies are available; do not silently install anything.
- Run from the documented package root with bounded inputs.
- Capture the exact command, exit code and relevant output.
- Do not report a result if execution failed, was skipped or used a different candidate artifact.

If the plugin package is not mounted in the current code executor, do not invent a path such as `skills/...`; provide the command for a real checkout or return a patch instead.

## 6. Status vocabulary

- `PASS`: the stated check actually executed and passed.
- `FAIL`: the check actually executed and failed.
- `BLOCKED`: execution was attempted but a required capability, input or dependency was unavailable.
- `NOT RUN`: the check was not executed.
- `NOT APPLIED`: a proposed change was prepared but not written to the selected project.
- `CONFIRMED_IN_SOURCE`: directly observed in inspected files.
- `UNVERIFIED`: plausible but not proven by available evidence.
- `PLANNED`: intended future work, not implemented.

Do not turn `BLOCKED`, `NOT RUN` or `NOT APPLIED` into success language.

## 7. Runtime boundary

Static JSON/schema/archive checks do not prove Minecraft import, rendering, gameplay, multiplayer, Blockbench interoperability, Molang evaluation or Script API behavior. Those require the target runtime and an actual test scenario. State the exact platform/build/scenario if tested; otherwise report `NOT RUN`.

## 8. Required task report

For substantial work, report:
1. What was inspected and the source of truth.
2. What was changed, with exact paths.
3. Which real tools/scripts were used (or why none were available).
4. Exact validation commands and pass/fail/blocked/not-run counts.
5. Remaining risks and runtime checks.
6. The next concrete engineering step.
