# Release 2.1.10 — Adaptive Process Control

## Purpose
Add evidence-based self-monitoring to execution workflows so the plugin can detect inefficient plans, repeated failures, stale evidence and no-progress cycles, then replan without discarding verified work.

## Changes
- Added `process-self-monitoring` skill with a lightweight execution telemetry ledger, process-smell detectors, bounded recovery policy and evidence-preserving replanning rules.
- Integrated monitoring checkpoints into the workflow execution engine, preflight planning and Domain Result integration.
- Added explicit retry ceilings, branch isolation, stale-evidence invalidation and revalidation rules.
- Added safeguards against metric gaming: required coverage and acceptance criteria cannot be weakened to improve apparent efficiency.

## Limits
- Monitoring is procedural and session/evidence-based; it is not a background service or persistent analytics backend.
- Time/cost metrics are recorded only when actually observable. No benchmark or runtime performance gain is claimed.
- Minecraft runtime validation remains separate and must be reported `NOT RUN` unless actually exercised.

## Validation
- Archive and manifest checks are performed on this overlay before publication.
- Plugin source read-back is required after publication.
