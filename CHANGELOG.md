# Changelog

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
