---
name: fast-project-analysis
description: Use for efficient, evidence-preserving analysis of large Minecraft Bedrock add-ons, uploaded archives, workspaces or projects with many files. Stage inventory, targeted reads, dependency expansion, batched checks and trustworthy incremental analysis.
---

# Fast Project Analysis

## Objective

Minimize time and context consumption while preserving coverage appropriate to the request. Fast triage is not a substitute for a complete audit when the user requests one.

## Analysis pipeline

1. **Establish scope and route.** Confirm actual project/archive root, readable files, executor and permissions. For archives, validate member paths before extraction and reject traversal/unsafe links.
2. **Inventory once.** Collect file paths, sizes, extensions, archive roots and manifests in one pass. Identify BP/RP boundaries and pack dependencies. Preserve a complete path inventory even when semantic reading is selective.
3. **Prioritize entry points.** Start with manifests, pack metadata, task-named files, registered definitions, script entry points, imports and direct references. Avoid reading every file in lexical order.
4. **Classify and filter.** Categorize text/config, code, assets, localization, documentation, generated output, dependencies, probable junk and unknown files. Apply the junk-file policy below before expensive parsing. Skip only high-confidence noise from semantic analysis; preserve inventory and disposition accounting.
5. **Build a focused dependency slice.** Index relevant definitions and references, then follow incoming and outgoing edges for the requested feature. Keep unresolved, ambiguous, external and heuristic edges distinct. Expand the slice when evidence demands it.
6. **Batch independent work.** Parse many text files through one bounded batch; run independent checks concurrently only if the real runtime supports it. Set sensible size/time limits, avoid duplicate reads, and never run conflicting writes concurrently.
7. **Escalate selectively.** Deep-read files with relevant symbols, failed parses, suspicious deltas, high-impact references or acceptance-critical behavior. Use full-tree checks for whole-project audits, releases, migrations and security/integrity-sensitive tasks.
8. **Return a compact evidence index.** Record exact path, role, relevant identifiers/references, findings, confidence, and source location. Reuse it across domain Skills.

## Incremental reuse

Reuse previous analysis only when it is actually accessible and its project identity, root, fingerprint/hash, analyzer version and schema are valid. Reprocess changed/new files and reverse dependents. Invalidate results when a dependency, parser, schema, target game version or analysis rule changes. Without a verifiable cache, perform a fresh inventory; do not pretend prior context is a cache.

## Correctness gates

- Never infer that a file is irrelevant solely from its extension or name if a reference points to it.
- Never treat unreadable, binary, oversized, malformed or unsupported files as successfully analyzed.
- Preserve exact path case and distinguish exact matches from normalized/heuristic matches.
- Do not auto-delete unreferenced assets or rewrite source while analyzing.
- For image assets, inspect dimensions, format, alpha and thumbnails first; load full-resolution content only when needed.
- For scripts, inspect entry points and imports, then relevant call paths; run syntax/tests where a real runtime exists.
- For JSON/resource graphs, parse structured fields and known reference locations rather than treating every string as a dependency.
- Whole-project audit coverage remains mandatory when requested. State explicit coverage gaps and runtime checks not performed.

## Report

Give total file count and total bytes when available; inspected counts by category; focused file set and why it was selected; skipped/excluded counts and reasons; parse errors; analysis stages/checks run; findings with exact evidence; and whether the result is triage or full audit.


## Coverage tiers: speed without hidden omissions

Select and label one tier before analysis. The tier controls depth, never honesty:

- **T0 — Orientation:** inventory, manifests, root layout, sizes, obvious entry points. Not an audit.
- **T1 — Focused diagnosis:** analyze the requested feature plus its dependency closure and relevant reverse dependents. Suitable for a narrow bug/feature request.
- **T2 — Detailed project analysis:** inventory every file; inspect all relevant text/config/code and metadata for every asset; resolve the complete in-scope reference graph; deep-review every finding and uncertain edge. Use when the user asks for detailed analysis, all details, or exhaustive review.
- **T3 — Release/security/integrity audit:** full archive and tree checks, all applicable parsers and structural checks, baseline diff, dependency closure, integrity/path checks, and explicit treatment of every unparsed/unsupported item. Runtime remains separate.

Never describe T0/T1 as a complete audit. If the user requests detail, do not silently downgrade from T2/T3 to a focused slice just to save time.

## Per-file evidence ledger

Maintain one row per discovered path, including assets and files excluded from semantic parsing. Minimum fields:
`path`, `size_bytes`, `sha256` (when practical), `category`, `pack/root`, `read_status`, `parser/checks`, `definitions`, `references_in`, `references_out`, `finding_ids`, `confidence`, `skip_reason`, `review_status`.

