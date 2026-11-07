---
name: outcome-quality-assessment
description: Use at the end of every non-trivial Minecraft Bedrock task to assess outcome completeness, correctness, reliability, evidence quality, integration, usability and delivery readiness against the original acceptance criteria.
---

# Outcome Quality Assessment

## Purpose and boundary

Assess the delivered outcome, not how confident the author feels or how many checks were run. This is an evidence-based acceptance layer over the Work Order. It is not a runtime, telemetry or benchmark tool. Do not claim automatic execution when only procedural review was possible.

Run after integration and before final delivery for every non-trivial task. For small answers, apply only relevant dimensions. For research-only or plan-only work, assess the requested artifact type; do not impose code/package criteria that do not apply.

## 1. Freeze the evaluation contract

Use the original Work Order and its acceptance criteria as the evaluation baseline. Do not rewrite criteria after seeing the result. For each criterion, record:
- exact criterion text and importance (critical, major, minor);
- expected observable outcome;
- evidence required to prove it;
- result: `MET`, `NOT MET`, `UNVERIFIED`, or `NOT APPLICABLE` with reason;
- evidence reference and any limitation.

If scope changed, record who authorized it and preserve the original criterion. An unapproved scope reduction is a quality defect, not a pass.

## 2. Quality dimensions

Score each applicable dimension from 0 to 4 and attach evidence. Use `N/A` only with a reason. A numeric score never overrides a failed critical criterion or a release blocker.

| Dimension | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Completeness | No usable outcome | Major requested parts absent | Partial; material gaps | All requested parts present; minor gaps disclosed | Every criterion addressed with evidence |
| Functional correctness | Proven critical failure | Multiple major defects | Core path plausible, material uncertainty | Checks pass; no known material defect | Adversarial and boundary evidence supports behavior |
| Cross-system consistency | Broken contracts | Multiple unresolved mismatches | Partial graph / open material edges | Relevant contracts and references reconciled | End-to-end producer/consumer and lifecycle chains verified |
| Reliability and failure handling | Unsafe or unstable | Major failure paths missing | Some boundaries/errors unverified | Important boundaries and recovery checked | Failure, cleanup, ordering and repeatability paths verified where applicable |
| Maintainability | Unusable structure | High confusion / duplication | Mixed clarity or localized debt | Clear structure, naming and focused changes | Cohesive, documented, easy to extend without overengineering |
| Verification and evidence | No usable evidence | Claims unsupported | Partial or weak evidence | Every material claim mapped to checks/artifacts | Independent/reproducible checks, provenance and limitations are explicit |
| Delivery integrity | Missing/corrupt output | Wrong or incomplete artifact | Artifact exists with unresolved packaging gaps | Exact output reopened and integrity checked | Final artifact, baseline delta, versions and handoff fully reconciled |
| User-fit and usability | Does not meet intent | Significant friction or mismatch | Partially usable | Matches stated intent and constraints | Ready to use with clear handoff and no avoidable ambiguity |

Do not score a dimension 4 from static evidence when its definition requires runtime or adversarial evidence. Mark `UNVERIFIED` when there is insufficient evidence; do not convert uncertainty into a low-quality factual claim.

## 3. Evidence rules

- Link every score and criterion result to exact paths, pointers, commands, outputs, hashes or observed behavior where available.
- Distinguish `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`, `NOT APPLIED`, `STATICALLY VERIFIED`, `RUNTIME TESTED` and `UNVERIFIED` accurately.
- Static parsing does not prove gameplay, rendering, multiplayer, event timing or API runtime behavior.
- A test result is valid only for the tested artifact/fingerprint, target version, configuration and relevant analyzer/rule version.
- Reopen the exact final output. Evidence from an intermediate staging tree cannot prove the delivered artifact.
- Absence of a detected issue is not proof of absence unless coverage and detection limits are known.
- Independent checks add confidence only when they test distinct failure modes; repeated equivalent heuristics do not multiply evidence.

## 4. Hard gates and readiness

Determine readiness separately from the numeric score:
- `HOLD`: any confirmed critical defect, unsafe change, corrupt/wrong artifact, unresolved high-severity conflict, or unmet critical criterion.
- `REVIEW`: material uncertainty, unresolved major finding, required check blocked/not run, incomplete coverage, or acceptance criterion unverified.
- `READY FOR RUNTIME TEST`: required static/integration checks pass, no known blocker remains, but runtime/gameplay validation has not been completed.
- `READY`: all applicable criteria met, required verification complete for the requested scope, no unresolved high/blocker findings, exact final artifact verified, and runtime criteria satisfied when runtime was part of the request.
- `NOT APPLICABLE`: only for an artifact/task type where a readiness label truly does not apply; explain.

Never use an average score to hide a critical failure. If any critical criterion is `NOT MET`, readiness is `HOLD`; if any critical criterion is `UNVERIFIED`, readiness cannot exceed `REVIEW`.

## 5. Score interpretation

Calculate the mean only across applicable scored dimensions, show the numerator/denominator and count of N/A dimensions, and round to one decimal. Report it as a diagnostic summary, not an objective probability or universal quality guarantee. Do not invent a score when dimensions lack evidence; report `INSUFFICIENT EVIDENCE`.

Suggested interpretation (not a substitute for gates):
- 0.0–1.4: unacceptable;
- 1.5–2.4: substantial rework;
- 2.5–3.2: usable with material limitations;
- 3.3–3.7: strong, with disclosed minor gaps;
- 3.8–4.0: high confidence within the explicitly tested scope.

## 6. Improvement loop

For each dimension below 3, each unmet/unverified criterion, and each material finding, create a prioritized improvement item with:
- root cause (observed or explicitly hypothesized);
- affected criterion/dimension and dependencies;
- smallest safe corrective action;
- owner/domain and write set;
- focused verification and regression checks;
- expected evidence that would raise the score/readiness.

Fix critical/high issues first, then major criterion gaps, then reliability/integration weaknesses, then maintainability/polish. After changes, rerun the affected checks and reverse dependents; invalidate only stale evidence. Reassess the exact final artifact. If no execution route exists, provide the actionable patch/plan and mark `NOT APPLIED` and `NOT RUN`.

## 7. Final quality report

Return a compact report containing:
1. overall readiness and score (or insufficient evidence);
2. criterion-by-criterion disposition;
3. dimension scores with short evidence references;
4. critical/high findings and unresolved uncertainties;
5. checks actually run versus not run/blocked;
6. final artifact identity/hash and baseline delta where applicable;
7. prioritized next fixes and whether they were applied;
8. runtime status and limitations.

Never state simply “100% complete”, “bug-free” or “fully reliable”. State the tested scope and remaining uncertainty. A quality report is not itself proof that the underlying checks executed.
