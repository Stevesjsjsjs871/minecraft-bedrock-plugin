---
name: bedrock-development
description: Use as the general version-aware engineering workflow for Minecraft Bedrock Behavior Packs, Resource Packs, Script API, manifests and cross-pack resources.
---

# Bedrock development

## Source-of-truth rules
Use the exact target version stated by the project. If none is stated, use 1.26.50 as the working baseline and clearly label it as a default. Prefer official Microsoft Creator documentation and Mojang Samples at a matching release/commit. Bundled samples under `references/mojang-samples-1.26.50.4/` are a curated, version-labelled corpus, not a guarantee that every current feature matches that release.

Do not assume a Mojang Samples search/read tool exists. Inspect the local index and sample files directly when mounted; otherwise use official web research through a real web capability. Cite exact source URLs and sample paths in the result.

## Project discovery
Inspect BP/RP roots, manifests, UUIDs, dependency links, `header.name`, `header.version`, `modules[].version`, format versions, namespaces, identifiers and existing resource references. For existing projects, preserve mechanics and assets. Establish the current add-on version and baseline before editing. Treat a `header.name` localization key as a pointer to `texts/*.lang`, not as the visible title itself.

## BP domains
For blocks/items/entities/recipes/loot/spawn/scripts, verify component and format support against target-version docs/schemas. Use JS ESM for `@minecraft/server` where appropriate and verify the manifest module dependency/API version. Check identifiers, events, component groups, recipes and cross-resource references.

## Script API authoring checklist
For a requested script feature, make the implementation plan explicit before writing:

1. **Compatibility contract:** record the target game version, module type/entry path, exact `@minecraft/*` dependency version and the official documentation/sample revision used. Confirm each imported symbol, event, method, option and return shape; do not infer availability from a newer sample or editor autocomplete.
2. **Boundary and state:** validate player/entity/block/component/config inputs at the boundary. Define who owns mutable state, its lifetime, its key (for example entity identity), cleanup conditions and behavior after reload, disconnect, death or invalidation.
3. **Execution model:** identify which work runs during startup, event callbacks, scheduled callbacks and per-tick paths. Keep callbacks small; avoid expensive world scans and unbounded task creation in repeated paths. Make asynchronous work and rejected promises visible.
4. **Failure behavior:** specify expected absence separately from faults. Guard optional entities/components and stale handles; report actionable context without swallowing errors or flooding logs. Do not silently retry or fall back unless the behavior is bounded and defined.
5. **Test design:** cover the normal path, missing/invalid inputs, boundary values, repeated events, cleanup, partial failure and multiplayer/ownership behavior where relevant. Separate pure logic tests from game-runtime checks.
6. **Delivery:** keep imports, subscriptions, state and cleanup easy to locate; document configuration units/defaults and side effects. Record exact static commands and game tests separately. If Bedrock runtime is unavailable, mark it `NOT RUN`.

Use this compact source layout as a readability guide, adapting names and APIs only after exact-version verification:

```js
// 1. Imports and verified constants
// 2. Pure input normalization / validation helpers
// 3. Feature logic with explicit inputs and outputs
// 4. World/entity side-effect boundary
// 5. Startup wiring and event subscription ownership
// 6. Cleanup / shutdown path when the lifecycle requires it
```

Do not paste this outline as a literal implementation. It is a reviewable separation of concerns, not a claim that any particular event or API exists in the selected version.

## RP domains
Inspect client entities, geometry, textures, materials, render controllers, animations, animation controllers, UI, localization and atlas mappings. Follow references rather than guessing filenames. UI audits should inventory the complete relevant `ui/` folder and include/namespace relationships.

## Implementation and validation
Use only a real file/code capability. Keep writes project-confined, avoid symlink/traversal escapes, preserve unrelated files and do not overwrite without authorization. Parse JSON, check UUIDs, identifiers, references, texture dimensions, geometry/UVs and animation graph edges. Run bundled scripts only when actually accessible and document their inputs/commands/results.

## Versioning on completed changes
When delivering a coherent implementation change set for an existing add-on, always invoke `skills/addon-versioning/SKILL.md` before final delivery unless the user explicitly says not to bump. Do not bump during inspection-only work or every intermediate save. Classify the completed changes as major, medium or fix; update the visible pack title to include `vMAJOR.MINOR.PATCH` and update `header.version` in every released BP/RP manifest. Align existing `modules[].version` and in-project BP→RP dependency versions. If pack names are localized, update their `.lang` values while preserving localization keys. Do not change UUIDs, `format_version`, `min_engine_version`, or built-in Script API dependency versions as a side effect. Never conflate the add-on version with the Minecraft Bedrock Engineer plugin package version.

## Evidence
Separate `CONFIRMED_IN_SOURCE`, `UNVERIFIED`, `PASS`, `FAIL`, `BLOCKED` and `NOT RUN`. Static checks do not prove Minecraft import, rendering, gameplay, multiplayer, Blockbench interoperability or Script API runtime behavior.

## Code readability, structure and maintainability
Before authoring or materially refactoring code, apply the package-root `references/code-quality-standard.md`. Treat it as the shared style contract for BP/RP JSON, JavaScript/TypeScript, UI definitions, resource naming, folder layout, comments and documentation. Follow the project's established conventions when they are coherent; do not reformat unrelated files or impose a new style across untouched code. If existing code is inconsistent, normalize only the touched scope and state the convention chosen.


## Correctness-first implementation
Before implementing non-trivial logic or refactoring existing behavior, apply sections 11 and 12 of the package-root `references/code-quality-standard.md` (contract, invariants, defect classes, failure handling and test design). For each changed behavior, identify normal, boundary, invalid-input and failure paths. Trace data from producer through transformations to every relevant consumer. Check numeric units/ranges, optional values, state ownership, repeated events, cleanup and partial-failure behavior. Fix root causes with the smallest safe change; do not suppress symptoms with broad catches or speculative fallbacks. Re-run focused checks and the dependency-impact/regression checks justified by the change. Treat static warnings as hypotheses until verified against real call paths and exact-version behavior.
