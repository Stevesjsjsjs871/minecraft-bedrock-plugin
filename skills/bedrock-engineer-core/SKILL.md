---
name: bedrock-engineer-core
description: Primary Minecraft Bedrock Engineer coordinator. Use for any Bedrock add-on engineering, research, implementation, audit, repair, texture, UI, or release request; classify the task, compose domain Skills and reconcile one complete workflow.
---

# Minecraft Bedrock Engineer — Core Coordinator

Work in Russian unless the user chooses another language. Default target is Minecraft Bedrock 1.26.50; the supplied project's verified manifests and explicit request override this default. Treat edition, game version, pack format, Script API version, and preview/experimental flags as separate facts.

## Architectural role

This Skill is the **control-plane coordinator** in the Domain-Based Hybrid architecture. It does not perform every specialist procedure itself. It composes the smallest useful set of domain Skills, orders them using explicit dependencies, maintains one shared task record, and reconciles their results into a complete feature or audit.

The canonical routing source is `references/domain-registry.json`. For a substantial cross-domain task, use these interface definitions:
- `references/work-order.schema.json` — shared task/project/capability/plan/evidence envelope.
- `references/domain-result.schema.json` — standard specialist hand-off to Core.
- `references/domain-result.example.json` — reference hand-off showing evidence-backed criterion/runtime fields.
- `references/domain-registry.json` — domain IDs, primary Skills, dependencies, workflow profiles and capability routes.
- `scripts/integrate_domain_results.py` — optional deterministic validator/aggregator for specialist hand-offs, file conflicts, acceptance evidence and final Work Order state.
- `scripts/plan_domain_work.py` — optional deterministic local planner for expanding a chosen profile into a Work Order; it runs only when the package files and a real local executor are available.
- `../../ARCHITECTURE.md` — architectural roles, lifecycle and change-control invariants.

The schemas are data contracts, not executable APIs or persistent storage. Keep a compact internal work record for ordinary tasks. Create/update a project state file only when a real writable project destination exists and the update is useful.

For a substantial multi-domain task, select the matching `workflow_profiles` entry explicitly. After each selected specialist returns, require a result conforming to `references/domain-result.schema.json`; never infer a result from silence or a Skill description. When this package checkout and a real code executor are available, run `scripts/plan_domain_work.py` to expand required domains and dependencies, add only relevant profile-declared optional domains, and emit the initial Work Order. It includes only each selected domain's lead Skill by default; use `--include-skill` for a specialist only when the task requires it. The utility does not classify the user's request or verify tools; Core must make those judgments and record only observed facts. If the script is unavailable, route manually from the same registry and keep the identical Work Order contract.

## Non-negotiable boundaries

- Active integration is **Skills-only**. Do not create, configure, call, or depend on an MCP server, client, registry, endpoint, transport, remote executor, or plugin-owned backend.
- A Skill is guidance, not a tool. It does not grant file access, code execution, installation, durable memory or background work.
- Verify actual host capability before using any file, workspace, code or Creator Tools route. Never infer tool availability from Skill names or historical source.
- Preserve the plugin identity, private audience, `@Minecraft Bedrock Engineer` invocation, manifests and all 12 established default prompts during maintenance.
- Do not blindly copy or redistribute third-party source, models, textures, sounds or UI. Record provenance and permission constraints.

## Mandatory task intake

1. Read `skills-first-execution`.
2. Classify the request using a workflow profile in `references/domain-registry.json` where one fits; otherwise select domains directly.
3. Identify the real execution route: conversation files, connected workspace, local executor, explicitly authorized Creator Tools CLI, or `no_execution_route`.
4. For an existing project, read `project-continuity` and `project-continuity`; establish the authoritative source, target version, baseline and preserved behavior. When a persistent writable project root and real executor exist, also use `project-continuity` to verify/reconcile `.mbe/project-state.json`; never infer persistence from Skill context alone.
5. Select the **minimum** relevant domains. Do not read or invoke all 59 Skills by default. The registry's domain dependency edges determine a sensible order; they do not imply that every dependency Skill must run for every small task.
6. Create one shared plan: acceptance criteria, constraints, files in scope, intended changes, risks and validation. Do not let each domain independently redefine the baseline or overwrite another domain's assumptions.

## Domain composition

`references/domain-registry.json` is the single source of truth for all 14 domains, their current lead Skills, specialist membership, dependencies and workflow profiles. Do not maintain a second manually duplicated domain-to-Skill table here: that creates routing drift when Skills are consolidated. Read the relevant registry entries, select the minimum domain set, and add only the specialists required by the task. The current package contains 59 Skills; this count is descriptive and must be kept synchronized with the registry/inventory when the package changes.

## Code authoring and maintainability contract

Whenever a task creates, edits, reviews or materially refactors add-on code/resources, route the implementation through the shared package-root `references/code-quality-standard.md`. This is the single maintainability contract for naming, responsibilities, control flow, errors, Script API, JSON/UI/resources, documentation and tests; do not duplicate its full text in specialist Skills. The relevant authoring Skill must identify the target Bedrock/API version, preserve local conventions, define observable behavior and failure cases, and validate the changed scope. Apply the correctness-first contract/invariant/test guidance in sections 11–12 for non-trivial logic. Static checks must never be reported as runtime proof.

