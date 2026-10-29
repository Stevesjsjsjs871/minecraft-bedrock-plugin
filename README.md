# Minecraft Bedrock Engineer — 0.9.3

## 0.9.3: optional Minecraft Creator Tools integration

- Adds read-only `creator_tools_status` to detect the installed Node.js, npm and MCT CLI without installing packages or calling `npx`.
- Adds `creator_tools_catalog` to return actual gallery template IDs/types from the installed MCT CLI. Gallery loading is delegated to MCT and may use its own cache or remote source.
- Adds `validate_with_mct`, which validates a bounded temporary copy of the selected project and directs reports to temporary storage; the source project is not used as the CLI working copy.
- Adds `create_entity_with_mct`, requiring an explicit gallery template whose type is MCT `entityType`. It stages generation, hashes the original BP/RP files, refuses changed/deleted existing files, runs our static baseline diff, and merges only new pack files when no new HIGH/BLOCKER findings or severity escalations are present.
- Never uses a shell, `npx`, automatic installation or deployment. MCT is optional. The official CLI notes that some operations may still access the network even when `--offline` is supplied.
- Tests cover tool schemas, unavailable-CLI behavior, template/path validation and staged merge safety. MCT is mocked in unit tests; runtime CLI behavior and Minecraft import/rendering remain `NOT RUN`.

## 0.9.2: coordinated custom entity authoring

- Adds the write-capable `create_addon_entity` tool: one validated operation creates the BP entity, RP client-entity, geometry model and render controller with consistent identifiers.
- Verifies the existing BP/RP scaffold and version link before writing; validates optional texture paths and PNG signature; refuses any output collision and removes partial outputs if a write fails.
- Never creates fake textures. Without a supplied PNG the output explicitly reports `texture_file_not_created` and the expected path.
- Adds regression tests for all cross-file identifiers, provided PNG mapping, path safety, collisions, no partial output and MCP annotations.
- Synchronizes package, MCP server, tests and CI at 0.9.2. Gameplay, entity rendering and AI behavior in Minecraft remain `NOT RUN`.

## 0.9.1: sample-index resilience and reproducible checks

- Fixes source-checkout failures when the generated compressed Mojang sample index is not present in GitHub.
- Sample search/read fall back to a searchable, hash-verified index built from curated text examples already shipped in the repository.
- Responses expose index_mode=curated_fallback and the actual curated entry count; the fallback is not represented as the full 22,252-entry index.
- Adds regression coverage for fallback mode and makes the result-cap test independent of whether the full generated index is installed locally.
- Synchronizes package, server and CI version markers to 0.9.1. Minecraft gameplay/runtime tests remain NOT RUN.

## 0.9.0: shaped and shapeless recipe authoring

- Adds the write-capable `create_addon_recipe` tool for crafting-table recipes using the version-labelled Mojang Samples recipe format (`format_version` `1.20.10`).
- Supports shaped patterns and explicit symbol-to-ingredient maps, as well as shapeless ingredient lists; supports output counts from 1 to 64.
- Validates recipe names, namespaced identifiers, pattern symbols, equal row widths, key-map coverage, project BP/RP manifest dependency and target-game version before writing.
- Custom result/ingredient identifiers must already exist in the project's BP item/block definitions; vanilla `minecraft:` identifiers are accepted. The tool refuses malformed/ambiguous custom resource definitions and never overwrites an existing recipe.
- Adds unit tests for shaped/shapeless output, unknown custom identifiers, malformed patterns, collision protection and write-capable tool metadata. This is static file generation; actual recipe unlocking and crafting in Minecraft remain `NOT RUN`.


## 0.8.9: first generated block slice

- Adds `create_addon_block` to generate a starter BP block definition and a matching RP `terrain_texture.json` mapping.
- Merges new mapping entries into existing valid terrain atlases, preserving unrelated atlas metadata and entries; rejects malformed atlases and slug collisions before writing the BP file.
- Validates the linked BP/RP scaffold, target version, expected texture path, PNG signature, path containment and symlink safety.
- Adds regression tests for block creation, atlas merge/preservation, collision failure and write-tool annotations.
- A real PNG remains required for correct in-game rendering; no Minecraft runtime test is claimed.

