---
name: project-preflight-planner
description: Mandatory bounded pre-work planner for Minecraft Bedrock Engineer. Use before any non-trivial Bedrock implementation, repair, audit, research-to-implementation, release, or plugin-maintenance task to identify outcome-changing unknowns, ask only necessary questions, and establish one execution plan without delaying work.
---

# Project Preflight Planner

## Purpose and activation

Before substantive work on any non-trivial Minecraft Bedrock task, apply this procedure. For explanations, translations, one-line answers and tiny unambiguous edits, perform a silent QUICK preflight and proceed without interrupting the user.

## 1. Recover context before asking

Read the current request and relevant conversation/project context. Inspect supplied files and available project state to resolve facts that can be discovered. Identify requested outcome, authoritative source, target Bedrock version, constraints, preservation requirements, output format and actual execution route. Reuse facts already supplied; never ask the user to repeat them. Separate confirmed facts, assumptions and unknowns. Never claim an unverified file, tool, permission or execution route exists.

## 2. Select planning depth

Choose the smallest mode that safely covers the task. These are hard maxima, not quotas:

| Mode | Typical task | Maximum initial questions |
|---|---|---:|
| QUICK | Small, localized, low-risk, unambiguous | 2 |
| STANDARD | Typical feature, repair, bounded audit | 5 |
| DEEP | New add-on, cross-domain, release, migration, destructive/high-impact or materially ambiguous | 8 |

Ask fewer questions whenever possible. Ask zero if context/files resolve the task or no answer can materially improve the result.

## 3. Understand intent and ambiguity

For short, informal, incomplete, typo-heavy or referential requests (such as "сделай", "почини", "улучши", "как-нибудь", "сделай нормально", "без подробностей", "ну типо вот это"), do deliberate internal intent analysis before acting. Do not expose private chain-of-thought. Extract the literal action, likely desired outcome, referenced object/component, relevant conversation context, plausible interpretations, known constraints, missing inputs and consequences of choosing incorrectly.

Use files, project state and earlier answers to resolve references first. Casual wording and brevity do not mean the request is unintelligible. If one interpretation is strongly supported, low-risk and reversible, briefly state the understanding if useful, record any assumption and proceed. Do not ask questions merely because the user wrote few words.

Ask when multiple plausible interpretations would materially change behavior, scope, compatibility, appearance, data changes or acceptance, or when essential input/authorization is missing. Never guess silently about destructive actions, overwriting, deletion, publishing, deployment, purchases, security-sensitive behavior or live-world changes. If the user says "на твой выбор" / "use your judgement", choose a safe conventional reversible option unless the decision is genuinely blocking.

## 4. Question filter and format

Ask only when the answer can materially change implementation, compatibility, scope, user-visible behavior, safety, data preservation or acceptance; cannot be reliably recovered from files/context; and has no safe reversible default.

When needed, ask in one compact batch. Prefer 2–5 clear options when alternatives are finite, include a recommendation when justified, and always allow an ordinary free-form answer ("Другое — напиши своими словами"). Allow "не знаю", "на твой выбор" or "пропустить" for non-critical questions. Mark a question required only when it is a real blocker and briefly explain why. Use plain language and short examples; avoid jargon and internal implementation questions. Ask one at a time only if the first answer determines which follow-up is relevant. Never repeat an answered question.

Example:

"Я понял задачу так: [краткое понимание]. Что именно должно получиться?
1. [Вариант A] — [последствие]
2. [Вариант B] — [последствие]
3. [Вариант C] — [последствие]
4. Другое — опиши своими словами.
Можно ответить номером, текстом или написать «на твой выбор»."

## 5. Defaults and blockers

Classify unresolved items:
- **Blocking:** contradictory requirements, missing essential input, no valid way to meet the core outcome, or unclear authorization for a destructive/irreversible action. Pause only the affected operation and ask the minimum clarification.
- **Non-blocking:** choose the safest conventional, reversible default, record it as an assumption, and continue. A skipped question is not permission for destructive changes, publishing, deployment, purchases or live-world modifications.
- **Out of scope:** do not silently expand scope; optionally note it as a later enhancement.

## 6. One execution plan

