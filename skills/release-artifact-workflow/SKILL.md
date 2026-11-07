---
name: release-artifact-workflow
description: Use to stage, package, manifest and diff Minecraft Bedrock add-on release artifacts.
---

# Release Artifact Workflow

## Goal
Create a reproducible deliverable with clear provenance rather than simply naming a ZIP as a release. Target game version defaults to 1.26.50 unless specified otherwise.

## Staging
1. Identify the existing project root and the exact BP/RP folder(s) to include. Inspect their manifests first.
2. Before staging a changed project, apply `skills/addon-versioning/SKILL.md` unless the user explicitly opts out. A coherent delivered change set must have its new version visible in each pack title and in each pack's `header.version`; align existing module versions and pack dependency versions.
3. Stage a copy in a temporary directory; do not move user files or rewrite the original project as a packaging side effect.
4. Include only the intended pack roots and required assets. Check that each pack has a valid `manifest.json`, unique header UUID, correct modules, valid dependency links and the expected min-engine target.
5. Never include secrets, caches, unrelated repositories, temporary audit reports, local paths, or private source archives. Inspect the final file list before packaging.
6. Create `.mcpack` for a single pack or `.mcaddon` for a paired BP/RP add-on only using the archive layout expected by the target workflow. Do not invent a packaging format or rename an archive without verifying its contents.
7. After packaging, reopen the output archive and verify CRC, canonical relative paths, absence of duplicate paths and presence of all expected manifests/resources.
8. Compute SHA-256 of the final artifact and record the exact byte size, target version, package type and file count.
9. Run the static audit on the exact final archive, not just the source directory. If a known-good archive is available, run `skills/addon-baseline-diff/scripts/addon_baseline_diff.py <baseline> <candidate> --release-candidate --report <diff.json>` and review every removal and manifest/resource regression. For intermediate workbench snapshots, omit `--release-candidate` so the comparator does not require a release version bump.

If the only input is an existing `.mcaddon`/`.mcpack`, use the safe archive path in `addon-versioning`: dry-run first with `addon_archive_versioning.py`, then apply into a distinct new output archive. The source archive must remain byte-identical. Read the final archive back and check title/version parity inside its actual manifest and `.lang` members; never rely only on the temporary extraction report.

## Validation manifest
Return or save a companion JSON document with:
- artifact filename and SHA-256;
- byte size and entry count;
- target Bedrock version and add-on release version;
- visible pack titles, BP/RP manifest names, UUIDs and module types (when present);
- audit/analyzer version;
- static checks and exact pass/fail/skip counts, if executed;
- baseline artifact hash and `addon-baseline-diff` summary (added/removed/modified files and findings) when available;
- Creator Tools version/result if actually run;
- runtime state (`NOT RUN`, `PARTIAL`, or `TESTED`) plus actual test context;
- unresolved resources and known caveats.

Do not claim that packaging proves game compatibility. Preserve the actual source project and report any exclusions or unsupported resources.

## Security and integrity
Never extract-and-run scripts from a submitted pack. Reject path traversal, absolute paths, duplicate names and unsafe symlink behavior. Do not silently overwrite previous deliverables. Use a distinct output name or require explicit authorization before replacing an existing artifact.

## Add-on version gate

Before staging a changed project, apply `skills/addon-versioning/SKILL.md` unless the user explicitly opts out. A coherent delivered change set must have its new version visible in each pack title and in each pack's `header.version`; align existing module versions and pack dependency versions. Include the visible pack titles and add-on release version in the validation manifest.

## Consolidated artifact preparation modes

This Skill absorbs the overlapping `release-artifact-workflow` procedure. Use modes:

- **stage** — stage only the authorized project files and preserve originals.
- **package** — create the requested `.mcpack`/`.mcaddon` from the exact BP/RP roots with deterministic membership and archive integrity checks.
- **manifest** — record pack identity, UUIDs, module layout, versions, dependencies, target engine and hashes.
- **artifact-diff** — compare the staged artifact to the exact prior baseline and explain every delta.

Artifact creation is not release approval. Keep add-on pack versioning in `addon-versioning`, plugin version governance in `version-governance`, and readiness decision in `release-quality-gate`. Never report runtime or host checks as passed unless evidence exists.
