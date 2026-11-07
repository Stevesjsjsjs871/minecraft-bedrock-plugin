## 2.3.4 — Consolidated domain entry points

- Consolidates seven requested areas: Geometry & UV, Project Continuity, Baseline Regression, Creator Tools, Add-on Authoring, Reference Texture Transfer and Release Engineering.
- Reduces the Skill inventory from 70 to 59 by retiring 11 redundant entry Skills; preserves independent specialist procedures, scripts, tests and approval gates.
- Preserves 14 domains, 8 workflow profiles, all 12 default prompts and plugin identity.
- Validation: 32/32 test files and 548/548 cases PASS; architecture 28/28 PASS; strict package integrity 20/20 PASS with zero warnings; 64 Python registry hashes match.
- Activation matrix: 295 scenarios designed, all NOT RUN on target Plugin Host. Creator Tools integration and Minecraft runtime remain NOT RUN. Candidate is unpublished.

## 2.3.3 — Entity authoring consolidation

- Consolidated `entity-authoring` into `entity-authoring-pipeline` as a focused authoring mode plus a full BP/RP resource-graph workflow.
- Preserved the standalone geometry example under the canonical Skill references.
- Retained the existing static audit utility and its test suite without changing their implementation.
- Updated Core routing, entity-animation domain membership, Skill inventory, activation design matrix and cross-Skill references.
- Removed one duplicate Skill entry; activation scenarios remain designed and `NOT RUN` until tested in the target Plugin Host.

# Changelog

## 2.3.2
- Route code and resource authoring through the shared maintainability standard from Core and specialist Skills.
- Add an operational, exact-version Script API authoring checklist.

## 2.3.1 — Project State descriptor-pinned inventory hashing (candidate)
- Closes a TOCTOU gap in Project State inventory hashing: regular files are opened once with `O_NOFOLLOW` where available, hashed through the pinned descriptor, and checked for descriptor/path identity and metadata changes.
- Rejects non-regular and symlink inputs at the hash boundary and refuses a path whose identity changed after the scan's initial `lstat`.
- Adds regression tests for symlink hashing and path replacement; Project State suite: 30/30 PASS.
- Full local suite: 32/32 test files, 548/548 cases PASS. Plugin Host activation/script integration NOT VERIFIED; Minecraft runtime NOT RUN.

## 2.3.0 — Archive security, JSONC compatibility and corpus verification (candidate)
- Fixes explicit ZIP directory-entry handling in the metadata benchmark builder.
- Adds shared ZIP namespace validation for normalized path safety, duplicate/case/Unicode collisions, file/directory conflicts, symlink/special-file rejection, encrypted-entry rejection and compression-ratio limits.
- Updates the reference corpus indexer to hash and read members through the same pinned file descriptor, verify CRC/decompression, and reject duplicate/ambiguous namespace entries.
- Adds 25 focused archive/security regression cases across ZIP namespace validation, benchmark builder and reference corpus indexer, plus six JSONC parser cases.
- Adds conservative JSONC parsing for comments/trailing commas, strict duplicate-key rejection and six parser regressions; real Furniture Add-On audit now parses 29 JSONC files and surfaces two actual duplicate-key files.
- Re-indexes ten supplied archives: 42,876 entries / 110 manifest records; static-audits five real archives without executing pack scripts or changing source archives.
- Full local suite: 32/32 test files, 546/546 cases PASS; package integrity 20/20; architecture 28/28; host integration NOT VERIFIED; Minecraft runtime NOT RUN.

## 2.2.0 — Multi-source Bedrock reference corpus
- Adds bounded read-only reference archive indexing and metadata for 10 supplied archives / 110 manifest records.
- Independent follow-up suite: 31/31 test files, 515/515 cases PASS; package integrity 20/20; architecture 28/28.
- Follow-up review identified duplicate-path acceptance, TOCTOU hash reopening and file/directory collision gaps in the indexer, plus an explicit-directory false rejection in the benchmark builder; fixed in 2.3.0.
- Host integration NOT TESTED; Minecraft runtime NOT RUN.

## 2.1.12 — Python utility audit corrections and bounded analyzers
- Adds bounded Script API lexical analysis, UI/PBR/Fog/resource-manifest inventory, and metadata-only real-pack corpus inventory.
- Hardens reference texture transfer with descriptor-relative no-follow reads and a PNG chunk-count limit.
- Corrects registry evidence/contracts and refreshes hashes for all 61 Python files.
- Validation: 30/30 test files, 511/511 cases PASS; plugin-host integration NOT TESTED; Minecraft runtime NOT RUN.

