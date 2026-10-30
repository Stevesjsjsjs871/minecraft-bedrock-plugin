# Development log

## 2026-10-30 — PNG decoder validation for texture-atlas registration

### Recovered state
- Plugin Creator: minecraft-bedrock-engineer version 1.0.11, current release pluginrel_6ae3d2b1b6888191bf4727998f694e48 (private; not modified in this stage).
- GitHub main: 4eb35503095c735d725597bdb2f517f4bf188803, version 1.0.11.
- Latest main CI: run #103, success; run #102 also success.
- Existing draft PR #1 is still open, but its branch is 18 commits ahead and 2 behind main; its 1.0.10 integrated-server approach is superseded by the separate texture MCP server already present on main. It is not safe to merge as-is.
- Before this branch, the Plugin Creator texture MCP source and tests matched GitHub main byte-for-byte. Metadata/documentation drift exists: plugin.json and .codex-plugin/plugin.json differ in descriptions/keywords/interface metadata; README.md, CHANGELOG.md and visual-resource-pipeline/SKILL.md differ; mcp.json is semantically equal and .mcp.json is byte-for-byte equal. The three defaultPrompt entries are byte-for-byte equal. GitHub code search returned no TODO/FIXME matches and no open issues were found; this does not prove no informal TODOs exist outside the indexed default branch.
- The three original default prompts are present and unchanged in both manifests.

### Selected task and acceptance criteria
Harden register_texture_atlas so a PNG with valid chunk CRCs but invalid compressed image data cannot be registered. Accept only structurally valid PNG image streams whose decompressed byte count and scanline filter bytes match IHDR.

### Changes
- Extend server/texture_generator_mcp.py::_read_valid_png to validate legal IHDR color-type/bit-depth combinations, compression/filter/interlace methods, palette placement and bounds, consecutive IDAT chunks, zlib stream integrity, exact decompressed scanline length, and filter bytes 0–4. Adam7 pass dimensions are accounted for. It also accepts unused trailing bytes in the final IDAT chunk, as required by the W3C PNG specification, and rejects a lowercase reserved third chunk-name bit.
- Add three negative regression tests that rewrite IDAT data while recomputing the chunk CRC (invalid zlib stream, incorrect decompressed scanline length, invalid scanline filter byte), plus positive 5x5 RGBA Adam7 and unused-trailing-IDAT fixtures. The reader caps file reads at MAX_PNG_BYTES + 1 before rejecting oversized inputs.
- Preserve both stdio MCP servers, tool names, plugin identity and all default prompts.
- No Plugin Creator update or public release was made.

