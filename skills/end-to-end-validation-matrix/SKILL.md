---
name: end-to-end-validation-matrix
description: Use after implementing or generating Minecraft Bedrock content to choose and report validation coverage across files, pack structure, reference graph, Creator Tools and game runtime.
---

# End-to-End Validation Matrix

## Objective
Select test layers based on what changed, run the feasible ones in a clear order, and report omissions without hiding them. No single green static report can guarantee that Minecraft will load and execute the add-on.

## Validation layers
1. **Artifact safety** — archive readability/CRC, duplicate or unsafe paths, file bounds, SHA-256 and expected archive inventory.
2. **Package structure** — JSON parse, BP/RP manifests, header/module UUIDs, dependency links, target version and expected folder layout.
3. **Resource contract** — custom identifiers, icon/terrain atlases, localization keys, recipe ingredients/results, entity/client-entity pairing and all relevant file references.
4. **Visual contract** — geometry IDs and bone hierarchy, textures/materials/render controllers, animation names and controller transitions, UI imports and literal localization references. Mark incomplete/heuristic domains explicitly.
5. **Tool contract** — actual MCP registry, closed argument schemas, safety annotations, representative dispatch success/errors and file-write collision/path tests.
6. **Regression contract** — audit baseline and candidate with the same analyzer version; compare file hashes, findings, severities and reference graph. Investigate new severe findings and unexplained removals.
7. **Creator Tools contract** — only when actual MCT tools/CLI are available and their version/options verified. Record command/output and re-audit any tool-written files.
8. **Benchmark contract** — only independently reviewed cases with verified artifact hashes. Report per-rule and aggregate precision/recall/F1, number of reviewed cases and severity mismatches separately. Never infer benchmark performance from fixtures.
9. **Runtime contract** — import the exact output into the target game version, inspect pack loading, visuals and requested behavior. For multiplayer mechanics, test relevant multiplayer conditions. Record exact game build and scenario.
10. **Release artifact** — package from a staged copy, reopen and validate the exact final archive, calculate its SHA-256 and preserve a report referencing that hash.

## Coverage selection
Run at least the layers affected by the change and the package safety/manifest layers. For a text-only skill change, inspect manifest/schema/package and skill discoverability; don't claim the game runtime is relevant unless content is changed. For writer/MCP code changes, require tool schema tests and collision/path tests. For generated content, require resource contract and baseline checks. For visual or behavior changes, runtime testing remains necessary to confirm engine behavior.

## Result states
`PASSED`, `FAILED`, `BLOCKED`, `PARTIAL`, `NOT RUN`, `SKIPPED`, or `INCONCLUSIVE`. Attach each state to a named layer, inputs and exact evidence. Required skips prevent an overall pass.

## Decision
- `HOLD`: a reproducible serious defect, invalid archive, unsafe write, broken critical dependency or failed mandatory test.
- `REVIEW`: unresolved/heuristic resource edges, blocked layers, unexplained changes or missing runtime evidence for runtime-sensitive behavior.
- `READY FOR USER TEST`: required static/tool gates actually passed; unresolved limitations are listed for user/game testing.
- Avoid `release-ready` if required engine/runtime checks haven't run.

## Report template
Candidate/hash/target version; layer table with status and evidence; changed/removed resources; baseline deltas; tool versions; benchmark metrics only if executed; runtime context; recommendation and remaining gates.
