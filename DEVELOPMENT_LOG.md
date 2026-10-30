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


## 2026-10-30 — Parity audit follow-up and symlink hardening

### State revalidation
- Current Plugin Creator remains version `1.1.1`, Release ID `pluginrel_6ae44256591c8191bc421cdca48403be`.
- GitHub `main` remains `1.0.14` at `0824c951fe780d21d5fa90b2c5749f411593affc`.
- PR #9 remains open as Draft; its CI run #158 completed successfully on commit `2ec289d22967f129ac9068f7f26fb4e1c4b30d91`.
- No Plugin Creator mutation, merge, or public release was performed.

### Full source inventory comparison
- Plugin Creator lists 95 files totalling 2,231,720 declared bytes.
- 94 text files were read through the Plugin Creator source API and compared against Git blob SHA-1 values at PR #6 commit `fe233407afb9515d23bc4a987ae228c1cf2c5413`.
- 87 of 94 text files were byte-identical.
- Seven text files differ: `server/mcp_server.py`, `server/tests/test_animation_controller_mcp.py`, `server/tests/test_entity_authoring_mcp.py`, `server/tests/test_mcp_server.py`, `skills/bedrock-development/SKILL.md`, `skills/package-integrity/SKILL.md`, and `skills/package-integrity/scripts/check_package_integrity.py`.
- The packaged Stable index `skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz` is 1,128,413 bytes in Plugin Creator but is absent from the PR #6 Git tree. No package paths other than this binary index were absent from that source tree, and no source package paths were absent from the Plugin Creator listing.
- This is a comparison against PR #6 head, not proof of the exact source commit used to build Plugin Creator 1.1.1. The release-to-source provenance is not recorded, so these differences must be treated as source-snapshot drift pending provenance confirmation, not automatically as a release defect.

### Security review and changes
- Code review found that checking only the leaf path missed a symlinked parent such as `.codex-plugin -> outside/`; repository scanning could follow that parent while reading the compatibility manifest.
- ZIP directory entries ending in `/` were skipped before checking their Unix file type, allowing a symlink-mode directory record to pass the archive safety checks.
- Updated `.github/scripts/check_plugin_creator_parity.py` to reject symlinks in every component of root metadata paths, reject resolved paths escaping the repository root, and reject ZIP directory entries whose Unix mode is not a directory (or unspecified).
- Added regression tests for both cases and documented the additional checks.

### Verification
- PR #9 CI run #158 on the initial checker revision: SUCCESS; all workflow steps completed.
- PR #9 CI run #159 after symlink hardening: SUCCESS; all 18 parity-checker tests and every workflow step completed.
- New symlink-hardening tests: 18/18 parity-checker tests passed in GitHub Actions run #159 (Python 3.12). The complete workflow, including compilation, existing server tests, package integrity, analyzer regressions, manifest checks and parity tests, completed successfully on commit `a937c7093a49e98e64ec3809cd2b7275e63e7aa6`.
- Actual private archive-level parity execution remains NOT RUN because the archive download could not be materialized in the working container. The source API inventory comparison above is complete for all 94 readable text files; the >1 MiB gzip index remains uninspected at byte level.

### Next step
- Verify the new tests in CI, then preserve the exact source commit/release provenance for the next Plugin Creator build. Do not update Plugin Creator or publish a release without explicit user confirmation.