## 2.1.0 — Strict Skills-only cleanup and migration workflow repair
- Removes all 34 historical files under `server/` after reviewing their dependency clusters, test companions and standalone replacements. No legacy server/protocol implementation is shipped.
- Retires the server-specific AST analyzer and its test; keeps the migration Skill path but repurposes it for user-supplied Bedrock project migration.
- Preserves 65 Skills, 14 domains, eight workflow profiles, plugin identity, USER/PRIVATE audience and all 12 default prompts.
- Synchronizes VERSION, both manifests, README, CHANGELOG and VERSION_HISTORY to 2.1.0; records 2.0.8 and 2.0.9 history that was missing from VERSION_HISTORY.
- Strict Skills-only package check: 20/20 PASS; architecture: 28/28 PASS; Skills tests: 27/27 files, 500/500 cases PASS; 27/27 active Python entry-point `--help` smokes PASS.
- Local-only evidence. Installed-plugin automatic activation and bundled-script execution remain NOT TESTED; real third-party add-on corpus and Minecraft runtime remain NOT RUN.

## 2.0.9 — Full local utility review and archive intake hardening
- Audits all 90 registered Python files against Technical Guide 2.0 and refreshes every source SHA-256 in the six-level registry.
- Hardens `bedrock_audit.py`: validates raw ZIP member paths before CRC/decompression, rejects ambiguous path segments, case-insensitive duplicates, symlink members and file/directory collisions.
- Adds five adversarial archive regression tests; archive-safety suite rises from 12 to 17 tests.
- Completes the two missing texture-painter registry cards and corrects two false dependency failures caused by package-local sibling imports in visual-reference analysis.
- Runs `--help` smoke checks for all 28 non-test Skills Python entry points; all return exit 0.
- Full Skills suite: 27/27 test files and 500/500 cases PASS. Architecture: 28/28 PASS. Package integrity: 19 PASS / 0 FAIL / 1 WARN (34 retained historical `server/` files).
- Local CPython 3.13.5 evidence only. Installed ChatGPT-host script integration remains NOT TESTED; Minecraft import/render/runtime remains NOT RUN. Historical `server/` code remains inert and unexecuted.

## 2.0.8 — Local utility hardening and script evidence
- Hardens `reference_pack_audit.py` for untrusted input: opens and pins one regular-file descriptor for hashing and ZIP inspection, rejects symlink archive paths, ambiguous raw path segments, case-insensitive duplicate names and file/directory collisions.
- Moves ZIP CRC/decompression verification after metadata preflight so excessive entry counts, declared expansion and compression ratios are rejected before the integrity/decompression pass.
- Adds six security-focused reference archive tests; focused reference audit passes 14/14 tests.
- Adds direct CLI validation for change-impact analysis, reference-pack audit, Bedrock report validation and the 18-case synthetic regression harness.
- Records `jsonschema==4.26.0` as an optional, explicitly installed dependency for benchmark/report/regression validation.
- Full Skills test runner: 27/27 test files and 495/495 cases PASS. Package integrity: 19 PASS / 0 FAIL / 1 WARN. Host integration NOT TESTED; Minecraft runtime NOT RUN.

## 2.0.7 — Full Skill quality audit and capability-truth repairs
- Reviews all 65 portable Skills against the supplied Technical Guide 2.0: metadata, scope, capability truth, inputs, workflows, safety, hand-offs, references, testing boundaries and domain ownership.
- Removes six confirmed phantom MCP/tool procedures and replaces them with actual local/manual workflows or explicit BLOCKED/NOT APPLIED fallbacks.
- Corrects unsupported general writer claims; removes duplicated cooking version-gate text; expands five specialist Skills with concrete input, verification, report and runtime-limit requirements.
- Aligns the UV-retarget transfer example to the actual reference-transfer request schema; keeps semantic mapping approval as a human-review step.
- Adds a reusable quality checklist and a 325-case Skill activation test matrix; all target-host activation tests remain NOT RUN.
- Rebuilds Tool Registry claims and retains six-level script evidence. No Skills were deleted/renamed; all 12 default prompts and 14-domain/65-Skill assignments are preserved.
- Static/local tests and Plugin Creator post-update read-back are reported separately from target-host activation and Minecraft runtime. Historical `server/` files remain retained/inert.

# Changelog

## 2.0.6 — Pinned ZIP inspection and audit-path integrity

