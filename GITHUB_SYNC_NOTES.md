# GitHub source mirror

This branch contains the maintained Minecraft Bedrock Engineer **1.5.11 Skills-first source**.

- Removed all retired server wrappers and server tests from this repository.
- Removed the legacy package-integrity checker that validates the retired server/registry architecture; the active Skills-only checker and tests remain.
- Removed MCP/Cloudflare deployment configuration and obsolete deployment scaffolding in the preceding sync.
- Kept release history and changelog entries as historical records; they are not active code.
- Repository CI and ignore rules are maintained for the Skills-first scripts.

## Binary reference data

The generated Mojang Samples index is not committed to Git. CI restores it from the exact official Mojang v1.26.50.4 full release asset (169,385,576 bytes). The release API digest matches the pinned ZIP SHA-256 \`c0b6151f5f9a0c31ebe3c909dfc82d97f12473ed2c6e039aa7e22d667042026c\`. The deterministic regenerated gzip is 1,128,406 bytes with SHA-256 \`48429d64391157553e6760b7f568e5e6d5d05fa6517427b5a1156c8bc18e61fc\`: 22,252 indexed entries from 22,859 ZIP entries, with all category totals matching. Plugin Creator 1.5.12's stored index is 1,128,413 bytes; its bytes were not materialized for direct comparison, so byte-for-byte parity is not claimed.

## Package provenance gate — 2026-10-30

- Added a safe package inventory that rejects symlinks, special files, __pycache__, .pyc and .pyo, with file-count and size budgets.
- Added a deterministic tar.gz builder that records the full Git commit, source date epoch, sorted per-file SHA-256 inventory and canonical payload digest in BUILD_PROVENANCE.json; the adjacent .sha256 file hashes the exact archive bytes.
- The checker now requires provenance, validates every listed file/hash and payload totals, checks README/CHANGELOG/version parity, and preserves the three original default prompts verbatim.
- Added regression tests for bytecode, symlinks, Windows drive/traversal paths, missing/tampered provenance, duplicate paths, sidecar tampering, overwrite protection and deterministic output.
- Local validation: 34/34 package integrity/provenance tests and Python compilation passed in an isolated temporary fixture.
- Initial PR CI run #41089549833 passed package integrity/provenance tests but failed the audit-benchmark suite (10/12) because the workflow did not install the jsonschema dependency required by evaluate_benchmark.py. Added pinned jsonschema==4.26.0, a requirements file and a CI install step; final PR-head CI #41091044577 completed SUCCESS on d1907efedd132a03b932aa0f5ca8e64a8df3968c: compileall PASS; geometry/UV 18/18; PNG/texture 22/22; package integrity/provenance 34/34; Mojang indexer 6/6; audit benchmark 12/12; release metadata check PASS. jsonschema==4.26.0 installed successfully.
- The builder is documented to package a clean git archive snapshot (not the post-test working tree), so test-generated __pycache__ files do not contaminate the candidate. The builder still rejects any bytecode or symlink present in that clean tracked snapshot.
- The first full candidate attempt (#41093309817) failed because the builder's own Python import generated a fresh \`__pycache__\` in the clean temporary snapshot. Job-wide \`PYTHONDONTWRITEBYTECODE=1\` fixed this without weakening the cache rejection.
- Final CI #41093546276 SUCCESS on code commit \`3e4ff559b00ac43e0c5795a759cc5942a16245eb\`: compile PASS; geometry/UV 18/18; PNG/texture 22/22; package/provenance 34/34; Mojang indexer+restore 14/14; audit benchmark 12/12; release metadata/Skills-only boundary PASS.
- Official source ZIP: 169,385,576 bytes, SHA-256 \`c0b6151f5f9a0c31ebe3c909dfc82d97f12473ed2c6e039aa7e22d667042026c\`. Generated index: 1,128,406 bytes, SHA-256 \`48429d64391157553e6760b7f568e5e6d5d05fa6517427b5a1156c8bc18e61fc\`; 22,859 ZIP entries, 22,252 indexed entries; all category totals match.
- Candidate \`minecraft-bedrock-engineer-1.5.11.tar.gz\`: archive SHA-256 \`6e262b797153715362dccb567542de1be1994725066b0f00e07d7f398e37d9e2\`; payload 132 files / 1,946,359 bytes. Extracted checker 22/22 PASS, 0 WARN, 0 FAIL; sidecar check OK. Provenance records Git commit \`81421622686f1eea3c16f3114f041ec0ab2d8270\`.
- The candidate was built and verified on the runner but was not uploaded as an Actions artifact. Runtime status is NOT RUN; Minecraft import, Blockbench and in-game rendering remain NOT RUN.

The current Plugin Creator release is 1.5.12 (Release ID pluginrel_6ae4b2ea22f88191a00187713b7e9b91), while this GitHub mirror remains 1.5.11. The paginated Plugin Creator inventory confirms the 1,128,413-byte Mojang index exists but is size-limited by the text API; the archive download did not materialize in the runtime. The package contains one generated .pyc file (14,282 bytes), no BUILD_PROVENANCE.json, and no package_provenance.py, build_skills_package.py, test_build_skills_package.py or audit-benchmark requirements.txt yet. The new gate will reject it until a future approved package update removes the bytecode and includes the new provenance/build/dependency files. This run did not modify Plugin Creator or publish a release.