After clarification—or immediately if none is needed—create one concise shared plan:
1. Goal and expected outcome.
2. Included and excluded scope.
3. Confirmed facts and explicit assumptions.
4. Actual execution route and capability limitations.
5. Ordered work steps, dependencies and minimum relevant domain Skills.
6. Preservation rules (identifiers, UUIDs, assets, mechanics, unrelated files and baseline).
7. Observable acceptance criteria.
8. Focused validation, regression checks, artifact read-back and runtime scenarios.
9. Material risks and blocker handling.

For cross-domain work use Core's shared Work Order and registry. Do not create competing plans per Skill. The plan remains an internal working record unless a real writable destination is available and persistence is useful.

## 7. Adaptive plan revision

After every user answer, new file discovery or execution finding, update the interpreted goal and confirmed constraints; mark assumptions confirmed, rejected or unresolved; re-evaluate only affected scope, dependencies, risks and acceptance criteria; and revise the same shared plan. Do not restart intake from zero or create a competing plan. Briefly tell the user what changed when the revision materially affects the work.

If an answer remains ambiguous, ask a narrower, more concrete follow-up with examples/options and free-form input; do not repeat the same question in different words. Normally allow at most two clarification rounds for one ambiguity cluster. If it remains unresolved, use a safe reversible default only if it still meets the core request; otherwise pause the blocked part and explain what cannot be decided. A genuinely new blocker discovered during execution may be clarified separately. Never enter an endless planning loop.

## 8. Approval and execution

Proceed without another approval when the user has clearly requested the work and the plan stays within scope. Ask approval only before material scope expansion, an incompatible design choice with no safe default, destructive action, or external side effect requiring authorization. Do not seek approval for routine implementation or validation. Start as soon as blockers are resolved; optional unanswered items must not delay work.

## 9. Execution guard

Compare actual work with the shared plan. Track concise statuses (`NOT STARTED`, `IN PROGRESS`, `PASS`, `BLOCKED`, `NOT RUN`, `NOT APPLIED`). Update the plan when new evidence changes understanding; distinguish evidence-driven refinement from scope expansion. Self-correct ordinary mistakes and rerun relevant checks. If a requirement/dependency fails, choose the smallest repair that preserves scope. Ask only when a new decision materially changes behavior, compatibility, risk, destructive scope, delivery or acceptance. Never silently broaden scope or discard existing behavior.

## 10. Completion gate

Reconcile every acceptance criterion against actual evidence (`MET`, `NOT MET`, `UNVERIFIED`, `BLOCKED`). Re-open changed files and outputs where possible; run focused tests first, then broader regression checks when justified. Report exact checks and results, deviations from plan and why they were necessary. Never label `NOT RUN` as `PASS`. Static checks do not prove Minecraft runtime behavior.

## Anti-patterns

Do not use generic long intake forms, ask questions answered by files/context, treat caps as quotas, stall over optional preferences, request approval for every step, hide assumptions, make irreversible choices silently, lecture the user for being brief, or re-plan indefinitely. Never claim that an internal plan was persisted when it was only held in conversation.


## 11. Fast project and file analysis

When a task involves an uploaded add-on, workspace or many project files, use the `fast-project-analysis` procedure. The goal is to reach reliable understanding with the least necessary reading, not to read every byte indiscriminately.

- **Stage 0 — orient:** establish the actual archive/project root, file count, total size, top-level layout and BP/RP boundaries. Read manifests and project metadata first. Do not extract or traverse untrusted archive paths blindly.
- **Stage 1 — classify:** group files by type and role (manifests, JSON definitions, scripts, UI, geometry, textures, localization, documentation, generated/build/cache, unknown). Apply the high-confidence junk-file exclusion policy in `fast-project-analysis`: exclude obvious OS metadata, transient/editor leftovers, caches, VCS internals and proven redundant build copies from expensive semantic parsing only when outside task scope. Preserve every path in inventory/ledger with a concrete skip reason; inspect references/config/baseline first, and reopen any excluded file if evidence or user scope points to it. Never treat unknown, binary, small, empty or merely unreferenced files as junk.
- **Stage 2 — target:** derive an initial file shortlist from the request, manifest entry points, identifiers, imports, references and dependency graph. Read likely entry points and directly referenced files before broad folders. Keep exact paths and case.
- **Stage 3 — expand on evidence:** follow references outward from relevant definitions and consumers. Expand to neighboring domains only when an edge, finding or acceptance criterion requires it. For a whole-project audit or release gate, perform the full required checks; speed must never become a reason to omit mandatory coverage.
- **Stage 4 — batch efficiently:** use one directory/archive inventory, parse suitable text files in batches, and parallelize independent reads/checks only when the actual executor supports it. Avoid repeatedly opening the same file or rescanning the same tree. Do not parallelize conflicting writes.
- **Stage 5 — summarize once:** maintain one compact index of paths, roles, definitions, references, findings and hashes where useful. Reuse that index across selected Skills instead of making each specialist rediscover the same files.

