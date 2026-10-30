---
name: package-integrity
description: Use before publishing a Minecraft Bedrock Engineer package or diagnosing version, shared manifest metadata, changelog, MCP configuration, prompt, skill inventory, tool registry, or Mojang sample-index drift.
---

# Package Integrity Audit

## Purpose
Run an offline structural audit of the actual package directory before creating a release candidate. The checker catches package drift that may not be visible from reviewing a changelog or updating the version number alone.

## Run
From the root of the extracted plugin package:

```bash
python skills/package-integrity/scripts/check_package_integrity.py .
python skills/package-integrity/scripts/test_check_package_integrity.py -v
```

The script emits a JSON evidence report and a non-zero exit code for failures. The default audit checks required files, strict SemVer agreement across both manifests and `VERSION`, plugin identity, shared root/compatibility manifest metadata and interface parity, exact default-prompt parity, compatibility/MCP configuration references, skill frontmatter uniqueness, statically discoverable MCP tool names and dispatch comparisons, writer annotations, README version heading, latest changelog version, and the Mojang sample-index metadata. If the generated gzip index is absent but the curated version-labelled sample files exist, it reports an explicit `WARN` for curated fallback rather than claiming the full index was verified.

To skip decompression of the sample index for a quick check, pass `--skip-deep-index`. This produces a warning, not a full pass for the index-content gate.

To repair only a recognized stale README first-line heading, use `--fix-readme-heading`. This option only changes the first line and preserves all remaining README content. It refuses unexpected heading formats and does not edit the manifest or version markers.

## Safety and interpretation

- The checker is offline and read-only unless `--fix-readme-heading` is explicitly passed.
- It never launches Minecraft, connects to the MCP host, executes add-on scripts, or extracts the Mojang sample archive.
- A static registry audit is not a replacement for `server/tests/test_mcp_server.py`; the complete test suite must still run separately.
- A report with `runtime_status: NOT RUN` does not prove import, rendering, behavior, or multiplayer compatibility in the game.
- Never overwrite a user's pack just to make an audit pass. Fix the source of a finding, then rerun the full gate.


## Versioned Mojang sample index integrity

- The checker discovers every `mojang-samples-*` directory under `skills/bedrock-development/references/` and audits each `INDEX_METADATA.json` and gzip index independently.
- The directory suffix, metadata `target_version` and compressed index `target_version` must agree. Stable four-part versions and explicit prerelease suffixes are accepted; cross-version metadata is rejected.
- The legacy `mojang_samples_index` report field continues to describe stable `1.26.50.4`; `mojang_samples_indices` contains the per-version reports.
