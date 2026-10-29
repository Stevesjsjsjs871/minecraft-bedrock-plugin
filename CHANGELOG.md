# Changelog

## 1.0.10 — Dedicated procedural texture MCP tool
- Adds an independent stdio MCP server, `server/texture_generator_mcp.py`, exposing `generate_texture` while leaving the original server and dispatch untouched.
- Generates bounded RGBA PNGs inside an existing project's RP `textures/` directory; validates canonical paths and dimensions, rejects symlinks and existing destinations, and returns structured metadata plus SHA-256.
- Adds an integration/JSON-RPC regression suite for schema closure, project/path safety, no-overwrite, defaults, output metadata and error handling.
- The tool uses deterministic procedural styles, not AI image synthesis or UV-aware painting. Minecraft import/render tests remain `NOT RUN`.


## 1.0.9 — Procedural texture reliability and pattern expansion
- Expands the standalone PNG generator to ten deterministic patterns, including gradients, brick/mortar, stone variation, connected ore-like veins and wood grain.
- Rejects malformed RGB hex, boolean dimensions/seeds/alpha, symlink destinations, and unsafe forced destinations; preserves atomic default no-overwrite behavior.
- Adds tests for all patterns, repeatability, gradients, transparency, symlink safety, CLI structured output and PNG CRC integrity.
- Does not claim MCP registration, UV-aware texture painting, AI image synthesis or Minecraft runtime verification.

## 1.0.6
- Adds an offline package-integrity checker and nine synthetic regression tests for manifest/version consistency, default prompts, MCP configuration, skill metadata, registry/dispatch parity, schema closure, writer annotations, sample-index path integrity and conservative README heading repair.
- Adapts the integrity audit to the GitHub source checkout: the generated full gzip index is optional when curated sample fallback files exist, and the checker reports that state as WARN rather than claiming full-index verification.
- Adds release-readiness, validation-runbook, MCP contract/registry, resource-integrity, dependency-closure, baseline-regression and end-to-end validation skills.
- Preserves the existing 0.9.3 MCP implementation and optional staged Minecraft Creator Tools CLI workflow. Full runtime tests are not claimed.

## 0.9.3
- Adds optional MCT CLI discovery and gallery-template listing tools. These never install packages or invoke npx.
- Adds MCT validation against a bounded temporary project copy with report output outside the source project.
- Adds entity-template handoff using an explicit MCT gallery template ID. Generation runs in staging; existing-file modifications/deletions are rejected; the baseline/candidate packs are statically diffed before merge.
- Only newly added pack files can be merged, and only when the diff introduces no HIGH/BLOCKER finding or escalation. Collisions, unsafe paths, symlinks, oversized project trees and partial-write failures are guarded.
- The integration may cause the installed MCT CLI to access its own gallery/cache. Official documentation says --offline does not guarantee every CLI action is network-free.
- Unit tests mock MCT; real CLI availability, MCT gallery operation, and Minecraft runtime tests remain NOT RUN.

## 0.9.2
- Adds `create_addon_entity` to generate a coordinated four-file custom entity slice: BP entity, RP client entity, geometry and render controller.
- Confirms linked BP/RP manifests, exact target version, canonical resource paths and matching identifiers before writing.
- Refuses collisions, symlink escapes and invalid supplied PNGs; rolls back newly created entity files if a write fails.
- Does not fabricate texture assets; missing textures are reported as such. Animations, spawn rules and in-game behavior are outside this starter slice.
- Adds cross-reference, texture, collision, rollback-safety and tool-schema regression tests.
- Minecraft runtime tests remain `NOT RUN`.

## 0.9.1
- Adds a curated, hash-verified Mojang sample search fallback when the generated compressed full index is absent from a source checkout.
- Makes fallback coverage explicit with index_mode=curated_fallback and full_index_available=false; it does not imply the full 22,252-entry index is present.
- Searches terms extracted from the packaged curated text examples; user-provided archive reads remain path-confined and bounded.
- Adds regression coverage for fallback behavior and result caps.
- Synchronizes VERSION, root and compatibility manifests, README and CI version assertion to 0.9.1.
- Minecraft runtime tests remain NOT RUN.

## 0.9.0
- Synced the GitHub `main` source tree to Minecraft Bedrock Engineer 0.9.0: package manifests, compatibility manifest, MCP server, skills, tests, CI and version marker are aligned at `0.9.0`.
- Added the write-capable `create_addon_recipe` tool for shaped and shapeless crafting-table recipes, including pattern/key-map validation, ingredient/result identifier checks, output counts, collision protection, and BP/RP scaffold checks.
- Added recipe-authoring skill guidance and regression coverage. Development notes report 22 targeted recipe-authoring tests and 6 Mojang Samples index tests passing; those counts have not been independently rerun in this update.
- Full MCP regression suite and GitHub Actions status were not independently verified during this update. Minecraft runtime crafting was not tested in-game.
- This changelog records source version 0.9.0; it does not by itself confirm a GitHub Release or `v0.9.0` tag.

## 0.8.0
- Synchronized the repository to the Minecraft Bedrock Engineer 0.8.0 Plugin Creator source.
- Added the eighth read-only MCP tool, `diff_packs`, for file changes, finding deltas, severity changes, and resource-graph regressions between two archives.
- Added bounded diff samples, archive hashes, analyzer-version details, conservative recommendations, and explicit `runtime_status: NOT RUN`.
- Updated CI to test the current `server/` layout, benchmark evaluator, regression suite, and version consistency. Removed the stale 0.6.7 `mcp-server/` implementation to avoid conflicting source trees.
- Local verification before synchronization: MCP unit tests 21/21, benchmark tests 12/12, regression scenarios 18/18. Minecraft runtime tests were not run.

## 0.7.9
- Hardened benchmark evaluation against symlink escapes, malformed UTF-8, and duplicate expected finding labels.
- Added tests for invalid input and benchmark-label integrity; no real-pack precision/recall figures are claimed.

## 0.7.8
- Added benchmark manifest/schema and evaluation for precision, recall, F1, and severity mismatch, plus safe Creator Tools handoff instructions.
- Did not add an automatic MCT subprocess wrapper or file-writing tools.

## 0.7.7
- Added conservative loot-table structure checks, nested loot-table graph edges, and iterative cycle detection.

## 0.7.6
- Added conservative Behavior Pack component-to-loot-table reference checks.

## 0.6.7
- Synchronized package manifests and MCP server version.
- Added a 50,000-entry archive cap in addition to compressed and declared uncompressed size limits.
- Corrected archive entry-count reporting so directory entries do not distort regular-file listing truncation.
- Added tests for manifest/server version and prompt parity, compact initialization instructions, structured tool errors, and archive member-count limits.
- Published the seven-tool read-only stdio MCP implementation and clarified that no remote ChatGPT endpoint is deployed.

## 0.6.5
- Added the read-only local stdio MCP adapter with strict argument schemas, structured results/errors, path confinement and safety annotations.

## 0.6.4
- Added regression-evals skill and a standard-library regression harness.
- Added synthetic positive and negative analyzer scenarios.

## 0.6.3
- Expanded resource-reference indexing and graph coverage metadata.

## 0.6.2
- Added initial cross-resource reference graph support.

## 0.5.0
- Added geometry, UV, texture and animation static checks.
