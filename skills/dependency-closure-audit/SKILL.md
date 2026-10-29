---
name: dependency-closure-audit
description: Use when validating a Bedrock add-on's complete resource dependency chain, especially across BP/RP manifests, entity render chains, textures, animations, UI imports and localization.
---

# Dependency Closure Audit

## Goal
Build an explainable view of whether all required resource references in an add-on resolve within the supplied pack set or are explicitly external/dynamic. Static closure is not proof of runtime correctness.

## Inputs and identity
- Record candidate path, SHA-256, target version and BP/RP roots.
- If auditing two packs, record each pack's own manifest, UUID and version.
- Do not unpack and execute submitted scripts. Reject unsafe paths and duplicate archive entries before payload analysis.

## Analyze in passes
1. **Manifest graph:** parse manifests; compare UUID/module identities; resolve BP dependencies against RP header UUIDs and note version mismatches.
2. **Definition index:** index namespaced item, block, entity, client-entity, geometry, animation, animation-controller, render-controller, material, loot-table, feature-rule and other supported definitions. Identify duplicates using exact namespaces and paths.
3. **File-reference edges:** discover texture paths, geometry aliases, animations, controller mappings, UI imports, localization references, recipe identifiers and loot-table paths. Attach the source file and JSON Pointer whenever possible.
4. **Normalize conservatively:** compare exact canonical pack-relative paths first. Generate alternative path candidates only when the relevant format convention is documented. Do not normalize namespace/case or aliases in ways that can hide a mismatch.
5. **Resolve states:** use `resolved`, `missing`, `ambiguous`, `external`, `dynamic`, and `not_indexed`. A missing path is a confirmed defect only when the reference format and search scope are sufficiently understood.
6. **Transitive closure:** follow resolved edges to compute reachable resource sets and unreachable definitions. Treat potentially intentional unused resources separately from missing resources and don't propose deletion automatically.
7. **Domain coverage:** show the count of resources/edges analyzed for each domain and the limitations of partial UI, localization, render-controller or component indexing.
8. **Change analysis:** compare against an optional baseline graph and classify new missing edges, changed targets, removed definitions and formerly resolved edges that are no longer found.
9. **Evidence and severity:** each finding includes source path/pointer, raw reference, candidate targets, resolution status, confidence and why the issue matters. Keep heuristics at lower severity.
10. **Follow-up checks:** run focused analyzer checks and the available Creator Tools validator when actually connected. Recompute closure after changes.

## Report format
- Candidate SHA-256, version and pack inventory.
- BP/RP manifest/dependency result.
- Per-domain definitions, edges and coverage.
- Missing/ambiguous/external/dynamic counts.
- Unreachable definitions with a warning that unused does not mean disposable.
- Baseline deltas and material findings.
- Exact tests/tool calls actually run and runtime status.

## Safety
No deletion follows automatically from an unused or unresolved resource. Never overwrite assets as a side effect of graph analysis. Preserve namespaced identifiers, localization overrides, external references and files not covered by the indexer.
