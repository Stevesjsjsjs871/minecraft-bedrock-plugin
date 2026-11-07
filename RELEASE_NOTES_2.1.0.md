# Release notes — 2.1.0

## Strict Skills-only package cleanup

- Removed all 34 historical files under `server/` (17 implementation modules and 17 test modules) after reviewing the dependency/provenance inventory and confirming that the active Skills package contains standalone replacements for the reusable workflows retained in current product scope. No historical protocol code was executed.
- Retired the server-specific source analyzer and its tests. The stable `legacy-source-migration` Skill remains, now focused on safe static migration of user-supplied Bedrock projects.
- Preserved all 65 Skills, 14 domains, eight workflow profiles, 12 default prompts, plugin ID, USER scope and PRIVATE audience.
- Corrected `VERSION_HISTORY.md` to include the 2.0.8 and 2.0.9 releases and synchronized all package version markers to 2.1.0.
- Updated active documentation so no current workflow depends on the removed server tree. Prior migration audits remain archival records only.

## Verification

- Strict Skills-only package gate: 20/20 PASS.
- Domain architecture: 28/28 PASS; 14 domains / 65 Skills / 8 workflow profiles.
- Skills tests: 27/27 files, 500/500 cases PASS.
- Active non-test Python entry points: 27/27 `--help` smoke checks exit 0.
- Skill catalog: 65/65 Skills discovered and their instruction files loaded in the current ChatGPT skill runtime. This is not proof of automatic selection from arbitrary user prompts in every installed-plugin surface.
- All 55 remaining Python files are covered by the six-level registry with refreshed SHA-256 values. Local Python evidence only; plugin-host script execution remains NOT TESTED.

## Not verified / blocked

- Real third-party Bedrock add-on archive testing: NOT RUN; no `.mcaddon` / `.mcpack` archives were supplied.
- Minecraft import, Content Log, rendering, gameplay, multiplayer and Creator Tools validation: NOT RUN; no game runtime or connected Creator Tools capability was available.
- Automatic activation of every Skill through the installed Plugin Creator plugin interface: NOT TESTED.
