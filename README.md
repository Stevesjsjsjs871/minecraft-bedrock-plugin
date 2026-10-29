# Minecraft Bedrock Engineer — 0.8.0

Private skills-first engineering toolkit for Minecraft Bedrock add-ons. Default target: 1.26.50 unless a task specifies another version.

## 0.8.0: high-level read-only pack diff

- Adds the eighth MCP tool `diff_packs`, producing a compact change report for two archives: added/removed/modified paths, new and no-longer-reported findings, severity escalations/de-escalations, and newly unresolved or regressed resource-graph edges.
- Each result includes archive hashes, analyzer versions, a conservative recommendation, explicit `runtime_status: NOT RUN`, and bounded sample lists (100 items per category). The tool never writes or patches pack files.
- The existing `compare_baseline` full report remains unchanged. Tests cover severity/finding/graph deltas, output caps, path guards, and byte-for-byte preservation of both input archives.
- `diff_packs` is a static change-impact summary, not proof that a changed resource breaks in Minecraft. This 0.8.0 source is now synchronized to GitHub; source synchronization does not deploy a remote MCP endpoint.


Private skills-first engineering toolkit for Minecraft Bedrock add-ons. Default target: 1.26.50 unless a task specifies another version.

## 0.7.9: benchmark evaluator safety and label integrity

- Rejects benchmark artifact/report symlinks that resolve outside their declared input directories.
- Reports malformed UTF-8 datasets and audit reports as INVALID instead of exiting with an uncaught decoding exception.
- Rejects duplicate expected finding fingerprints (exact title + path), which otherwise make independently reviewed labels ambiguous.
- Adds regression tests for path confinement, invalid UTF-8, and duplicate labels. No real-pack accuracy metrics are claimed. At the time of this release, GitHub synchronization was deferred until 1.0.0.


Private skills-first engineering toolkit for Minecraft Bedrock add-ons. Default target: 1.26.50 unless a task specifies another version.

## 0.7.8: benchmark methodology and Creator Tools handoff

- Adds a real-pack benchmark manifest schema and evaluator. Only independently reviewed cases and explicitly scoped finding titles are scored; reports must match the artifact SHA-256 and report schema.
- Reports precision, recall, F1 and severity mismatches without calling them overall accuracy. Missing reports, hash mismatches, invalid schema and pinned tool-version mismatches invalidate the whole run rather than silently disappearing from the denominator.
- Adds `audit-benchmark` workflow instructions for building a provenance/licensing-aware golden corpus and a `creator-tools-bridge` workflow for using an already-installed Mojang Creator Tools CLI when a compatible local execution host is available.
- Honest capability boundary: this release still ships seven read-only MCP tools. It does not add `scaffold_addon`, `scaffold_entity`, a writer tool, or an automatic subprocess wrapper for MCT. It never auto-installs MCT or accepts the EULA.
- The benchmark manifest is only a template: no real-pack corpus has been run and no precision/recall percentage is claimed. At the time of this release, GitHub synchronization was deferred until 1.0.0.

## 0.7.7: loot-table structure and reference-cycle checks

- Adds conservative static checks for common loot-table pools, entries, roll counts and weights.
- Indexes literal nested entries of type `loot_table` as resource-graph edges.
- Detects cycles only when nested table references resolve uniquely to in-archive files; does not run conditions/functions or simulate the game engine.
- Removes duplicate component-indexing and duplicate regression assertion blocks left from the 0.7.6 patch, and consolidates duplicate documentation entries.
- Adds synthetic tests for a recursive two-table chain, malformed pool structure, and a 1,005-node reference chain. Medium-severity findings now produce a `REVIEW` recommendation rather than an all-clear. At the time of this release, GitHub synchronization was deferred until 1.0.0.

## 0.7.6: conservative BP component-to-resource links

- Adds allowlisted graph edges for literal `minecraft:loot.table` component paths (with recognized string-form compatibility) and resolves them against common in-archive loot-table path candidates.
- Adds regression scenarios for a matching loot table and a missing loot table.
- Component checks remain partial; full versioned component validation and Minecraft runtime are not claimed. At the time of this release, GitHub synchronization was deferred until 1.0.0.

## 0.7.5: resource graph localization edge hardening