### Incremental analysis and cache discipline

If a real prior inventory/cache exists, verify its project identity, root, target version, schema/version and file fingerprints before reuse. Re-analyze changed/new files and their reverse dependents; retain unchanged-file results only when the fingerprint matches and the relevant analyzer/schema version is unchanged. If no trustworthy cache exists, build a fresh lightweight inventory. Never claim caching, persistence or incremental scanning unless the mechanism and data are actually available.

### Performance and correctness safeguards

- Prefer cheap filters first: path/type/size/manifest metadata, then targeted text parsing, then expensive graph/semantic analysis, then deep/manual review.
- Avoid dumping huge files or binary payloads into the reasoning context. Extract only relevant structured fields, snippets and exact line/path evidence; retain a way to reopen the source.
- For images and other binaries, inspect metadata/thumbnails or task-relevant assets first; decode full-resolution assets only when visual/texture work requires it.
- Deduplicate identical content by hash for analysis where safe, but preserve every original path and reference relationship. Never merge or rewrite source files merely because their hashes match.
- Treat parse failures, unsupported formats and skipped files as explicit coverage gaps. Do not silently count them as analyzed.
- Use a two-pass result: fast triage first, then deeper verification only for in-scope files, high-impact findings, uncertain references and acceptance-critical behavior.
- Report coverage honestly: total files, files inspected by category, files skipped/excluded with reason, parse errors, and checks not run when a complete audit is requested.



## 12. Detailed file-analysis requirement

When the task depends on project files, use `fast-project-analysis` to choose the correct coverage tier and build the file/evidence index. If the user asks for complete, exhaustive, forensic, release, integrity, or "all details" analysis, use T2/T3 coverage and the `deep-evidence-analysis` procedure. Do not confuse a fast focused diagnosis with a full-project audit. Keep per-file status and explicit gaps; never claim all files were analyzed unless the inventory and ledger reconcile.

## Workflow handoff and phase gates 2.1.9

After preflight, hand the same task envelope to `workflow-execution-engine`. Do not create a second plan in each specialist. The plan must identify observable acceptance checks, work-package owners, dependencies, write sets, risks and the real capability route. Keep the user's requested scope fixed; replan only when new evidence changes a dependency, compatibility assumption or acceptance condition. A missing execution route is not a reason to keep planning indefinitely: produce a complete unapplied patch/command plan and mark it honestly.

## Adaptive process control 2.1.10

Use `process-self-monitoring` throughout this workflow. Maintain a minimal process ledger for non-trivial tasks: planned package/action, observed outcome, evidence, failure signature/root-cause category, retry count, recovery decision and evidence freshness. Record timing only when actually observable.

At each gate and after each failed check, inspect for repeated failures, no-progress loops, redundant reads/checks, late validation, plan drift, unowned dependencies, stale evidence, write contention and repeated non-blocking questions. Treat each as a diagnostic trigger and attach concrete evidence; do not infer a process defect from a single ambiguous symptom.

Recovery is bounded: correct the precondition, then retry the same failure signature at most once. If it recurs, stop that branch and replan, change to a genuinely different supported route, or mark it blocked/unverified. Two consecutive no-progress actions trigger a branch pause and re-scope. Never blindly retry a capability gap.

Before replanning, checkpoint the Work Order, acceptance criteria, baseline, completed packages, changed files and evidence fingerprints. Mark evidence RETAIN, REVALIDATE, INVALIDATE or UNKNOWN. Rebuild only the affected dependency subgraph and reverse dependents; preserve unaffected verified results. Re-run integration checks for affected edges.

Process monitoring must not weaken requested coverage, remove acceptance criteria or turn skipped/failed checks into PASS. It is procedural and current-task scoped, not a persistent telemetry service or background monitor.
