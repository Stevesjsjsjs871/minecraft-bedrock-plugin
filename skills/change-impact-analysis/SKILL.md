---
name: change-impact-analysis
description: Use before or after changing an existing Minecraft Bedrock add-on to trace static BP/RP dependencies, identify potentially affected files, expose unresolved references, and select focused regression checks.
---

# Change Impact Analysis

## Purpose and boundary
Use `skills/bedrock-engineer-core/scripts/analyze_change_impact.py` to create a bounded, read-only dependency graph and reverse-impact report for a real project directory. The graph connects consumers to the files/resources they depend on. Starting from changed paths, reverse traversal identifies files that may require inspection or regression testing.

The utility reads project source files without altering them; by default it emits the report to stdout, and it writes a separate report file only when `--output` is explicitly supplied. It is a static analysis aid, not a Minecraft runtime oracle. It does not execute scripts, evaluate Molang, import packs, infer dynamic identifiers, delete resources or automatically approve changes. An affected file is a review candidate, not proof of a defect. Unresolved/ambiguous references must be inspected before treating them as errors.

## When to run

- Before modifying a linked BP/RP resource, to identify likely dependent files and preserve complete feature chains.
- After implementation, using the actual changed paths, to confirm the expected dependency closure and select focused regression checks.
- Before release or baseline comparison, when changes cross entity, geometry, texture, animation, controller, UI, recipe, script or manifest relationships.

For a narrow standalone text-only answer or when no actual project directory and local executor are available, do not pretend the utility ran. Use the registry, inspected source and current Work Order manually, and mark automated analysis `NOT RUN`.

## Command

Run from the plugin package root. Each changed path is relative to the add-on project root. Repeat the flag for multiple changed files:

```bash
python skills/bedrock-engineer-core/scripts/analyze_change_impact.py \
  --project-root /path/to/addon \
  --changed-path resource_packs/my_rp/entity/guardian.entity.json \
  --changed-path behavior_packs/my_bp/entities/guardian.json \
  --changed-path resource_packs/my_rp/textures/entity/old_guardian.png \
  --output change-impact.json
```

The tool prints JSON to stdout. `--output` is optional and writes a separate report artifact; it refuses to overwrite an existing report unless `--overwrite` is supplied. It does not modify existing project source files. Scan budgets can be adjusted with `--max-files`, `--max-file-bytes` and `--max-total-bytes`. A truncated/incomplete scan returns `PARTIAL` and a non-zero exit code. Exit code 0 means the scan completed, not that every finding is clean; exit code 1 means partial coverage; exit code 2 means invalid arguments or an operational input/output error.

## Supported static relationships

- BP entity identifiers to matching RP client-entity identifiers.
- Client-entity geometry, texture, animation, animation-controller and render-controller bindings.
- Geometry, animation, controller and render-controller identifiers.
- Item/block identifiers referenced by recipes and other explicit JSON fields.
- BP/RP manifest dependency UUIDs.
- Explicit UI definition/file paths and relative JavaScript/TypeScript imports.
- Explicit path fields such as textures/images where the referenced file can be resolved inside the pack.

Only exact resolved paths and identifiers become graph edges. The report distinguishes direct changed paths from indirect consumers, includes edge type and confidence, and reports ambiguous or unresolved references. When a removed/renamed path is listed as changed, explicit references that still point to that missing path are connected to it as `CHANGED_DEPENDENCY_MISSING`, so dependent files remain in the impact closure. Include both the old removed path and new added path when analyzing a rename. The scanner skips symlinks and common generated/dependency directories, rejects unsafe changed paths, bounds file/byte budgets and never executes project code.

## Review procedure

1. Inspect the report coverage first. Do not use an incomplete graph as a complete dependency closure.
2. Review direct changes, then indirect affected files ordered by dependency distance.
3. Prioritize high-severity findings, ambiguous declarations and unresolved references, including `CHANGED_DEPENDENCY_MISSING`. Distinguish project-owned identifiers from vanilla `minecraft:` references.
4. Compare the predicted impact with the intended feature chain. Missing expected edges require manual source inspection; static reference extraction cannot discover every runtime-generated or aliased dependency.
5. Build the regression set from affected files and feature behavior, not from file names alone. Examples: entity behavior/client binding, geometry/UV/texture rendering, animation/controller state, recipe crafting, UI imports/bindings, and BP/RP manifest/dependency loading.
6. After changes, rerun with the actual changed paths. Record the report path/hash or exact stdout summary as Work Order evidence. Keep Minecraft import/render/gameplay tests separately marked `RUNTIME TESTED` or `NOT RUN`.
7. Do not remove files because the graph shows no inbound edges. Unreferenced assets remain review candidates only.

## Report contract

The report follows `skills/bedrock-engineer-core/references/change-impact.schema.json`; `change-impact.example.json` is a synthetic fixture, not evidence about a user's add-on. Edges are directed `consumer -> dependency`; reverse impact traversal starts at changed dependency files. Preserve the report with the task evidence where useful, but do not treat it as a durable project-state mutation unless an actual writable state record is separately updated.
