# Development log — 2026-10-30

## Baseline
- Repository: `Stevesjsjsjs871/minecraft-bedrock-plugin`
- Base source snapshot: PR #13 head `9c8980dd70df2af28c0f85e628a228cf83a5248e`
- Current GitHub main: `1.3.0`, commit `45e44ac18ea68c0841d44b480ef43c27dcdd7ff2`
- Current Plugin Creator release observed read-only: `1.4.1`, release ID `pluginrel_6ae482e7caa48191b602dda4abd1b074`

## Findings
- Plugin Creator manifests report `1.4.1`, but its `VERSION`, README title, and latest CHANGELOG heading still report `1.4.0`.
- Both plugin manifests contain 12 identical prompts; the original first three prompts are preserved.
- Both MCP registries contain 16 servers and resolve to present server scripts. Their only observed difference is omitted `env` versus explicit `env: {}` entries; these are semantically equivalent.
- The current Plugin Creator package contains two Python bytecode files and no `BUILD_PROVENANCE.json`.
- Its main MCP server does not register the four Creator Tools bridge tools present in the GitHub PR #13 source snapshot.
- No Plugin Creator mutation was performed.

## Work in this branch
- Strengthened deterministic archive validation so README title and newest CHANGELOG heading must match `VERSION`.
- Normalized omitted MCP `env` to an empty object, then compare all remaining server configuration fields exactly.
- Validate MCP commands, argument arrays, environment maps, and referenced project files.
- Added regression tests for README/CHANGELOG version drift and MCP environment/extra-field drift.
- Updated the build-release skill with the release acceptance contract.

## Verification
- GitHub Actions run #41058783899 passed on executable-source commit `6c32110556ceb8da8afdbcfaf3037cb22b2e5ccf` (Python 3.12.15).
- Server regression suite: 399/399.
- MCP registry contract: 3/3.
- PNG validator: 15/15.
- Texture-link auditor: 20/20.
- Benchmark evaluator: 12/12.
- Mojang indexer: 6/6.
- Procedural texture generator: 12/12.
- Package Integrity tests: 11/11.
- Analyzer regression: 18/18.
- Deterministic archive builder: 15/15.
- Candidate archive built from the CI merge commit: 134 payload files, version 1.3.0, SHA-256 `defcf6ffaf3f0937a5e5c5531e79e3296e5e963a02af91ffa77636a4965bb06b`.
- The candidate archive upload step was skipped in pull-request context; no retained downloadable artifact was produced.
- Local clone/test attempt was blocked by DNS resolution for github.com; CI supplied the successful executable-code verification.
- Minecraft import/runtime and Creator Tools CLI remain NOT RUN.
- After the passing run, only this journal file was updated; executable files and workflow were not changed.

## PR history
- Initial PR #14 CI failed at compile time because a Unicode em dash was placed in a bytes literal in one test assertion.
- Corrected the test to compare UTF-8 encoded text, created replacement PR #15, and closed PR #14 as superseded (not merged).
- PR #15 is the active Draft review target, based on PR #13.

## Risks and next step
- Plugin Creator 1.4.1 remains unchanged; its metadata drift and bytecode files require a separately approved update using the current expected release ID.
- After CI passes, review PR #14 as a dependent change on PR #13. Do not merge automatically.
