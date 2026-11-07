---
name: workflow-execution-engine
description: Use for every non-trivial Minecraft Bedrock add-on task to run a staged, dependency-aware workflow with explicit gates, parallel-safe work packages, change batches, verification loops, and evidence-based completion.
---

# Workflow Execution Engine

## Purpose

Turn the user's outcome into the shortest safe sequence of verified work. This is a process contract, not a tool or executor. `skills-first-execution` and `bedrock-engineer-core` remain authoritative for capability truth, domain routing and final integration. Use this Skill to control the work between intake and delivery.

## Operating loop

### Gate 0 — Intake and feasibility
- Restate the outcome as observable acceptance criteria; preserve the user's language and constraints.
- Resolve project/source-of-truth, target Bedrock version, BP/RP roots, baseline, preserved behavior and output destination from available evidence.
- Verify the actual read/write/execute route and permissions. If execution is unavailable, switch immediately to a patch/instructions workflow; never simulate execution.
- Classify unknowns as blocking, non-blocking or out-of-scope. Ask only for blocking facts; choose reversible defaults for the rest.
- Stop before destructive, overwrite, deploy or live-world actions without explicit authorization.

**Exit:** a bounded task envelope, explicit criteria, known blockers and a real execution route (or an honest no-execution plan).

### Gate 1 — Plan as a dependency graph
- Split work into small work packages with: owner domain, inputs, expected outputs, acceptance check, dependencies, risk and write set.
- Model prerequisites as a DAG. Run independent read-only inspections in parallel only when the host supports it. Serialize writes to shared files and any dependent operation.
- Separate discovery, design, implementation, integration and validation. Do not let implementation begin while its required compatibility or contract decisions are unresolved.
- Add a reviewer/validator work package for every high-risk or cross-domain change; it must challenge the implementation rather than repeat it.
- Keep one shared baseline, naming/identifier map, decision log and change list. Specialists must not create competing sources of truth.

**Exit:** every package has an owner, dependency, output and pass/fail test; no circular or unowned dependency remains.

### Gate 2 — Discover once, expand by evidence
- Inventory the project once and build a compact evidence index. Reuse it across domains; do not repeatedly rediscover the same files.
- Start with manifests, entry points, registrations, direct consumers and the requested feature chain. Expand through incoming/outgoing references and reverse dependents only when evidence requires it.
- Escalate to full-tree coverage for explicit exhaustive/release/security requests. Preserve per-file disposition and skipped reasons.
- Record unresolved/external/dynamic edges separately. Do not interpret an incomplete index as proof that a producer or consumer does not exist.

**Exit:** the relevant dependency closure is covered to the requested tier and every uncertainty is visible.

### Gate 3 — Implement in bounded change batches
- Make one coherent, reviewable change batch per feature or contract. Avoid mixing unrelated cleanup with functional fixes.
- Before editing, state the invariant and expected behavior. Keep changes local to the responsible domain and preserve unrelated assets.
- After each batch: reopen changed files, inspect the diff, run the cheapest relevant parser/type/syntax/unit checks, then update the shared evidence index.
- If a check fails, stop downstream work that depends on the failed output; diagnose the root cause and replan only the affected branch.
- Do not allow two work packages to write the same path concurrently. Shared-file ownership must be explicit; otherwise serialize and integrate patch-by-patch.

**Exit:** each batch has a clean diff, verified file state and focused test evidence, or a clearly recorded failure/blocker.

### Gate 4 — Integrate and adversarially review
- Collect a Domain Result from every selected domain. Validate schema, domain identity, file actions, exact acceptance criteria and evidence.
- Reconcile overlapping writes, add/remove conflicts, identifier/schema disagreements and cross-domain producer/consumer contracts. Never silently choose a conflicting version.
- Ask the reviewer pass to attempt to falsify the claimed success: test boundary cases, alternate paths, stale state, failure/cleanup, target-version compatibility and regressions.
- Deduplicate findings by underlying contract/defect, not by matching wording. Multiple heuristic alerts do not increase confidence by themselves.
- Re-run only affected edges and reverse dependents after a fix, then run the required broader regression set.

