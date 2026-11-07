# Minecraft Bedrock 1.26.50 — checked compatibility notes

Source checked 2026-10-31:
https://learn.microsoft.com/en-us/minecraft/creator/documents/update1.26.50?view=minecraft-bedrock-stable

This is a change-note index, not a substitute for the target-version schema or runtime test.

## Changes relevant to add-on engineering

- Entity JSON using `format_version` 1.26.50 or later is subject to stricter validation in a number of entity components, AI goals and `minecraft:projectile`.
- `minecraft:interact` fields `interactions`, `spawn_entities`, and `play_sounds` accept arrays only for the stated format version.
- `minecraft:projectile` no longer accepts alternate field names for the stated format version.
- The release notes enumerate stricter schemas for `minecraft:anger_level`, `minecraft:barter`, `minecraft:boss`, `minecraft:collision_box`, `minecraft:damage_over_time`, `minecraft:exhaustion_values`, `minecraft:flocking`, `minecraft:game_event_movement_tracking`, `minecraft:grows_crop`, `minecraft:home`, `minecraft:trade_table`, `minecraft:physics`, `minecraft:tamemount`, `minecraft:preferred_path`, `minecraft:instant_despawn`, and `minecraft:insomnia`.
- `minecraft:can_stand_on_powder_snow`, `minecraft:freezing_immune`, `minecraft:freezing_vulnerable`, and `minecraft:block_movement_slowdown_immunity` are documented entity additions/changes.
- Horizontal multi-blocks are released; `minecraft:sound` block component is stable for format versions 1.26.20 or later.
- `@minecraft/server` v2.10.0 and `@minecraft/server-ui` v2.2.0 are stable in this release. `@minecraft/server-graphics` v1.0.0 is stable and requires `@minecraft/server` v2.3.0 or later. The same release notes identify later versions as beta; do not conflate them with stable.

## Engineering response

Do not automatically raise every existing entity or block format version. When a project opts into `format_version` 1.26.50+, audit every instance of the stricter components and fields before changing the version. For scripts, set the dependency versions to those supported by the actual target game and keep beta APIs clearly labelled.
