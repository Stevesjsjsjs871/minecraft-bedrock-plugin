# Minecraft Bedrock Engineer — Domain-Based Hybrid Architecture

## Architecture decision

**Selected architecture:** Domain-Based Hybrid.  
**Integration model:** Skills-only.  
**Status:** Canonical architecture; current package version 2.3.4 (unpublished candidate).

The plugin is not a monolithic instruction and not a collection of unrelated Skills. It is a coordinated system made of a small control plane, domain-owned procedures, versioned knowledge, optional bounded local utilities, and an evidence/quality plane.

## Five architectural planes

| Plane | Owner | Responsibility | Boundary |
|---|---|---|---|
| Control | `bedrock-engineer-core`, `skills-first-execution`, `domain-result-integration` | Intake, task classification, capability check, domain selection/order, shared work state and final reconciliation | Routes work; does not pretend to be an executor |
| Domain | 12 specialist/operational domains in `domain-registry.json` (the other two are Core and project continuity) | Focused BP/RP, UI, entity, animation, geometry, texture, research, audit and release procedures | Skills own procedures; they do not grant tools or permissions |
| Knowledge | `references/`, schemas, examples, Mojang sample corpus, source links | Versioned factual basis, reusable examples, file formats and provenance | Target version and source provenance are mandatory when behavior is version-sensitive |
| Execution | Host-provided file/workspace tools, actual code executor, explicitly authorized local Creator Tools CLI | Read, edit, validate and package actual project files | Only routes verified in the current host are usable; local scripts are optional utilities |
| Evidence | Focused tests, package checks, resource graph, baseline diff, benchmarks and runtime scenarios | Establish what passed, failed, was blocked or not run | Static evidence never impersonates Minecraft runtime evidence |

## Domain boundaries

The canonical registry defines 14 primary domains and assigns each of the 59 current Skills to exactly one primary domain:

1. Core orchestration
2. Project continuity and state
3. BP/RP content authoring
4. RP UI engineering
5. Entities and animation
6. Geometry and UV
7. Visual resources and texture workflows
8. Script API engineering
9. Version compatibility and research
10. Reference pack analysis
11. Audit, dependency graph and validation
12. Release and version governance
13. Optional Creator Tools bridge
14. Plugin architecture and maintenance

The registry is the source of truth for domain membership, entry Skill, dependencies and workflow profiles. The portable Skill paths remain one directory below `skills/` so that existing Skill discovery and user-facing invocations are not broken. Logical domains therefore live in the registry rather than being implemented as nested Skill folders.

## Task lifecycle

1. **Intake:** Core converts the user request into a task type and acceptance criteria.
2. **Capability check:** identify the actual input files, authorized workspace and available executor. Select `no_execution_route` when none is available.
3. **Continuity:** for an existing project, recover state and select the authoritative baseline before editing.
4. **Domain composition:** select the smallest relevant domain set using the registry. Apply domain dependencies as ordering hints; do not load every Skill by default. When package scripts are accessible, `plan_domain_work.py` can deterministically expand the selected workflow profile into dependency order and its ordered Skills.
5. **One shared plan:** all selected domains share the same project identity, baseline, preserved behavior, constraints, file-change list and acceptance criteria. The planner can emit the initial Work Order JSON; Core remains responsible for truthful project/capability facts and human/model task interpretation.
6. **Domain work:** each specialist returns a standard Domain Result: status, summary, evidence-backed findings, exact changed paths, explicit runtime state, acceptance-criterion claims and any next-domain handoff.
7. **Integration:** `integrate_domain_results.py` validates and joins the specialist results, merges file/evidence claims, detects cross-domain write conflicts, assesses acceptance criteria and recalculates the Work Order state. A domain's local PASS does not make the whole feature complete.
8. **Validation:** run focused domain checks, cross-domain/resource-graph checks and baseline regression checks as applicable.
9. **Delivery gate:** apply add-on version/title alignment only at a coherent add-on delivery boundary; prepare artifacts only when an actual packaging route exists.
10. **Evidence report:** report exact source, commands, exit codes, test counts and runtime status.

## Shared interfaces

- `references/work-order.schema.json` defines the shared task envelope: task, project identity, target version, baseline, capability route, selected domains, ordered Skills, plan, file changes, domain results, evidence and completion status.
- `references/domain-result.schema.json` defines the hand-off from a specialist domain to Core, including per-file status, explicit runtime state and acceptance-criterion claims.
- `references/domain-registry.json` defines domain membership, selection rules, domain dependencies, workflow profiles, capability routes and status vocabulary.

The Work Order integration report records domain coverage, per-domain status, criterion dispositions, file conflicts, suggested next domains and aggregate runtime status. These are data contracts and local JSON records, not a database, tool API, plugin runtime or background service. A Work Order can be kept as an internal working record; save a project state artifact only when an actual writable project destination exists and doing so is useful.

