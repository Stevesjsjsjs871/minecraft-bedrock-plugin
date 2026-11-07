---
name: deep-evidence-analysis
description: Use for exhaustive, fine-grained, high-confidence analysis of Minecraft Bedrock projects when the user requests all details, a complete audit, release readiness, integrity review, or when risk requires full coverage. Complements fast-project-analysis with a complete evidence ledger and verification gates.
---

# Deep Evidence Analysis

## Purpose

Deliver detailed, reproducible analysis without wasting time on duplicate discovery or flooding the reasoning context with raw files. The complete project is inventoried; each file receives an explicit disposition; relevant content and dependencies are deeply examined; every claim is traceable to source evidence.

## 1. Declare scope and coverage

Before reading, record: project/archive identity and hash, target Bedrock version, BP/RP roots, baseline identity, user goal, requested coverage tier, available tools, known limitations and acceptance criteria. Use T2 for detailed project analysis and T3 for release/security/integrity audits. If the user asked only about a specific feature, T1 may be enough unless the request also asks for all files/details.

## 2. Complete inventory

Create a deterministic inventory of every archive member/project path. Record exact case, size, pack/root, category, hash when practical and duplicate-content groups. Detect duplicate archive entries, unsafe paths, symlinks, suspicious compression ratios, unexpected nesting and root ambiguity. Do not execute scripts or extract unsafe paths. Reconcile inventory counts against the archive/directory listing.

## 3. File-by-file disposition

Every discovered file must have a ledger row and one explicit status. Text files are parsed with an appropriate parser; source code is syntax-checked where a real runtime exists; images/audio/binaries receive metadata inspection and content review when relevant; high-confidence junk, generated/vendor/cache content may be excluded from semantic review only with a documented reason under `fast-project-analysis` junk policy; inventory, integrity and package-safety checks still apply. A reference to an otherwise excluded file reopens it for analysis. Unknown formats remain unsupported/pending, not passed.

### Junk exclusion guard

Apply the high-confidence junk-file policy in `fast-project-analysis`. OS metadata, transient editor files, caches, VCS internals and proven redundant build copies can be inventory-only when outside task scope. Never use extension/name/size alone as proof of irrelevance. Check references, manifests, build configuration, baseline deltas and user scope before exclusion. Keep every excluded path in the ledger with a reason and counts/bytes; re-open it if later evidence points to it. T2/T3 still perform applicable archive safety, path, duplicate-entry, hash and integrity checks even when semantic parsing is skipped.

## 4. Deep semantic analysis

Analyze all applicable structures for the selected tier:
- manifests, pack identities, module types, UUIDs, dependencies, versions, engine constraints and script modules;
- typed definitions and references across BP/RP, exact path case, identifier namespaces and dependency closure;
- entity/client-entity/geometry/texture/material/render-controller/animation/controller/attachable chains;
- blocks, items, components, recipes, loot, spawn rules, functions, features, scripts and registrations as present;
- UI imports, controls, bindings, texture references and localization;
- geometry bones/cubes/UVs and texture dimensions/alpha when relevant;
- duplicate IDs/keys, dangling references, collisions, inconsistent version pairs and suspicious baseline deltas.

Do not treat arbitrary strings as references. Preserve resolved, unresolved, ambiguous, external and heuristic states separately. Follow both forward and reverse dependencies. Use exact source locations and typed edges.

## 5. Cross-check and challenge findings

For every material finding, verify the source path and pointer/symbol, inspect its consumer/provider, search for alternate definitions or overrides, consider version-specific conventions, and check whether it is intentional or external. Distinguish confirmed defect from likely issue, heuristic warning, design concern and unverified runtime behavior. Never convert absence of evidence into evidence of absence.

## 6. Performance discipline

Use a single inventory, parser-specific batches, bounded read-only concurrency, streaming hashes, and verified cache reuse. Deep-review only the relevant dependency closure for a focused request; for T2/T3 complete the required checks across the full project. Reuse parsed structures and evidence across domain Skills. Isolate corrupt files rather than aborting all other checks. Set resource limits and report when a limit prevented inspection. Do not trade correctness for arbitrary speed targets.

## 7. Evidence ledger and findings

Keep a file ledger with path, size/hash, category, parser/checks, definitions, incoming/outgoing references, status, findings and exclusion reason. Each finding includes ID, severity, confidence, exact source location, observed evidence, expected behavior, impact/dependents, validation status and minimal recommendation. Attach a baseline delta where a known-good baseline exists.

## 8. Validation

Run focused static checks, parser checks, syntax checks and available unit/regression tests. Re-open changed files and final artifacts. Report exact commands and exit codes. Minecraft import, rendering, gameplay, multiplayer, performance and Script API runtime are separate scenarios and remain NOT RUN unless actually exercised. Do not call static checks runtime verification.

## 9. Final quality gate

Confirm inventory/ledger counts reconcile; every file has a status; all findings have evidence; all required reference classes were checked; parse failures and unsupported files are explicit; acceptance criteria have evidence-backed statuses; and no unexplained removals or identity changes remain. If a gate cannot be satisfied, label the result partial/blocked rather than pass.

## Output

Provide: scope and tier; project totals (files/bytes); per-category inspected/metadata-only/skipped/failed counts; manifest and dependency summary; detailed findings with exact locations; reference-graph summary; baseline delta; commands/tests and results; coverage gaps; runtime checks not run; and a clear readiness conclusion. Offer a machine-readable ledger/report when a real output route exists. Never claim full analysis when any required coverage is missing.

## Controlled execution and revalidation 2.1.9

Follow `workflow-execution-engine` gates. Partition T2/T3 work into owned read-only inspection batches with explicit inputs and outputs, then reconcile all batches against the single file ledger before drawing conclusions. A failed parser must not abort unrelated files; quarantine that file as `PARSE_FAILED` and continue other independent checks. For every fix, link the finding to its root cause, changed paths, focused retest and affected reverse-dependency regression. Recompute only stale evidence, but rerun all coverage required by T2/T3 on the final candidate. Completion is blocked by unreconciled inventory counts, missing ledger dispositions, unresolved high/blocker findings or unverified acceptance criteria.
