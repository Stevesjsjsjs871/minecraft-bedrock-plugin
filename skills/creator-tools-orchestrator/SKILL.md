---
name: creator-tools-orchestrator
description: Use to sequence available native authoring, validation and audit capabilities across a Bedrock project without assuming remote tools exist.
---

# Capability orchestration

Orchestrate workflows through specialist skills and real host capabilities only. This skill does not expose a tool registry, MCP orchestrator or hidden execution backend.

1. Classify the task and select a minimal chain of specialist skills.
2. Inventory the actual available file, code, web and optional Creator Tools capabilities. Do not infer availability from names in old source files.
3. Assign each step an input, expected output, write scope, validation and evidence requirement.
4. Execute steps in dependency order. Stop if an upstream artifact is missing or validation fails; do not fabricate downstream success.
5. Keep authoring, static validation, benchmark scoring and in-game verification as separate stages.
6. Reconcile file changes after each write stage and preserve unrelated resources.
7. Return a concise stage table with `PASS`, `FAIL`, `BLOCKED` or `NOT RUN`, plus exact artifacts and remaining work.

If no execution route is available, orchestrate the work as a complete patch plan and mark it `NOT APPLIED`.