## 0.8.8: safe shared item resource merging

- `create_addon_item` now adds an item to an existing valid RP `item_texture.json` and `en_US.lang`, preserving unrelated atlas metadata, mappings, comments and translations.
- Rejects malformed atlas JSON, malformed localization lines, duplicate localization keys, colliding atlas keys, and unsafe/non-regular shared files before creating the item definition.
- Stages generated outputs and uses atomic same-directory replacement with rollback attempts if the write sequence fails.
- Adds targeted tests for merging a second item, collisions and malformed localization data.
- Still requires a real PNG for an in-game icon and marks Minecraft runtime `NOT RUN`.

## 0.8.7: first generated content slice — custom item

- Adds `create_addon_item` for an existing clean BP/RP scaffold. It creates one namespaced BP item JSON, a Resource Pack `textures/item_texture.json` mapping, and an `en_US.lang` display-name key.
- Checks the target game version against both manifests and verifies the BP dependency references the actual RP header UUID.
- Limits writes to a validated existing project directly under the configured workspace; refuses unsafe paths, symlinks and conflicting files rather than overwriting.
- Does not generate a PNG. A supplied texture must exist at the expected RP path and have a PNG signature; in-game appearance remains `NOT RUN`.
- Adds tests for item definition/atlas/localization, collision protection, unsafe paths and write-capable annotations.
- Existing atlas/localization merge scenarios are refused until a dedicated merge operation is implemented.

## 0.8.6: Mojang samples index and example search

- Uses the user-provided Mojang `bedrock-samples` archive labelled 1.26.50.4 as a version-specific reference corpus. The exact uploaded archive SHA-256 is recorded in the sample metadata.
- Adds an indexer that can generate a compact index of 22,252 source-archive entries, with resource-category labels, paths, sizes, hashes and selected literal identifiers. The generated compressed index is an optional local artifact and is not committed in this source checkout.
- Adds `search_mojang_samples` for offline search and `read_mojang_sample` for curated example excerpts or a specific indexed text file from the user's source ZIP placed inside the configured workspace.
- Adds a safe index rebuild script. It validates archive bounds and raw member paths, rejects traversal/absolute/non-canonical paths, does not extract or execute archive members, and can write deterministic gzip output.
- Bundles a small set of representative manifests, item/block/recipe definitions, entity/geometry/animation examples, and offline documentation pages. It does not embed the full vanilla ZIP or binary vanilla assets.
- Updates the new-project workflow to search version-labelled examples before creating the first content slice. Samples remain references: adapt namespaces and dependencies, remove undocumented vanilla-only fields, and don't assume 1.26.50.4 automatically proves compatibility with every 1.26.50 runtime.
- Static and unit tests cover search ranking/filtering/output caps, source index and sample hashes, unsafe path rejection, bounded indexed-archive reads, deterministic index output, and curated fallback. The full generated index still requires the original ZIP and a local indexer run. Minecraft runtime remains `NOT RUN`.

## 0.8.5: start add-on projects from scratch

- Shifts the primary workflow from auditing existing packs alone to creating a new add-on project first, then developing and auditing it incrementally.
- Adds the `create_addon_project` MCP tool. It creates a fresh project directory containing a Behavior Pack and a Resource Pack with unique UUIDs, linked BP→RP manifest dependency, versioned `min_engine_version`, standard content directories, `README.md`, and `PROJECT_STATE.md`.
- Restricts the destination to one new child directory of the configured workspace; paths and existing targets are rejected. It does not overwrite an existing project.
- The scaffold intentionally creates no dummy entity, item, block, texture, model, animation, or script. Those are the next implementation slices and require feature-specific schemas/examples and checks.
- At 0.8.5, only `create_addon_project` wrote files, and it only scaffolded a new project directory; the other eight tools were read-only. Version 0.8.6 adds two read-only sample-reference tools. The project scaffold is a write-capable operation, and full content creation still depends on available writing tools or Mojang Creator Tools MCP/CLI; MCT is not silently installed or invoked.
- Adds tests for linked manifests, unique UUIDs, path validation, existing-directory protection, and tool annotations. Runtime tests remain `NOT RUN`.

