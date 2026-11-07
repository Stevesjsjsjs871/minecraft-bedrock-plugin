---
name: animated-entity-bundle-authoring
description: Use when a new Minecraft Bedrock entity needs a coordinated BP/RP bundle with geometry, multiple bone animation clips, a controller, and linked resource validation.
---

# Animated Entity Bundle Authoring

## Code quality contract

Before creating or changing code or structured resources, follow the shared `references/code-quality-standard.md` from the package root. Preserve established project conventions, keep changes scoped, and document contracts, invariants, failure paths and focused tests for non-trivial logic. For Script API work, verify every API and lifecycle assumption against the exact target version; static analysis is not runtime proof.


## Purpose and capability boundary

This Skill coordinates a complete animated-entity file change. It is **not a bundled generator or live tool**: the current package does not contain `create_animated_entity_bundle` or lower-level entity/animation generator tools. Do not invoke historical MCP names or imply an automatic transaction. Follow `skills-first-execution`; write files only through a real, currently available project/file capability. Without one, return the complete file plan or patch and mark writes `NOT APPLIED`.

## Required inputs

- Existing linked BP/RP project and exact target Bedrock version/build.
- Project namespace, entity identifier, intended behavior and visual requirements.
- Existing BP/RP manifests, UUID dependency, entity/client-entity conventions and a baseline.
- Geometry design: unique geometry identifier, bone names/parents/pivots, cubes, UV mode and texture canvas.
- For each clip: unique identifier/alias, duration, loop behavior, target bones, channels (`rotation`, `position`, `scale`) and ordered keyframes.
- Controller initial state, states, animation aliases, transitions and any entry/exit Molang commands.
- Texture asset or an explicit statement that texture creation is out of scope.

If the project, target version or resource ownership is ambiguous, inspect supplied files and ask only for the missing decision that blocks safe authoring. Do not scaffold over an existing project.

## Coordinated workflow

1. **Recover and plan.** Read `project-continuity`, `project-continuity` and the relevant registry profile. Establish one source of truth, project version, baseline and acceptance criteria.
2. **Research compatibility.** Use `research-versions`, `version-aware-compatibility` and matching Mojang samples for version-sensitive entity components, geometry, animation/controller formats and Molang behavior. Record source version/date and the exact pattern used. Examples are not proof of runtime compatibility.
3. **Design stable interfaces.** Finalize the BP entity identifier, RP client entity identifier, geometry identifier, bone names, texture/material aliases, animation identifiers/aliases, controller identifier and state names before writing dependent files.
4. **Author in dependency order.** Create or update only the requested BP entity and supporting behavior resources; RP client entity; geometry; texture; render controller; animation clips; controller. Keep every alias/reference exact. Do not add optional spawn rules, loot, scripts or UI unless requested.
5. **Preserve existing content.** Do not overwrite colliding files or replace existing identifiers. Stage each write; record exact paths and before/after hashes. If a write fails partway through, report the partial state and do not attempt unsafe rollback over concurrent edits.
6. **Validate the graph.** Parse changed JSON with duplicate-key rejection when available. Run `skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py --bp-root <BP> --rp-root <RP> [--entity-id namespace:name]` when a real Python executor can access the package and project. Pair with geometry/UV, PNG, dependency-closure and general resource audits as applicable.
7. **Regression and release.** Compare the result against the baseline. Review removals and changed identifiers manually. When delivering a coherent add-on build, apply `skills/addon-versioning/SKILL.md` once at the handoff boundary.
8. **Runtime.** Import into the exact Bedrock build and test spawn, visibility, texture, animation transitions/interruption, reload, multiplayer and Content Log. If no game runtime was used, state `NOT RUN`.

## Playback and graph contract

- Client-entity `description.animations` aliases map to exact animation/controller identifiers.
- `description.scripts.animate` activates the intended controller alias or direct clip playback; avoid duplicate direct playback when a controller owns it unless intentionally designed.
- Controller state animation entries must use aliases available on the client entity.
- Every transition target must exist in the same controller.
- Animation bone names must be compared with the intended geometry variant; report missing or variant-specific names rather than silently remapping them.
- Geometry and texture identifiers, render-controller aliases, BP/RP entity identifiers and manifest dependency UUIDs must resolve consistently.

## Acceptance and output

Return: target game version; project/entity IDs; planned and actual resource graph; exact files created/modified; changed identifiers/aliases; baseline delta; source provenance; static commands/results; unresolved or dynamic references; texture status; Molang evaluation status; runtime status; and next actions.

A bundle is `COMPLETE` only when all required files exist, exact resource links resolve, no unexplained removals or write conflicts remain, and each acceptance criterion has evidence. A static graph pass is not a gameplay or rendering pass.

## Safety limits

Never execute scripts from supplied add-ons. Reject traversal/symlink escapes and ambiguous output paths. Do not delete or roll back files merely because a check fails; inspect whether another writer changed them. Do not infer semantic body-part mappings or Molang truth from geometry similarity or text checks.
