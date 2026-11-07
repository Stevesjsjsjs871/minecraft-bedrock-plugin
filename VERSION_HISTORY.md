## 2.3.4

Consolidated seven domain groups into canonical Skills with explicit modes; preserved specialist procedures, local utilities, tests and separate release/audit gates. No live publication.

## 2.3.3

Entity authoring Skill consolidation; no live publication.

# Version History

## 2.3.2 — Code authoring quality and readability (candidate)
- Route Core and specialist authoring workflows through the shared maintainability standard.
- Add an operational, exact-version Script API authoring checklist.


## 2.3.1 — Project State pinned-file hashing hardening (candidate)
- Hardens `.mbe` inventory capture against symlink/path replacement races using one pinned regular-file descriptor, `O_NOFOLLOW` where supported, and post-read identity/metadata checks.
- Adds two Project State regression tests; 32/32 test files / 548 cases PASS.
- Plugin Host activation NOT VERIFIED; Minecraft runtime NOT RUN; no live update.

## 2.3.0 — ZIP hardening, JSONC parser and real-pack audit (candidate)
- Base archive: verified 2.2.0 candidate, SHA-256 `694a21adc6eb31ab0d22ae764c59d4386cc3e40e10f2695fc00dda4cc3b584eb`; live release remains 2.1.11.
- Corrects archive namespace handling and pinned-descriptor hashing; adds CRC checks, ratio/size limits and adversarial regression tests.
- Adds JSONC-aware static parsing with duplicate-key rejection; re-indexes ten archives / 110 manifests and static-audits five real projects.
- Local validation: 32 test files / 546 cases PASS; package integrity 20/20; architecture 28/28; 8/8 workflow profile smoke plans.
- Plugin-host integration NOT VERIFIED; Minecraft runtime NOT RUN; no live update.

## 2.2.0 — Multi-source Bedrock reference corpus (verified candidate, unpublished)
- Base candidate: 2.1.12; live Plugin Creator remains 2.1.11.
- Added ten-source reference corpus / 110 manifests and separate moving Mojang `main` snapshot.
- Independent validation: 31/31 test files / 515 cases PASS; package integrity 20/20; architecture 28/28.
- Follow-up review identified three hardening issues, corrected in 2.3.0.

## 2.1.12 — Python utility audit corrections and bounded analyzers (candidate)
- Added Script API lexical analysis, resource/UI/PBR/Fog inventory and metadata-only benchmark inventory.
- Hardened reference texture transfer; registry covered 61 Python files.
- Validation: 30/30 test files / 511 cases PASS. Host integration NOT TESTED; Minecraft runtime NOT RUN.

