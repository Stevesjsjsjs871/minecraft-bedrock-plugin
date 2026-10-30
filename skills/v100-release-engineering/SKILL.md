---
name: v100-release-engineering
description: Historical 1.0.0 milestone notes and release-quality principles. Use only for historical context; current releases must follow the Skills-only maintenance and release gates.
---

# Historical 1.0.0 release engineering notes

This file records the original 1.0.0 milestone and is not the current release runbook. It must not be used to restore retired server integrations or to infer current package state.

## Durable principles
- Preserve plugin identity, user data, specialist workflows, examples and safety boundaries.
- Repair existing behavior before adding scope; prefer backward-compatible, tested changes.
- Keep project writes confined, collision-safe and non-destructive.
- Verify exact target Bedrock version and source provenance.
- Separate implementation, static validation, benchmark scoring and Minecraft runtime tests.
- Never invent available tools or report unexecuted tests as passing.

## Historical execution record
The original 1.0.0 package record and 1.0.5 checker notes below are retained for audit history only. They are not evidence about the current package and must not be used as current release instructions. For current maintenance use `skills-only-maintenance`, `package-integrity`, `validation-runbook` and `release-quality-gate`.

All current status must be established from the current extracted candidate. Use `PASS`, `FAIL`, `BLOCKED`, `NOT RUN` and `INCONCLUSIVE` precisely. Minecraft import, rendering, behavior and multiplayer checks remain `NOT RUN` until actually performed.
