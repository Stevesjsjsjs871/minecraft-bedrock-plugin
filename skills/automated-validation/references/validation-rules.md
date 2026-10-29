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

## Reference graph
The graph indexes common geometry, animation/controller/material, entity/item/block identifiers and a partial set of attachable, UI, localization and recipe file/key references. Every graph report includes per-domain definition counts and coverage declarations. `resolved` means exactly one indexed in-archive candidate, not engine proof; `unresolved` means no indexed in-archive definition; `ambiguous` means more than one indexed candidate; `dynamic_or_expression` and `alias_or_heuristic` explicitly defer semantic resolution. UI and localization checks are heuristics and must not be escalated to confirmed failures without version-matched evidence. Recipe/loot usage and Script API edges remain incomplete; external packs are not resolved.

## Archive resource limits 0.7.0

Before payload reads, the shared `archive_safety.py` rejects compressed archives larger than 256 MiB, archives containing more than 50,000 entries, any file member larger than 128 MiB, and cumulative declared uncompressed payloads larger than 512 MiB. These are resource-safety limits, not Minecraft format limits. Archive CRC checking follows only after this preflight. The analyzer CLI and MCP wrapper use the same implementation.

## Recommendation gate 0.7.7

`HOLD` is reserved for BLOCKER/HIGH findings. If there are MEDIUM-severity findings but no BLOCKER/HIGH, the report recommendation is `REVIEW`; an otherwise clean static analysis still does not establish runtime correctness. The report schema includes this recommendation state.

## Report contract 0.7.0

Each synthetic regression report is validated against `report-schema.json` using JSON Schema Draft 2020-12. Schema validation checks structural consistency; it does not prove that a detected game-resource reference is semantically correct or runtime-valid.


## Graph contract 0.7.1

The valid synthetic pack is compared against `skills/regression-evals/references/golden-graph.json`. The test checks exact stable edge projections (source file, source pointer, reference kind, referenced value, target domain and status), edge count and status counts. Domain filtering treats an explicit `target_domain` as authoritative; path/name heuristics are used only when that field is absent. This reduces cross-domain leakage but does not increase semantic coverage beyond the analyzer's declared reference inventory.


## Animation references 0.7.2

Animation-controller `initial_state` and literal transition target keys are compared only with the state map in the same controller. Molang condition values are never evaluated. Missing literal targets are reported with source evidence. Animation bone names are compared with a global inventory of in-archive geometry bones; absent names are only `INFO`/`LOW` because the analyzer cannot prove which geometry is active or whether an external/omitted geometry supplies the bone. No asset is modified automatically.


## UI and localization checks 0.7.3

The analyzer checks common UI JSON object shape, the optional `namespace` type, `ui_defs` array and entry types, and path candidates within the archive. Path candidates use common pack-root/UI-root and source-relative interpretations only. Missing/ambiguous paths are INFO/LOW heuristics because external packs, loading precedence and every UI path convention are not modeled.

For `.lang` files, an empty key is reported as INFO and a duplicate key is reported only when repeated within the same file; repeated keys across different locale files are expected and are not duplicates for this rule. Simple literal `$key` strings in UI `text` properties are checked against all indexed `.lang` files and missing keys are INFO/LOW. Variable-based text, Molang, `.locres`, external translations, control references and actual UI rendering are not proven.


## UI imports and control-name heuristics 0.7.4

The UI checker reports exact repeated `ui_defs` strings and records recognized `ui_defs` imports as resource-graph edges using common path candidates. It also flags certain literal `extends`, `control_name`, or string-list `controls` values when they look namespace-qualified and their namespace does not occur in indexed UI JSON. This is intentionally narrow: UI declarations may use implicit namespaces, inherited/global definitions, version-specific naming and external packs. Results remain INFO/LOW; this does not validate the full control schema, variables, binding expressions, or actual rendering.

The resource graph records literal `$key` values found in UI `text` properties as edges to indexed localization keys. Missing in-archive keys are low-confidence heuristics because external or dynamic translation sources may exist.


## BP/RP component and loot-table checks 0.7.7

The allowlisted component pass reads the documented `minecraft:loot.table` field and resolves common in-archive candidates; recognizable literal string values are also retained for compatibility. Loot-table JSON receives conservative shape checks for the root object, `pools`, each pool's `entries`, roll counts and entry weights. Recognized nested entries of type `loot_table` become graph edges; cycles are reported only when their links resolve uniquely to in-archive files. These findings are evidence of a recursive link in the indexed archive, not a simulation of the game loot engine. Dynamic values, external packs, complete version-specific constraints, conditions and functions are not evaluated. `minecraft:icon` values remain aliases, not assumed direct texture paths.




## Real-pack benchmark discipline 0.7.8

A real-pack score is valid only when each scored case is tied to the exact tested artifact hash and independently reviewed labels. The evaluator validates the benchmark manifest and each audit report against JSON Schema, checks candidate SHA-256, and can pin the analyzer version. Any invalid scored report invalidates aggregate metrics; cases marked pending are skipped explicitly. Precision/recall/F1 apply only to reviewed cases and explicitly selected `scored_rules`, matching exact `(title, path)` signatures. These metrics do not count true negatives, measure all possible issue classes, or prove Minecraft runtime correctness. No real-pack metric should be published until a real corpus has been collected and labeled.

## Authoring boundary and MCT handoff 0.7.8

At the 0.7.8 release point, the bundled MCP server had seven local stdio, read-only tools. That release did not scaffold or modify content and did not invoke Creator Tools. Version 0.8.0 adds the read-only `diff_packs` summary; it still does not scaffold or modify content or invoke Creator Tools. The `creator-tools-bridge` skill describes a guarded handoff to an already-installed MCT CLI where the host provides a local shell. Any future writer wrapper requires an explicit output path, strict command allowlist, argv-based subprocess invocation, bounded execution/output, path validation, explicit authorization and destructive tool annotations. Never auto-install packages or accept the Minecraft EULA.

## Benchmark input safety 0.7.9

Benchmark artifacts and reports are resolved within their configured input roots. Symlinks escaping those roots are rejected. Invalid UTF-8 is reported as invalid input, not an unhandled exception. Reviewed expected findings must have unique exact `(title, path)` fingerprints so ambiguous labels cannot skew precision/recall.


## Pack-to-pack regression summary 0.8.0

The MCP `diff_packs` tool summarizes baseline file changes and compares current static findings and resource-graph edges against the baseline. Finding identity uses exact `(title, path)`; severity changes are reported separately. A reference regression means an edge resolved in the baseline is unresolved/ambiguous in the candidate, and a new unresolved edge is only a candidate finding. These are change indicators rather than engine proof. Lists are bounded to 100 displayed examples with the total count retained. The tool is read-only and always reports runtime `NOT RUN`.
