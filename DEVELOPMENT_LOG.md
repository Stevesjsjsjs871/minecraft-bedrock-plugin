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
- First GitHub Actions run #41019454214 executed 172 tests and found one stale assertion in the copied entity-server test: it expected server version 1.1.0 while the package is 1.1.1. All animation-array tests, registry tests, MCT-preservation checks and other entity tests passed.
- Corrected the stale assertion in commit `03c7a170950969b1af1fe5d597e124c2de7b7410`.
- Follow-up CI #41019515461 passed the 172-test suite but failed the workflow's final compatibility script, which still expected the new entity server to expose the legacy name. Updated the script in commit `231baaa7ba3ad6c307cec34ca99f3af803f43d0e` to assert the advanced tool name and separately assert that the core legacy entity tool plus all four Creator Tools bridge tools remain registered. Full rerun pending.
- Minecraft import, entity spawn/render, Molang execution, controller transitions in-game and Creator Tools CLI: NOT RUN.

### Remaining
- PR #6 remains separate and unmerged; this branch is intended as a dependent compatibility fix.
- Plugin Creator 1.1.1 still differs from GitHub in the MCT bridge and stable sample-index packaging. No release update is authorized or performed.


## 2026-10-30 — Animation blend-expression authoring

### Baseline
- Based on PR #7 head `d6558dd3e19119f3ab85692600f0364c8d2a9ecb` (entity/animation compatibility contracts); PR #7 is a Draft stacked on PR #6 and neither is merged.
- Plugin Creator current release was re-read: version 1.1.1, Release ID `pluginrel_6ae44256591c8191bc421cdca48403be`. No Plugin Creator write was performed.
- Plugin Creator 1.1.1's animation-controller server accepted state animation aliases only as strings; the GitHub follow-up branch had the same restriction.
- GitHub main remains `0824c951fe780d21d5fa90b2c5749f411593affc` (1.0.14). The local machine working tree is not accessible.

### Finding and acceptance
Microsoft's stable Animation Controllers Reference shows state animation entries as either alias strings or single-key objects mapping an alias to a Molang blend expression, e.g. `{ "walk": "query.modified_move_speed" }`. The existing tool supported only strings, so it could not author a documented blending form.

Acceptance:
1. Preserve all existing string alias inputs.
2. Accept one-key alias-to-Molang objects and preserve their order in generated JSON.
3. Require each alias to resolve to an existing client-entity animation alias.
4. Bound and validate expression text without claiming to parse or execute Molang.
5. Make the read-only validator inspect blended entries and count their expressions.
6. Reject multi-key objects, unknown aliases and invalid expression text before writing.
7. Preserve MCP names, existing MCT bridge tools, Plugin ID, five stdio servers and three original default prompts.

### Changes
- `server/animation_controller_mcp.py`: expanded the closed MCP input schema; normalize string/object animation entries; validate aliases and blend expression text; include blend expressions in generated result metrics; teach the read-only validator to inspect them.
- `server/tests/test_animation_controller_mcp.py`: added schema, successful blend, invalid/multi-key/missing-alias and validator regression tests.
- `skills/animation-controller-authoring/SKILL.md`, `README.md`, `CHANGELOG.md`: document the official animation-entry form and static-only limits.
- No version marker, manifest, default prompt, MCP server registration or Plugin Creator release was changed.

### Official evidence
- Microsoft Learn, Animation Controllers Reference, stable view: https://learn.microsoft.com/en-us/minecraft/creator/documents/animationcontroller?view=minecraft-bedrock-stable (accessed 2026-10-30). It documents state animation entries such as `{ "walk": "query.modified_move_speed" }` and explains that Molang controls the animation blend value.

### Verification
- CI status: pending at the time this journal entry was prepared. The tested code commit and subsequent journal-only commit will be recorded after GitHub Actions completes.
- Minecraft import, Molang evaluation, in-game animation blending and Creator Tools CLI remain NOT RUN.

### Risks and next work
- The expression is not parsed; syntactically invalid but printable Molang may pass this static validator.
- State variables, nested animation-controller aliases and full animation clip authoring remain outside this tool's current scope.
- Plugin Creator 1.1.1 is not synchronized with this follow-up branch. Do not update it without a separate explicit user confirmation and an expected-current-release guard.
