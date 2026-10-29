# Mojang Bedrock Samples index — 1.26.50.4

This directory is a **reference index**, not a copy of the full vanilla resource pack. It was built from the user-provided archive using `skills/bedrock-development/scripts/index_mojang_samples.py`.

## Provenance

- Source: [Mojang bedrock-samples](https://github.com/Mojang/bedrock-samples)
- Target label provided for the archive: `1.26.50.4`
- Uploaded ZIP SHA-256: `c0b6151f5f9a0c31ebe3c909dfc82d97f12473ed2c6e039aa7e22d667042026c`
- ZIP entries: 22,859
- Entries indexed: 22,252
- Declared uncompressed size: 319,437,100 bytes
- CRC integrity check: passed
- Method: no extraction; path checks; SHA-256 for files small enough to read under the indexer cap; strict JSON parsing for eligible JSON files and allowlisted identifier harvesting.
- Runtime testing: not performed.

## Indexed resource families

- `animation`: 143
- `animation_controller`: 73
- `attachable`: 55
- `block`: 98
- `block_model`: 4
- `client_entity`: 180
- `entity_behavior`: 128
- `geometry`: 193
- `item`: 79
- `json`: 1,684
- `localization`: 269
- `loot_table`: 309
- `other`: 24
- `particle`: 192
- `recipe`: 1,892
- `render_controller`: 173
- `sound`: 4,766
- `texture`: 11,756
- `trading`: 27
- `ui`: 207

## How the plugin should use this reference

1. Find a path or pattern that matches the target resource family and exact target version.
2. Open the relevant source example and its adjacent manifest or documentation sample before proposing a new file.
3. Extract only the minimal schema/shape/identifier relationship required for the task; never copy a vanilla file wholesale as a mod template.
4. Adapt examples to the add-on's unique namespace, UUIDs, dependency graph, localization, texture paths and target engine/API versions.
5. Mark version/API compatibility as verified only after consulting version-matched official docs/source or running the applicable validator. Mark Minecraft import and gameplay as `NOT RUN` unless actually tested.
6. Treat Mojang sample assets and license notices according to the applicable Minecraft EULA. Do not automatically bundle vanilla textures, sounds or models into generated packs.

## Core example snippets available

The bundled source examples focus on representative structures:
- BP and RP manifests (`behavior_pack/manifest.json`, `resource_pack/manifest.json`)
- Item definition (`behavior_pack/items/apple.json`)
- Block definition (`behavior_pack/blocks/black_concrete_slab.block.json`)
- Shaped recipe (`behavior_pack/recipes/emerald.json`)
- Client entity linkage (`resource_pack/entity/pig.entity.json`)
- Animation data (`resource_pack/animations/pig.animation.json`)
- Geometry (`resource_pack/models/entity/goat.geo.json`)
- Selected offline HTML documentation pages for Items, Blocks, Recipes, Animations and Schemas.

The original full sample ZIP is not embedded in this plugin package. The bundled index contains metadata, paths and selected literal identifiers only; use `read_mojang_sample` with the original ZIP placed in the configured workspace to read an indexed text file that is not one of the curated bundled examples. Store the archive locally and pass it to the indexer when rebuilding the index.
