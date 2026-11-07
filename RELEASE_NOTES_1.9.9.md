# Minecraft Bedrock Engineer 1.9.9 — Minimal specialist Skill routing

## Changes

- The domain planner emits each selected domain's lead Skill only by default, rather than listing every Skill in that domain. This keeps the selected execution set small and predictable.
- Adds repeatable `--include-skill <slug>` for an additional specialist Skill required by the task. The planner checks that the Skill exists in the registry, belongs to a selected domain, is not duplicated and is not already the domain lead.
- Updates Core, skills-first execution, architecture and package/release guidance to separate domain composition from specialist Skill selection.
- The workflow profile, domain dependency closure, Work Order schema, project/source fields and honest `PLANNED` / `NOT RUN` statuses are unchanged.

## Validation

- Architecture + planner tests: 67/67 passed (44 planner tests + 23 architecture-validator tests).
- Add-on baseline-diff regression suite: 27/27 passed.
- Add-on folder/archive versioning suite: 31/31 passed.
- Python compilation and current-registry smoke tests: final candidate validation.
- Full package checker: NOT RUN (local source remains a partial update overlay, not a complete extracted package).
- Minecraft import/render/gameplay, Creator Tools and Script API runtime: NOT RUN.
