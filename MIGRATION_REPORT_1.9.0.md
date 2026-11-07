# Domain-Based Hybrid migration report — 1.9.0

## Inventory snapshot
- Base archive: local verified 1.8.0 source ZIP, 195 files, 59 Skills.
- Live Plugin Creator source separately confirmed: USER scope, PRIVATE discoverability, version 1.8.0, release `pluginrel_6ae5c0a3617881918fc109c040d65a28`.
- Existing 59 Skills are retained; no mass skill merge or removal was performed.
- Main domains identified: Core/execution, BP authoring, RP/UI, entities, geometry/UV, animation, texture/visual resources, Script API, Mojang research, reference-pack analysis, audit/regression, validation and release governance.
- Reference JSON/examples and bundled Python scripts remain at their existing paths; this update does not move files or change their imports.

## Changes in this candidate
- `skills/bedrock-engineer-core/SKILL.md`: rewritten as a Domain-Based Hybrid coordinator with explicit routing table, complete-feature rules, provenance and evidence requirements.
- `skills/skills-first-execution/SKILL.md`: clarifies domain composition, shared baselines and test evidence ordering.
- `skills/geometry-uv-engine/scripts/test_png_engine.py`: fixes `sys.path` precedence so canonical tests import canonical `png_engine.py` rather than the compatibility shim in the Geometry/UV folder.
- `skills/version-governance/SKILL.md`, `VERSIONING.md`: current live release evidence updated from stale 1.7.3 reference to verified 1.8.0; 1.9.0 successor noted.
- `README.md`, `CHANGELOG.md`, `VERSION_HISTORY.md`, `RELEASE_NOTES_1.9.0.md`, both manifests and `VERSION`: synchronized to 1.9.0.

## Preserved
- Plugin ID, name, description, USER scope, PRIVATE discoverability.
- Exactly 12 default prompts with exact text and ordering.
- All 59 Skills, all their references/scripts, and the bundled Mojang sample index.
- Historical server-side source tree, kept inert and excluded from active capability routing.

## Deliberately not done
- No legacy server source or tests deleted: import graph spans multiple modules; removing them without migrating dependency clusters would be unsafe.
- No claims of adding new runtime integrations. Skills do not themselves provide tools or file access.
- No Minecraft runtime or Blockbench test; the target runtime was unavailable.
- GitHub sync not performed in this update; repository source may differ from Plugin Creator package.