### Operational domain planner

`skills/bedrock-engineer-core/scripts/plan_domain_work.py` is a deterministic, standard-library utility that turns an explicitly selected workflow profile into a dependency-expanded domain order, a minimal list of domain lead Skills and planned domain/delivery-gate steps. It does not add every Skill in a selected domain. A caller may add a task-relevant specialist with repeatable `--include-skill <slug>`; the planner verifies that the Skill belongs to a selected domain. It validates the generated envelope against the bundled Work Order/Domain Result contracts and can emit JSON to stdout or an explicitly selected output file.

The planner deliberately does **not** infer which workflow the user intended, inspect a project, verify a host tool, invoke Skills, run project code, modify project files or retain state. The caller must select a registry profile, explicitly opt into any profile-declared optional domains, provide source-of-truth details and declare the actual capability route. An unverified capability remains unverified. Output status starts at `PLANNED` and runtime status is always `NOT RUN`.

Example from the plugin package root:

```bash
python skills/bedrock-engineer-core/scripts/plan_domain_work.py \
  --profile existing_addon_change \
  --request "Repair the existing UI regression" \
  --project-name "My Add-on" \
  --source-of-truth "provided baseline and candidate archives" \
  --target-game-version 1.26.50 \
  --include-domain ui_engineering \
  --include-skill ui-resource-audit \
  --output work-order.json
```

Use `--list-profiles` to inspect available profiles. Omit optional domains unless the task requires them. Add specialist Skills only when the actual task needs them; otherwise Core chooses among the domain's Skills after inspecting the task and references. Existing output files are not replaced without `--overwrite`. When the package/script is unavailable in the real execution environment, follow the registry manually and do not claim the planner ran.

### Domain Result integration

`skills/bedrock-engineer-core/scripts/integrate_domain_results.py` is a deterministic, standard-library local utility. It validates each specialist result against the Domain Result schema and registry, requires the domain to be selected in the parent Work Order, rejects duplicate/unsafe file claims, merges evidence and changed files, and emits a single integration report. The architecture validator also rejects duplicate values within schema `enum` arrays so duplicated statuses cannot silently drift into a published contract. Existing results cannot be replaced without an explicit `--replace-domain <domain_id>`. Input JSON is read-only; output is written only to an explicitly supplied path, and existing output is protected unless `--overwrite` is supplied.

The integrator detects case-insensitive path collisions, remove-versus-write conflicts, differing actions for the same path, and file-level overlapping writes by multiple domains. A file-level overlap is marked `HIGH` for review because the hand-off does not contain patch hunks; the utility never pretends it performed a merge. Remove-versus-write and case-collision conflicts are `BLOCKER`.

Acceptance criteria are assessed by exact text. `MET` and `NOT MET` require evidence; opposing claims become `CONFLICT`; missing claims remain `UNVERIFIED`. `COMPLETE` requires every selected domain to report `PASS`, no high/blocker finding or file conflict, and every declared criterion to be `MET`. Missing domains remain `IN_PROGRESS`, unresolved work remains `PARTIAL`, and blocked domains/blocker conflicts produce `BLOCKED`. Runtime remains a separate aggregate and defaults to `NOT RUN`.

Example:

```bash
python skills/bedrock-engineer-core/scripts/integrate_domain_results.py \
  --package-root . --work-order work-order.json \
  --result domain-results/bp-rp.json --result domain-results/audit.json \
  --output work-order.integrated.json
```

The script is optional and runs only when the current host exposes a real executor with package files mounted. Otherwise Core must follow the same contract manually and mark the utility `NOT RUN`.

### Project State Management

`skills/bedrock-engineer-core/scripts/project_state.py` is an optional standard-library utility for a project root that is actually writable by the current host. The Skill `project-continuity` defines the safe workflow; the utility stores metadata under `.mbe/` and never edits files in the add-on project.

The state document has a project identity, monotonically increasing revision, categorized evidence records, a hash-chained event history and a SHA-256 integrity field. Mutations require `--expected-revision`; state writes use a lock and atomic replacement. The supported record categories separate decisions, requirements, features, issues, tasks, tests and notes, each with category-specific statuses. `verify` checks the state checksum, event chain, referenced snapshot data and backup metadata. `inspect` compares the current workspace inventory with the latest complete snapshot and reports drift.

Snapshots contain only relative paths, sizes and SHA-256 digests. They are immutable inventories, **not file-content backups**. Ignored directories are bounded by documented defaults and explicit exclusions. Symlinks are not followed. If a scan is incomplete due to file-count, size or read limits, the result is marked partial and missing paths are not classified as deletions. State restore is metadata-only; it never restores project files. Recovery is also metadata-only: it selects a verified state backup, archives the damaged state record, rotates the project ID and captures the current workspace rather than rolling project files backward.

