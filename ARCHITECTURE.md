# Minecraft Bedrock Engineer — Architecture (2.3.4)

## Architecture decision

- Architecture: Domain-Based Hybrid.
- Integration model: Skills-only.
- Package status: local, unpublished 2.3.4 candidate.
- No plugin-owned backend, MCP server/client, remote execution service, or background runtime is part of this architecture.

The package is organized as a small control plane, specialist domains, versioned knowledge, optional bounded local utilities, and an evidence/quality plane.

## Architecture planes

| Plane | Responsibility | Boundary |
|---|---|---|
| Control | Intake, task classification, capability checks, domain selection/order, reconciliation | Routes work; does not claim to execute it |
| Domain | BP/RP, UI, entities, animation, geometry, textures, Script API, research, audit and release procedures | Skills define procedures; they do not grant tools or permissions |
| Knowledge | References, schemas, examples, sample corpus and source provenance | Version-sensitive behavior requires a target version and evidence |
| Execution | Host-provided workspace tools, actual code executor, or explicitly authorized local Creator Tools CLI | Only verified routes in the current host may be used |
| Evidence | Focused tests, package checks, resource graph, baseline diff, benchmarks and runtime scenarios | Static evidence is not Minecraft runtime evidence |

## Domains and workflow

The registry defines 14 primary domains and assigns each of the 59 Skills to one primary domain. The domains cover Core orchestration; project continuity; BP/RP authoring; UI; entities and animation; geometry/UV; visual resources; Script API; compatibility research; reference-pack analysis; audit and validation; release governance; optional Creator Tools bridge; and plugin architecture/maintenance.

The task lifecycle is: intake and acceptance criteria; capability check; baseline/continuity recovery; minimal dependency-aware domain selection; shared work plan; domain procedures and evidence; cross-domain integration; focused and regression validation; delivery/version gate; and a truthful evidence report.

The registry is the source of truth for domain membership, entry Skills, dependencies, workflow profiles and capability routes. Portable Skill paths remain one directory below `skills/` to preserve discovery and invocation compatibility.

## Shared contracts and utilities

The Work Order and Domain Result JSON schemas define task state and specialist hand-offs. The domain registry defines selection and ordering. Optional standard-library utilities can plan a selected workflow, integrate domain results, maintain project metadata, and analyze static dependency impact. They are local utilities, not a database, tool API, plugin runtime or background service.

Utilities must only be reported as run when the current environment actually exposes an executor and the package files. Otherwise their status is `NOT RUN`; the workflow can be followed manually. Planning output starts at `PLANNED`, and an unverified capability route remains unverified.

Project state is metadata-only: snapshots contain relative paths, sizes and hashes, not file-content backups. Restore/recovery operations do not roll project files backward. Static dependency analysis does not execute source, evaluate Molang, edit files, or authorize asset deletion.

## Capability and safety boundaries

Skills do not independently grant filesystem access, execute code, install dependencies, retain durable state, or run in the background. Scripts are usable only when a real executor can access package files and required dependencies. If no such route exists, provide an unapplied patch or explicit steps and mark them `NOT APPLIED` / `NOT RUN`.

No MCP integration or plugin-owned remote backend is included. A Creator Tools bridge procedure may coordinate a real host-connected tool or explicitly authorized local CLI, but must not invent one. User-supplied legacy projects are treated as untrusted data during static review; source code is not executed as part of that review.

## Quality invariants

- Preserve plugin identity, private audience, invocation name and all 12 default prompts.
- Preserve project mechanics, identifiers, UUIDs, assets, localization and unrelated files unless a change is required.
- Record exact Minecraft Bedrock version; do not conflate game, format, engine, Script API, add-on and plugin package versions.
- Findings require evidence, source pointers where applicable, severity and confidence.
- Test status reflects an actual invocation. Runtime is `NOT RUN` unless Minecraft was launched with the candidate and the scenario was executed.
- Reconcile registry coverage against the complete Skill inventory before release.

Architectural changes to domain IDs, Skill membership, dependency edges, workflow profiles or task schemas require registry validation, focused tests, package-integrity checks, synchronized release documentation and post-update read-back.