## Release 2.1.11 — Outcome Quality Assessment
- New `outcome-quality-assessment` Skill for evidence-based evaluation of completed work against the original acceptance criteria.
- Eight quality dimensions: completeness, functional correctness, cross-system consistency, reliability/failure handling, maintainability, verification/evidence, delivery integrity and user-fit/usability.
- Separate readiness gates (`HOLD`, `REVIEW`, `READY FOR RUNTIME TEST`, `READY`) so averages cannot hide critical defects or unverified critical criteria.
- Explicit evidence provenance, exact-final-artifact reopening, score limitations and prioritized improvement loop.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release 2.1.10 — Adaptive Process Control
- Added `process-self-monitoring` skill with a lightweight execution telemetry ledger, process-smell detectors, bounded recovery policy and evidence-preserving replanning rules.
- Integrated monitoring checkpoints into the workflow execution engine, preflight planning and Domain Result integration.
- Added explicit retry ceilings, branch isolation, stale-evidence invalidation and revalidation rules.
- Added safeguards against metric gaming: required coverage and acceptance criteria cannot be weakened to improve apparent efficiency.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release 2.1.9 — Workflow process engineering
- New `workflow-execution-engine` defines explicit intake, planning, discovery, implementation, integration and release gates.
- Dependency-DAG work packages clarify ownership, inputs, outputs, write sets and acceptance checks.
- Parallel read-only work is separated from serialized shared-file writes and dependent validation.
- Bounded change batches add inspect-diff-test loops and stop/replan behavior after failures.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release 2.1.8 — Pre-runtime contract and conflict detection
- A mandatory producer/consumer contract pass for cross-system features, tracing registration and triggers through state/data flow, effects and cleanup.
- Explicit checks for identifier/value-shape mismatches, duplicate registration, dependency/version conflicts, invalid state transitions, stale references, partial updates and missing cleanup.
- Evidence rules that distinguish deterministic two-sided conflicts from inferred, dynamic, Molang and external-pack edges.
- End-to-end validation now requires contract-edge coverage for multi-system changes; unresolved dynamic edges remain visible rather than being guessed.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release 2.1.7 — Correctness-first code review
- Expanded the shared code quality standard with explicit contracts, preconditions, postconditions and invariants.
- Added targeted checks for boundary values, numeric units/ranges, state transitions, duplicate events, async failures, partial mutations and data/resource integrity.
- Added a failure-handling protocol that avoids silent catches and undocumented fallbacks.
- Added contract-derived test coverage for normal, boundary, invalid, repeated, stale-object, partial-failure and regression paths.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release 2.1.6 — Code clarity and maintainability
- Added a shared Code Quality Standard for readable, understandable and maintainable Bedrock add-on code.
- Added practical rules for naming, function/module boundaries, control flow, error handling, Script API lifecycle, JSON/UI resource organization, comments, documentation and folder structure.
- Added behavior-preserving refactoring and validation guidance; avoided blanket formatting or unnecessary abstractions.
- Linked the standard from the general Bedrock development workflow and Script API performance/safety audit.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release 2.1.5 — Junk-aware project analysis
- High-confidence filtering of obvious OS metadata, editor leftovers, caches, VCS internals and proven redundant build output from expensive semantic parsing.
- Explicit re-inclusion rules for references, manifests, build configuration, release artifacts, baseline deltas, security/integrity work and user-requested scope.
- Inventory/ledger accounting for excluded paths, reasons, counts and bytes; excluded files remain visible and can be reopened when evidence requires it.
- T2/T3 package-safety and integrity checks remain applicable even when semantic parsing is skipped.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release Notes — 2.1.4
- Extends staged analysis with explicit T0–T3 coverage tiers so fast triage cannot be mistaken for exhaustive review.
- Adds a per-file evidence ledger and terminal statuses for every inventoried file.
- Adds detailed checks for manifests, JSON/JSONC, scripts, typed resource references, UI, geometry, animation, localization and binary asset metadata.
- Adds bounded scheduling, streaming/hash reuse, cache invalidation and archive safety/resource limits.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release Notes — 2.1.3
- Adds `fast-project-analysis` for large add-ons and multi-file projects.
- Introduces staged inventory, classification, targeted reads, dependency-slice expansion and batched independent checks.
- Adds verified incremental reuse rules: changed files and reverse dependents are re-analyzed; stale or unverifiable caches are rejected.
- Reuses one compact evidence index across selected domain Skills to reduce repeated file discovery.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release Notes — 2.1.2
- Adds an ambiguity protocol for short, informal, incomplete and referential requests.
- Requires internal intent analysis using wording, conversation context, project files and known constraints without exposing private chain-of-thought.
- Distinguishes genuinely ambiguous requests from merely brief but clear requests; avoids unnecessary questioning.
- Adds concise multiple-choice clarification with an always-available free-form answer and safe skip/default paths for non-blocking choices.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.

## Release Notes — 2.1.1
- Adds `project-preflight-planner` for proportional pre-work planning.
- Defines QUICK / STANDARD / DEEP modes with hard caps of 2 / 5 / 8 initial questions; caps are maxima, not quotas.
- Supports selectable options, free-form answers, skipping non-critical questions and safe reversible defaults.
- Establishes one plan with scope, assumptions, dependencies, preservation rules, acceptance criteria and validation.
- Preserved the existing Skills-only plugin boundary; target-host activation and Minecraft runtime evidence remain separate.


