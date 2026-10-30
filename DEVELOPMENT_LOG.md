# Development Log

## 2026-10-30 — MCP authoring contract compatibility follow-up

### Baseline
- Base PR #6 branch: `feature/1.1.1-animation-controller-authoring`, head `fe233407afb9515d23bc4a987ae228c1cf2c5413`.
- Plugin Creator current release was re-read: version 1.1.1, Release ID `pluginrel_6ae44256591c8191bc421cdca48403be`. No Plugin Creator write or release operation was performed.
- PR #6 adds entity and animation-controller MCP servers, but its new entity server exposes the same `create_addon_entity` tool name as the existing core server, with a different input schema.
- PR #6's animation authoring accepts a transition object map only. The generated Bedrock JSON is an ordered transition array, but the tool contract does not let callers express priority explicitly using the engine's array form.

### Changes
- Kept the existing core `create_addon_entity` tool and its schema unchanged.
- Renamed the geometry-first tool to `create_addon_entity_with_geometry` in its server, tests and skill so aggregated MCP clients have unambiguous tool names.
- Extended animation-controller input to accept ordered arrays of one-key transition objects and the legacy object-map shorthand. Arrays preserve caller-specified transition priority; both forms serialize to Bedrock's array format.
- Added regression tests for ordered transition preservation and rejection of multi-target transition entries.
- Added `server/tests/test_mcp_registry.py` to check the five stdio server registrations, unique tool names, all existing Creator Tools bridge tools, and exact preservation of the three original default prompts.
- Updated README, CHANGELOG, skill instructions and the example to describe the compatibility behavior.

### Official format evidence
- Microsoft Learn's Animation Controllers Reference says transition entries are evaluated in order and at most one transition is processed per frame. It shows `transitions` as an array of single-key objects: https://learn.microsoft.com/en-us/minecraft/creator/documents/animations/animationcontroller?view=minecraft-bedrock-stable
- Microsoft Learn's Creating New Entity Types guide documents the coordinated BP entity, RP client entity, geometry and render-controller resources: https://learn.microsoft.com/en-us/minecraft/creator/documents/introductiontoaddentity?view=minecraft-bedrock-stable
- Tool-level object-map input remains supported for backward compatibility; generated Bedrock controller JSON remains an ordered array.

### Verification
- GitHub Actions on this follow-up branch: pending.
- Minecraft import, entity spawn/render, Molang execution, controller transitions in-game and Creator Tools CLI: NOT RUN.

### Remaining
- PR #6 remains separate and unmerged; this branch is intended as a dependent compatibility fix.
- Plugin Creator 1.1.1 still differs from GitHub in the MCT bridge and stable sample-index packaging. No release update is authorized or performed.
