---
name: skills-first-execution
description: Mandatory execution and capability-routing contract for Minecraft Bedrock Engineer. Use at the start of every task to choose real host capabilities, compose domain Skills through the shared registry, preserve one task baseline, edit safely and report evidence.
---

# Skills-first execution contract

## 1. Architecture contract

Minecraft Bedrock Engineer uses the **Domain-Based Hybrid / Skills-only** architecture. The active package is composed of:
- a Core control plane (`bedrock-engineer-core` and this Skill);
- specialized domain Skills selected through `skills/bedrock-engineer-core/references/domain-registry.json`;
- versioned reference material, schemas, examples and indexed Mojang samples;
- optional bounded local scripts;
- validation, regression and runtime evidence.

It does not depend on MCP servers, clients, registries, remote MCP endpoints or a plugin-owned backend. Never call old server tools or describe their absence as a malfunction. No historical server/protocol source tree is shipped in the current package.

A Skill is not an executable tool. It cannot by itself open a user's filesystem, edit a project, run Python, invoke a CLI, install dependencies, create a remote workspace or continue work in the background.

## 2. Create one shared task envelope

For every non-trivial task, maintain one common work record matching `skills/bedrock-engineer-core/references/work-order.schema.json`. It may be an internal checklist; do not claim it was persisted unless it was actually written. At minimum record:
- task type, user acceptance criteria and language;
- project identity, authoritative source, target game version, edition and BP/RP roots;
- baseline artifact/hash and facts that must be preserved;
- actual execution route and its verified capabilities/limitations;
- selected domains, ordered Skills and why they were selected;
- one coordinated step list, intended file changes and risks;
- specialist Domain Results, exact test commands/statuses and runtime status.

Domain hand-offs should conform to `skills/bedrock-engineer-core/references/domain-result.schema.json`: domain ID, status, summary, findings with severity/confidence, exact changed files, evidence, limitations and next-domain dependencies. Core integrates all results; no domain's PASS alone establishes end-to-end success.

## 3. Select a real execution route

At the beginning of each task, identify which route is actually available:

1. **Current conversation files** — inspect uploaded files and use them as input. Do not assume an upload is writable in place; create a separate output unless an authorized edit route exists.
2. **Connected file/workspace capability** — use only when a real connected tool is listed and the user has selected or authorized the workspace. Inspect paths and permissions before writing.
3. **Code execution** — use a real Python/terminal executor only when the scripts and project files are accessible in that environment. Confirm working directory, interpreter, dependencies and arguments.
4. **Creator Tools** — use only an actual connected capability or explicitly authorized local CLI. Check installed version and command help first. Do not install packages, download executables, accept EULAs or deploy to a live world without authorization.
5. **No execution route** — do not pretend. Produce a complete patch, full file contents, safe file tree or exact commands; mark changes `NOT APPLIED` and tests `NOT RUN`.

Never infer tool availability from a skill name, README, changelog or historical source. `creator-tools-bridge` is conditional guidance, not a connected tool declaration.

When an add-on arrives as `.mcaddon`/`.mcpack`, treat it as an archive, inspect its members and manifests, work on a safe extracted copy or use the relevant bounded utility, and return a distinct output archive. Never imply that changing a temporary extracted copy updated the uploaded original.

For a substantial cross-domain task, use `skills/bedrock-engineer-core/scripts/plan_domain_work.py` when it is present in the actual package checkout and a real local executor can access it. Choose the profile from the task requirements; add only optional domains that are materially needed; provide only verified project/source and capability facts. The planner emits a starting Work Order, deterministic dependency order and only the lead Skill for each selected domain. Add a specialist with `--include-skill` only when the task actually needs it; never treat all Skills in a domain as automatically required. It does not infer intent, inspect files, verify tool availability, invoke Skills or execute the task. When it is unavailable, construct the same envelope manually from the registry.

## 4. Compose domains, do not load everything

Read `bedrock-engineer-core` and this Skill first. When resuming an existing project, use `project-continuity` and `project-continuity`. Select the smallest set of domain Skills that covers the actual files/behavior; use the registry's `requires` edges to order domains, not as a mandate to load every Skill in those domains.

