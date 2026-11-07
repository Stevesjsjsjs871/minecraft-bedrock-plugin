# Bedrock reference corpus — intake report (2026-11-07)

## Scope and method

Ten user-provided ZIP archives were inventoried read-only. In 2.3.0, the hardened indexer reran CRC/decompression and namespace validation on all ten pinned input streams; no unsafe paths, duplicate/case/Unicode collisions, symlinks, special files or file/directory conflicts were found. No archive was extracted and no embedded script was executed. The machine-readable index is `reference-corpus-index-2026-11-07.json`.

The index contains **110 manifest records** across the ten archives. It is a provenance/manifest inventory, not a correctness certification. Branch ZIPs do not embed a Git commit SHA; their archive SHA-256 values identify the exact supplied bytes, while the upstream commit remains unknown.

## Official reference sources

| Archive | Files | Dirs | Entries | Manifests | What it contributes | Authority boundary |
|---|---:|---:|---:|---:|---|---|
| Mojang `bedrock-samples` main snapshot | 22,327 | 612 | 22,939 | 3 | Vanilla BP/RP resource families, JSON and asset layout; both root pack manifests declare `min_engine_version` 1.26.60 | Official schema/example evidence for this snapshot, but main branch is not a pinned release commit |
| Microsoft `minecraft-samples` | 1,666 | 641 | 2,307 | 77 | Starter add-ons, BP/RP pairings, legacy and modern manifests, entities, UI, assets and script-enabled examples | Official sample repository; individual samples span many game/API versions and are not one compatibility baseline |
| Microsoft `minecraft-scripting-samples` | 303 | 108 | 411 | 19 | Script API projects, custom components, commands, editor examples and module declarations | Official sample source; stable, beta and editor APIs must remain distinguished |
| Microsoft `minecraft-gametests` | 37 | 15 | 52 | 2 | GameTest pack manifests and test code | Official test examples; both supplied manifests declare `@minecraft/server` 1.13.0-beta and `@minecraft/server-gametest` 1.0.0-beta |

### Version observations (not a compatibility matrix)

- The Mojang main snapshot's BP and RP manifests both declare `min_engine_version: [1, 26, 60]`.
- Microsoft sample manifests are intentionally heterogeneous: the supplied archive includes older examples and modern samples. Do not promote a version merely because it appears in a sample.
- The scripting samples include stable versions such as `@minecraft/server` 2.0.0 and 2.1.0, plus beta/editor declarations. Each dependency must be checked against the requested target build and official versioned documentation.
- The GameTests repository snapshot uses beta dependencies in both inspected manifests. It is evidence for the test harness shape, not a stable runtime recommendation.

## Community and user-supplied reference packs

- `minecraft-robot-addon-main.zip`: small BP/RP entity example with a Blockbench `.bbmodel`; README states MIT. Useful for tracing a compact entity → client entity → geometry/texture/animation chain. Do not assume the example's declared minimum version proves compatibility with newer game builds.
- `MinUI-main.zip`: experimental UI tooling/framework, MIT. Treat as a community implementation, not vanilla UI schema authority; inspect compiler/runtime assumptions before recommending it.
- `actions-stuff-1-12.mcpack.zip`: RP-only inventory, with `min_engine_version` 1.26.40. License/provenance was not established from the inspected manifest; no assets are redistributed.
- `FURNITURE Add-On (addon).mcaddon.zip`: BP/RP pair, one script module, `@minecraft/server` 2.4.0 and `@minecraft/server-ui` 2.0.0. Useful as a large real-world structural and reference-graph stress corpus; no license conclusion is made here.
- `CinematicInteractions_Bedrock_v1_24_1.mcaddon.zip`: BP/RP + JS. Its embedded license notice explicitly restricts redistribution/reposting without permission. Use only as read-only structural evidence; do not copy code/assets into MBE or derivative packs.
- `CreateMovement.mcaddon`: BP/RP + scripts, declares `@minecraft/server` 2.3.0 and `@minecraft/server-ui` 2.0.0. License/provenance was not established from the inspected manifest; no code/assets are redistributed.

## Recommended use in MBE

1. Use Mojang samples for vanilla resource layout and version-matched structural comparisons; retain both the pinned 1.26.50.4 index and this separate 1.26.60-labelled main-branch snapshot.
2. Use Microsoft samples for starter-pack conventions and examples across multiple historical versions. Always inspect the specific manifest and source path.
3. Use scripting samples and GameTests to design API review and test scenarios, not to infer stable API support from beta samples.
4. Use community/user packs as adversarial or real-world audit fixtures: dependency closure, UI/animation/model reference graphs, scripts, large resource trees and packaging edge cases.
5. Keep original archives outside the plugin package. The package stores only metadata, paths, hashes and written technical observations—not third-party assets or source code.
6. Do not claim import, rendering, gameplay, multiplayer, Blockbench or performance validation from this static intake. Those remain `NOT RUN`.