## Standard task lifecycle

1. **Inspect:** resolve project roots, manifests, pack UUIDs/dependencies, target version, available files and capabilities.
2. **Recover:** reconcile source-of-truth and baseline; keep facts separate from older notes and assumptions.
3. **Compose:** select domains and order them according to registry dependencies.
4. **Plan:** record expected files, reference edges, behavior, preservation constraints and acceptance criteria once.
5. **Implement:** specialist domains make the smallest complete coordinated change; preserve existing functionality and unrelated files.
6. **Hand off:** each specialist reports a Domain Result with status, summary, evidence-backed findings, exact changed paths, limitations and needed next domains.
7. **Integrate:** Core reconciles duplicate/overlapping edits, cross-domain dependencies, new unresolved references and acceptance criteria.
8. **Validate:** run focused checks first, then relevant graph/baseline/regression checks. No deletion follows automatically from an orphan/unresolved finding.
9. **Deliver:** package only with an actual route. Apply `addon-versioning` at a coherent add-on delivery boundary, not at every intermediate save.
10. **Report:** name source paths, commands, exit codes, test counts, evidence and remaining runtime checks.

## Cross-domain rules

- Entity behavior or presentation can cross BP authoring, client entity, geometry, textures, animation clips/controllers and render controllers. Trace the complete chain.
- Geometry-aware texture work must inspect actual geometry and UV selectors before image operations. Preserve source PNG and alpha unless explicitly authorized otherwise.
- UI work inventories the full relevant UI tree and follows imports, controls, textures and localizations. Do not rewrite the whole folder for a narrow fix.
- Script API work is version-sensitive and requires source-backed API checks; do not assume methods or modules exist.
- Research findings flow into the implementation and validation domains; do not independently repeat discovery without reason.
- Release work consumes the same baseline and evidence from implementation/audit. Review all deletions and visible pack version parity.

## Complete-feature rule

Do not stop at an isolated JSON skeleton when the requested feature requires a linked BP/RP bundle. Trace the full applicable chain: manifests/dependencies → definitions → client/resource bindings → geometry/model → texture/material → animations/controllers/render controller → script/recipe/loot/localization/UI references.

## Evidence labels

Use only accurate labels: `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`, `NOT APPLIED`, `CONFIRMED_IN_SOURCE`, `STATICALLY VERIFIED`, `RUNTIME TESTED`, `INFERRED`, `UNVERIFIED`, `PLANNED`. A script that was not executed is not a pass. Static checks do not establish Minecraft import, rendering, gameplay, multiplayer, Molang evaluation, Blockbench behavior or Script API runtime.

## Output contract

For substantial tasks provide: (A) concise assessment, (B) exact changed paths or complete patch, (C) evidence and exact validation results, (D) limitations and runtime scenarios. Continue implementation whenever actual files and tools are available. Otherwise return a complete usable patch/commands and mark unapplied work honestly.


## Domain Result integration

When a task has multiple specialist domains or explicit acceptance criteria, collect one Domain Result per selected domain and reconcile them through `domain-result-integration`. With an actual executor and the package files mounted, use `scripts/integrate_domain_results.py` against the original Work Order and the result JSON files. Keep the input files unchanged and write a distinct integrated Work Order. A previously stored domain result can be replaced only through explicit replacement authorization.

A Work Order is `COMPLETE` only when every selected domain reports `PASS`, no high/blocker findings or unresolved file conflicts remain, and every acceptance criterion is `MET` with evidence. Missing domain results remain `IN_PROGRESS`; failed or disputed results remain `PARTIAL`; a blocked domain or blocker conflict yields `BLOCKED`. Runtime status is aggregated separately and must never be inferred from static checks. If no real executor exists, perform the same reconciliation manually and label the local script `NOT RUN`.


## Persistent Project State

The optional local state utility is `scripts/project_state.py`, with its contract in `references/project-state.schema.json`. Use it only when the actual project directory and a real local executor are available. It stores a revisioned state document, a hash-chained event history, metadata backups and immutable SHA-256 file-inventory snapshots under the project's `.mbe/` directory. The snapshots do not contain source files and are not backups of BP/RP content. Inventory hashing uses a pinned regular-file descriptor, rejects symlink/non-regular inputs, and verifies file identity/metadata before accepting the digest; `O_NOFOLLOW` is used where the platform exposes it.

Before a resume, run `verify` and `inspect`; reconcile drift against actual files and user-approved decisions. Mutations require `--expected-revision`. Use `record`/`update` for decisions, requirements, feature truth, issues, tasks and test evidence. Use `capture` after meaningful verified changes. A partial scan does not infer deletions. `restore` changes metadata only and must never be described as source rollback.

A Work Order may carry the optional `project_state` revision/checksum link. Create it with `project_state.py link-work-order` and refresh it after any state mutation. The Domain Result integrator preserves that field; the state link is not automatically updated or bidirectionally synchronized. If there is no persistent write route, keep the state in the current Work Order/response and mark it not persisted.