- Adds `open_bounded_zip()`, a context-managed reader that opens a regular archive once and retains the same descriptor for hashing, ZIP metadata, CRC validation and member reads.
- Rejects symlink/non-regular archive paths, detects path replacement during open, caps bytes while hashing, and detects in-place file mutation while inspection is active.
- Updates `bedrock_audit.py` to use the pinned reader instead of validating, hashing and reopening the candidate path separately.
- Adds 4 focused regression cases for pre-open inode swaps, after-open path replacement, in-place mutation and the auditor's use of the pinned source. Focused archive-safety suite: 12/12 PASS.
- Full Skills suite: 490/490 across 27 test files; architecture validator: 28/28 PASS; compatibility package checker: 19 PASS / 0 FAIL / 1 WARN. Strict Skills-only gate remains blocked by 34 historical `server/` files; host script execution and Minecraft runtime remain unverified/not run.

## 2.0.5 — Standalone visual reference analysis

- Ports deterministic 4-connected alpha/color segmentation into the Skills package as a local, read-only Python utility; removes the need to invoke its inert historical MCP source for this workflow.
- Adds optional cube-face candidate ranking against geometry extracted through the shared Geometry & UV Engine (aspect ratio 80%, normalized area 20%); no semantic recognition or automatic crop assignment is claimed.
- Adds bounded PNG validation/decoding, strict project-relative paths, symlink rejection, duplicate JSON-key rejection, geometry-size and segmentation-run budgets, and reference SHA-256 provenance.
- Updates the visual-reference Skill with an executable CLI workflow, input limits, host/runtime boundaries and human-review requirements.
- Focused visual-reference tests: 13/13 PASS; full Skills suite: 486/486 across 27 test files; architecture validator: 28/28 PASS; compatibility package checker: 19 PASS / 0 FAIL / 1 WARN. Strict Skills-only gate remains blocked by 34 retained historical `server/` files. Minecraft runtime NOT RUN; installed ChatGPT-host script execution NOT VERIFIED.

## 2.0.4 — Skills-only maintenance hardening

- Adds standalone geometry-aware texture painting utilities and 26 focused tests.
- Hardens package integrity against nested MCP declarations and renamed protocol adapters; adds negative regression probes.
- Expands reference texture transfer and ZIP/file safety regression coverage.
- Refreshes execution/tool evidence registries and package documentation.
- Local Skills tests: 473/473 passed. Strict Skills-only gate remains BLOCKED by 34 inert historical `server/` files; no server was executed or deleted. ChatGPT host and Minecraft runtime remain unverified/not run.

## 2.0.3 — 2026-11-07

- Hardened the visual-resource PNG validator interface: `max_chunks` is now configurable through the file API and CLI, matching the existing byte/dimension/pixel limits.
- Added regression coverage for chunk-count enforcement, invalid chunk-limit values, and forwarding the limit through file validation.
- Updated both portable and Codex-compatible plugin manifests to version 2.0.3; no Skills, MCP configuration, or remote execution components were introduced.
- Verification scope: local Python tests and static package checks; ChatGPT-host script execution and Minecraft runtime remain unverified/not run.

# Plugin package changelog

## 2.0.3 — PNG validator safety-limit interface

- Exposed `max_chunks` through `validate_file()` and the PNG validator CLI (`--max-chunks`), so file-based and command-line validation can apply the same chunk-count bound as `inspect_png()`.
- Added three focused regression tests covering enforcement, argument validation and API forwarding.
- Version markers synchronized: `plugin.json`, `.codex-plugin/plugin.json`, and `VERSION` = 2.0.3.
- Change class: patch/fix; no architecture, Skill inventory, UUID, or MCP changes.

## 2.0.4 — Extended implementation notes
- Adds a read-only legacy server dependency/provenance auditor. It parses Python AST without importing or executing legacy modules, records hashes, imports, dynamic import literals, test companions and textual references, and labels all legacy files as inert historical input.
- Adds a compatibility-mode package integrity warning for physical `server/` files and empty MCP/server-named Skill directories, plus an opt-in `--strict-skills-only` gate that fails while that legacy footprint remains.
- Adds explicit legacy migration/deletion policy and a session-scoped Tool Registry; local script execution is kept separate from installed ChatGPT Skill integration.
- Adds a six-level script execution registry for all 85 Python files and records the 24 Skills test files / 416 test cases executed locally. No server protocol tests, ChatGPT host integration, Minecraft runtime, or Blockbench tests are claimed.
- No historical source files were deleted and no MCP functionality was reactivated. Three empty MCP-named placeholder directories were removed after confirming they contained no files and had no active package references.
- Hardens the canonical standalone PNG validator with exact IHDR-derived IDAT expansion bounds, chunk ordering/type checks, dimension/pixel caps, symlink-safe file reads and 15 focused tests; the legacy server implementation remains inert and is not claimed as semantically identical.
- Extends package integrity to verify that the six-level Script Execution Registry covers every Python file, uses only documented statuses, and matches each file SHA-256; adds negative tests for missing, duplicate, stale, hash-mismatched and invalid-status entries.
- Hardens the isolated Skills test runner: rejects symlinked Skills roots/test files, constrains timeouts and test-file count, handles OS launch errors, and documents that package test code must be reviewed before execution. Adds five focused safety tests.
- Full Skills test runner now reports 24/24 test files and 416/416 cases passing in the local Python 3.13.5 environment; ChatGPT integration and Minecraft runtime remain NOT RUN.

