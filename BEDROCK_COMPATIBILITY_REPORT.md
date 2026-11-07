# Bedrock Compatibility and Static Technical Audit — 2.3.0

## Reference versions
- Pinned Mojang sample corpus: 1.26.50.4; root manifests in that pinned sample set declare `min_engine_version` 1.26.50.
- Supplied Mojang `main` snapshot: both root pack manifests declare `min_engine_version` 1.26.60; no commit SHA is embedded, so this is a mutable snapshot identified by its archive SHA-256.
- Microsoft sample repositories are heterogeneous; they are not one compatibility baseline.
- Supplied GameTests manifests declare beta `@minecraft/server` 1.13.0-beta and `@minecraft/server-gametest` 1.0.0-beta. Treat as beta test-harness evidence, not stable recommendation.
- Script samples contain stable and beta/editor API declarations; every project must be checked individually.

## Real-pack static audit
Five archives were read-only audited. Exact counts/findings are recorded in `skills/reference-pack-corpus/references/REFERENCE_CORPUS_REPORT_2026-11-07.md`. Furniture contains 29 JSONC files accepted by the parser and two duplicate-key failures. Create Movement has 26 negative cube-size findings that require exact geometry-schema review; they are not auto-fixed. Cinematic Interactions contains many unresolved player references likely supplied externally/vanilla; not confirmed errors. Actions and Stuff reports low-confidence path hints only. Robot Add-on has one medium-confidence unresolved render-controller identifier.

## Coverage and limits
- Manifests: JSON shape, UUID uniqueness, module/dependency references are statically checked by the auditor.
- Geometry: conservative structure/vector/cube/UV checks; no full Bedrock schema validator. Negative dimensions may be intentional and remain review items.
- Animation/controllers: selected shape and literal resource graph checks; no Molang evaluation or engine controller simulation.
- Textures: file/path inventory and existing PNG utilities; no full semantic texture correctness proof for these five archives.
- Script API: archive index records manifest dependencies; the generic auditor does not perform full AST/type analysis or exact-version API compatibility. Embedded scripts were not executed.
- UI/PBR/Fog: selected recognizable JSON/resource reference heuristics only; dynamic bindings and engine semantics are incomplete.
- Runtime: Minecraft import, Content Log, render, gameplay, multiplayer and FPS tests are NOT RUN.

Do not infer compatibility merely because a manifest declares a version or a static JSON parser succeeds.
