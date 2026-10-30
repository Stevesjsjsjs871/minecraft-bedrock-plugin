# GitHub source mirror

This branch contains the maintained Minecraft Bedrock Engineer **1.5.11 Skills-first source**.

- Removed all retired server wrappers and server tests from this repository.
- Removed the legacy package-integrity checker that validates the retired server/registry architecture; the active Skills-only checker and tests remain.
- Removed MCP/Cloudflare deployment configuration and obsolete deployment scaffolding in the preceding sync.
- Kept release history and changelog entries as historical records; they are not active code.
- Repository CI and ignore rules are maintained for the Skills-first scripts.

## Binary reference data

The compressed Mojang Samples index (skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz, 1,128,413 bytes) is present in the Plugin Creator release but was not readable through its text-source API. The binary archive download endpoint was not reachable from the current file-transfer runtime. It is not replaced with a fabricated or partial index. The GitHub mirror is therefore source-complete except for this one binary index; the Plugin Creator release remains the authoritative complete distribution.

## Package provenance gate — 2026-10-30

- Added a safe package inventory that rejects symlinks, special files, __pycache__, .pyc and .pyo, with file-count and size budgets.
- Added a deterministic tar.gz builder that records the full Git commit, source date epoch, sorted per-file SHA-256 inventory and canonical payload digest in BUILD_PROVENANCE.json; the adjacent .sha256 file hashes the exact archive bytes.
- The checker now requires provenance, validates every listed file/hash and payload totals, checks README/CHANGELOG/version parity, and preserves the three original default prompts verbatim.
- Added regression tests for bytecode, symlinks, Windows drive/traversal paths, missing/tampered provenance, duplicate paths, sidecar tampering, overwrite protection and deterministic output.
- Local validation: 30/30 package integrity/provenance tests and Python compilation passed in an isolated temporary fixture.
- The full extracted-package check and release archive build were NOT RUN: the GitHub mirror still lacks the exact 1.26.50.4 compressed Mojang Samples index. Do not fabricate or bypass this asset requirement.

The current Plugin Creator release is 1.5.12 (Release ID pluginrel_6ae4b2ea22f88191a00187713b7e9b91), while this GitHub mirror remains 1.5.11. The Plugin Creator package currently contains one generated .pyc file (14,282 bytes) and no BUILD_PROVENANCE.json; the new gate will reject it until a future approved package update removes the bytecode and includes generated provenance. This run did not modify Plugin Creator or publish a release.