### Verification
- Pre-change baseline: GitHub Actions run #103 passed all configured checks on main (Python compile, MCP/unit suites, benchmark tests, Mojang sample-index tests, texture generator tests, package-integrity audit, analyzer regression and version/prompt consistency).
- Initial code/test commit d9ca200 passed run #106 (136 unit tests); documentation-only commits 5ab6fd3 and f5b801d passed runs #107 and #108. Final PNG compatibility commit 8a82953 passed run #109. Run #109 compiled all listed Python modules; passed 137 unit tests across five suites (98 MCP/server, 12 benchmark, 6 sample-index, 12 procedural texture, 9 package-integrity); passed all 18 analyzer regression cases; passed package-integrity audit and version/manifest/default-prompt/MCP-configuration consistency checks. All five new PNG cases passed: three negative CRC-valid corruptions and two positive fixtures (Adam7 and trailing IDAT bytes). Runs #104–#108 also passed on earlier heads.
- Reference basis: W3C PNG Specification (https://w3c.github.io/png/), especially IDAT concatenation/trailing-byte behavior, chunk naming and IHDR restrictions; Microsoft Learn custom block tutorial (https://learn.microsoft.com/en-us/minecraft/creator/documents/addcustomdieblock?view=minecraft-bedrock-stable) and item icon reference (https://learn.microsoft.com/en-us/minecraft/creator/reference/content/itemreference/examples/itemcomponents/minecraft_icon?view=minecraft-bedrock-stable) confirm the Bedrock atlas/key relationship.
- Minecraft import/rendering and Creator Tools CLI runtime: NOT RUN. GitHub Actions emitted non-failing Node.js 20 deprecation and Node punycode warnings.

### Git state
- PR #2 remains Draft and unmerged. Final code/test commit: 8a829534218e058e11faa2e8b7bb74dda1b1f680; main remains unchanged. Local uncommitted changes on the user's own workstation could not be inspected.
- PR #1 remains open and unmerged; do not merge its divergent 1.0.10 implementation without a fresh review.

### Risks and next step
- The new validator is static PNG-structure validation, not a full pixel reconstruction: it does not validate every ancillary-chunk semantic or every palette-index value. Minecraft's exact importer behavior still requires an in-game test.
- Residual file-operation risk: _atomic_update_json compares the existing atlas hash and then calls os.replace. The compare and replace are separate operations, so a non-cooperating external writer can still race in the narrow interval between them; path-based parent checks also are not a complete defense against a hostile directory swap. The next safety task is to harden this update path with a cross-platform, tested concurrency strategy before claiming strict lost-update protection.
- After that, reconcile the Plugin Creator/GitHub metadata and documentation drift without changing the three prompts, then review and clearly supersede draft PR #1.


## 2026-10-30 — Cross-process texture-atlas transaction locking

### Recovered state
- Plugin Creator current release: 1.0.11 (release ID pluginrel_6ae3d2b1b6888191bf4727998f694e48); its current texture MCP source and tests match GitHub main, not the unmerged PR #2 branch. No Plugin Creator mutation was made.
- GitHub main: 1.0.11 at 4eb35503095c735d725597bdb2f517f4bf188803. PR #2 is open Draft, unmerged, and based on main; its head before this stage was aba509a35f910e31232927a37db45e08b3f4ffc4. PR #1 remains open Draft and is based on an older divergent history; it is not merged.
- Latest PR #2 CI run #110 succeeded on Ubuntu 24.04 with Python 3.12. The run contains one python-checks job. There are no open GitHub issues.

### Selected task and acceptance criteria
Harden the texture-atlas read/merge/write transaction so concurrent instances of this tool do not overwrite each other's updates. Acceptance: acquire a per-atlas cross-process lock on Windows and POSIX; hold it across atlas read, validation, merge and atomic write; return a stable timeout error; detect a replaced parent directory before writing; preserve atomic no-overwrite creation; test concurrent writers, lock contention and parent replacement.

### Changes
- Add a per-user lock directory in the OS temporary directory, with persistent per-atlas lock files. The files are deliberately not unlinked after release because unlinking can split waiters across different inodes.
- Use fcntl.flock(LOCK_EX | LOCK_NB) on POSIX and msvcrt.locking(LK_NBLCK) on Windows. Locks are advisory and released by the OS when a process exits. A 10-second timeout returns ATLAS_LOCK_TIMEOUT.
- Hold the lock over the complete atlas transaction, not just the final replace, so two cooperating tool processes serialize and the second process reads the first process's update.
- Capture the atlas parent directory identity and recheck it before reading/writing and immediately before atomic link/replace. Keep the existing SHA-256 change check and atomic replacement/no-overwrite behavior.
- Add subprocess tests for two concurrent registrations, lock timeout under contention, and detection of a replaced parent directory.
- Add a dedicated Ubuntu/Windows Python 3.12 GitHub Actions workflow for the texture-atlas tests.
- Update the visual-resource-pipeline skill to document structural PNG validation, cross-process locking and the timeout response.

### Verification
- Dedicated portability workflow push run 40978756333 and PR run 40978761725 both succeeded. Ubuntu 24.04 / Python 3.12 passed 26/26 tests in 0.379s; Windows / Python 3.12 passed 26/26 tests in 0.813s. The concurrent-registration, lock-timeout and replaced-parent tests passed on both systems; no skips or failures were reported.
- Main PR validation run #111 (40978761714) succeeded: 140 unit tests across five suites (101 MCP/server, 12 benchmark evaluator, 6 Mojang sample index, 12 procedural texture generator, 9 package-integrity). Python compilation, package-integrity audit, all 18 analyzer regression cases, report-schema checks, version/manifest consistency, default-prompt preservation and MCP configuration checks passed. No failing test/error lines were present in the job log.
- GitHub Actions emitted non-failing Node.js 20 deprecation and Node punycode warnings. No dedicated linter/type-check step is configured; lint/type-check: NOT RUN. macOS and network-filesystem locking: NOT RUN.
- Minecraft import/rendering and Creator Tools CLI runtime: NOT RUN.
- Existing Plugin Creator release 1.0.11, manifests, MCP server definitions and the three original default prompts remain unchanged.

### Residual risks
- Advisory locks serialize cooperating instances of this tool; unrelated programs that ignore the lock can still race with the final path-based replace.
- Parent identity rechecks narrow and detect many directory-swap cases but do not provide a kernel-level directory-handle guarantee on both platforms. A hostile same-user process that swaps the directory after the final check remains outside the current guarantee.
- Persistent zero/one-byte lock files accumulate in a private per-user temporary directory. They are not placed in Resource Packs and do not alter add-on contents.
- Network-filesystem locking semantics are not verified. Minecraft import/rendering and Creator Tools CLI runtime remain NOT RUN.

### Next step
- Inspect both OS workflow results and fix any portability failures. After that, reconcile Plugin Creator/GitHub metadata drift without changing the three default prompts.


## 2026-10-30 — Manifest metadata parity and changelog release guard

### Recovered state
- Plugin Creator current private release: 1.0.11, release ID `pluginrel_6ae3d2b1b6888191bf4727998f694e48`; its source files and metadata were re-read before deciding not to mutate it. No Plugin Creator update was made.
- GitHub `main`: 1.0.11 at `4eb35503095c735d725597bdb2f517f4bf188803`; latest main CI run #103 succeeded. The repository has no open Issues; GitHub code search for TODO/FIXME returned no results (not proof that every unindexed/local file is clear).
- PR #2 remains Draft/open/unmerged, based on `main`. At the end of this stage its head is `05db0c94c1c5b1e1c3c7f531c1bd81185bf00217`, 14 commits ahead and 0 behind. PR #1 remains Draft/open/unmerged on the older procedural-texture branch; it is not merged.
- Plugin Creator and GitHub package source are not fully synchronized: `VERSION` matches byte-for-byte; `.mcp.json` matches byte-for-byte; `mcp.json` is semantically equivalent; the two original Creator Tools bridge skills match byte-for-byte. The root and compatibility manifests in the Plugin Creator release share the same metadata and all three prompts. On GitHub `main`, root and compatibility metadata matched except the compatibility manifest had six fewer keywords. README, CHANGELOG, root/compat manifests and `visual-resource-pipeline/SKILL.md` also differ between the Plugin Creator release and GitHub source. GitHub's README is substantially more complete; it was not replaced with the shorter Plugin Creator copy.
- The three default prompts were compared directly between Plugin Creator and GitHub and remain exactly equal (3/3).

### Selected task and acceptance criteria
Add a deterministic package-integrity gate for shared root/compatibility manifest metadata and the latest versioned CHANGELOG entry. Fix the observed keyword drift in the GitHub compatibility manifest without changing identity, MCP configuration or default prompts. Do not mutate Plugin Creator or publish a release without explicit confirmation.

### Changes
- Align `.codex-plugin/plugin.json` keywords with the root `plugin.json` list (52 entries); retain the three default prompts unchanged.
- Add `manifest-metadata` validation for shared name, version, description, author, keywords and interface display metadata. Keep exact prompt parity as its separate existing check.
- Make `CHANGELOG.md` a required package file and add `changelog-version` validation. A stale/missing latest release heading is a warning rather than an automatic failure.
- Bump the package checker implementation marker to 1.0.7; add regression tests for top-level metadata drift, interface metadata drift and stale changelog entries. The synthetic fixture now uses three prompts.
- Update the package-integrity skill and README instructions to describe and run the new checks.
- Changed files: `.codex-plugin/plugin.json`, `README.md`, `skills/package-integrity/SKILL.md`, `skills/package-integrity/scripts/check_package_integrity.py`, `skills/package-integrity/scripts/test_check_package_integrity.py`. Earlier texture-atlas changes remain in the same PR branch.

### Commits
- `48e85898aa451df0eff085fe59d39b7f1504135e` — metadata and changelog audit.
- `3865eb0187e40cc2eda7486cf4d272245d2bfb0f` — regression tests.
- `86509a0ac54ea3b555fbaaf05394289fd5f9871c` — skill documentation.
- `a00feb7daaabef8be543a50ce9c76a8d0a0ab5e3` — compatibility keyword alignment.
- `25ef66020f3eb754e1a8505005db460f9d373ab4` — fix changelog-heading regex after CI failure.
- `05db0c94c1c5b1e1c3c7f531c1bd81185bf00217` — README instructions.

### Verification
- Initial CI runs #113 and #114 failed in the new package-integrity suite: the first implementation over-escaped the changelog-heading regex, so a valid synthetic heading was reported missing. All earlier test groups passed. The failure was inspected in job logs and fixed in commit `25ef660`; it is not hidden.
- Final validation run #116 on head `05db0c94` succeeded. Unit tests: 143/143 across five suites (101 MCP/server, 12 benchmark, 6 Mojang sample index, 12 procedural texture, 12 package-integrity). Python compilation, report-schema checks, 18/18 analyzer regression cases, version/manifest checks and the package-integrity test step passed.
- Package-integrity checker 1.0.7: 17 checks, 16 PASS, 1 WARN, 0 FAIL. The sole warning is expected source-checkout coverage: the generated full gzip Mojang index is absent while 14 curated fallback files remain. The new `manifest-metadata` and `changelog-version` checks both PASS. Runtime status remains `NOT RUN`.
- Portability run #7 on the same head succeeded: Ubuntu ran 26/26 texture/atlas tests in 0.375s; Windows ran 26/26 in 0.693s.
- Non-failing GitHub Actions warning remains: actions/checkout@v4 and actions/setup-python@v5 target Node.js 20 and are currently forced to Node.js 24. Dedicated lint/type-check, macOS, network-filesystem semantics, Minecraft import/rendering and real Creator Tools CLI execution remain `NOT RUN`.

### Git and release state
- PR #2 remains Draft, open and unmerged; `main` remains unchanged. The latest head has 14 commits ahead and 0 behind `main`.
- Plugin Creator remains at 1.0.11 with release ID `pluginrel_6ae3d2b1b6888191bf4727998f694e48`. No Plugin Creator update or public release was made.
- Plugin Creator/GitHub README, CHANGELOG, manifest description/keywords and visual-resource-pipeline skill drift remains. Synchronizing the Plugin Creator release would change its current release and therefore remains blocked pending explicit user authorization.

### Risks and next step
- Metadata parity is now enforced inside the GitHub package, but it does not prove parity with the separately stored Plugin Creator release. The latter is a separately versioned source and must be updated only with an explicitly authorized, expected-release-ID-guarded operation.
- Next: prepare a precise Plugin Creator-to-GitHub synchronization diff without applying it; then review PR #1's divergent history and propose safe supersession/closure rather than merging it. Keep all runtime and Creator Tools claims marked `NOT RUN` until actually exercised.


## 2026-10-30 — Plugin Creator/GitHub manifest synchronization audit

### Recovered state
- Plugin Creator current private release: `1.0.11`, plugin ID `plugins_6ae33ff6e8d8819182f246d8d3d97323`, current release ID `pluginrel_6ae3d2b1b6888191bf4727998f694e48`. The current source was re-read before this work. Plugin Creator was not modified.
- GitHub `main`: `1.0.11`, commit `4eb35503095c735d725597bdb2f517f4bf188803`; latest main validation run #103 succeeded.
- PR #2 is open, Draft, unmerged, based on `main`; pre-stage head `3ca91b3129c030f491a135185f09f1b46a42d76e`, 16 commits ahead and 0 behind. Its latest pre-stage PR checks were run #117 and portability run #8; both succeeded. No PR reviews or inline review threads are recorded.
- PR #1 remains open Draft and unmerged on the older `automation/mcp-generate-texture-1-0-10-20261029b` branch. It has 18 commits and is based on an older implementation; it must not be merged without a fresh compatibility review.
- No open GitHub Issues were returned by the repository issue search.

### Package inventory and parity findings
- Plugin Creator contains 83 files; GitHub `main` contains 85; PR #2 contains 87.
- The only Plugin-Creator-only path is `skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz` (1,128,413 bytes in the Plugin Creator file listing). It is absent from GitHub `main` and PR #2. The matching `INDEX_METADATA.json` exists in both and is byte-for-byte identical. The gzip is binary and is not returned by the UTF-8 `get_plugin_files(read_paths)` operation; the archive download URL could not be materialized in this run, so no binary transfer was attempted.
- GitHub-only files on `main`: `.github/workflows/validate.yml`, `.gitignore`, `ROADMAP.md`. PR #2 additionally contains `.github/workflows/atlas-locking-portability.yml` and `DEVELOPMENT_LOG.md`.
- Exact matches confirmed for `.mcp.json`, `VERSION`, `server/texture_generator_mcp.py`, `server/tests/test_texture_generator_mcp.py`, `skills/package-integrity/scripts/test_check_package_integrity.py`, and `INDEX_METADATA.json`.
- `mcp.json` is semantically equivalent after JSON parsing, but formatting/schema-key text differs.
- GitHub `README.md` and `CHANGELOG.md` are substantially more complete than the Plugin Creator copies (31,236 vs 1,541 characters; 8,640 vs 3,893 characters respectively). Keep the richer GitHub documentation; do not replace it with the shorter package copies.
- GitHub's `visual-resource-pipeline/SKILL.md` and `bedrock-development/SKILL.md` are also richer than their Plugin Creator counterparts. The package-integrity skill/checker differ because PR #2 contains the newer metadata/changelog integrity work; retain those candidate improvements.

### Selected task and acceptance criteria
Synchronize the two GitHub manifests to the current Plugin Creator 1.0.11 manifests without touching the Plugin Creator release. Acceptance: exact shared metadata parity, stable plugin identity/version, and all three original default prompts byte-for-byte unchanged in both manifest forms.

### Changes
- Re-read current Plugin Creator `plugin.json` and `.codex-plugin/plugin.json`; confirmed their shared metadata and three prompts are consistent.
- Replaced GitHub PR #2 `plugin.json` with the exact current Plugin Creator 1.0.11 root manifest.
- Replaced GitHub PR #2 `.codex-plugin/plugin.json` with the exact current Plugin Creator 1.0.11 compatibility manifest.
- The Plugin Creator metadata has 77 keywords; GitHub `main` previously had 52 root keywords and 46 compatibility keywords, while the PR branch had aligned both to 52. The exact current Plugin Creator manifests now supply the same 77-keyword metadata to both GitHub manifests.
- Preserved all three default prompts; no plugin/App ID, version, MCP server, tool registration, skill or project behavior was changed.
- Retained the richer GitHub README/CHANGELOG/skills and GitHub-specific CI/development files intentionally; these are source-repository documentation/workflows, not release-package copies.

### Commits
- `0ce6803e038192a24dac9cec680159ae8a1b15f2` — synchronize root manifest.
- `1763c39532c157ff3b5ade1eb3cdd4dca2827c1f` — synchronize compatibility manifest.
- Development log update follows this entry; final CI results are recorded after the run completes.

### Verification before final CI
- Exact manifest parity against current Plugin Creator: PASS for both files.
- GitHub root/compatibility shared metadata parity: PASS.
- Default prompts: 3/3 in each manifest; both GitHub arrays exactly match current Plugin Creator: PASS.
- `.mcp.json`: byte-for-byte match: PASS.
- `mcp.json`: semantic JSON equivalence: PASS.
- `VERSION`: byte-for-byte match: PASS.
- Full GitHub Actions validation for the two new manifest commits: PENDING at log creation time.
- Minecraft import/rendering and real Creator Tools CLI: NOT RUN.

### Risks and next step
- The full compressed Mojang sample index is present in Plugin Creator but absent from GitHub source. The current tool path could list the binary but not materialize its bytes. Next: add a reproducible, pinned-source workflow that obtains the official Mojang v1.26.50.4 full release asset, verifies provenance and regenerates the metadata-only index, or use an authorized binary transfer route. Do not substitute the text-only/min archive while claiming full texture/sound path coverage.
- Keep Plugin Creator at 1.0.11 and its current release ID; no update or public release was made. Any future Plugin Creator mutation still requires an explicit user confirmation and the current expected release ID.
