# Release Notes — 2.3.1 candidate

## Project State inventory hardening
- Hashes regular project files through one pinned file descriptor.
- Uses `O_NOFOLLOW` where available and verifies descriptor/path identity plus size/mtime/ctime stability.
- Rejects symlink/non-regular files and detects replacement between inventory `lstat` and hash open.
- Adds regression tests for symlink and replaced-path inputs.

## Validation
- Full local suite: 32/32 test files, 548/548 cases PASS.
- Project State tests: 30/30 PASS.
- Installed Plugin Host activation and bundled Python execution: NOT VERIFIED.
- Minecraft runtime: NOT RUN.
- Candidate only; no live publication/update.