## 2.0.2 — Static Change Impact Analysis
- Adds `change-impact-analysis` to the audit/validation domain and `analyze_change_impact.py`, a read-only reverse dependency analyzer with strict relative-path validation and bounded project scanning.
- Traces supported Bedrock BP/RP entity/client-entity bindings, geometry, textures, animation/controller/render-controller bindings, recipe item/block references, manifest UUID dependencies, UI file imports and relative JS/TS imports.
- Reports direct and indirect impact paths, confidence, duplicate/ambiguous identifiers, unresolved project references and incomplete scan coverage; output follows a dedicated JSON Schema.
- Adds synthetic fixtures and focused tests for dependency traversal, manifest links, UI/script imports, ambiguous identifiers, path safety, symlink handling, scan budgets, deterministic output and atomic report writes.
- Updates Core and architecture guidance to use impact analysis before/after substantive existing-project changes; preserves existing Skills paths, 14 domains, plugin identity, private audience and all 12 default prompts. No Minecraft runtime or code execution is introduced.


## 2.0.1 — Revisioned Project State Management
- Adds `project-continuity` and `project_state.py` for optional local, revisioned project-state records under `.mbe/`.
- Adds typed records for decisions, requirements, features, issues, tasks, tests and notes; integrity-checked state metadata, hash-chained history, immutable SHA-256 file-inventory snapshots, drift inspection and backup verification.
- Requires expected-revision preconditions for mutations; uses atomic state writes and lock protection. Partial scans do not infer deletions.
- Adds metadata-only restore and explicit metadata recovery. Snapshot inventories do not contain file contents; neither restore nor recovery rewrites add-on project files.
- Extends Work Order with an optional project UUID/revision/state-hash/snapshot link. Domain Result integration validates and preserves this reference.
- Adds 28 project-state tests, two state-link integration tests and five architecture checks/tests; registry now contains 14 domains / 64 Skills. All 12 default prompts and existing Skill paths are preserved.


## 2.0.0 — Domain Result integration and conflict-aware Work Orders
- Adds the Core `domain-result-integration` Skill and a deterministic local integrator for validated specialist hand-offs.
- Extends Domain Result with explicit per-file status, runtime status and evidence-backed acceptance-criterion results; extends Work Order with a structured integration report.
- Detects overlapping writes, inconsistent file actions, remove-versus-write conflicts and case-insensitive path collisions. Does not auto-merge or delete files.
- Aggregates domain coverage, findings, evidence, acceptance status, next-domain hints and runtime state; only marks a Work Order `COMPLETE` when all selected domains pass and all criteria are met with evidence.
- Adds 38 focused integration tests, extends the architecture validator to reject duplicate schema enum values, and updates architecture/release instructions. Preserves plugin identity and all 12 default prompts.

## 1.9.9 — Minimal specialist Skill routing
- Refines the domain planner to emit one lead Skill per selected domain by default, respecting the minimum-Skill selection policy.
- Adds repeatable `--include-skill` for additional specialists, rejecting unknown Skills, Skills outside selected domains, duplicate requests and redundant lead Skills.
- Updates Core, skills-first, architecture and release instructions so selecting a domain does not imply loading every Skill in it.
- Adds focused planner regression coverage; no registry membership, schema, plugin identity or default prompt changes.

## 1.9.8 — Operational domain planner
- Adds `plan_domain_work.py`, a standard-library utility that expands a caller-selected workflow profile through the registry's domain dependency graph and emits ordered domains, Skills, planned steps and delivery gates in the shared Work Order format.
- Validates profile membership, unique primary Skill ownership, dependency targets/cycles, capability routes, baseline digest format and presence of both JSON contract schemas.
- Keeps planning separate from execution: no task-intent classification, project inspection, tool discovery, Skill invocation, project-script execution or background persistence.
- Adds 39 planner tests, extends the architecture validator with three planner integrity checks/tests, and keeps 23 architecture checks in the combined 62-test suite.
- Preserves the 14-domain/62-Skill registry, all existing Skill paths and all 12 default prompts.
- Existing add-on baseline-diff regression suite: 27/27 passed; add-on folder/archive versioning suite: 31/31 passed.

