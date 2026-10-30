# Development Log

## 2026-10-30 — Plugin Creator source-parity gate

### Initial state
- GitHub `main`: `1.0.14`, commit `0824c951fe780d21d5fa90b2c5749f411593affc`.
- Plugin Creator current release: `1.1.1`, Release ID `pluginrel_6ae44256591c8191bc421cdca48403be`.
- Plugin Creator inventory: 95 files, 2,231,720 declared bytes; 12 files under `server/`, 75 under `skills/`, and 8 root/metadata files.
- PRs #1–#8 were open and unmerged at inspection time. PR #6 is the 1.1.1 entity/animation source line; PR #7 and #8 depend on it.
- No Plugin Creator mutation or public release was authorized or performed.

### Evidence-based parity findings
Compared selected current Plugin Creator files with the PR #6 source line:
- Exact matches: `plugin.json`, `.codex-plugin/plugin.json`, `.mcp.json`, `mcp.json`, `VERSION`, `CHANGELOG.md`, `server/entity_authoring_mcp.py`, and `server/animation_controller_mcp.py` (plus the corresponding focused entity/animation tests).
- Differences: `server/mcp_server.py` and `server/tests/test_mcp_server.py`.
- Plugin Creator `server/mcp_server.py`: 111,574 bytes; GitHub PR #6 source: 156,737 bytes.
- The Plugin Creator package has a dedicated entity-authoring stdio server, so `create_addon_entity` is available there; it must not be incorrectly reported as absent from the whole package.
- The four Creator Tools bridge registrations present in the GitHub primary MCP server but absent from the Plugin Creator primary server are `creator_tools_status`, `creator_tools_catalog`, `validate_with_mct`, and `create_entity_with_mct`.
- The Plugin Creator package contains the Stable 1.26.50.4 sample index. The Preview 1.26.60.30 index is not in this 1.1.1 package; PRs #3/#4 remain separate and unmerged, so that absence is expected for this release line.
- Molang-blended animation entries from PR #8 are not in Plugin Creator 1.1.1; PR #8 is unmerged, so this is also expected rather than a 1.1.1 regression.
- All three default prompts match between the two manifests and the PR #6 source snapshot.

### Work performed
- Added repository-only `.github/scripts/check_plugin_creator_parity.py`.
- Supports ZIP and tar/tar.gz archives without extracting them.
- Compares all package root files plus the complete `server/` and `skills/` trees byte-for-byte.
- Checks version/manifest consistency, the three default prompts, stdio MCP server-name parity, and referenced server-script presence.
- Rejects unsafe paths, Windows drive paths, symlinks, non-regular archive members, duplicate paths, case-insensitive path collisions, excessive entry counts, and oversized archives/files.
- Added 16 synthetic regression tests covering matching ZIP/tar packages, source drift, missing/extra files, metadata/prompt drift, missing MCP scripts, duplicate entries, path traversal, symlinks, Windows paths, case collisions, invalid archives, and missing repository roots.
- Added usage/scope documentation in `.github/scripts/README.md`.
- Extended `.github/workflows/validate.yml` to compile and run the parity checker tests.

### Local verification
- Python compilation: PASS.
- `python -m unittest discover -s .github/scripts -p 'test_*.py' -v`: 16/16 PASS on the available local Python 3.13 runtime.
- CI Python 3.12 result: pending at time this log entry was prepared.
- The private current Plugin Creator tar.gz was not materialized in the working container. File-level source comparison was performed through Plugin Creator's source API; the new archive-level checker has only been exercised with synthetic ZIP and tar.gz fixtures so far.

### Files / branch
- Branch: `tools/plugin-creator-source-parity-20261030`, based on main commit `0824c951fe780d21d5fa90b2c5749f411593affc`.
- Added `.github/scripts/check_plugin_creator_parity.py`.
- Added `.github/scripts/test_check_plugin_creator_parity.py`.
- Added `.github/scripts/README.md`.
- Updated `.github/workflows/validate.yml`.
- Added this `DEVELOPMENT_LOG.md` entry.

### Risks and next step
- The archive checker is repository release tooling; it is not included in the Plugin Creator package.
- It does not verify external Plugin ID/Release ID; those must be re-read in Plugin Creator immediately before any guarded update.
- A passing parity check does not establish Minecraft runtime correctness.
- Next: wait for CI, then run the checker against the actual current Plugin Creator tar.gz using the exact source snapshot used for release 1.1.1. Prepare a source-parity candidate for the missing Creator Tools bridge only after reviewing the full archive diff. Do not update Plugin Creator or publish a release without explicit user confirmation.
