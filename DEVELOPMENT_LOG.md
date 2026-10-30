# Development Log

## 2026-10-30 — Entity and animation authoring compatibility integration

### Baseline
- GitHub `main`: `0824c951fe780d21d5fa90b2c5749f411593affc`, package version 1.0.14.
- Current Plugin Creator source was re-read at release `pluginrel_6ae44256591c8191bc421cdca48403be`, version 1.1.1. No Plugin Creator mutation was performed.
- Plugin Creator 1.1.1 has five stdio servers and includes dedicated entity/animation authoring modules, but its core server exposes 14 tools and no longer includes the four Creator Tools bridge tools present in GitHub `main`.
- GitHub `main` retains 19 core tools, including `create_addon_entity` and the Creator Tools bridge. Replacing the core server with the Plugin Creator copy would remove existing functionality and break the existing entity tool contract.
- Plugin Creator 1.1.1 includes the stable 1.26.50.4 compressed index; GitHub `main` still does not. The binary index remains in the separate PR #2 stack and could not be transferred through the available text-file interface in this stage.
- The current PR #5 texture-audit completeness fix remains separate and unmerged.

### Decision
Integrate the new authoring servers into a separate GitHub branch without replacing the existing core MCP server:
1. Preserve the legacy `create_addon_entity` tool and all Creator Tools bridge tools.
2. Rename the new geometry-first tool to `create_addon_entity_with_geometry` to avoid a duplicate MCP tool name and a breaking schema collision.
3. Register the dedicated entity and animation-controller stdio servers in both MCP configuration files.
4. Add a registry contract test covering server registration, unique tool names, MCT bridge preservation and the three original default prompts.
5. Extend animation-controller input to accept ordered transition arrays (preferred) and the legacy object-map shorthand. The generated Bedrock JSON always uses an ordered array.

### Format evidence
- Microsoft Learn's stable "Creating New Entity Types" guide documents the coordinated BP entity, RP client entity, geometry, texture and render-controller resources, including format versions and file naming: https://learn.microsoft.com/en-us/minecraft/creator/documents/introductiontoaddentity?view=minecraft-bedrock-stable
- Microsoft Learn's stable Animation Controllers Reference documents ordered transition arrays and states that transitions are evaluated in order, with at most one transition processed per frame: https://learn.microsoft.com/en-us/minecraft/creator/documents/animations/animationcontroller?view=minecraft-bedrock-stable
- The entity tool supports classic box UV only. Per-face UV, poly meshes and Blockbench project files remain unsupported. It does not create a texture PNG or animation clips.
- Molang strings receive bounded text validation only; no parser/interpreter or Minecraft runtime test is claimed.

### Files and changes
- Added dedicated entity and animation-controller server modules, tests, skills and reference examples.
- Added `server/tests/test_mcp_registry.py`.
- Updated `mcp.json`, `.mcp.json`, README and CHANGELOG.
- Kept package version 1.0.14 and all three original prompts unchanged on this unmerged branch. No Plugin Creator release was created or updated.

### Verification
- Pending GitHub Actions on the completed branch.
- Minecraft import, entity spawning, texture UV alignment, controller transitions, Molang execution and Creator Tools CLI remain NOT RUN.

### Next step
- Inspect CI and PR review results, then reconcile the remaining stable sample-index binary and PR #2–#5 dependency stack without merging any PR automatically.