## Reproducibility

Archive SHA-256 values and manifest summaries are in `reference-corpus-index-2026-11-07.json`. The 2.3.0 indexer revalidated all ten exact archive byte streams through a pinned descriptor: CRC/decompression PASS, path namespace PASS, SHA-256 PASS; no archive was extracted or executed. The index records `crc_test: PASS` and `hash_source: same_pinned_descriptor`. Re-run intake for any changed or newly supplied archive.

## Selected navigation paths (source archives remain external)

- Microsoft compact robot chain: `minecraft-samples-main/add_entity_robot/full/robot_example_full_behavior/entities/robot.json`, paired with `.../robot_example_full_resources/entity/robot.entity.json`, `.../models/entity/robot.geo.json`, `.../animations/robot.animation.json` and the behavior animation controller. The matching minimal pair is under `add_entity_robot/min/`.
- Microsoft scripting sample: `minecraft-scripting-samples-main/build-challenge/scripts/main.ts` plus `Challenge.ts`, `ChallengePlayer.ts`, `Team.ts` and the `behavior_packs/buildchallenge/manifest.json` declaration.
- Microsoft GameTests: `minecraft-gametests-main/js-gametests/behavior_packs/JsGameTests/scripts/ChallengeTests.js`, `CommandTests.js`, `MobBehaviorTests.js` and `manifest.json`.
- Community robot source: `minecraft-robot-addon-main/Robot_BP/entities/robot.json`, `Robot_RP/entity/robot.entity.json`, `Robot_RP/models/entity/robot.geo.json`, `Robot_RP/animation/robot.animation.json`, and `robot.geo.bbmodel`.
- MinUI's experimental compiler/linter examples include `MinUI-main/lib/compile.js` and `MinUI-main/lib/lintjsonui.js`; these are not vanilla schema authority.
- The Furniture archive contains large families of BP animation controllers and blocks; the Cinematic archive has a multi-file JS module tree; Create Movement contains extensive animation resources and scripts. Use these as graph/scale audit fixtures only, subject to license and provenance limits above.

## 2.3.0 real-project static audit

Five available real archives were processed read-only by `skills/automated-validation/scripts/bedrock_audit.py`; source hashes were preserved. All five archive integrity/path checks passed and all five reports explicitly mark Minecraft runtime `NOT RUN`.

| Archive | Indexed files | Parsed JSON | JSON mode | Findings | Recommendation |
|---|---:|---:|---|---:|---|
| Actions and Stuff 1.12 | 10,653 | 12 | 12 strict | 524 INFO/LOW | STATIC CHECKS PASSED — RUNTIME NOT VERIFIED |
| Furniture Add-On | 5,037 | 3,667 | 3,638 strict / 29 JSONC / 2 duplicate-key failures | 19 HIGH/HIGH, 3 MEDIUM/HIGH, 57 MEDIUM/MEDIUM, remaining INFO | HOLD |
| Cinematic Interactions 1.24.1 | 183 | 98 | 98 strict | 72 MEDIUM/MEDIUM, remaining INFO | REVIEW |
| Create Movement | 1,013 | 705 | 705 strict | 26 MEDIUM/HIGH, 35 MEDIUM/MEDIUM, remaining INFO | REVIEW |
| Community Robot Add-on | 11 | 6 | 6 strict | 1 MEDIUM/MEDIUM, 1 INFO/MEDIUM | REVIEW |

These are static tool findings, not independent proof of in-game defects. Furniture's two duplicate-key JSON files are exact parser findings: `FURNITURE Add-On BP/entities/xp/furniturepack/deco/small_fountain.json` (`minecraft:is_sheared`) and `FURNITURE Add-On RP/animations/func/aquarium.animation.json` (`head_ml`). JSONC comments/trailing commas were accepted conservatively in 29 other files. Create Movement's 26 high-confidence MEDIUM findings concern negative cube dimensions in selection/funnel geometry and need target-version/schema review before edits. Cinematic Interactions has numerous player-resource references likely supplied by vanilla/external resources; these remain unresolved static references, not confirmed defects.

No benchmark precision/recall score is reported: there is no independently exhaustively labelled ground-truth set for these five archives. The real-pack benchmark remains `INVENTORY_ONLY` / unscored.
