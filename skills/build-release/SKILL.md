---
name: build-release
description: Use when preparing or changing a Minecraft Bedrock add-on release, creating .mcaddon/.mcpack archives, versioning BP/RP, creating changelogs, or enforcing pre-release gates.
---

# Build and Release Workflow

## Release policy
Build an artifact when requested and the tools allow it. Do not publicly publish, distribute, or replace the user's approved release without the user's authorization. Building a candidate archive is not the same as publishing it.

## Before build
- Identify and preserve the exact baseline.
- Determine expected BP/RP roots and desired output type.
- Check pack manifests and dependency UUID/version links.
- Keep add-on release version distinct from manifest format and Script API versions.
- Confirm that required external resource packs are documented.
- Record what files are expected to change.

## Build
- Include the intended pack roots and required files; exclude temporary files, caches, secrets, unrelated sibling projects, and local-only paths.
- Ensure paths work inside the archive.
- Validate JSON and JavaScript using available appropriate tools.
- Check archive integrity after creation.
- Inspect the final archive listing and critical manifest content.
- Compare candidate files to baseline and explain unexpected deltas.

## Release gate
Block a ready-to-release recommendation when there are unexplained deletions, broken manifest dependencies, broken resource references, syntax errors, missing critical resources, or unaddressed high-confidence regressions. If runtime tests were not available, label the candidate `static checks passed; runtime not verified` rather than fully tested.

## Changelog and report
Report version, baseline, intended changes, files changed, checks actually run, results, runtime status, known risks, and pack installation order/dependencies. Preserve rollback ability. If user approval is required, wait before final release/publication while still delivering a candidate for review.