## 0.8.4: canonical diff paths

- Tightens `diff_packs` path validation: report paths must use canonical `/` separators and cannot contain repeated/trailing separators, control characters, traversal segments, or alternate backslash spellings.
- Prevents separator aliases from bypassing duplicate and cross-bucket overlap checks.
- Adds focused regression tests for malformed separators and valid nested relative paths.
- This is static report validation only; it makes no claims about runtime pack behavior.

## 0.8.3: more reliable duplicate-finding severity deltas

- Finding comparison still uses exact `(title, path)` as its fingerprint, but now matches unchanged severity occurrences first before pairing remaining instances for escalation/de-escalation checks.
- When a fingerprint has duplicate occurrences, remaining pairs are chosen by minimum severity-rank distance, so a lower-priority instance is not incorrectly treated as the changed one when a closer match exists.
- Unmatched occurrences remain explicit as newly reported or no-longer-reported findings; aggregate counts still correspond to bounded detail lists.
- Adds regression tests for a shared exact-severity occurrence plus a changed duplicate, and for selecting the closest-severity instance when counts differ.
- `diff_packs` remains a static, read-only signal. This does not resolve finding semantics, replace independent labels, or prove Minecraft runtime behavior.

## 0.8.2: diff provenance and path hardening

- `diff_packs` rejects absolute, traversal, non-canonical and malformed file-diff paths before including them in a report.
- If SHA-256 values are available, the comparison's baseline hash is checked against the separately audited baseline report. Contradictory provenance now fails closed instead of producing a potentially misleading diff.
- The result exposes whether baseline artifact provenance was verified, with candidate and baseline hashes when available; legacy/synthetic reports without hashes are marked `not_available`, not falsely verified.
- Adds tests for traversal/absolute paths, baseline-hash mismatch, malformed hashes and the provenance result shape.
- Output remains bounded, read-only, and static-only. Minecraft runtime tests and real-pack accuracy metrics remain unrun.

## 0.8.1: diff regression semantics and input validation

- Treat repeated resource-graph edges as a multiset so one previously resolved edge does not incorrectly label every duplicate unresolved edge as a regression.
- Validate analyzer diff buckets for malformed paths, duplicates and overlap; reject malformed findings and graph-edge records instead of silently undercounting or reporting a false clean result.
- Include severity de-escalations in summary counts and route newly unresolved references to `REVIEW` rather than a static pass.
- Add regression tests for duplicate-edge matching, newly unresolved references, severity de-escalations, malformed findings and overlapping file buckets.
- The output remains bounded and read-only; static graph changes are still not proof of runtime failure. Minecraft runtime tests and a real-pack accuracy benchmark remain unrun.

## 0.8.0: high-level read-only pack diff

- Adds the eighth MCP tool `diff_packs`, producing a compact change report for two archives: added/removed/modified paths, new and no-longer-reported findings, severity escalations/de-escalations, and newly unresolved or regressed resource-graph edges.
- Each result includes archive hashes, analyzer versions, a conservative recommendation, explicit `runtime_status: NOT RUN`, and bounded sample lists (100 items per category). The tool never writes or patches pack files.
- The existing `compare_baseline` full report remains unchanged. Tests cover severity/finding/graph deltas, output caps, path guards, and byte-for-byte preservation of both input archives.
- `diff_packs` is a static change-impact summary, not proof that a changed resource breaks in Minecraft. At that release point, GitHub was not yet synchronized; the source repository was subsequently synced to 0.8.0. Later plugin releases require a separate source sync.


Minecraft Bedrock creation and verification toolkit. Create a clean linked BP/RP project first, build features in small tested increments, then use the static audit tools. Default target: 1.26.50 unless a task specifies another version.

## 0.7.9: benchmark evaluator safety and label integrity