## 2.1.0 — Strict Skills-only cleanup and documentation/version repair
- Base Plugin Creator release: 2.0.9 (`pluginrel_6aeef187613c819193b9fd1d4ef333e2`), USER / PRIVATE; verified from live Plugin Creator metadata and source inventory on 2026-11-07.
- Removed 34 historical `server/` implementation and test files after static dependency/provenance review. Their protocol dependency clusters were excluded; current standalone Skills utilities cover the retained PNG, geometry/UV, texture-painting and reference-transfer workflows. The server-specific analyzer was retired.
- Preserved all 65 Skills, 14 domains, eight workflow profiles, 12 default prompts, plugin identity and audience.
- Corrected version-history omissions for 2.0.8 and 2.0.9. Synchronized `VERSION`, both plugin manifests, README, CHANGELOG and VERSION_HISTORY to 2.1.0.
- Verification: Skills-only package strict gate 20/20 PASS; architecture 28/28 PASS; 27/27 test files / 500/500 cases PASS; 27/27 active entry-point help smokes PASS; 65/65 Skill instructions loaded in the current ChatGPT skill runtime.
- Boundaries: automatic Skill activation inside all installed-plugin surfaces and execution of packaged scripts by the plugin host remain NOT TESTED. No real third-party add-on archives or Minecraft game runtime were available; import/render/gameplay remain NOT RUN.

## 2.0.9 — Full local utility review and archive intake hardening
- Audited 90 Python files, hardened raw ZIP member preflight, and added five archive adversarial tests.
- Local evidence: 27 test files / 500 cases, 28 CLI help smokes, architecture 28/28; strict Skills-only gate remained blocked by 34 retained historical files.
- Host integration NOT TESTED; Minecraft runtime NOT RUN.

## 2.0.8 — Local utility hardening and script evidence
- Hardened reference-pack archive intake and added six security-focused tests.
- Local evidence: 27 test files / 495 cases; strict Skills-only gate remained blocked by 34 retained historical files.
- Host integration NOT TESTED; Minecraft runtime NOT RUN.

## 2.0.7 — Full Skill quality audit and capability-truth repairs
- Base current Plugin Creator release: 2.0.6 (`pluginrel_6aeed67929008191bf56e690123be1f3`), verified 2026-11-07.
- Candidate scope: audit all 65 Skills using the supplied Technical Guide 2.0; repair six phantom tool procedures; tighten manual/real-script capability boundaries; align UV transfer request example; improve specialist skill contracts; add reusable checklist and 325 NOT RUN activation cases.
- Preserve 65 Skill paths, 14 domains, all 12 default prompts, plugin identity, USER scope and PRIVATE audience. Preserve 34 historical `server/` files as inert inputs.
- Local static/test evidence and Plugin Creator source read-back are separate from target-host activation, plugin-host script execution and Minecraft runtime, which remain NOT RUN/NOT TESTED.
- See `SKILL_AUDIT_REPORT_2.0.7.md` and `SKILL_ACTIVATION_TEST_MATRIX.csv` for the per-Skill disposition and activation scenarios.


## 2.0.6 — Pinned archive inspection and audit-path integrity
- Base current Plugin Creator release: 2.0.5 (`pluginrel_6aeecff237348191bbd433dc732837d9`), confirmed 2026-11-07.
- Candidate scope: one-descriptor bounded ZIP inspection for `bedrock_audit.py`; stable source hashing, CRC and member reads; path-replacement and concurrent in-place mutation detection.
- Focused archive-safety tests: 12/12; full Skills suite: 490/490 across 27 test files; architecture validator: 28/28; compatibility package checker: 19 PASS / 0 FAIL / 1 WARN.
- Strict Skills-only gate remains BLOCKED by 34 retained historical `server/` files. Installed-host script execution NOT VERIFIED; Minecraft import/render/gameplay NOT RUN.
- Plugin Creator publication and post-update read-back are recorded separately from local static/test evidence.

