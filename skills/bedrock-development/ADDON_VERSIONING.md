# Minecraft Bedrock add-on versioning

This policy applies to **the user's individual Minecraft Bedrock add-on project**, not to the Minecraft Bedrock Engineer Plugin Creator package. Keep these version tracks separate.

## Three-part meaning

Use `MAJOR.MINOR.PATCH` with these exact meanings:

- **Major** — substantial feature release, a major new system, or significant structural/content expansion. `1.2.3 → 2.0.0`.
- **Medium** — meaningful addition or improvement within the existing add-on. `1.2.3 → 1.3.0`.
- **Fix** — bug fix, compatibility correction, small balance adjustment or minor repair. `1.2.3 → 1.2.4`.

These are increment categories, not literal numbers to restore on every update. Preserve the project's established version track. This policy permits normal SemVer components; it does not inherit the Plugin Creator package's separate one-digit component limit.

## Release-boundary rule

When a coherent changed add-on is ready to be delivered as an updated project or build, bump its version automatically unless the user explicitly says not to. Do not bump for inspection-only tasks or every intermediate edit during a multi-turn implementation. The classification must reflect the actual delivered change set rather than the number of changed files.

## Required manifest changes

For every BP/RP manifest in the coordinated release:

1. Bump `header.version` to the selected `MAJOR.MINOR.PATCH`, preserving the existing vector `[major, minor, patch]` or stable SemVer string representation.
2. Update each existing `modules[].version` to the same pack version.
3. Update the visible pack title in `header.name` to `<existing title> vMAJOR.MINOR.PATCH`. Replace an old trailing version suffix; do not duplicate it.
4. When `header.name` is a localization key, keep that key and update its matching value in `texts/*.lang` for every shipped language.
5. Update dependency versions for UUIDs that identify another pack included in the same release, especially BP → RP. Do not touch built-in Script API dependencies (`module_name` such as `@minecraft/server`).

Preserve pack and module UUIDs. Never change manifest `format_version` or `header.min_engine_version` merely because the add-on release version changed. Those describe different compatibility tracks.

If BP and RP versions are inconsistent before a release, stop and explain the mismatch instead of guessing. Independent pack versions require explicit project policy.

## Changelog and verification

Record old/new versions, change category and reason, affected packs, manifest/localization paths, compatibility impact and migration notes. Re-open the files after edits. Validate JSON, title suffixes, header/module/dependency alignment and unchanged UUIDs/API dependencies. Report Minecraft import/rendering/runtime as `NOT RUN` unless it was tested.

See `../addon-versioning/SKILL.md` for the operational workflow and the bundled dry-run/apply utility.
