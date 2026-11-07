# Release readiness — Minecraft Bedrock Engineer 2.1.0 candidate

**Baseline:** Plugin Creator 2.0.9, USER / PRIVATE, release `pluginrel_6aeef187613c819193b9fd1d4ef333e2`.
**Candidate scope:** strict Skills-only cleanup, documentation/version-history repair, script-registry refresh.

| Required criterion | Result | Evidence / limitation |
|---|---|---|
| Remove unused MCP/server legacy | PASS (package tree) | All 34 `server/` source/test files removed; two server-specific analyzer files retired. No code was executed. |
| Strict Skills-only Gate | PASS | 20/20 package checks, including no legacy server tree and no MCP config/protocol adapter. |
| Verify 65 Skills | PARTIAL PASS | 65/65 discovered and 65/65 instruction files loaded in this current ChatGPT skill runtime. Automatic selection through the installed Plugin Creator UI on representative user prompts remains NOT TESTED. |
| Verify all 14 domains on real tasks | PARTIAL | Registry/architecture validated 28/28; 8 workflow profiles listed. Script-backed domains have local tests. A complete per-domain real-add-on task campaign remains NOT RUN. |
| Cross-Skill interaction | PARTIAL | Domain planner, Work Order/Domain Result contracts, integrator and architecture tests pass; real host hand-off between Skills remains NOT TESTED. |
| Several real Bedrock add-ons | BLOCKED | No real third-party `.mcaddon` / `.mcpack` archives were supplied. The uploaded `plugin (4).zip` is the MBE plugin package, not an add-on. |
| BP/RP create/change/validate/package | PARTIAL | Local utilities and synthetic fixtures test manifest/versioning, archive audit, resource graph, geometry/UV and textures. No real add-on package was imported into Minecraft or Creator Tools. |
| Documentation and version history | PASS | VERSION, both manifests, README, CHANGELOG and VERSION_HISTORY synchronized to 2.1.0; 2.0.8 and 2.0.9 history entries added. |

## Local verification results

- Skills tests: 27/27 files, 500/500 cases PASS.
- Active Python entry-point help smoke: 27/27 PASS.
- Architecture: 28/28 PASS; 14 domains, 65 Skills, 8 workflow profiles.
- Strict Skills-only package checker: 20/20 PASS.
- Skill instruction loading in current ChatGPT runtime: 65/65 PASS.
- Plugin-host script execution: NOT TESTED.
- Real third-party add-on archives: NOT RUN.
- Minecraft import/render/gameplay/Content Log: NOT RUN.

## Release decision

This is a technically validated **private 2.1.0 candidate**, not a fully certified professional release. Do not describe the host integration or Minecraft runtime as complete. Final acceptance still requires real `.mcaddon` / `.mcpack` archives, controlled per-Skill prompt activation in the installed Plugin Creator surface, and actual Minecraft import/render/gameplay checks.