## 1.9.7 — Domain-Based Hybrid architecture implementation
- Documents the approved five-plane architecture: control, domain, knowledge, execution and evidence.
- Adds the canonical registry for 14 domains and all 62 existing Skills, with unique primary ownership, lead Skills, domain ordering dependencies and eight task workflow profiles.
- Adds Work Order and Domain Result JSON Schema contracts for consistent cross-domain hand-offs and a shared project/baseline/evidence record.
- Strengthens Core routing and skills-first execution around one coordinated task plan and verified host capability routes.
- Adds a read-only architecture/package-structure validator and 20 focused synthetic regression tests.
- Preserves all existing Skill paths, the Skills-only boundary, plugin identity, private audience and all 12 default prompts. No MCP service or runtime backend added.

## 1.9.6 — Deterministic add-on baseline diff
- Adds `addon-baseline-diff`, a read-only `.mcaddon`/`.mcpack` comparator for known-good baseline versus candidate workbench/release archives.
- Adds SHA-256 file deltas with BP/RP root normalization, manifest/header/module UUID and version checks, internal pack dependency validation, `format_version`/`min_engine_version`/Script API drift reporting, and visible/localized title parity at release boundaries.
- Adds bounded ZIP scanning, path traversal/symlink/encryption/duplicate protections, duplicate JSON-key failure handling, JSONC/oversized-file review states and `node --check` syntax validation without executing add-on scripts.
- Integrates baseline comparison into existing-addon routing, regression workflow and release-artifact-workflow guidance. Removed files are surfaced for review and are never auto-deleted.
- Adds 27 focused tests. User project archives were used as workflow context only; the actual WB07 archive bytes were not available to the local test runner, so no claim of testing that user archive is made.


## 1.9.5 — Archive-safe add-on versioning and release parity
- Adds `addon_archive_versioning.py` for safe `.mcaddon`/`.mcpack` preview and new-archive creation without modifying the input.
- Adds bounded ZIP extraction/repacking, CRC checks, canonical path checks, duplicate/case-collision detection, symlink/encryption rejection and output read-back.
- Adds conventional BP/RP manifest auto-discovery for extracted projects; ambiguous multi-pack variants fail closed and require explicit path selection.
- Corrects localization-key updates so `header.name` remains a key while matching `.lang` values receive the new suffix; adds optional per-language display-name overrides.
- Adds verification of manifest/module/dependency version parity and title suffix presence, including the final output archive.
- Adds a small synthetic Cinematic Interactions-style paired-pack fixture and 31 focused tests. It is an example fixture, not a copy of the user's project.

## 1.9.4 — Mandatory version-gate routing and helper hardening
- Extends the mandatory task router so existing and new add-on workflows invoke `addon-versioning` when a coherent changed build is delivered.
- Adds release-boundary version guidance to add-on creation, bundle authoring, release artifact preparation and the cooking add-on specialist.
- Reinforces visible `vMAJOR.MINOR.PATCH` title and manifest version synchronization.
- Hardens the local utility to reject empty module lists and preserve file permission bits during atomic writes.
- Adds focused regression tests for these safeguards.

## 1.9.3 — Coordinated Bedrock add-on versioning
- Adds a dedicated workflow and standalone utility to version the user's Bedrock add-on separately from this plugin package.
- Requires the visible Minecraft pack title and `header.version` to receive the same `vMAJOR.MINOR.PATCH` at a coherent delivery boundary.
- Aligns existing module versions and in-project pack dependency versions while preserving UUIDs, engine minimums, manifest format versions and built-in Script API dependency versions.
- Supports localization keys in `.lang` files without replacing the key in `header.name`.
- Adds dry-run/apply safety and 13 focused regression tests.

## 1.9.2 — Version-aware compatibility and migration
- Adds a dedicated version-aware compatibility workflow for Bedrock BP/RP JSON, Script API dependencies, manifest requirements, preview/beta features and Creator Tools versions.
- Adds a dated Minecraft Bedrock 1.26.50 change-note reference documenting relevant stricter entity schemas, field migrations, stable block components and stable Script API versions.
- Adds focused compatibility skill tests and conservative migration guidance that forbids unnecessary global format-version bumps.
- Preserves existing skills, scripts, reference corpus, assets, plugin identity, scope, audience and all 12 default prompts.
- Historical server sources remain inert; no remote/MCP backend is introduced.
- Static skill tests pass; full package integrity and Minecraft runtime were not run in that update.
