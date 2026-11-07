# Minecraft Bedrock Engineer 1.9.8 — Operational domain planner

## Changes

- Adds `skills/bedrock-engineer-core/scripts/plan_domain_work.py` to translate an explicitly selected `domain-registry.json` workflow profile into a deterministic, dependency-expanded domain order and Skill list.
- Emits a Work Order conforming to the shared contract, including project/source facts supplied by the caller, the capability route supplied by the caller, planned domain steps, release gates, empty pending file changes/results, and honest `PLANNED` / `NOT RUN` statuses.
- Adds optional-domain allow-list checks, unknown dependency and dependency-cycle rejection, duplicate domain/Skill ownership checks, baseline SHA-256 format checks, and safe no-overwrite output by default.
- Integrates planner availability/tests into the architecture integrity gate and documents how Core uses it when a real local executor and package checkout exist.

## Safety boundaries

This is a local planning utility only. It does not understand or classify natural-language intent, inspect a user's project, verify the host's actual capabilities, invoke Skills, call MCP, execute project scripts, alter a project or run in the background. The chosen profile, optional domains, project source and capability facts must be supplied by the caller.

## Validation

- `python -m unittest discover -s skills/bedrock-engineer-core/scripts -p 'test_*.py' -v`: 62/62 passed (39 planner tests + 23 architecture-validator tests).
- `python -m unittest discover -s skills/addon-baseline-diff/scripts -p 'test_*.py' -v`: 27/27 passed.
- `python -m unittest discover -s skills/addon-versioning/scripts -p 'test_*.py' -v`: 31/31 passed.
- `python -m py_compile` on both architecture utilities and their two test modules: passed.
- Real registry smoke test: all 8 current workflow profiles emitted dependency-safe plans.
- Sample Work Order: Draft 2020-12 schema validation returned zero errors.
- Full package checker: NOT RUN (local source remains a partial update overlay, not a complete package checkout).
- Minecraft import/render/gameplay, Creator Tools and Script API runtime: NOT RUN.
