# Release Notes — 2.3.0 (unpublished candidate)

## Archive and input safety
- Adds a shared ZIP member namespace validator used by the corpus indexer and metadata benchmark builder.
- Accepts ordinary explicit directory entries (`behavior_pack/`, nested directories) and archives that omit explicit directory entries.
- Rejects absolute/drive/UNC/backslash/traversal paths, empty/dot/parent segments, NUL/control characters, duplicate paths, case-fold and NFC collisions, file/directory conflicts, file-as-parent conflicts, symlinks, special files, encrypted entries, inconsistent directory type markers and compression ratios above 1000:1.
- Uses one pinned file descriptor for archive SHA-256 and ZIP inspection; detects path swaps and in-place mutation through `archive_safety.py`.
- Verifies CRC/decompression before indexing; limits compressed archive size to 256 MiB, entry count to 50,000, one member to 128 MiB, total declared expansion to 512 MiB and compression ratio to 1000:1. No extraction or embedded-code execution.

## Static audit quality
- Adds conservative JSONC parsing for `//` / `/* */` comments and trailing commas while preserving string contents. Duplicate keys and malformed JSON/JSONC remain rejected.
- Real Furniture archive re-audit parsed 29 JSONC files and found two duplicate-key files; these remain source findings, not modifications.
- Re-indexed all ten supplied archives: 42,876 ZIP entries / 110 manifest records; all archive hashes and CRCs verified.
- Static-audited five real packs read-only. No precision/recall score is claimed because no independent ground-truth labels exist.

## Package state
- 71 Skills, 14 domains, eight workflow profiles, 12 default prompts, 64 Python files.
- Full Skills suite: 32/32 files, 546/546 cases PASS. Package integrity: 20/20 PASS. Architecture: 28/28 PASS. Workflow profile smoke plans: 8/8 PASS.
- Live Plugin Creator remains 2.1.11 USER / PRIVATE. This 2.3.0 candidate is not published.
- Plugin Host automatic activation/script execution NOT VERIFIED; Minecraft import/render/gameplay/multiplayer/Blockbench/Creator Tools NOT RUN.