- Rejects benchmark artifact/report symlinks that resolve outside their declared input directories.
- Reports malformed UTF-8 datasets and audit reports as INVALID instead of exiting with an uncaught decoding exception.
- Rejects duplicate expected finding fingerprints (exact title + path), which otherwise make independently reviewed labels ambiguous.
- Adds regression tests for path confinement, invalid UTF-8, and duplicate labels. No real-pack accuracy metrics are claimed. At that release point, GitHub was not yet synchronized; the source repository was subsequently synced to 0.8.0. Later plugin releases require a separate source sync.


Minecraft Bedrock creation, version-matched example search, and verification toolkit. Start with a clean linked BP/RP project, build features in tested increments, and audit results. Default target: 1.26.50 unless a task specifies another version.

## 0.7.8: benchmark methodology and Creator Tools handoff

- Adds a real-pack benchmark manifest schema and evaluator. Only independently reviewed cases and explicitly scoped finding titles are scored; reports must match the artifact SHA-256 and report schema.
- Reports precision, recall, F1 and severity mismatches without calling them overall accuracy. Missing reports, hash mismatches, invalid schema and pinned tool-version mismatches invalidate the whole run rather than silently disappearing from the denominator.
- Adds `audit-benchmark` workflow instructions for building a provenance/licensing-aware golden corpus and a `creator-tools-bridge` workflow for using an already-installed Mojang Creator Tools CLI when a compatible local execution host is available.
- Honest capability boundary: this release still ships seven read-only MCP tools. It does not add `scaffold_addon`, `scaffold_entity`, a writer tool, or an automatic subprocess wrapper for MCT. It never auto-installs MCT or accepts the EULA.
- The benchmark manifest is only a template: no real-pack corpus has been run and no precision/recall percentage is claimed. At that release point, GitHub was not yet synchronized; the source repository was subsequently synced to 0.8.0. Later plugin releases require a separate source sync.

## 0.7.7: loot-table structure and reference-cycle checks

- Adds conservative static checks for common loot-table pools, entries, roll counts and weights.
- Indexes literal nested entries of type `loot_table` as resource-graph edges.
- Detects cycles only when nested table references resolve uniquely to in-archive files; does not run conditions/functions or simulate the game engine.
- Removes duplicate component-indexing and duplicate regression assertion blocks left from the 0.7.6 patch, and consolidates duplicate documentation entries.
- Adds synthetic tests for a recursive two-table chain, malformed pool structure, and a 1,005-node reference chain. Medium-severity findings now produce a `REVIEW` recommendation rather than an all-clear. At that release point, GitHub was not yet synchronized; the source repository was subsequently synced to 0.8.0. Later plugin releases require a separate source sync.

## 0.7.6: conservative BP component-to-resource links

- Adds allowlisted graph edges for literal `minecraft:loot.table` component paths (with recognized string-form compatibility) and resolves them against common in-archive loot-table path candidates.
- Adds regression scenarios for a matching loot table and a missing loot table.
- Component checks remain partial; full versioned component validation and Minecraft runtime are not claimed. At that release point, GitHub was not yet synchronized; the source repository was subsequently synced to 0.8.0. Later plugin releases require a separate source sync.

## 0.7.5: resource graph localization edge hardening

- Records recognizable literal `$key` references from UI `text` properties as graph edges to indexed `.lang` definitions.
- Resolved keys point to in-archive `.lang` files; missing keys are marked `heuristic_unresolved` with LOW confidence, never a confirmed runtime defect.
- Adds regression coverage for both a present localization key and a missing key, and updates the golden graph projection accordingly.
- Keeps UI import/control checks and all archive/report safety boundaries; no game runtime or rendering success is claimed.
- At that release point, GitHub was not yet synchronized; the source repository was subsequently synced to 0.8.0. Later plugin releases require a separate source sync.

## 0.7.4: UI import graph and conservative control-reference checks

