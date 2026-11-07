---
name: cooking-addon-engineering
description: Use when designing, implementing or auditing Bedrock cooking/food add-ons with stations, recipes, ingredients, transactions, animations, UI and BP/RP integration.
---

# Cooking Add-on Engineering

## Code quality contract

Before creating or changing code or structured resources, follow the shared `references/code-quality-standard.md` from the package root. Preserve established project conventions, keep changes scoped, and document contracts, invariants, failure paths and focused tests for non-trivial logic. For Script API work, verify every API and lifecycle assumption against the exact target version; static analysis is not runtime proof.


## Inputs and discovery

Confirm the exact Bedrock target version/build, BP/RP roots, manifests, dependency UUIDs, Script API module versions, project namespace and requested cooking loop. For an existing add-on, recover source-of-truth and baseline before editing. Inventory stations/blocks, item and food definitions, recipe types, tags, loot, functions, scripts, models, geometry, textures, animations, UI and localization.

## End-to-end workflow

1. Map the user-visible cooking loop: station interaction → input validation → recipe selection → ingredient reservation/consumption → output delivery → station/player state update → visual/animation/UI feedback → cleanup.
2. Identify each transaction boundary. Do not consume ingredients before confirming the recipe and output capacity; define behavior for invalid blocks, unavailable/disconnected players, inventory changes, duplicate events and interrupted actions.
3. Trace all BP/RP references and identifiers. Verify recipe ingredients/results against real item/block definitions and station tags. Check manifest dependency UUIDs and exact Script API modules.
4. For script-driven interactions, use `script-api-performance-audit` and exact-version documentation. Check event subscription lifecycle, repeated queries, optional results, concurrency, tick cost and cleanup.
5. For stations/blocks/items, compose the relevant block/item/recipe/entity/UI/animation Skills. Keep the chosen domains and shared baseline consistent; do not invent a single generator for the whole cooking system.
6. Preserve existing recipes, identifiers, localization overrides, atlases and assets. Create new paths unless replacement is authorized. Compare normalized file hashes and parsed definitions before/after; flag removed recipes/stations and identifier changes.
7. Run focused JSON/resource graph tests and static audits. For a coherent delivered add-on, apply `addon-versioning` once at the release boundary.
8. In Minecraft, test success/failure recipes, ingredient consumption, output-full inventory, interruption/disconnect, block removal, reload, multiplayer and UI/animation synchronization. Without game execution, mark runtime `NOT RUN`.

## Acceptance and output

Return target version, station/item/recipe identifiers, transaction sequence, relevant BP/RP/script paths, reference graph, versioned source evidence, exact validations and test counts, baseline delta, unresolved risks and runtime status. Keep static validation separate from actual crafting/gameplay tests.

## Safety

Do not copy third-party implementations/assets without authorization. Do not execute code from supplied packs. Do not claim a static recipe or JSON check proves correct ingredient consumption or multiplayer safety. Never delete resources solely because the audit cannot resolve a reference.