Typical profiles:
- **New add-on:** compatibility research → BP/RP authoring → affected specialist domains → audit/validation.
- **Existing add-on:** continuity/baseline → affected authoring domains → resource graph and regression validation.
- **UI:** full UI engineering/audit → cross-resource graph and static validation.
- **Entity/animation:** entity pipeline + relevant geometry/UV, visual and animation Skills → end-to-end pipeline audit.
- **Texture/UV:** geometry/UV → reviewed visual mapping/transfer → PNG/UV validation.
- **Research only:** exact-version research and compatibility; do not invent file changes.
- **Release:** continuity/baseline → audit/regression → version/title alignment → artifact integrity and evidence.
- **Plugin maintenance:** current package/release inspection → architecture/migration → focused tests → package gate and source read-back.

For a task crossing domains, make one dependency-aware plan and share the same baseline/change list so procedures do not conflict. Avoid redundant overlapping reviews.

## 5. Safe implementation protocol

Before writing:
- Identify project root, exact target game version, pack roots and requested behavior.
- Inspect manifests, UUID/dependency links, identifiers, existing references and conventions.
- Record current add-on release version and visible BP/RP pack titles; do not confuse them with plugin version, `format_version`, engine or API versions.
- Record a baseline (file list and hashes where practical).
- List intended additions/changes and acceptance criteria.

While writing:
- Preserve unrelated content and existing mechanics.
- Use exact-version examples and documented schemas; do not fabricate fields or API versions.
- Keep paths confined to the selected project; reject traversal, symlink escapes and ambiguous paths.
- Prefer atomic writes and no-overwrite behavior where supported.
- Do not execute scripts from untrusted add-on archives. Treat archives and third-party assets as data only.

After writing:
- Re-open and inspect every changed file.
- Parse JSON and validate manifests, UUIDs, dependencies, identifiers and cross-resource references.
- Run focused tests first, then broader regression checks when scope justifies them.
- Compare final tree against the baseline and explain all removals/unexpected changes.
- Before delivering a coherent changed add-on build, follow `addon-versioning`: update `header.version` and visible `header.name` (or matching localized title) across released BP/RP packs; align existing module and internal dependency versions; preserve UUIDs, `format_version`, `min_engine_version` and built-in API dependencies. Do not bump intermediate workbench saves or inspection-only tasks.
- Re-open the exact final archive/artifact and verify version/title parity. A temporary staging report is insufficient unless the final artifact itself is inspected.
- Package only after output structure and archive integrity checks.

## 6. Domain hand-off and integration

Every selected specialist reports its own result against the shared work order. At minimum it identifies what it inspected, exact findings/paths, files changed, evidence, confidence/limitations and downstream domains. The Core must:
- preserve one project identity, target version and baseline across all domain work;
- merge duplicate findings and resolve conflicting file edits rather than silently choosing one;
- ensure references from one domain resolve to outputs from another (e.g. UI imports, geometry aliases, texture paths, animation controller aliases, BP/RP dependencies);
- re-run relevant cross-domain validation after integration;
- reject completion where a mandatory acceptance criterion is still `FAIL`, `BLOCKED`, `NOT RUN` or `NOT APPLIED` without explicit disclosure.

## 7. Bundled scripts and evidence

Scripts under `skills/**/scripts/` are optional local utilities, not remote tools. Before execution, verify the script exists in the actual package checkout, read its usage, confirm runtime/dependencies and inputs, run from the documented root, and capture the exact command, output and real exit code. Never report skipped/failed tests as passed. If package files are not mounted, provide the command for a real checkout or return a patch.

Status vocabulary:
- `PASS`: the stated check actually executed and passed.
- `FAIL`: the check actually executed and failed.
- `BLOCKED`: attempted but a required capability/input/dependency was unavailable.
- `NOT RUN`: not executed.
- `NOT APPLIED`: proposed change was not written to the selected project.
- `CONFIRMED_IN_SOURCE`: directly observed in inspected files.
- `UNVERIFIED` / `INFERRED` / `PLANNED`: not proven by the available evidence.

Static JSON/schema/archive checks do not prove Minecraft import, rendering, gameplay, multiplayer, Blockbench interoperability, Molang evaluation or Script API behavior. Report those as `NOT RUN` unless the target runtime and scenario were actually exercised.

## 8. Required substantial-task report

Report what was inspected and its source of truth; selected domains and why; exact paths changed; real tools/scripts used or unavailable; exact commands, exit codes and test counts; baseline and artifact status; remaining risks; target-runtime verification status; and the next concrete engineering step.