- Adds heuristic resource-graph edges for literal `ui_defs` imports, recording source file, JSON pointer, candidate paths, and resolution state.
- Detects repeated literal `ui_defs` entries with an INFO warning.
- Adds a narrow INFO/LOW check for recognizable namespace-qualified UI control references in `extends`, `control_name`, and string-list `controls` forms.
- Adds synthetic regression cases for import/control heuristics and literal localization graph edges; report schema and golden graph invariants remain enforced.
- The UI schema and runtime semantics remain partial; no Minecraft UI rendering test is claimed. At that release point, GitHub was not yet synchronized; the source repository was subsequently synced to 0.8.0. Later plugin releases require a separate source sync.

## 0.7.3: UI and localization static checks

- Adds conservative checks for the common UI JSON top-level shape, optional `namespace` type, and `ui_defs` value/entry shapes.
- Checks each literal `ui_defs` path against common pack-root/UI-root and source-relative candidates. Missing and ambiguous candidates remain `INFO`/`LOW` heuristics because external packs and engine path resolution are not modeled.
- Detects duplicate `.lang` keys within the same file (not across locales) and empty localization keys. Checks simple literal `$key` values in UI `text` properties against indexed `.lang` keys; unresolved lookups remain `INFO`/`LOW` heuristics.
- Adds regression cases for missing UI definition paths, duplicate per-file localization keys, and missing literal UI localization lookups. Regression reports continue to be checked against the JSON Schema and graph invariants.
- Does not parse the full Bedrock UI schema, validate control bindings/rendering, evaluate variable/Molang expressions, or claim UI runtime correctness. At that release point, GitHub was not yet synchronized; the source repository was subsequently synced to 0.8.0. Later plugin releases require a separate source sync.

## 0.7.2: animation/controller cross-resource checks

- Validates literal animation-controller `initial_state` and transition target state names against the state map in the same controller; Molang condition expressions are not evaluated.
- Compares animation bone targets with the global in-archive geometry bone inventory. Missing names remain `INFO`/`LOW` heuristics because the analyzer cannot reliably infer which geometry is active or supplied by external packs.
- Adds three synthetic regression cases for missing animation bones, missing controller transition states, and missing initial states; every report still goes through the report schema and graph invariants.
- Keeps the golden reference-graph projection and domain-filter isolation regressions from the 0.7.1 candidate.
- At that release point, GitHub was not yet synchronized; the source repository was subsequently synced to 0.8.0. Later plugin releases require a separate source sync.

## 0.7.1: graph contract and version-source hardening

- Makes explicit `target_domain` authoritative in MCP graph filtering so a UI path cannot leak into geometry or texture results merely because its text matches.
- Filters graph definitions by exact domain buckets instead of substring matching that could mix animations and animation controllers.
- Adds an exact golden projection for the valid synthetic graph, including source pointers, reference kinds, target domains, statuses, edge count and status counts.
- Makes both MCP and analyzer read their runtime version from the package-root `VERSION` file; the version-consistency test also checks release heading and both manifests.
- GitHub remains intentionally unchanged until planned 1.0.0 synchronization.

## 0.7.0: graph filtering and bounded report validation

- Fixes MCP resource-graph filters to use the analyzer's actual edge fields (`source_file`, `source_pointer`, `target_domain`, `reference_kind`, and `referenced_value`) and covers each filter with synthetic contract tests.
- Adds `archive_safety.py` as the shared source for compressed archive, member-count, per-member and cumulative uncompressed-size limits. The standalone CLI and MCP wrapper apply the same limits before member payloads are read.
- Adds `VERSION` as the single release-version source; manifests, MCP initialization and analyzer reports are checked against it in tests.
- Adds Draft 2020-12 report validation with `skills/automated-validation/scripts/validate_report.py` and schema checks for each regression fixture.
- This is a Plugin Creator package update only. GitHub remains unchanged until the planned 1.0.0 synchronization.

## Checks

The analyzer and MCP server use Python's standard library. Schema validation and regression tests require `jsonschema`:

```bash
python -m pip install jsonschema
python -m py_compile archive_safety.py server/mcp_server.py server/tests/test_mcp_server.py
python -m unittest discover -s server/tests -v
python -m py_compile skills/automated-validation/scripts/bedrock_audit.py skills/automated-validation/scripts/validate_report.py skills/regression-evals/scripts/regression_tests.py
python skills/regression-evals/scripts/regression_tests.py --auditor skills/automated-validation/scripts/bedrock_audit.py
python -m unittest discover -s skills/audit-benchmark/scripts -p 'test_*.py' -v
```

