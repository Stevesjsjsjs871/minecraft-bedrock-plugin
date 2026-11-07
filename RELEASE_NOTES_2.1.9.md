# Release 2.1.9 — Workflow process engineering

## Added
- New `workflow-execution-engine` defines explicit intake, planning, discovery, implementation, integration and release gates.
- Dependency-DAG work packages clarify ownership, inputs, outputs, write sets and acceptance checks.
- Parallel read-only work is separated from serialized shared-file writes and dependent validation.
- Bounded change batches add inspect-diff-test loops and stop/replan behavior after failures.
- Evidence reuse and targeted invalidation reduce repeated work without reducing declared audit coverage.
- Independent challenge/reviewer passes and exact-final-artifact gates strengthen completion decisions.

## Updated
- Preflight, fast analysis, deep evidence, project audit and end-to-end validation now share one process controller and consistent phase gates.

## Boundaries
- No new runtime executor or background service is introduced. Actual host capabilities must still be verified. Static checks do not prove Minecraft runtime behavior.
