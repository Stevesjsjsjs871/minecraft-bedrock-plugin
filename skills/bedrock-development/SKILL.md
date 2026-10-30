---
name: bedrock-development
description: Use as the general version-aware engineering workflow for Minecraft Bedrock Behavior Packs, Resource Packs, Script API, manifests and cross-pack resources.
---

# Bedrock development

## Source-of-truth rules
Use the exact target version stated by the project. If none is stated, use 1.26.50 as the working baseline and clearly label it as a default. Prefer official Microsoft Creator documentation and Mojang Samples at a matching release/commit. Bundled samples under `references/mojang-samples-1.26.50.4/` are a curated, version-labelled corpus, not a guarantee that every current feature matches that release.

Do not assume a Mojang Samples search/read tool exists. Inspect the local index and sample files directly when mounted; otherwise use official web research through a real web capability. Cite exact source URLs and sample paths in the result.

## Project discovery
Inspect BP/RP roots, manifests, UUIDs, dependency links, format versions, namespaces, identifiers and existing resource references. For existing projects, preserve mechanics and assets. Establish a baseline before editing.

## BP domains
For blocks/items/entities/recipes/loot/spawn/scripts, verify component and format support against target-version docs/schemas. Use JS ESM for `@minecraft/server` where appropriate and verify the manifest module dependency/API version. Check identifiers, events, component groups, recipes and cross-resource references.

## RP domains
Inspect client entities, geometry, textures, materials, render controllers, animations, animation controllers, UI, localization and atlas mappings. Follow references rather than guessing filenames. UI audits should inventory the complete relevant `ui/` folder and include/namespace relationships.

## Implementation and validation
Use only a real file/code capability. Keep writes project-confined, avoid symlink/traversal escapes, preserve unrelated files and do not overwrite without authorization. Parse JSON, check UUIDs, identifiers, references, texture dimensions, geometry/UVs and animation graph edges. Run bundled scripts only when actually accessible and document their inputs/commands/results.

## Evidence
Separate `CONFIRMED_IN_SOURCE`, `UNVERIFIED`, `PASS`, `FAIL`, `BLOCKED` and `NOT RUN`. Static checks do not prove Minecraft import, rendering, gameplay, multiplayer, Blockbench interoperability or Script API runtime behavior.
