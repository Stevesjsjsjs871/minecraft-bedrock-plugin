---
name: resource-reference-graph
description: Use when auditing cross-file identifiers and references across Minecraft Bedrock resource packs, including client entities, geometry, textures, render controllers, animations, attachables, UI and related resources.
---

# Bedrock Resource Reference Graph

## Goal
Audit the relationships between files and identifiers, not just each JSON file's syntax. The target is Bedrock 1.26.50 by default; confirm any version-sensitive convention with the matching official docs/sample.

## Build a source-backed inventory
1. Inventory actual pack roots and manifests; separate behavior packs from resource packs and external dependencies.
2. Parse JSON files without extracting untrusted archive paths. Preserve original file spelling and case.
3. Index definitions and uses for at least the resource types present in the project: entity identifiers, geometry identifiers, texture aliases/paths, material aliases, render-controller identifiers, animation identifiers, animation-controller identifiers/states, attachable references, recipe/loot/feature identifiers, localization keys, and UI resource paths when applicable.
4. Record each edge as `{source_file, source_pointer_or_context, reference_kind, referenced_name_or_path, target_file, status, confidence}`. Keep `resolved`, `unresolved`, `ambiguous`, `external_dependency`, and `heuristic` distinct.
5. Do not treat every string as a reference. Parse known fields and patterns, and clearly label text-search heuristics.

## Validation
- File-path edges: check exact case and path existence; report normalization-only matches separately.
- Identifier edges: resolve only against indexed definitions for the correct resource type and namespace. Identical strings in different identifier domains are not automatically duplicates.
- Parent/child graphs: detect cycles only where the relation is explicitly a hierarchy, such as bone parents or controller state references where appropriate.
- Pack dependencies: compare UUID/version pairs to manifests and distinguish missing in-archive packs from intentional external packs.
- UI: map paths/names referenced by supported UI definitions to files in the complete UI folder; avoid assuming undocumented engine lookup rules. Verify exact target-version conventions.
- Regression: compare the graph before and after the patch. Surface newly unresolved references, removed targets still referenced, and unreferenced additions for review. Unreferenced files are not automatically safe to delete.

## Evidence and disposition
Each finding includes severity, confidence, file path and pointer, the expected target and actual search results, likely impact, and proposed action. Use `INFO` for uncertain heuristics, `MEDIUM` for probable issues, and `HIGH`/`BLOCKER` only with strong evidence of functional impact. Never auto-delete recipes, models, textures, animations or UI resources.

## Tests
Run JSON/archive checks and any suitable language-level checks. Runtime scenarios must cover resource-pack ordering, dependency activation, entity spawn/reload, missing-texture/geometry symptoms, relevant UI screens, animation triggers and interruption. Mark tests `NOT RUN` unless genuinely executed in Minecraft.

## Deliverables
Provide the indexed resource graph or a human-readable summary, unresolved/ambiguous edges, baseline delta, source links for version-specific assumptions, and runtime checks still required. Preserve the existing project and return an editable artifact when the tools permit.
