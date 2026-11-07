# Code Quality Standard — Minecraft Bedrock Engineer

This standard applies when creating, editing, reviewing or refactoring Bedrock add-on source. Its purpose is to make code easy to read, understand, navigate, debug and extend without introducing unnecessary abstraction or changing behavior.

## 1. Preserve conventions, then improve locally

- Inspect neighboring files and the existing project's naming, formatting, module and folder conventions before editing.
- Follow a coherent existing convention. If the project has no consistent convention, use the rules below for new/touched files only.
- Do not reformat, rename or reorganize unrelated files as incidental cleanup.
- Keep diffs focused. Separate behavior changes from formatting/refactoring where that makes review safer.
- Never change public identifiers, manifest UUIDs, resource identifiers, event names, exported APIs or referenced paths merely to make names prettier without updating every consumer and validating the migration.

## 2. Naming that communicates intent

- Use descriptive names for functions, variables, classes, modules, events, identifiers and files. Prefer `getNearbyPlayers` over `getData`, `isValidTarget` over `check`, and `cooldownTicks` over `n`.
- Use verbs for actions and predicates (`create`, `load`, `resolve`, `isReady`, `canUse`); nouns for data and domain concepts.
- Avoid unexplained abbreviations, one-letter names outside tiny local loops, vague names (`data`, `thing`, `value`, `manager`, `utils`) and misleading names.
- Keep Bedrock resource identifiers namespaced and stable. Use consistent namespace, folder and file naming; never infer that a file can be renamed without checking references.
- Name constants for meaning and units, e.g. `MAX_SPAWN_ATTEMPTS`, `COOLDOWN_TICKS`, `SEARCH_RADIUS_BLOCKS`.

## 3. Functions, modules and responsibility

- Each function should have one clear responsibility and a name that describes its observable effect or result.
- Keep functions short enough to follow without scrolling across unrelated concerns; split when there is a meaningful boundary, not at an arbitrary line count.
- Separate input validation, domain decisions, side effects and output/reporting where practical.
- Keep module boundaries aligned with stable concepts or feature domains. Avoid both monolith files and excessive one-function-per-file fragmentation.
- Prefer explicit parameters and return values over hidden mutable globals. Keep state ownership clear and minimize shared mutable state.
- Avoid duplicate logic; extract a helper only when it improves shared meaning or prevents meaningful drift. Do not create generic frameworks for one trivial use.
- Keep dependency direction understandable. Avoid circular imports and broad catch-all `utils` modules; place shared helpers in a narrow, well-named module.

## 4. Control flow and error handling

- Prefer guard clauses and early returns for invalid inputs and boundary cases; reduce deeply nested conditionals.
- Make optional values, empty collections, missing entities/components and invalidated handles explicit before use.
- Handle errors at meaningful boundaries. Do not silently swallow exceptions or use empty catch blocks; include enough context to diagnose failures without flooding the log.
- Distinguish expected absence from actual failure. Use safe fallbacks only when behavior is defined and intentional.
- Avoid magic numbers, unexplained booleans and opaque compound conditions. Extract named constants or predicates when they improve comprehension.
- Keep asynchronous flow explicit; document/handle rejected promises and avoid unbounded task creation.

## 5. JavaScript / TypeScript for Script API

- Follow the project's module system; use the verified manifest module entry point and exact target Script API version.
- Prefer `const`; use `let` only for reassignment; avoid `var`.
- Use strict equality (`===` / `!==`) unless a documented coercion is intentional.
- Prefer small pure helpers for calculations and explicit functions for world/entity side effects.
- Keep event subscription setup and teardown/lifecycle ownership visible. Prevent duplicate subscriptions and clean up timers/subscriptions when their owner ends.
- Avoid expensive world/entity queries in per-tick paths; cache only with a clear invalidation/lifecycle rule.
- Validate external/player/config input at the boundary. Never assume `players[0]`, a component, entity, block or query result exists.
- Do not use undocumented APIs, speculative typings or unsupported syntax for the target runtime.

## 6. JSON, UI and resource definitions

- Preserve valid schema/format and exact version-specific field semantics. JSON has no comments: do not insert comment syntax into strict JSON files.
- Use stable, meaningful property ordering within each resource family; keep related fields together and match nearby project conventions.
- Use consistent indentation and avoid needless one-line/minified JSON in human-maintained source.
- Do not add decorative metadata or duplicate fields that the game ignores or rejects.
- Keep identifiers, aliases, paths and localization keys consistent across BP/RP. Prefer a single authoritative definition and trace all consumers.
- Group UI controls and resource entries by screen/feature purpose; use clear names and avoid opaque nested bindings where a named reusable control is appropriate.
- Preserve localization keys and merge language files rather than replacing unrelated entries.

## 7. Comments and documentation

- Explain why, constraints, non-obvious engine behavior, version caveats and tricky algorithms; do not narrate obvious syntax.
- Update comments when behavior changes. Remove stale or contradictory comments only in the touched scope.
- Document public/configurable values, units, valid ranges, defaults and side effects.
- Add a short module/file header only when it clarifies ownership, purpose or lifecycle; avoid boilerplate headers everywhere.
- Prefer examples and exact identifiers over vague prose. Keep README/setup instructions aligned with actual files and commands.

## 8. Folder and project organization

- Organize by Bedrock resource family and feature/domain while respecting engine-required paths and established pack layout.
- Keep BP and RP responsibilities distinct; do not place files in arbitrary folders for visual neatness.
- Separate source, generated output, tests, tooling and documentation where the project/build process supports it.
- Keep one obvious entry point per script subsystem when practical and make imports traceable.
- Do not introduce build systems, transpilers, package managers, lint frameworks or dependencies without a demonstrated need and explicit compatibility review.
- Do not rename/move existing files unless all typed references, import paths, build configuration and package rules are updated and validated.