## 2.0.5 — Standalone visual reference analysis
- Adds `skills/visual-reference-analysis/scripts/analyze_visual_reference.py` for deterministic 4-connected alpha/color segmentation of Bedrock reference PNGs.
- Optional geometry ranking reuses the shared cube-face UV extraction and scores aspect ratio (80%) plus normalized area (20%); the report labels these as geometric hints only.
- Adds bounded PNG/geometry input handling, path and symlink checks, duplicate-key rejection, read-only execution and source-image SHA-256 provenance.
- Focused tests: 13/13; full Skills suite: 486/486 across 27 test files; architecture validator: 28/28; compatibility package checker: 19 PASS / 0 FAIL / 1 WARN. Strict Skills-only gate remains blocked by 34 retained historical `server/` files. Minecraft runtime NOT RUN; installed-host script execution NOT VERIFIED.

## 2.0.4 — Skills-only maintenance hardening
- Adds deterministic geometry-aware texture painting utility and standalone regression tests; focused painter suite: 26/26 PASS.
- Hardens package-integrity detection for nested/renamed protocol components and adds adversarial negative tests.
- Expands reference transfer and archive/path-safety regression coverage; reference-transfer suite: 28/28 PASS.
- Adds read-only legacy dependency/provenance auditing, explicit migration policy, and a six-level SHA-256 script-execution registry.
- Hardens the isolated Skills test runner and the canonical standalone PNG validator; full local suite evidence: 473/473 tests across 26 files; 88 Python files in the registry.
- Plugin Creator release: `pluginrel_6aeec9f1334081918688cb9d4cd63c54`. The strict Skills-only gate remained blocked by 34 historical `server/` files; those files were retained and not deleted. Host integration and Minecraft runtime were not run.

## 2.0.3 — PNG validator safety-limit interface

- Exposed configurable PNG chunk-count limit through file validation and CLI.
- Added three regression cases; visual-resource-pipeline tests: 30/30 PASS.
- Both plugin manifests and VERSION synchronized to 2.0.3.
- ChatGPT-host script integration: NOT VERIFIED. Minecraft runtime: NOT RUN.

Minecraft Bedrock Engineer Version History

## 2.0.2 — Static Change Impact Analysis
- Base current release confirmed by live Plugin Creator metadata on 2026-11-01: 2.0.1 (`pluginrel_6ae64f5e27f0819184576d2780be411b`).
- Candidate scope: bounded static reverse dependency analysis for Bedrock BP/RP bindings and references, including explicitly listed removed/renamed paths, impact closure, ambiguity/unresolved-reference reporting and focused regression selection.
- Validation: Core tests 181/181; analyzer tests 32/32; architecture validator tests 37/37. Python compilation 10/10; four Draft 2020-12 schemas passed meta-validation; synthetic impact example validated. Manifest/prompt parity 2.0.2 / 12 prompts PASS.
- Local architecture validator: 27/28 checks on the partial overlay; the only failure is expected full Skill inventory coverage (8 of 65 Skill folders present locally). Unchanged Skills remain in the existing release and are preserved by the overlay. Full package-integrity checker: NOT RUN.
- Guarded Plugin Creator publication and source read-back are tracked separately. Minecraft import/render/gameplay and Creator Tools runtime: NOT RUN.

