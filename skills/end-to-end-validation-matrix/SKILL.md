---
name: end-to-end-validation-matrix
description: Use after Bedrock content changes to select and report artifact, manifest, resource-graph, regression, benchmark and runtime validation coverage.
---

# End-to-end validation matrix

Choose layers based on the files changed. No static report guarantees Minecraft will load or execute the add-on.

## Validation layers
1. **Artifact safety:** archive readability/CRC, duplicate or unsafe paths, bounded sizes, SHA-256 and expected inventory.
2. **Package structure:** JSON parse, BP/RP manifests, UUID uniqueness, dependency links, target version and folder layout.
3. **Resource contract:** identifiers, icon/terrain atlases, localization, recipes, entity/client-entity pairing and file references.
4. **Visual contract:** geometry IDs/bones, UVs, textures/materials/render controllers, animation aliases/controllers/transitions, UI imports and literal localization references.
5. **Execution contract:** only actual host file/code capabilities or an explicitly authorized local CLI. Skills do not expose tool registries or hidden dispatch APIs. For a text-only skill change, check package structure and skill discoverability; for code changes, run the relevant local script/unit tests.
6. **Regression contract:** compare baseline and candidate with the same analyzer version/configuration; review file hashes, findings, severities and resource-graph deltas.
7. **Creator Tools:** optional and only when an actual connected capability or authorized installed CLI is available. Record exact version/command and re-audit all files it changed.
8. **Benchmark:** use independently reviewed cases with exact artifact hashes. Report precision/recall/F1, case count and severity mismatches. Synthetic fixtures are not real-pack evidence.
9. **Runtime:** import the exact candidate into the target game version; inspect pack loading, visuals and requested behavior. Record exact build and scenario. Multiplayer behavior requires relevant multiplayer tests.
10. **Release artifact:** package from a staged copy, reopen and validate the exact final archive, calculate SHA-256 and preserve a report referencing that hash.

## Coverage and decision
Run package safety/manifest checks plus every layer affected by the change. Required skips prevent an overall pass. Use `PASS`, `FAIL`, `BLOCKED`, `PARTIAL`, `NOT RUN`, `SKIPPED` or `INCONCLUSIVE` with named inputs and evidence.
- `HOLD`: reproducible serious defect, invalid archive, unsafe write, broken critical dependency or failed mandatory test.
- `REVIEW`: unresolved heuristic edges, blocked layers, unexplained changes or missing runtime evidence for runtime-sensitive behavior.
- `READY FOR USER TEST`: required static checks actually passed and remaining runtime limitations are explicit.

## Report
Candidate/hash/target version; layer status/evidence; changed and removed resources; baseline deltas; tool versions; benchmark metrics only if actually scored; runtime context; recommendation and remaining gates.
