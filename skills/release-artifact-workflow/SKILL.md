---
name: release-artifact-workflow
description: Use when preparing a Minecraft Bedrock add-on or pack for handoff/release, especially when creating .mcaddon/.mcpack archives, hashes, artifact inventories, and a validation manifest.
---

# Release Artifact Workflow

## Goal
Create a reproducible deliverable with clear provenance rather than simply naming a ZIP as a release. Target game version defaults to 1.26.50 unless specified otherwise.

## Staging
1. Identify the existing project root and the exact BP/RP folder(s) to include. Inspect their manifests first.
2. Stage a copy in a temporary directory; do not move user files or rewrite the original project as a packaging side effect.
3. Include only the intended pack roots and required assets. Check that each pack has a valid `manifest.json`, unique header UUID, correct modules, valid dependency links and the expected min-engine target.
4. Never include secrets, caches, unrelated repositories, temporary audit reports, local paths, or private source archives. Inspect the final file list before packaging.
5. Create `.mcpack` for a single pack or `.mcaddon` for a paired BP/RP add-on only using the archive layout expected by the target workflow. Do not invent a packaging format or rename an archive without verifying its contents.
6. After packaging, reopen the output archive and verify CRC, canonical relative paths, absence of duplicate paths and presence of all expected manifests/resources.
7. Compute SHA-256 of the final artifact and record the exact byte size, target version, package type and file count.
8. Run the static audit on the exact final archive, not just the source directory. If a baseline is available, run a diff and inspect the final regressions.

## Validation manifest
Return or save a companion JSON document with:
- artifact filename and SHA-256;
- byte size and entry count;
- target Bedrock version and pack type;
- BP/RP manifest names, UUIDs and module types (when present);
- audit/analyzer version;
- static checks and exact pass/fail/skip counts, if executed;
- baseline artifact hash and diff summary if available;
- Creator Tools version/result if actually run;
- runtime state (`NOT RUN`, `PARTIAL`, or `TESTED`) plus actual test context;
- unresolved resources and known caveats.

Do not claim that packaging proves game compatibility. Preserve the actual source project and report any exclusions or unsupported resources.

## Security and integrity
Never extract-and-run scripts from a submitted pack. Reject path traversal, absolute paths, duplicate names and unsafe symlink behavior. Do not silently overwrite previous deliverables. Use a distinct output name or require explicit authorization before replacing an existing artifact.
