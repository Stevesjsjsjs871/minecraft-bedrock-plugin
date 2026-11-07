# Release 2.1.11 — Outcome Quality Assessment

## Added
- New `outcome-quality-assessment` Skill for evidence-based evaluation of completed work against the original acceptance criteria.
- Eight quality dimensions: completeness, functional correctness, cross-system consistency, reliability/failure handling, maintainability, verification/evidence, delivery integrity and user-fit/usability.
- Separate readiness gates (`HOLD`, `REVIEW`, `READY FOR RUNTIME TEST`, `READY`) so averages cannot hide critical defects or unverified critical criteria.
- Explicit evidence provenance, exact-final-artifact reopening, score limitations and prioritized improvement loop.
- Integrated the quality gate into workflow completion and Domain Result integration.

## Guardrails
- No fabricated scores, timings, tests, runtime results or benchmark claims.
- `NOT RUN`, `BLOCKED`, `NOT APPLIED` and `UNVERIFIED` remain visible.
- Quality scoring never relaxes acceptance criteria or substitutes for runtime validation.

## Scope
Plugin-only process and skill update. No Minecraft add-on runtime benchmark was performed as part of this release.
