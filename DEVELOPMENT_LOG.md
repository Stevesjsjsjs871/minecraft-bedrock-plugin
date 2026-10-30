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
- Pending GitHub Actions for this branch.
- Minecraft import/runtime and Creator Tools CLI are not part of these static release-gate tests.

## Risks and next step
- Plugin Creator 1.4.1 remains unchanged; its metadata drift and bytecode files require a separately approved update using the current expected release ID.
- After CI passes, review PR #14 as a dependent change on PR #13. Do not merge automatically.
