# Release Notes — 2.1.1

## Bounded preflight planning and execution guard

- Adds `project-preflight-planner` for proportional pre-work planning.
- Defines QUICK / STANDARD / DEEP modes with hard caps of 2 / 5 / 8 initial questions; caps are maxima, not quotas.
- Supports selectable options, free-form answers, skipping non-critical questions and safe reversible defaults.
- Establishes one plan with scope, assumptions, dependencies, preservation rules, acceptance criteria and validation.
- Adds an execution guard for plan drift, self-correction, material blockers and completion evidence.
- Additive Skill; existing Skill files, plugin identity, privacy and 12 default prompts are preserved.
- Static package checks, host activation and Minecraft runtime must be reported separately. Minecraft runtime is NOT RUN unless actually tested.
