# Release Notes — 2.0.6

## Pinned archive inspection

- Adds a context-managed ZIP reader that pins a regular-file descriptor for the whole audit operation.
- SHA-256, ZIP central-directory inspection, CRC checks and member reads now use the exact same opened file. A path swap or symlink replacement cannot silently redirect later reads to a different archive.
- Uses bounded streaming hash reads and validates file identity/size/mtime before and after inspection; in-place changes during the audit are rejected.
- Retains the existing `validate_zip_limits()` API as a compatibility wrapper; new readers should use `open_bounded_zip()` and complete all member reads inside its context.
- Updates the `automated-validation` Skill to state the pinned-descriptor guarantee and the local-executor boundary.
- Adds 4 focused regression cases, bringing the archive-safety suite to 12/12.

## Validation evidence

- Full Skills runner: 27/27 test files, 490/490 test cases passed under Python 3.13.5.
- Focused archive-safety suite: 12/12 passed, including archive path replacement during audit and in-place mutation detection.
- Domain-Based Hybrid architecture validator: 28/28 passed; 14 domains, 65 Skills and 8 workflow profiles.
- Compatibility package checker: 19 passed, 0 failed, 1 warning. The warning is the retained 34-file historical `server/` footprint.
- Strict Skills-only gate remains BLOCKED until the legacy dependency/provenance work is complete and cleanup is separately approved.
- Host-level script execution NOT VERIFIED. Minecraft import/render/gameplay NOT RUN.

## Release lineage

- Update base inspected through Plugin Creator: version 2.0.5, release `pluginrel_6aeecff237348191bbd433dc732837d9`.
- Existing plugin identity retained: `minecraft-bedrock-engineer` / `plugins_6ae33ff6e8d8819182f246d8d3d97323`; USER scope and PRIVATE audience unchanged.