## 9. Tests and refactoring discipline

- Refactor in small, behavior-preserving steps. State the intended invariant before changing structure.
- For every structural refactor, compare observable behavior and resource/API references before and after.
- Add or update focused tests for pure logic and boundary cases when a real test route exists.
- Run formatter/linter/type checker only when the project already has a compatible tool/config or the user authorizes adding one. Do not silently install tools.
- Validate JSON/manifests/resource references and run focused tests after edits; broaden regression checks according to impact.
- Do not claim a refactor is safer/faster without test or benchmark evidence. Readability improvement can be described qualitatively with concrete examples.
- Do not execute untrusted scripts from submitted add-ons during static analysis.

## 10. Review checklist

Before delivery, check:
- names express intent and units;
- functions/modules have clear responsibilities;
- control flow is understandable and edge cases explicit;
- side effects and state ownership are visible;
- duplication is reduced without over-abstraction;
- comments/docs explain non-obvious constraints and match current behavior;
- folder layout and naming match Bedrock conventions;
- references, identifiers and public behavior remain intact;
- changed files are formatted consistently with the project;
- exact checks, unverified assumptions and runtime gaps are reported.

The goal is **clear, conventional, maintainable code**, not maximal abstraction, maximal comments, minimum line count or cosmetic churn.


## 11. Correctness before cleanup

Readability is useful only when the behavior is correct. Before implementing or refactoring non-trivial logic, write down the contract in plain language:
- **Inputs:** expected shape, type, units, valid range and whether absence is allowed.
- **Outputs:** exact result, failure/absence representation and observable side effects.
- **Preconditions:** what must already be true before the operation starts.
- **Postconditions:** what must be true when it succeeds or fails.
- **Invariants:** facts that must remain true across every branch, tick and event.

Check the data path end to end: source → validation/normalization → transformation → state mutation or API call → consumer. Confirm that every conversion preserves meaning, units and coordinate spaces. Do not rely on a variable name as proof of its type or units.

### High-value defect classes

- **Boundary values:** empty/missing values, `undefined`/`null`, zero, negative values, maximum values, off-by-one indices, invalid enum values, malformed strings and unexpected object shapes.
- **Numeric correctness:** `NaN`, infinities, division by zero, integer-vs-float assumptions, rounding/truncation, overflow/precision, coordinate units and inclusive/exclusive bounds.
- **State correctness:** stale references, partial updates, invalidated entities/blocks/components, duplicated initialization, repeated events, re-entrancy, ordering assumptions and state that is reset too early or never cleaned up.
- **Control flow:** branches that skip required cleanup, fall-through/default behavior, loops that do not terminate, early returns after partial mutation, and catch blocks that hide the original failure.
- **Async and scheduling:** rejected promises, work that outlives its owner, overlapping callbacks, unbounded queues, race-like tick ordering, and assumptions that a scheduled action runs immediately or exactly once.
- **Data integrity:** mutation of shared objects, shallow-copy mistakes, inconsistent identifiers, mismatched producer/consumer schemas, serialization round-trip loss and non-deterministic ordering.
- **Resource/API correctness:** references that resolve to the wrong resource, wrong dimension/coordinate context, unsupported target-version APIs, lifecycle misuse and mismatched manifest dependencies.

### Failure handling

- Validate untrusted or externally supplied data at the boundary; validate internal invariants at the narrowest useful point.
- Distinguish expected absence from failure. Use explicit result states or documented return contracts where ambiguity would cause a bug.
- Choose fallback behavior deliberately. A fallback must preserve a documented invariant; otherwise fail visibly and safely rather than inventing a plausible value.
- Catch errors only where the code can add context, recover, translate the error or safely terminate the operation. Preserve the original cause and relevant identifiers; never use an empty catch or silently continue after a partial write.
- Make multi-step mutations safe: validate before mutation, stage changes when possible, and avoid leaving half-updated state if a later step fails.

### Test design

For each changed behavior, derive tests from the contract, not merely from the implementation. Cover as applicable:
1. normal successful input;
2. missing, empty and malformed input;
3. lower/upper boundaries and just-outside values;
4. repeated invocation and duplicate event delivery;
5. stale/invalid objects and unavailable dependencies;
6. failure during a multi-step operation;
7. ordering, cleanup and state-reset behavior;
8. deterministic output and preservation of existing behavior.

Prefer small tests for pure logic; isolate engine side effects behind narrow functions where the existing architecture permits. Use property-based, fuzz or mutation testing only when a compatible toolchain already exists or the user authorizes it. Never add a testing framework merely for appearance. A test that repeats the implementation's assumptions without asserting the contract is weak evidence.

### Review procedure

1. State the intended behavior and invariants before editing.
2. Trace inputs, transformations, side effects, state and consumers.
3. Challenge the happy path with boundary and failure cases.
4. Identify the smallest root cause; distinguish symptom, cause and contributing design risk.
5. Apply a focused fix; avoid unrelated rewrites.
6. Re-run focused tests, then affected dependency/regression checks.
7. Inspect the final diff for accidental behavior changes, dead branches, stale comments and unhandled paths.

Static pattern matches are leads, not proof. Confirm each finding against surrounding control flow, target-version semantics and all relevant callers before assigning severity. Report uncertainty rather than turning a heuristic into a confirmed defect.
