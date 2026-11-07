# Minecraft Bedrock Engineer 1.9.4

## Mandatory version-gate routing and helper hardening

- Extends `skills-first-execution` routing so existing and new add-on workflows explicitly select `addon-versioning` at the coherent delivery boundary, not only when a release skill is selected.
- Adds the same version gate to add-on creation, BP/RP bundle authoring, release artifact workflow and the cooking add-on specialist.
- Reinforces that a released update must show `vMAJOR.MINOR.PATCH` in the visible pack title and in each released manifest's `header.version`.
- Hardens the local version helper: requires a non-empty module list and preserves original file permission bits during atomic manifest/localization replacement.
- Adds focused tests for the new safeguards; 15 add-on versioning tests pass.

## Validation boundary

- Add-on versioning unit tests: PASS (15 tests).
- Python compile check: PASS.
- Candidate manifests, prompts, skill frontmatter and overlay ZIP: validated locally.
- Full package-integrity check: NOT RUN in this session because the complete base archive remains unavailable for download; use the plugin source reader/read-back for exact changed-file checks.
- Minecraft pack import, visible in-game title rendering, pack replacement behavior and gameplay: NOT RUN.
