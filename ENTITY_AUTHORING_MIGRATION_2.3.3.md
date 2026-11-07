# Entity Authoring Consolidation — MBE 2.3.3

## Decision

Merged the former `entity-authoring` procedure into the canonical `entity-authoring-pipeline` Skill. The canonical Skill now offers two scopes: (1) focused single-entity authoring and (2) complete connected BP/RP resource-graph authoring and static audit. The merge reduces routing duplication without requiring full graph validation for every small request.

## Source-to-target mapping

| Source | Disposition | Target / evidence |
|---|---|---|
| `skills/entity-authoring/SKILL.md` | Removed after migration | Unique discovery, BP, RP, bundle-integrity and safety guidance incorporated as `Focused entity-authoring mode` in `skills/entity-authoring-pipeline/SKILL.md` |
| `skills/entity-authoring/references/basic-geometry.example.json` | Moved | `skills/entity-authoring-pipeline/references/basic-geometry.example.json`; byte content preserved |
| `skills/entity-authoring-pipeline/SKILL.md` | Retained and expanded | Canonical Skill with focused and full-graph modes |
| `skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py` | Retained unchanged | Existing optional static graph checker |
| `skills/entity-authoring-pipeline/scripts/test_audit_entity_pipeline.py` | Retained unchanged | 5/5 tests PASS |
| `skills/entity-authoring-pipeline/references/entity-pipeline.example.json` | Retained | Existing full graph example |

## Routing and dependency updates

- Entity/animation domain remains `entity_animation`; lead Skill remains `entity-authoring-pipeline`.
- Removed retired slug from domain membership, Core composition summary, activation matrix and Skill inventory.
- Updated the domain purpose to explicitly cover focused entity authoring and full graph validation.
- Updated animation and animated-bundle Skills to refer to the canonical audit utility path.
- Activation design matrix now contains 70 Skills × 5 cases = 350 designed cases. All remain `NOT RUN` because target Plugin Host activation evidence is unavailable.
- Plugin identity and all 12 default prompts remain unchanged.

## Tests and evidence

| Check | Result |
|---|---|
| Entity pipeline unit tests | 5/5 PASS |
| Full Skills test runner | 32/32 test files; 548/548 cases PASS |
| Domain architecture validator | 28/28 PASS; 14 domains; 70 registered/discovered Skills; 8 workflow profiles |
| Strict package integrity | 20/20 PASS; six-level registry covers 64 Python files and hashes match |
| Python compileall | PASS |
| Entity-animation workflow planner smoke | PASS; selected `entity-authoring-pipeline`; plan status `PLANNED`; runtime `NOT RUN` |
| Default prompt parity | PASS; 12 prompts identical |
| Minecraft runtime / Plugin Host activation | NOT RUN |

## Regression issue caught and fixed

The first full test run found one stale hard-coded assertion expecting 71 Skills in `test_validate_domain_architecture.py`. The test was updated to expect 70 and explicitly assert that `entity-authoring` is absent while `entity-authoring-pipeline` remains registered. Its SHA-256 was refreshed in `SCRIPT_EXECUTION_REGISTRY.csv`. The full suite was rerun afterward and passed.

## Safety and release boundary

- Immutable baseline: `minecraft-bedrock-engineer-2.3.2-candidate.zip` SHA-256 `d95b60ac4f3e51eaa215c8737e264cc96a8d70092e23481ed2a697217217af1b`.
- Work performed in a separate copy; baseline archive was not modified.
- No local Python implementation was removed or rewritten in this migration.
- No MCP/backend/server components were added.
- No live Plugin Creator update or publication was performed.
- Runtime behavior, automatic Skill activation and in-game behavior are not established by these local checks.

## Status

**ENTITY GROUP MIGRATION: PASS — READY FOR NEXT GROUP REVIEW.**

This status applies only to the Entity Authoring consolidation. It is not a full product release approval or proof of host/game runtime integration.
