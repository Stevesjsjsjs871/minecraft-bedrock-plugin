---
name: script-api-performance-audit
description: Use when reviewing Bedrock JavaScript/TypeScript Script API code for exact-version compatibility, scheduling, query cost, optional-value safety, event lifecycle and performance risks.
---

# Script API Performance and Safety Audit

## Inputs and source authority

Confirm exact Bedrock build, BP root, script entry points, `manifest.json` dependencies and module versions. Separate pack version, engine minimum, `format_version` and `@minecraft/server`/UI module versions. Prefer official versioned Creator documentation and matching Mojang Samples/typings; record URL, version/commit and checked date. Do not infer API availability from an identifier or current typings unrelated to the target build.

## Static review workflow

1. Inventory JavaScript/TypeScript files, entry points, imports, dynamic imports, event subscriptions, intervals/timeouts and world/dimension/entity queries.
2. Build a module/import graph. Identify unreachable modules and circular imports as review items; do not treat an unreferenced module as disposable.
3. Inspect tick-sensitive work: per-tick full scans, nested/unbounded loops, repeated dimension/entity queries, broad selectors, synchronous heavy work, repeated parsing, excessive logging and duplicate subscriptions.
4. Inspect lifecycle cleanup: unsubscribe/cancel paths, world reload, entity/block removal, player disconnect/death, repeated initialization and duplicate event delivery.
5. Inspect optional/nullable results and collections before indexing or dereferencing (`players[0]`, `list[i]`, query results, components, blocks, entities). Check empty collections, invalidated handles and exceptions at boundaries.
6. Check exact-version API presence and event/property semantics using official sources. If sources disagree, record the conflict and do not silently pick the newest API.
7. Never execute submitted add-on scripts. Use syntax/static checks only on source code in a trusted review environment; run unit tests only when their code has been reviewed and execution is authorized.
8. For performance claims, define repeatable in-game profiling conditions: same device/build/world/entity count/settings, measurement interval and baseline. Static heuristics are risk indicators, not proof of FPS impact.

## Output and status

Return target version and declared modules; files/import graph; findings with path, symbol/context, severity/confidence and exact API source; likely impact; suggested bounded fix; tests/commands and exit codes; and in-game profiling status. Label API use `CONFIRMED_IN_SOURCE`, `DOCUMENTED`, `INFERRED` or `NOT VERIFIED` as appropriate. Gameplay performance and multiplayer behavior stay `NOT RUN` until measured in the target client/server.

## Safety

Do not upgrade Script API dependencies merely because the game or pack version changed. Never call undocumented APIs or assume unavailable tools. Do not rewrite unrelated script architecture or remove apparently unused modules without reference and runtime review.

## Readability and maintainability review

Apply the package-root `references/code-quality-standard.md` to every script review. In addition to runtime/performance defects, identify confusing naming, excessive function/class responsibility, hidden side effects, duplicated logic, deep nesting, fragile state ownership, unclear event lifecycle, magic values, dead/commented-out code and missing boundary/error handling. Prefer small, behavior-preserving refactors with explicit before/after rationale. Do not trade clarity for unnecessary abstraction or split files merely to reduce line count. Preserve public identifiers and event semantics unless a coordinated migration is explicitly in scope.


## Logic correctness and defect hunting
Use the contract-first and defect-class review in the package-root `references/code-quality-standard.md`, not only performance heuristics. Trace each critical event/callback from subscription to handler, state change and cleanup. Check repeated delivery, re-entrancy, stale entity/block handles, optional API results, dimension/coordinate assumptions, tick ordering, asynchronous rejection, timer ownership and partial state updates. For numeric/gameplay logic inspect units, bounds, rounding and zero/negative/extreme values. Confirm findings against all callers and exact target-version API semantics before marking them confirmed. Recommend minimal root-cause fixes and derive tests from the intended invariants; do not rewrite unrelated architecture.

## Optional bounded analyzer

When the package is available in an actual local Python environment, run:

```bash
python skills/script-api-performance-audit/scripts/script_api_analyzer.py <project-root> [--output report.json]
```

The analyzer is a read-only lexical inventory. It reports literal imports, manifest script-module dependencies, event subscription sites, timer calls, selected world-query calls and heuristic review hints. It is deliberately `PARTIAL`: it does not parse a complete ECMAScript AST, prove control flow or cleanup, type-check, resolve every import, validate API availability, or measure performance. Treat its output as a navigation aid; complete the workflow above with exact-version official evidence. The script does not execute submitted JavaScript/TypeScript.