A Work Order may carry `project_state`, containing the project UUID, state revision, canonical state path, state hash and latest snapshot ID/hash. The Domain Result integrator validates this link and preserves it through integration. After any state mutation, refresh the Work Order link; stale links are intentionally not auto-updated. This gives a traceable association without claiming the Work Order and state file are a transactional database.

No durable state is implied by a Skill invocation. If there is no real writable project root and local executor, do not create fictitious paths or claim persistence; retain the work record in the current task and label it unsaved. The utility has no network, cloud-sync, subprocess or Minecraft-runtime behavior.

Example commands from the plugin package root:

```bash
python skills/bedrock-engineer-core/scripts/project_state.py init --project-root ./my-addon --project-name "My Add-on" --target-game-version 1.26.50 --source-of-truth "verified baseline archive"
python skills/bedrock-engineer-core/scripts/project_state.py verify --project-root ./my-addon
python skills/bedrock-engineer-core/scripts/project_state.py inspect --project-root ./my-addon
python skills/bedrock-engineer-core/scripts/project_state.py record --project-root ./my-addon --expected-revision 1 --category decision --title "Preserve pack UUIDs" --status APPROVED --details "Existing identifiers remain unchanged."
python skills/bedrock-engineer-core/scripts/project_state.py link-work-order --project-root ./my-addon --work-order ./work-order.json --output ./work-order.linked.json
```

Consult `skills/project-continuity/SKILL.md` for the complete command contract and recovery preconditions. Do not run mutating commands against a user's project without an actual writable target and explicit task scope.

### Change Impact Analysis

`change-impact-analysis` and `analyze_change_impact.py` add a read-only dependency-impact layer to the audit domain. The graph is directed from consumer to dependency; changed paths are traversed in reverse to list potentially affected consumers. Supported static edges include BP entity ↔ RP client-entity binding, client-entity links to geometry/textures/animations/controllers/render controllers, recipe item/block references, manifest UUID dependencies, UI imports and relative script imports.

The analyzer is deliberately conservative: it emits exact edges only for resolved references, flags ambiguity/unresolved paths for review, and retains consumers of explicitly listed removed/renamed paths as `CHANGED_DEPENDENCY_MISSING` edges. It skips symlinks and generated dependency folders, and marks incomplete scans `PARTIAL`. It never runs source code, evaluates Molang, edits project files or treats no inbound references as authorization to delete an asset. Core uses the impact set to choose regression checks; actual Minecraft runtime remains a separate test gate.

## Composition rules

- New add-on work starts with Core, exact-version research, BP/RP authoring and validation; add UI/entity/visual/Script API/reference-pack domains only when the task requires them.
- Existing-project work starts with continuity and a known-good baseline; route to only the affected authoring domains, then audit and compare.
- Cross-domain features are one dependency-aware plan, not separate uncoordinated rewrites. Entity/animation work may need geometry/UV; texture work needs geometry/UV; UI work needs resource-reference validation; Script API work needs exact-version evidence.
- Release governance is applied at delivery boundaries, not to every intermediate workbench save.
- Unreferenced assets are review candidates, never automatic deletion candidates.
- Ambiguous static references remain ambiguous; heuristic matches cannot become blockers without stronger evidence.

## Capability and integration boundaries

The active integration contract is Skills-only. The plugin does not register or call MCP servers, MCP clients, registries, transports, remote endpoints or a plugin-owned backend. A Creator Tools bridge Skill may coordinate a real host-connected tool or explicitly authorized local CLI, but may not invent one. No historical server/protocol implementation is shipped. User-supplied legacy projects are inspected as untrusted data through the generic migration workflow; source code is never executed during static review.

Skills do not grant filesystem access, run code, install dependencies, retain durable state or work in the background. Bundled scripts run only when a real executor can access package files. If no execution route exists, provide a complete unapplied patch or explicit steps and mark them `NOT APPLIED` / `NOT RUN`.

## Quality invariants

- Preserve plugin identity, private audience, `@Minecraft Bedrock Engineer` invocation and all 12 default prompts.
- Preserve existing project mechanics, identifiers, UUIDs, assets, localization and unrelated files unless a change is explicitly required.
- Record the exact Minecraft Bedrock version; do not conflate game version, `format_version`, engine version, Script API dependency, add-on version and plugin package version.
- Every meaningful finding has evidence, a source path/pointer when applicable, severity and confidence.
- Every test status reflects an actual invocation. Runtime is `NOT RUN` unless Minecraft was actually launched with the candidate and the scenario was executed.
- Reconcile the registry against the full discovered Skill inventory before a plugin release.

## Change control

Changes to domain IDs, Skill membership, dependency edges, workflow profiles or task schemas are architectural changes. They require registry validation, focused tests, package integrity checks, synchronized release documentation and post-update source read-back. Do not move or rename existing Skill directories merely to make the tree look grouped; update the registry first and preserve portable discovery paths.