Allowed statuses include `INVENTORIED`, `METADATA_READ`, `PARSED`, `DEEP_REVIEWED`, `BINARY_METADATA_ONLY`, `SKIPPED_WITH_REASON`, `UNREADABLE`, `UNSUPPORTED`, `PARSE_FAILED`, `NOT_APPLICABLE`. A file is not `DEEP_REVIEWED` merely because it appeared in a directory listing. Every file must end with an explicit status; no silent disappearances.

For large projects, keep the full ledger as a structured artifact or compact indexed table rather than pasting all file contents into the reasoning context. Preserve exact paths, JSON pointers, symbol names, line/range locations where available, hashes and short evidence snippets so any finding can be reopened. Summaries must link back to ledger entries.

## High-detail inspection rules

- **Manifests:** inspect every pack manifest, header/module UUIDs, versions, dependencies, engine constraints, capabilities, script modules and entry points. Keep pack version, format version, engine version and Script API version separate.
- **JSON/JSONC:** parse with the correct/available parser; retain duplicate-key, comments/trailing-comma and malformed-file distinctions. Record JSON Pointer paths and exact source locations. Never silently normalize source.
- **JavaScript/TypeScript:** map entry points and imports, identify event subscriptions, command registrations, dynamic property use, API calls and call paths relevant to the request. Syntax checks are not semantic/runtime proof.
- **Resource references:** index typed definitions and uses; resolve exact case-sensitive paths and names; distinguish resolved, unresolved, ambiguous, external, heuristic and version-dependent edges. Follow both consumers and providers.
- **Geometry/animation/UI:** inspect linked identifiers and alias chains end-to-end, not only individual files. For geometry include bones, parents, cubes, pivots, rotations, locators, texture dimensions and UV faces when relevant. For animation include clips, channels, controllers, states, transitions, aliases and client-entity bindings. For UI include imports, controls, bindings, textures and localization paths.
- **Images/audio/binary assets:** inventory all paths and sizes; read format/dimensions/alpha/duration/codec metadata when supported; generate thumbnails or contact sheets for visual review when appropriate. Metadata-only inspection must be labelled as such. Do not claim visual/audio content was reviewed if it was not opened.
- **Localization:** compare keys across locales, detect missing/duplicate/unused keys with evidence, and preserve intentional fallbacks.
- **Unknown formats:** record file signatures/size and classify as unsupported or awaiting review. Never assume harmlessness from an unfamiliar extension.

## Safe acceleration and workload scheduling

1. Perform one deterministic inventory pass and compute hashes while streaming where possible; avoid repeatedly reopening archives.
2. Group files by parser and process bounded batches. Retain per-file outcomes even if a batch fails; isolate failures and continue with remaining files.
3. Use bounded concurrency only for independent read-only tasks. Set limits for workers, file size, archive expansion ratio, total expanded bytes, nesting depth and time. Do not launch unbounded tasks or load all binary bytes into memory.
4. Prefer streaming ZIP member reads and metadata; reject traversal, absolute paths, unsafe symlinks, duplicate archive entries and suspicious expansion. Never execute code from an untrusted pack.
5. Use hash-based deduplication to avoid repeating expensive content analysis, but retain each path, pack membership and reference edge. Identical bytes at two paths are not interchangeable identities.
6. Cache parser outputs only with verified project identity, path, content hash, analyzer/parser version, schema version and target game/API context. Recompute reverse dependents after a definition/reference changes. If dependency graph completeness is uncertain, widen the invalidation set.
7. Never use cached results to conceal unreadable files or a changed analyzer. Cache miss means reprocess; cache mismatch means invalidate.
8. Escalate expensive human/semantic review by risk and relevance, but never omit mandatory static coverage in T2/T3.

## Detailed findings format

Every nontrivial finding should include: stable ID; severity; confidence; exact path(s); JSON Pointer/symbol/line range; observed value or short evidence; expected behavior/source; impact; affected dependents; reproduction/validation status; proposed minimal fix; and whether the fix was applied. Separate facts, inferences and recommendations. A list of filenames without evidence is not a detailed analysis.

## Completion and quality gates

Before reporting:
- reconcile discovered file count with ledger row count;
- account for every file with a terminal or explicitly pending status;
- reconcile definitions and references, including unresolved/ambiguous/external edges;
- verify every reported finding points to actual source evidence;
- state exact coverage percentages/counts only when denominators are known;
- list skipped, unsupported, unreadable and failed files separately;
- distinguish static checks, manual review, tests actually executed and runtime checks not run;
- compare time-saving choices against acceptance criteria: speed may reduce repeated work and irrelevant context, never required coverage or evidence quality.

