# Individual Minecraft Bedrock add-on versioning

This policy is for the add-on being developed, not the Minecraft Bedrock Engineer plugin package. For every completed coherent change set delivered as an updated add-on, classify the work as major, medium or fix and bump the appropriate `MAJOR.MINOR.PATCH` component unless the user explicitly says not to.

The version must be visible in the Minecraft pack title (`header.name`, or matching `texts/*.lang` translation when `header.name` is a localization key) and in `header.version` for every released BP/RP manifest. Also align existing `modules[].version` and dependencies that point to the other released pack. Preserve UUIDs, `format_version`, `min_engine_version` and built-in Script API dependency versions.

Examples: major `1.2.3 → 2.0.0`; medium `1.2.3 → 1.3.0`; fix `1.2.3 → 1.2.4`. Preserve the project's established alternative scheme where documented. This is separate from the Plugin Creator package version policy in `VERSIONING.md`.

See `skills/addon-versioning/SKILL.md` for the full workflow and the dry-run/apply script.