**Exit:** all domain outputs agree on the same baseline and acceptance criteria; conflicts are resolved or explicitly open.

### Gate 5 — Release and completion decision
- Validate the exact final staged artifact, not an earlier intermediate tree. Reconcile inventory, manifests, identifiers, resource graph, baseline deltas, package integrity and test results.
- Use a readiness state that reflects evidence: `HOLD` for confirmed serious defects; `REVIEW` for unresolved material risks or required checks not run; `READY FOR RUNTIME TEST` only after required static checks pass. Never call static success a runtime pass.
- A task is complete only when every acceptance criterion is evidenced, every selected domain has reported, no unresolved blocker/high finding or file conflict remains, and the exact output is verified. Otherwise report `PARTIAL`, `BLOCKED` or `NOT APPLIED`.
- Deliver concise summary, exact changed paths/artifact hash, tests and exit codes, remaining risks and runtime scenarios.

## Recovery and replanning

Replan when the target version changes, a new dependency is discovered, the baseline drifts, a test contradicts an assumption, a write conflicts, or the actual capability route differs from plan. Preserve completed evidence that remains valid; invalidate only checks affected by changed inputs, parser/rule versions, schemas or dependency edges. Never continue a downstream branch on stale evidence.

## Efficiency rules

- Prefer one inventory, one shared graph, one baseline and one integration pass.
- Parallelize independent read-only tasks; serialize conflicting writes and ordered validations.
- Run cheap/high-signal checks early, expensive deep checks only on relevant closure unless coverage tier requires more.
- Stop repeating a check whose inputs and rule version are unchanged and whose prior evidence is verifiable.
- Do not optimize by skipping required coverage, hiding unsupported formats or relaxing acceptance criteria.

## Adaptive process control 2.1.10

Use `process-self-monitoring` throughout this workflow. Maintain a minimal process ledger for non-trivial tasks: planned package/action, observed outcome, evidence, failure signature/root-cause category, retry count, recovery decision and evidence freshness. Record timing only when actually observable.

At each gate and after each failed check, inspect for repeated failures, no-progress loops, redundant reads/checks, late validation, plan drift, unowned dependencies, stale evidence, write contention and repeated non-blocking questions. Treat each as a diagnostic trigger and attach concrete evidence; do not infer a process defect from a single ambiguous symptom.

Recovery is bounded: correct the precondition, then retry the same failure signature at most once. If it recurs, stop that branch and replan, change to a genuinely different supported route, or mark it blocked/unverified. Two consecutive no-progress actions trigger a branch pause and re-scope. Never blindly retry a capability gap.

Before replanning, checkpoint the Work Order, acceptance criteria, baseline, completed packages, changed files and evidence fingerprints. Mark evidence RETAIN, REVALIDATE, INVALIDATE or UNKNOWN. Rebuild only the affected dependency subgraph and reverse dependents; preserve unaffected verified results. Re-run integration checks for affected edges.

Process monitoring must not weaken requested coverage, remove acceptance criteria or turn skipped/failed checks into PASS. It is procedural and current-task scoped, not a persistent telemetry service or background monitor.


## Outcome quality gate 2.1.11

Before delivery, run `outcome-quality-assessment` against the original Work Order. Freeze the acceptance criteria before scoring; assess only applicable dimensions and attach evidence to every score. Report completeness, functional correctness, cross-system consistency, reliability, maintainability, verification/evidence, delivery integrity and user-fit separately. Use `HOLD`, `REVIEW`, `READY FOR RUNTIME TEST` or `READY` gates; a numeric average cannot override a critical failure or unverified critical criterion. Reopen the exact final artifact, then prioritize corrective work by severity and revalidate only affected dependency branches. If checks cannot run, disclose `NOT RUN`/`BLOCKED`; do not infer quality from a clean diff or a completed plan.
