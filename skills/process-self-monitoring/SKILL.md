---
name: process-self-monitoring
description: Use during every non-trivial workflow to detect inefficient plans, repeated failures, avoidable rework, stale evidence and no-progress loops, then trigger bounded evidence-preserving replanning.
---

# Process Self-Monitoring

## Purpose and limits

Act as a lightweight control loop over the current Work Order. Monitor execution quality from observed events and artifacts, not intuition. This is a procedural Skill, not a telemetry backend, persistent memory, background agent, timer or executor. Do not claim automatic observation of tools or processes that the host does not expose. Record duration, counts and resource use only when directly measurable; otherwise use qualitative statuses.

## Minimal process ledger

Maintain one compact ledger per task/work order (in the shared task record where supported; otherwise as an internal checklist):

| Field | Required content |
|---|---|
| Work package | Stable ID, owner/domain, dependency IDs, intended output |
| Plan | Planned action sequence, acceptance check, risk and write set |
| Observation | Actual action/check, result, evidence reference and timestamp/order |
| Failure | Stable failure signature, affected package/files, root-cause category |
| Recovery | Corrective action, retry number, invalidated evidence and retained evidence |
| Decision | Continue, retry, isolate branch, replan, ask, or stop |

Failure categories: missing/invalid input; capability/permission gap; compatibility/contract mismatch; implementation defect; test/tool/environment failure; dependency/order failure; conflicting write; stale baseline/evidence; scope/acceptance ambiguity; unknown.

Do not invent timings, failure causes, test outcomes or persisted ledger files. Distinguish an observed fact from a hypothesis.

## Detect process smells

At each phase gate and after every failed check, inspect for:
1. **Repeated failure:** the same normalized failure signature recurs after an attempted correction.
2. **No progress:** consecutive actions produce no new evidence, no resolved blocker and no acceptance-criterion movement.
3. **Redundant work:** the same file/check is repeated without changed inputs, fingerprints, analyzer version or a documented reason.
4. **Late validation:** many dependent edits accumulate before the first relevant cheap check.
5. **Plan drift:** work packages expand beyond agreed scope or acceptance criteria silently change.
6. **Unowned dependency:** a package waits on a missing input/result with no owner or recovery path.
7. **Stale evidence:** a file, baseline, target version, tool, schema or dependency changed after the evidence was produced.
8. **Write contention:** overlapping or conflicting writes, or a dependent write starts before its prerequisite is integrated.
9. **Question loop:** the same non-blocking uncertainty is repeatedly sent back to the user instead of using a reversible default.
10. **False completion pressure:** a skipped, blocked or failed check is being treated as passed to finish faster.

A smell is a trigger to inspect, not automatically proof of a defect. Link every trigger to concrete ledger events or artifacts.

## Bounded recovery policy

- First failure: classify it, preserve the exact error/evidence, identify the smallest plausible root cause, and correct the input/order/configuration before retrying.
- Retry at most **once for the same unchanged failure signature** after a meaningful corrective change. A retry without a changed precondition is prohibited.
- If the same signature fails again, stop that dependent branch. Do not keep repeating the same command, read, edit or test. Replan the branch, switch to a genuinely different supported route, or mark it `BLOCKED`/`UNVERIFIED` and ask only for a blocking input.
- If two consecutive actions in a branch yield no new evidence or state change, pause and re-scope that branch. Do not count status narration as progress.
- For a capability/permission gap, do not retry blindly; switch to a supported patch/instruction route or stop.
- For a tool/environment failure, separate infrastructure failure from project defect. Preserve the raw failure and do not mark the project check as failed/passed unless it actually evaluated the project.
- For conflicts, serialize writes and reconcile against the common baseline; never resolve by silently selecting one writer's result.
- Replan only the affected branch and its dependents. Preserve unrelated completed work and valid evidence.

## Evidence-preserving replanning

Before replanning, freeze a checkpoint:
- current Work Order identity, acceptance criteria, baseline and target version;
- completed work packages and their exact outputs;
- evidence references, file hashes/fingerprints where available, and analyzer/schema versions;
- changed files and current write status;
- failed checks, raw signatures, blockers and unresolved risks.

Classify existing evidence:
- **RETAIN:** unaffected and still matches current file/baseline/tool/schema fingerprints and assumptions.
- **REVALIDATE:** affected by a changed dependency, configuration, target version, contract, analyzer or downstream integration.
- **INVALIDATE:** demonstrably stale, contradictory, tied to a changed input, or produced by a failed/unsupported check.
- **UNKNOWN:** freshness cannot be established; never promote it to RETAIN by assumption.

Rebuild only the affected dependency subgraph. Re-run changed nodes, their reverse dependents and acceptance-critical integration edges. Keep unaffected nodes and results intact. Do not reuse evidence across different project identities or baselines.

## Process quality checkpoint

At every gate, answer from evidence:
- Is the current sequence still dependency-correct?
- Did any action repeat without a new precondition or evidence need?
- Are blockers owned and bounded?
- Is validation happening early enough to localize failures?
- Which evidence remains fresh, and what became stale?
- Did scope or acceptance criteria change? Was that authorized?
- Are required checks still present in the plan?

If the plan is inefficient, adjust order, batch size, ownership or route—not the acceptance bar. Run cheap/high-signal checks earlier, isolate failing branches, and parallelize only independent read-only work when supported. Serialize shared writes.

## Anti-gaming and completion rules

- Never improve apparent efficiency by skipping required files, checks, coverage tiers, regression edges or user acceptance criteria.
- Do not treat fewer tool calls, shorter output or fewer tests as success by itself.
- Do not label a workflow optimized without measured before/after evidence.
- A replan does not erase a failure from the ledger.
- Completion requires the original acceptance criteria to be evidenced, all selected domains integrated, no unresolved high/blocker issue, and explicit disclosure of `NOT RUN`, `BLOCKED`, `NOT APPLIED` and `UNVERIFIED` items.
- Runtime and performance claims require actual runtime/benchmark evidence; static process checks cannot establish them.
