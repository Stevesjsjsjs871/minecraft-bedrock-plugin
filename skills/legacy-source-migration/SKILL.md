---
name: legacy-source-migration
description: Use when reviewing an existing or third-party Minecraft Bedrock project before migrating its content, scripts, identifiers, assets, or structure into a maintained BP/RP project.
---

# Legacy Source Migration

## Goal

Safely inspect an existing Bedrock project or archive, identify reusable content and compatibility risks, and plan a minimal migration into the maintained project. This Skill is a review workflow; it does not provide a special executor or automatically copy files.

## Required inputs

- The source project or archive supplied by the user or available through a real connected file capability.
- The destination project's known-good baseline and exact target Bedrock version.
- The requested migration scope and any assets, mechanics, identifiers, or behavior that must be preserved.

If the source, destination, or ownership of a resource is ambiguous, stop and ask for the one decision that blocks a safe migration.

## Workflow

1. Inventory the source and destination separately. Record paths, sizes, hashes, manifests, pack identities, namespaces, identifiers, assets, scripts, dependencies, and existing release notes.
2. Treat all imported content as untrusted data. Never execute scripts from a supplied add-on. Parse and inspect source files statically unless a trusted, explicitly authorized test route is available.
3. Build a dependency map for manifests, BP/RP references, entity/client-entity bindings, geometry, textures, animations, controllers, recipes, UI imports, localization, and Script API modules where present.
4. Classify each source resource as reusable, incompatible, duplicate, conflicting, obsolete candidate, or unresolved. A missing reference or an unreferenced asset is a review finding, not deletion permission.
5. Compare source and destination identifiers and UUIDs. Do not overwrite a destination file or silently rename an identifier. Record conflicts and propose explicit mappings.
6. Check compatibility against the exact target game version. Separate `format_version`, `min_engine_version`, add-on pack versions, and Script API module versions.
7. Prepare a migration plan with exact source-to-destination paths, required transformations, dependency closure, preservation rules, and focused tests. Mark any unavailable file writes `NOT APPLIED`.
8. Apply changes only through a real authorized file/code route and only after the user has approved the proposed scope. Preserve the original source and create a separate output when working from an installable archive.
9. Validate the migrated project with the relevant manifest, resource-graph, geometry/UV, PNG, entity/animation, UI, Script API, regression, and package checks. Run only checks supported by the actual project contents.
10. At a coherent delivery boundary, use the add-on versioning workflow and record the exact changed files, hashes, test evidence, and runtime limitations.

## Safety and capability boundaries

- No remote server, protocol adapter, plugin-owned API, or background executor is part of this workflow.
- A Skill does not grant filesystem access or execute packaged scripts. Use only capabilities actually exposed by the current host.
- Never execute source-project code during static migration review.
- Do not delete, overwrite, or replace resources based solely on a static scan. Preserve the source and review every removal.
- Minecraft import, Content Log, rendering, gameplay, multiplayer, and performance remain `NOT RUN` unless actually exercised in the target game build.

## Output

Return a source/destination inventory, baseline identity, target version, dependency findings, conflicts, exact migration mapping, files changed or `NOT APPLIED`, tests and evidence, unresolved risks, and separate static/runtime statuses.