If the user asks for "all details", provide a detailed report or a generated ledger artifact when a real file-output route exists. Do not dump thousands of raw lines into chat; provide structured findings and exact source references instead.


## Junk and low-value file exclusion policy

The goal is to avoid spending parser, context and graph-analysis time on files that cannot affect the add-on, while never hiding a real dependency or audit target. Use a **high-confidence, reversible filter**, not a blanket extension blacklist.

### Exclude from semantic parsing by default when clearly incidental

- OS/file-manager metadata: `.DS_Store`, `Thumbs.db`, `desktop.ini`, `__MACOSX/` and AppleDouble `._*` sidecars.
- Editor/runtime leftovers: swap files (`*.swp`, `*.swo`, `*~`), temporary files (`*.tmp`, `*.temp`), crash dumps and clearly transient logs, unless the task is to diagnose those logs/crashes.
- Cache directories and bytecode caches: `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.cache/`, tool-specific cache folders, and compiled cache artifacts when not part of the requested deliverable.
- Repository internals and local editor state: `.git/`, `.svn/`, `.hg/`, `.idea/`, `.vscode/` are normally outside Bedrock runtime semantics; inspect their relevant config/history only when the task concerns source control, workspace setup, build tooling or provenance.
- Clearly redundant generated/build output or packaged copies (for example a build directory duplicating the authoritative source tree), but only after identifying the authoritative source and checking whether the output itself is the requested release artifact.
- Dependency/vendor trees may be excluded from deep semantic review when they are clearly third-party, unchanged and not the subject of the task; still inspect dependency manifests, versions, licenses and entry points as required. If runtime behavior or a security/dependency audit depends on their contents, include the relevant closure.

### Never classify as junk solely because

- a file is small, empty, hidden, unfamiliar, has an unusual extension, or is not referenced by the first-pass graph;
- its name contains `old`, `backup`, `test`, `example`, `generated`, `data` or similar words;
- it is binary, compressed, or has no parser available. Such files may need metadata/integrity inspection or remain `UNSUPPORTED`.

### Re-open / include conditions

A candidate exclusion must be included if it is referenced by a manifest, import, build script, pack definition, known resource field, project configuration or user request; is an authoritative input or release deliverable; differs from or explains a baseline change; or is needed to validate package integrity, licensing, provenance, reproducibility or security. When uncertain, retain it for cheap metadata inspection and defer expensive semantic parsing rather than dropping it.

### Accounting and safety

- Inventory every path once, including excluded files. Record `SKIPPED_WITH_REASON` with a concrete reason such as `OS_METADATA`, `EDITOR_CACHE`, `TEMPORARY`, `VCS_INTERNAL`, `REDUNDANT_BUILD_OUTPUT` or `UNRELATED_VENDOR_CONTENT`; never silently omit it.
- Keep excluded paths in the evidence ledger and report counts/bytes separately as inventory-only/excluded. Do not count them as semantically analyzed.
- For T2/T3, exclusion from semantic parsing does **not** exempt archive/path safety, duplicate-entry detection, suspicious size/compression checks, hash/integrity accounting or other applicable package-level checks.
- A reference discovered later overrides the exclusion and reopens the file plus its relevant dependencies. Never delete, rewrite or recommend deleting a file merely because it was excluded or appears unreferenced.
- Deduplicate identical content for expensive parsing only after hashing; preserve every original path, pack membership and reference identity.


## Code correctness pass
When the dependency slice contains executable code, add a focused correctness pass after the import/call graph is known. Trace high-impact values from input to mutation/API call and consumers. Check boundary values, optional results, numeric units/ranges, state invariants, duplicate events, lifecycle cleanup, async failures, partial mutations and exact-version API semantics. Prioritize paths that can corrupt persistent state, break pack loading, duplicate actions or fail silently. Verify each candidate against surrounding code before reporting it; static pattern matches alone are not confirmed defects. For T2/T3, include all in-scope code and explicitly account for any unreviewed path.

## Process control: staged discovery and verification 2.1.9

Use `workflow-execution-engine` as the phase controller. Maintain one inventory/evidence index and share it with every selected domain. Execute cheap, high-signal checks first (archive safety, manifests, JSON parse, entry points), then build the requested dependency slice, then deep-review suspicious and acceptance-critical paths. Parallelize only independent read-only batches supported by the host; never parallelize writes to the same path or dependent checks. When a failure appears, stop only downstream packages that depend on it, preserve independent work, fix the root cause and invalidate only evidence whose inputs/rules/dependencies changed. Do not repeat unchanged checks without a reason. This optimization never reduces the declared T0–T3 coverage tier.
