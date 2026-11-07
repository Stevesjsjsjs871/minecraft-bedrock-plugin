---
name: end-to-end-validation-matrix
description: Use after Bedrock content changes to select and report artifact, manifest, resource-graph, regression, benchmark and runtime validation coverage.
---

# End-to-end validation matrix

Choose layers based on the files changed. No static report guarantees Minecraft will load or execute the add-on.

## Validation layers
0. **Pre-runtime contract consistency:** for cross-system features, reconcile producer/consumer identifiers and value shapes, manifest/module dependencies, lifecycle and state transitions, event registration, failure handling, cleanup and the complete trigger-to-effect chain. Keep explicit/deterministic mismatches separate from inferred, dynamic or external edges.
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
Run package safety/manifest checks plus every layer affected by the change. A cross-system feature cannot receive a complete static review from isolated per-file checks alone: include the pre-runtime contract-consistency layer and report its edge coverage and unresolved dynamic/external edges. Required skips prevent an overall pass. Use `PASS`, `FAIL`, `BLOCKED`, `PARTIAL`, `NOT RUN`, `SKIPPED` or `INCONCLUSIVE` with named inputs and evidence.
- `HOLD`: reproducible serious defect, invalid archive, unsafe write, broken critical dependency or failed mandatory test.
- `REVIEW`: unresolved heuristic edges, blocked layers, unexplained changes or missing runtime evidence for runtime-sensitive behavior.
- `READY FOR USER TEST`: required static checks actually passed and remaining runtime limitations are explicit.

## Report
Candidate/hash/target version; layer status/evidence; changed and removed resources; baseline deltas; tool versions; benchmark metrics only if actually scored; runtime context; recommendation and remaining gates.

## Process orchestration and test ordering 2.1.9

Use `workflow-execution-engine` to order the matrix by dependency and risk. Execute in this order unless a concrete dependency requires otherwise:
1. artifact safety and source identity;
2. package/manifest/JSON structure;
3. changed-feature contract and focused tests;
4. cross-domain graph and reverse-dependency checks;
5. baseline regression and preservation review;
6. exact final archive integrity and hash;
7. runtime scenarios when the game/host is available.

Run independent static checks in parallel only when the real executor supports it. A failure blocks only its dependent stages; unrelated checks may continue. After fixes, rerun focused checks plus impacted reverse dependents, then all mandatory release-tier checks. Do not rerun unaffected checks unless their input, analyzer version, schema or rule set changed. Record why a check was reused or invalidated. The final decision is based on the exact candidate hash, not a temporary pre-fix report.
