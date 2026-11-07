# Minecraft Bedrock Engineer 1.9.3

## Coordinated Bedrock add-on versioning

- Adds a dedicated `addon-versioning` skill for the version of the user's Bedrock add-on, explicitly separate from the Plugin Creator package version.
- Makes versioning a required release-boundary step whenever a coherent changed add-on is delivered, unless the user explicitly opts out. It does not bump on inspection-only work or intermediate saves.
- Requires a `vMAJOR.MINOR.PATCH` suffix in the visible Minecraft pack title and the matching `header.version` in each released BP/RP manifest.
- Documents alignment for existing `modules[].version` and pack-to-pack dependency versions, including BP → RP.
- Handles localized `header.name` keys by preserving the key and updating the matching `texts/*.lang` translations.
- Explicitly protects UUIDs, `format_version`, `min_engine_version`, built-in Script API dependency versions and unrelated manifest fields.
- Adds a dependency-free dry-run/apply utility with path, symlink, duplicate-JSON-key and version-alignment guards.
- Adds 13 focused tests for fix/medium/major classification, vector/string version forms, visible names, localization, dependencies, UUID preservation, safety checks and dry-run behavior.

## Validation boundary

- Focused add-on versioning unit tests: PASS (13 tests).
- Python compile check: PASS.
- Full package-integrity check: NOT RUN in this session because the complete archive download did not succeed; existing package inventory and changed source were inspected through Plugin Creator's text reader.
- Minecraft import, pack replacement behavior, in-game title rendering and gameplay: NOT RUN.
