# Minecraft Bedrock Engineer 2.2.0 — Candidate

## Scope
This release adds multi-source reference corpus intake and provenance-aware sample discovery. It does not embed source archives, third-party code, vanilla assets, textures, sounds, models or UI resources.

## Included sources
- Mojang Bedrock Samples main snapshot (root manifests declare min_engine_version 1.26.60; upstream commit SHA unavailable).
- Microsoft Minecraft Samples, Scripting Samples and GameTests.
- Community Robot Add-on and experimental MinUI.
- Four user-supplied packs: Actions RP, Furniture Add-On, Cinematic Interactions and Create Movement.

## Safety and license handling
Original archives remain external to the plugin. Cinematic Interactions contains an explicit restriction against redistribution without permission. Licenses/provenance for some user-supplied archives were not established. No source assets or code were copied into the plugin.

## Validation status
- ZIP CRC and path checks were completed during intake; all ten archives passed CRC and had no detected unsafe paths or symlink entries.
- New indexer unit tests: 4/4 PASS.
- Full Skills suite: 31/31 files and 515/515 cases PASS. Package integrity: 20/20 PASS. Architecture: 28/28 PASS.
- Follow-up code review found three hardening opportunities in the metadata indexer (duplicate-path rejection, pinned-descriptor hashing, file/directory collision rejection); none were present in the supplied source archives. See VALIDATION_REPORT_2.2.0.md.
- ChatGPT host/plugin integration: NOT TESTED. Minecraft import, rendering, gameplay, multiplayer and performance: NOT RUN.

## Publication
Candidate only. Live plugin remains unchanged until explicit publication approval.