## 2.0.1 — Revisioned Project State Management
- Base release confirmed by live Plugin Creator metadata on 2026-10-31: 2.0.0 (`pluginrel_6ae64516da8481919917a9a0a73bb5a3`).
- Candidate scope: revision-guarded local project state, typed evidence records, hash-chained state history, immutable file-inventory snapshots, drift inspection, integrity verification, metadata-only restore/recovery and Work Order state links.
- Validation: combined Core suite 144/144; Python compilation for 8 affected scripts/modules; Draft 2020-12 meta-validation of all three contracts; project-state example schema validation; synthetic end-to-end state/Work Order/domain integration passed with 3/3 domains and zero schema errors. Runtime remained NOT RUN.
- Local architecture validator: 23/24 checks on the partial update overlay; the sole failure is full Skill inventory coverage (7/64 local Skill folders). Unchanged Skills are retained by the overlay update. Full package-integrity checker: NOT RUN.
- Base release was live 2.0.0 (`pluginrel_6ae64516da8481919917a9a0a73bb5a3`). Guarded Plugin Creator update and post-update source read-back are performed separately from local test claims.
- Minecraft import/render/gameplay and Creator Tools runtime: NOT RUN.

## 2.0.0 — Domain Result integration and conflict-aware Work Orders
- Base current release confirmed by live Plugin Creator metadata on 2026-10-31: 1.9.9 (`pluginrel_6ae628f00d648191bff6bfd49aaf85a0`).
- Candidate scope: Core specialist-result integration, extended Domain Result/Work Order contracts, cross-domain file conflict detection, evidence-backed acceptance reconciliation and aggregate runtime status.
- Focused integrator tests: 38/38; architecture validator tests: 27/27; domain planner tests: 44/44; combined Core suite: 109/109 passed. Python compilation, schema meta-validation and synthetic three-domain Work Order integration passed (3/3 results, acceptance MET, runtime NOT RUN). The live package-wide architecture validator was attempted on a partial local overlay and reported only the expected inventory limitation (6/63 Skill folders available locally); full package-integrity checker remains NOT RUN.
- Minecraft import/render/gameplay and Creator Tools runtime: NOT RUN.

## 1.9.9 — Minimal specialist Skill routing
- Base current release confirmed by Plugin Creator metadata on 2026-10-31: 1.9.8 (`pluginrel_6ae627e7c2d88191af7fb3b187a2a9ec`).
- Candidate scope: one lead Skill per selected domain by default; explicit `--include-skill` opt-in for task-relevant specialists, restricted to selected domains.
- Validation: domain planner + architecture validator suite 67/67; previous add-on baseline-diff 27/27 and add-on versioning 31/31 remain green. Python compilation and current-registry schema smoke checks pending final run.
- Full package integrity remains pending a complete extracted checkout; Minecraft/Creator Tools runtime NOT RUN.

## 1.9.8 — Operational domain planner
- Base current release confirmed by Plugin Creator metadata on 2026-10-31: 1.9.7 (`pluginrel_6ae62560f48c81918757072e9d5c988d`).
- Candidate scope: deterministic profile-to-domain planner, transitive dependency closure/topological ordering, Work Order emission, planner/registry/schema guards and architecture gate integration.
- Validation: domain planner + architecture validator tests 62/62 (39 planner + 23 architecture); Python compilation and real-registry smoke planning for all eight profiles passed; emitted sample Work Order validated against Draft 2020-12 schema with zero schema errors.
- Full package integrity remains pending a complete extracted checkout; Minecraft/Creator Tools runtime NOT RUN.
- Status at candidate-preparation time: candidate overlay prepared; Plugin Creator publication/read-back pending.

## 1.9.7 — Domain-Based Hybrid architecture implementation
- Previous current release confirmed as 1.9.6 (`pluginrel_6ae61ea4b67c81918f2a1b0f703422d6`); 1.9.7 published at Plugin Creator release `pluginrel_6ae62560f48c81918757072e9d5c988d`.
- Scope: five-plane architecture definition; canonical 14-domain/62-Skill registry; Work Order and Domain Result schemas; Core and skills-first routing contract; architecture validator and focused tests.
- Candidate validation: architecture unit tests 20/20; Python compilation and schema/registry JSON parsing passed. Plugin Creator read-back confirmed version 1.9.7 and all 12 prompts preserved.
- Full package checker and Minecraft/Creator Tools runtime were NOT RUN because the complete extracted package and target runtime were unavailable.

