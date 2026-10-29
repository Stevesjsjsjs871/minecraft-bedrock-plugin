---
name: v100-release-engineering
description: Use for the Minecraft Bedrock Engineer 1.0.0 milestone, major-version readiness, preserving existing functionality, narrowing release scope and separating completed code from planned features.
---

# 1.0.0 Release Engineering

## Purpose
Treat 1.0.0 as a major stability and usability milestone. Do not declare the release complete simply because a version number or changelog was changed. The package must preserve its existing tool contracts, safety boundaries, sample references and workflows.

## Compatibility invariants
- Keep the existing plugin identity, scope, MCP configuration and all three default prompts unchanged.
- Keep existing project/item/block/recipe writer behavior additive and collision-safe.
- Preserve read-only annotation and non-destructive semantics for audit/reference tools.
- Keep the exact target-game version explicit; default remains 1.26.50 unless the user requests another.
- Treat the bundled Mojang Samples labelled 1.26.50.4 as reference corpus with provenance, not a universal runtime compatibility guarantee.
- Keep all new authoring/CLI capabilities conditional on real available tools. Do not invent an endpoint, CLI, tool call or runtime test.

## Implementation-first priorities
1. Inspect real server code and tests before changing any public tool or handler.
2. Repair existing behavior before expanding API surface. Prefer backward-compatible fixes and tested helper functions.
3. Add capabilities only where a real implementation and safe host execution route exist. Instructions alone must not be reported as executable features.
4. For file writes, keep paths confined to the selected workspace, reject traversal and symlink escapes, refuse collisions, preserve unrelated shared resources, and report partial failures truthfully.
5. For Creator Tools coordination, verify actual connected tools or installed CLI and its help first; never auto-install, accept EULA, deploy or overwrite without consent.
6. After each functional change, test both success and adversarial cases using temporary workspaces. Do not point path-safety tests at the user's real project.
7. Keep `README.md`, skills, changelog, manifests and tests consistent with the implementation and current version.

## Minimum 1.0.0 release gate
- [x] Parse root and compatibility manifests and verify strict SemVer/name/version consistency with `VERSION`.
- [x] Verify default prompts are preserved between both manifests.
- [ ] Verify MCP connection is preserved by the actual host after update.
- [ ] Compile analyzer, server and all tests.
- [ ] Run the complete MCP unit suite, benchmark evaluator tests and analyzer regression harness.
- [ ] Run report/benchmark schemas and resource index integrity tests.
- [ ] Check all registered MCP tools against schemas, handlers and safety annotations.
- [ ] Test writer collisions, malformed inputs, path traversal, symlinks and preservation of unrelated files.
- [ ] Test archive safety limits, malformed archives and read-only byte preservation.
- [ ] Compare generated candidate output against a known baseline and classify unexpected changes.
- [x] Verify the submitted package archive layout, JSON parseability, versions, default-prompt parity and skill frontmatter.
- [ ] Verify the installed plugin's complete source inventory after update.
- [ ] Clearly mark Minecraft import, rendering, behavior and multiplayer checks `NOT RUN` unless actually performed.

### Execution record for this package update
The candidate ZIP was checked locally using Python: both manifests parsed, package and compatibility versions were `1.0.0`, `VERSION` matched, all three original default prompts and their order matched, and all three new skill files contained valid basic frontmatter. This does **not** constitute execution of the Python source/test suite because the full plugin source was not materialized into this local workspace. Full MCP/analyzer/benchmark/sample-index tests and game-runtime tests remain `NOT RUN`.

### Historical record note and 1.0.5 follow-up
The execution record above is specific to the original 1.0.0 overlay candidate, not to the currently stored release. The stored patch sequence is recorded in the root `CHANGELOG.md` and release metadata. In 1.0.5, a new offline package-integrity checker adds executable checks for manifest/version parity, default prompts, MCP configuration references, skill inventory, statically registered MCP tools versus dispatch names, writer annotations, and the bundled sample-index metadata/content relationship. Its eight synthetic regression tests are intended as a focused test of the checker itself; they do not substitute for the complete plugin's MCP, analyzer, benchmark, indexer, or game-runtime suites.

## Release status vocabulary
Use `PASS`, `FAIL`, `BLOCKED`, `PARTIAL`, `NOT RUN`, or `INCONCLUSIVE` for each gate. A package version is not evidence that gates passed. If any required gate cannot be executed, call the release candidate partially verified and list the missing execution layer.
