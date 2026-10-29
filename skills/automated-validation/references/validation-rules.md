# Validation rules and interpretation

## Executed checks
- ZIP CRC integrity, unsafe/duplicate paths, JSON parsing and SHA-256 baseline diffs.
- Manifest/header/module UUID checks and conservative in-archive dependency context.
- Geometry identifier duplicates; bone name duplicates, parents, cycles and transform vectors.
- Cube origin/size/pivot/rotation shape and selected box/face UV structures.
- Animation definition shape and `animation_length` sanity.
- Selected client-entity geometry/animation/render-controller/texture references and literal file paths.

## Limits
The helper is a conservative static analyzer, not the Minecraft engine's complete schema validator. It does not interpret Molang expressions, prove animation timing, infer every texture lookup convention, run JavaScript, check every UI lookup rule, launch Minecraft, or establish visual correctness. External packs can intentionally satisfy references absent from the candidate archive. Face UV and animation syntax vary by resource format/version, so findings for less common forms require review.

## Interpretation
- `BLOCKER` / `HIGH` should require strong evidence; path/texture heuristics remain `INFO`.
- Do not automatically correct suspicious dimensions, UVs, bone names or transforms. They may be intentional.
- Every unexplained removal from a baseline needs review; a removed file is not proof it is obsolete.
- Use matching official Creator docs and release-tagged Mojang samples for compatibility decisions.
- Minecraft runtime and visual tests remain `NOT RUN` unless actually executed.


## Reference graph 0.6.0
The report now includes `reference_graph` with indexed common definitions and evidence-backed edges. Edges distinguish `resolved`, `unresolved`, `ambiguous`, `dynamic_or_expression`, and `heuristic_unresolved`. Identifier domains are kept separate. An unresolved in-archive reference is not automatically proof of a runtime failure: external packs, dynamic expressions, aliases and unsupported resource conventions can account for it. The graph currently covers common client-entity geometry/animation/controller references, client-entity texture aliases and selected literal render-controller references. It is not a complete Bedrock resource graph; UI, localization, recipe/loot usage and all Script API references remain partial/not comprehensively indexed.


## Reference graph 0.6.3 coverage
The graph indexes common geometry, animation/controller/material, entity/item/block identifiers and a partial set of attachable, UI, localization and recipe file/key references. Every graph report includes a per-domain definition count and coverage declarations. `resolved` means exactly one indexed in-archive candidate, not engine proof; `unresolved` means no indexed in-archive definition; `ambiguous` means more than one indexed candidate; `dynamic_or_expression` and `alias_or_heuristic` explicitly defer semantic resolution. UI and localization checks are heuristics and must not be escalated to confirmed failures without version-matched evidence. Recipe/loot usage and Script API edges remain incomplete; external packs are not resolved.