## 1.9.6 — Deterministic add-on baseline diff
- Base current release confirmed by live Plugin Creator metadata on 2026-10-31: 1.9.5 (`pluginrel_6ae618a0f3fc81919b8fc54429c2ffd9`).
- Candidate successor: 1.9.6 (one-step PATCH increment under the one-digit plugin-package policy).
- Plugin Creator later confirmed 1.9.6 as current at release `pluginrel_6ae61ea4b67c81918f2a1b0f703422d6`; root and compatibility manifests were read back at 1.9.6 with all 12 prompts preserved.
- Scope: deterministic SHA-256 file delta and manifest regression checks for add-on workbench milestones/releases; no actual user's WB07 archive bytes were processed by the local runner.
- Validation: baseline-diff tests 27/27; add-on folder/archive versioning tests 31/31; Python compilation 4/4. Synthetic WB06-style → WB07-style diff returned PASS with 1 added, 0 removed and 5 modified files; this was a fixture, not the user's WB07 archive. Full package integrity and version-governance tests NOT RUN in this partial checkout.
- Git commit SHA: NOT AVAILABLE.
- Runtime: Minecraft import/render/gameplay/multiplayer/performance NOT RUN.


## 1.9.5 — Archive-safe add-on versioning and title/manifest parity
- Base current version confirmed by live Plugin Creator metadata on 2026-10-31: 1.9.4 (`pluginrel_6ae613d2c5288191b144f71f894a4897`).
- Complete Plugin Creator attachment history inspected: 66 entries; no pre-existing `1.9.5` attachment.
- Candidate: 1.9.5 (one-step PATCH increment under the plugin package's one-digit version policy).
- Status before upload: candidate prepared locally; Plugin Creator upload/read-back pending.
- Scope: safe `.mcaddon`/`.mcpack` versioning, manifest auto-discovery, localized title preservation, module/dependency alignment and final archive read-back verification.
- Validation: add-on versioning + archive versioning 31/31 tests; Python compile check passed; synthetic paired-pack dry-run verified version `1.2.3 → 1.2.4`, both pack title translations, both manifests, module versions and BP→RP dependency. Full package integrity NOT RUN in the partial local working checkout.
- Runtime: Minecraft import/render/pack replacement/gameplay, multiplayer, Blockbench and Script API runtime NOT RUN.
- Git commit SHA: NOT AVAILABLE.

## 1.9.4 — Mandatory version-gate routing and helper hardening
- Published current Plugin Creator release at 2026-10-31 metadata refresh: `pluginrel_6ae613d2c5288191b144f71f894a4897`.
- Previous release confirmed as 1.9.3 (`pluginrel_6ae612e911b8819195c6e332f60a0b99`).
- Subsequent validation record: add-on versioning helper tests 15/15; Python compile passed; source read-back confirmed version parity and all 12 default prompts preserved.

## 1.9.3 — Coordinated Bedrock add-on versioning
- Plugin Creator release attachment `pluginrel_6ae612e911b8819195c6e332f60a0b99` (2026-10-31).
- Added the dedicated add-on versioning skill and local helper, separate from the plugin package's own version.

## 1.9.2 — Version-aware compatibility and migration
- Historical Plugin Creator release attachment `pluginrel_6ae5fef0f0088191b34c325e21152741` (2026-10-31).

## 1.9.1 — Historical attached release
- Plugin Creator release attachment `pluginrel_6ae5d41b27b481919d01fc55bfb4dd48` dated 2026-10-31.
- Public distribution status and a separate change summary are not independently verified in this history entry.

## 1.9.0 — Domain-based architecture and validation hardening
- Plugin Creator release attachment `pluginrel_6ae5d27066f881918b68f2658a235a11` dated 2026-10-31.
- Earlier validation record: Skills-only package checker and synthetic regression tests passed; Minecraft runtime NOT RUN.

## 1.8.0 and earlier
- Historical release attachments are retained; no historical manifest or version string is rewritten.