- Records recognizable literal `$key` references from UI `text` properties as graph edges to indexed `.lang` definitions.
- Resolved keys point to in-archive `.lang` files; missing keys are marked `heuristic_unresolved` with LOW confidence, never a confirmed runtime defect.
- Adds regression coverage for both a present localization key and a missing key, and updates the golden graph projection accordingly.
- Keeps UI import/control checks and all archive/report safety boundaries; no game runtime or rendering success is claimed.
- At the time of this release, GitHub synchronization was deferred until 1.0.0.

## 0.7.4: UI import graph and conservative control-reference checks

- Adds heuristic resource-graph edges for literal `ui_defs` imports, recording source file, JSON pointer, candidate paths, and resolution state.
- Detects repeated literal `ui_defs` entries with an INFO warning.
- Adds a narrow INFO/LOW check for recognizable namespace-qualified UI control references in `extends`, `control_name`, and string-list `controls` forms.
- Adds synthetic regression cases for import/control heuristics and literal localization graph edges; report schema and golden graph invariants remain enforced.
- The UI schema and runtime semantics remain partial; no Minecraft UI rendering test is claimed. At the time of this release, GitHub synchronization was deferred until 1.0.0.

## 0.7.3: UI and localization static checks

- Adds conservative checks for the common UI JSON top-level shape, optional `namespace` type, and `ui_defs` value/entry shapes.
- Checks each literal `ui_defs` path against common pack-root/UI-root and source-relative candidates. Missing and ambiguous candidates remain `INFO`/`LOW` heuristics because external packs and engine path resolution are not modeled.
- Detects duplicate `.lang` keys within the same file (not across locales) and empty localization keys. Checks simple literal `$key` values in UI `text` properties against indexed `.lang` keys; unresolved lookups remain `INFO`/`LOW` heuristics.
- Adds regression cases for missing UI definition paths, duplicate per-file localization keys, and missing literal UI localization lookups. Regression reports continue to be checked against the JSON Schema and graph invariants.
- Does not parse the full Bedrock UI schema, validate control bindings/rendering, evaluate variable/Molang expressions, or claim UI runtime correctness. At the time of this release, GitHub synchronization was deferred until 1.0.0.

## 0.7.2: animation/controller cross-resource checks

- Validates literal animation-controller `initial_state` and transition target state names against the state map in the same controller; Molang condition expressions are not evaluated.
- Compares animation bone targets with the global in-archive geometry bone inventory. Missing names remain `INFO`/`LOW` heuristics because the analyzer cannot reliably infer which geometry is active or supplied by external packs.
- Adds three synthetic regression cases for missing animation bones, missing controller transition states, and missing initial states; every report still goes through the report schema and graph invariants.
- Keeps the golden reference-graph projection and domain-filter isolation regressions from the 0.7.1 candidate.
- At the time of this release, GitHub synchronization was deferred until 1.0.0.

## 0.7.1: graph contract and version-source hardening

- Makes explicit `target_domain` authoritative in MCP graph filtering so a UI path cannot leak into geometry or texture results merely because its text matches.
- Filters graph definitions by exact domain buckets instead of substring matching that could mix animations and animation controllers.
- Adds an exact golden projection for the valid synthetic graph, including source pointers, reference kinds, target domains, statuses, edge count and status counts.
- Makes both MCP and analyzer read their runtime version from the package-root `VERSION` file; the version-consistency test also checks release heading and both manifests.
- At the time of this release, GitHub synchronization was intentionally deferred until 1.0.0.

## 0.7.0: graph filtering and bounded report validation

- Fixes MCP resource-graph filters to use the analyzer's actual edge fields (`source_file`, `source_pointer`, `target_domain`, `reference_kind`, and `referenced_value`) and covers each filter with synthetic contract tests.
- Adds `archive_safety.py` as the shared source for compressed archive, member-count, per-member and cumulative uncompressed-size limits. The standalone CLI and MCP wrapper apply the same limits before member payloads are read.
- Adds `VERSION` as the single release-version source; manifests, MCP initialization and analyzer reports are checked against it in tests.
- Adds Draft 2020-12 report validation with `skills/automated-validation/scripts/validate_report.py` and schema checks for each regression fixture.
- At the time of this release, the update was limited to Plugin Creator; repository synchronization remained deferred until 1.0.0.

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

All bundled MCP tools are read-only. The server does not extract archives, execute pack scripts, alter or delete project files, launch Minecraft, or make network requests. It bounds paths to a configured workspace and returns structured errors on invalid input. It never automatically deletes resources based on heuristic findings. Do not package tokens, credentials, private user data, or proprietary packs. This plugin remains private; the GitHub source repository has separate visibility controls.