## 0.6.8: task-directed MCP workflow instructions

Clarifies tool selection: use archive inspection for structural/path questions, full audit for general pack review, baseline comparison for regressions, and focused tools only when relevant. Instructions stay in the MCP `initialize` response and `mcp-tools` skill; the portable plugin manifest is not extended with unsupported top-level fields. No remote endpoint is configured in this release.

## 0.6.7: MCP hardening and consistency checks

Aligns the MCP server version with the package release, caps archives at 50,000 entries in addition to the existing byte limits, and reports archive entry count separately from regular-file count so directory entries do not skew the listing truncation flag. Unit tests now check version/prompt parity, compact initialize instructions, structured tool errors and the member-count guard.

## 0.6.5: structured local MCP tools

Adds a read-only stdio MCP server exposing seven tools: `audit_pack`, `compare_baseline`, `get_resource_graph`, `validate_manifest`, `audit_geometry`, `audit_animation`, and `inspect_archive`. Tool schemas reject unknown fields, constrain the resource-graph domain, validate paths before file access, and advertise read-only/non-destructive annotations. The server wraps the existing static analyzer and returns structured JSON results and errors.

**Deployment boundary:** this package contains a local stdio MCP server, not a hosted remote service. Uploading this package does not deploy the server or make it available to ChatGPT web/mobile by itself. The target host must support and launch local stdio MCP plugins. For a remote ChatGPT integration, the tool implementation must be deployed behind a reachable and appropriately authenticated MCP endpoint and that endpoint must be configured; no fake endpoint is included.

## Existing workflows

- `bedrock-development`: safe BP/RP implementation and regression review.
- `project-audit`: evidence-backed static audits.
- `automated-validation`: bounded archive reads, manifest, geometry/bone/UV, selected animation/reference checks, report-schema validation, resource graph and baseline comparison.
- `regression-evals`: synthetic positive/negative fixtures for the analyzer report contract.
- `model-animation`: geometry, UV, texture, animation/controller and visual-debugging guidance.
- `resource-reference-graph`: definitions/uses and unresolved-reference interpretation.
- `research-versions`: version-specific research from verifiable sources.
- `project-continuity`: verified project state and continuity.
- `build-release`: candidate packaging and release gates.
- `mcp-tools`: MCP tool routing, schemas, safety boundaries and result interpretation.

## Local setup

Python 3.10+; analyzer/server are standard-library only, while JSON Schema report validation uses `jsonschema`. The root `mcp.json` launches `server/mcp_server.py` with `python3`. On Windows, use the Python executable supported by the host. The server's working directory defines the allowed archive workspace by default; set `MINECRAFT_BEDROCK_WORKSPACE` to an explicit directory if needed. Only `.mcaddon`, `.mcpack`, `.mcworld`, and `.zip` files inside that directory are accepted. Archives are inspected without extraction; pack scripts are never executed.

Passing these checks does not launch Minecraft and is not proof of runtime behavior. Resource-graph and UI/localization coverage is partial/heuristic.

## Official references

- [Minecraft Creator documentation](https://learn.microsoft.com/en-us/minecraft/creator/)
- [Mojang Bedrock samples](https://github.com/Mojang/bedrock-samples)
- [Bedrock Wiki](https://wiki.bedrock.dev/)

## Safety and privacy

The audit/reference MCP tools are read-only. The four creation tools (`create_addon_project`, `create_addon_item`, `create_addon_block`, `create_addon_recipe`) are write-capable but confined to a validated workspace scaffold; they refuse existing targets/collisions and never apply audit-driven deletion. The server does not extract pack archives, execute pack scripts, launch Minecraft, or make network requests. It returns structured errors on invalid input. Do not package tokens, credentials, private user data, or proprietary packs. This plugin remains private; the GitHub source repository has separate visibility controls.
