# Plugin package changelog

## 1.8.0 — Standalone reference texture transfer and validation hardening
- Migrates the reference-to-UV transfer algorithm into a dependency-free local Python CLI; no legacy server, protocol, registry, endpoint or remote execution dependency is imported.
- Adds deterministic crop mapping to exact bone/cube/face UV regions, nearest/bilinear sampling, rotation/flips, opacity, replace/source-over blending and optional base-texture preservation.
- Adds strict PNG decoding/encoding and CRC/filter validation, geometry/UV bounds and overlap guards, duplicate selector checks, bounded texel operations, safe project paths and exclusive no-overwrite output creation.
- Adds focused transfer regression tests and integrates reference-transfer presence/contract/legacy-import checks into the Skills-only package gate.
- Aligns the reference-transfer, texture painting, visual-resource and Geometry/UV skills with the actual standalone CLI; clarifies runtime and semantic-mapping limitations.
- Updates version markers and release evidence to 1.8.0; preserves all 12 default prompts, plugin identity, scope and PRIVATE discoverability.
- Retains historical server sources as inert migration inputs; unrelated legacy modules are not deleted while they still have cross-import dependencies.

## 1.7.3 — Skills-only maintenance, archive recovery and migration audit
- Adds a static migration ledger for legacy server-side sources, import dependencies and current standalone substitutes; domain algorithms remain separate from protocol/host adapters.
- Converts legacy package-integrity script entry points into compatibility shims that delegate to the Skills-only release checker; old registry/server assertions are no longer run as release validation.
- Repairs the Geometry/UV PNG test entry point and documents the local-only, no-backend execution boundary.
- Removes empty legacy skill/deployment placeholder directories and generated Python bytecode from the package; retains legacy source modules pending safe, dependency-aware algorithm migration.
- Adds version governance evidence for 1.7.2 → 1.7.3 and preserves both manifests’ exact defaultPrompt content/order.

## 1.7.1 — Reference audit reliability and version-sequence correction
- Corrects the release successor: the verified 1.7.0 current release advances to 1.7.1, not a new minor version.
- Synchronizes both plugin manifests, VERSION, README, release notes and version history to 1.7.1.
- Hardens archive intake against invalid ZIP CRC entries and makes malformed archive members explicit findings.
- Adds regression coverage for ZIP integrity and hostile archive paths while retaining read-only, no-extraction inspection.
- Preserves Skills-only architecture, prompts, scope, discoverability and historical inert source files.

## 1.7.0 — Reference corpus and resource-domain audits
- Adds a provenance-aware workflow for analyzing user-supplied Bedrock add-on/resource-pack archives without executing untrusted scripts or redistributing third-party assets.
- Adds a bounded read-only archive intake utility with ZIP path safety checks, expansion limits, SHA-256, manifest inventory, duplicate-key-aware strict/comment-aware JSON parsing and test coverage.
- Adds specialist skills for RP UI controls/bindings, Subpack consistency, Vibrant Visuals/fog/PBR, Script API performance/safety, Skin Packs and cooking add-on architecture.
- Adds an observed reference-domain inventory covering the user-supplied examples; explicitly distinguishes prior intake notes from a fresh exhaustive audit.
- Expands UI audit coverage for imports, namespaces, controls, button mappings, property bags, bindings, modifications, localization and textures while retaining the documented heuristic/runtime boundary.
- Preserves all existing skill prompts, assets, sample corpus, binary index and inert historical server sources. No third-party archive payload is packaged.

## 1.6.0 — Entity pipeline and release governance
- Adds `entity-authoring-pipeline`, a coordinated BP/RP workflow spanning entity definitions, client entities, geometry, textures, animation clips/controllers and render controllers.
- Adds a dependency-free static entity pipeline audit CLI with conservative literal-reference checks, duplicate-key/non-finite JSON rejection, machine-readable findings and isolated regression tests.
- Adds version governance for the user's one-digit component rollover policy (`1.0.9 → 1.1.0`, `1.9.9 → 2.0.0`), preserves legacy version strings and records release evidence without treating attached historical releases as published.
- Expands maintenance documentation to distinguish active Skills-only workflows from inert legacy server source. This update does not enable or expose MCP tools.
- Preserves all existing skills, prompts, sample assets, binary index and legacy source files through an overlay update; only the stale generated Python bytecode cache is explicitly removed.
- Corrects the historical 1.5.10 note: the standalone UV template renderer was introduced in 1.5.11; its functionality is not dormant in the current package.
- The Plugin Creator source reader reports the compressed Mojang Samples index at 1,128,413 bytes, but its gzip contents and corpus completeness were not readable through the text-source API and are not certified by this release.
- Removes the generated `check_skills_package.cpython-313.pyc` cache artifact; legacy MCP-era source files are retained as inert migration material until their reusable logic can be safely ported and dependency-audited.

## 1.5.12 — Skills-first workflow alignment
- Aligns Geometry & UV, UV-template authoring and visual-resource instructions with the actual standalone CLI paths and commands.
- Removes stale migration wording that described already-migrated UV tools as dormant.
- Clarifies canonical PNG validation, focused test commands and the boundary between static analysis and game/runtime verification.
- Strengthens release notes around the required full Mojang Samples index; this candidate is blocked while the 67-byte placeholder is present.

## 1.5.11 — Standalone UV template renderer
- Adds `uv_template_engine.py`, a separate transparent PNG UV guide generator for classic box and supported per-face cube UV.
- Adds pixel-scale and total-pixel budget controls, labeled bone/cube/face regions, output SHA-256 and exclusive no-overwrite file creation.
- Adds eight focused renderer tests and updates Geometry & UV/visual-resource instructions with the real CLI contract.
- Explicitly records remaining limits: mesh projection, actual UV orientation/mirror sampling, client-entity bindings, texture-canvas matching and Minecraft/Blockbench runtime checks remain outside scope.

## 1.5.10 — Geometry analyzer hardening
- Corrects package integrity coverage to check the geometry analyzer and PNG validator exactly once each.
- Repairs checker regression fixtures so they include actual geometry engine source/test placeholders rather than testing only a text token.
- Clarifies which geometry checks are implemented and which remain outside the static CLI (mesh projections, client-entity bindings, PNG/canvas matching and game rendering).
- At 1.5.10, UV template rasterization was still dormant; it was separated into an independent CLI in 1.5.11.

## 1.5.9 — Standalone Geometry & UV analyzer
- Adds `geometry_engine.py`, a dependency-free `.geo.json` parser and static cube-UV bounds/overlap analyzer.
- Supports classic box UV and per-face cube UV maps; selects exact geometry identifiers and rejects duplicate JSON keys/non-finite values.
- Reports out-of-bounds UVs as failures and UV overlap intersections as review warnings.
- Adds ten focused positive, negative and boundary tests.
- Removes duplicate PNG implementation by retaining a single canonical PNG validator and a thin compatibility entrypoint.
- Keeps legacy server wrappers and dormant UV template renderer preserved.

## 1.5.9 — Standalone Geometry & UV analyzer
- Adds `geometry_engine.py`, a dependency-free `.geo.json` parser and static UV bounds/overlap analyzer.
- Supports classic box UV rectangles and per-face cube UV maps; selects geometry identifiers, rejects duplicate JSON keys and non-finite coordinates, and checks declared texture canvas bounds.
- Reports UV overlaps as review warnings and out-of-bounds regions as failures; does not assume shared/mirrored UVs are defects.
- Adds ten independent positive, negative and boundary tests and documents the CLI.
- At 1.5.9, template rasterization remained dormant; it was migrated in 1.5.11.

## 1.5.8 — Geometry & UV migration foundation
- Adds the `geometry-uv-engine` skill with supported-format boundaries, validation procedure, output status vocabulary and explicit migration status.
- Adds the shared PNG validator as a standalone script entry in the geometry engine directory.
- Updates UV audit/template and maintenance documentation to distinguish preserved legacy algorithms from currently executable utilities.
- Does not delete or advertise old server wrappers; full geometry parser/template CLI migration remains unfinished.

## 1.5.7 — Standalone PNG validation utility
- Adds `png_engine.py`, a dependency-free standalone PNG validator for Bedrock texture assets.
- Validates PNG signature, chunk CRCs/order, IHDR combinations, IDAT zlib stream, scanline lengths and filter values, including Adam7 pass sizing.
- Adds eight focused synthetic unit tests and documents the CLI in the visual resource workflow.
- Keeps legacy server wrappers untouched; this release migrates one bounded algorithm without deleting source dependencies.

## 1.5.6 — Release gate and stale-instruction audit
- Reworked the end-to-end validation matrix, recipe authoring, baseline comparison, regression evaluation and release-readiness skills to remove retired tool assumptions.
- Reclassified the 1.0.0 release skill as historical context only.
- Strengthened the offline package checker to reject stale invocations of retired tools and obsolete Cloudflare deployment scaffolding.
- Expanded synthetic checker regression tests to cover stale calls and deployment remnants.

## 1.5.5 — Skills-only workflow hardening
- Rewrote add-on creation, Bedrock development, automated validation, entity authoring, visual-resource, texture-painting and UV mapping instructions to remove calls to unavailable MCP tools.
- Replaced release quality gate and validation runbook with Skills-only package, script and evidence procedures.
- Reworked Creator Tools bridge/orchestration as optional capability detection; no integration is assumed.
- Added `skills-only-maintenance` for architecture audits, safe legacy migration and package release discipline.
- Removed obsolete Cloudflare deployment scaffolding and generated Python bytecode caches from the package.
- Preserved specialist references, sample corpus, reusable source modules and tests pending dependency-aware migration.

## 1.5.4 — Version-marker consistency fix
- Corrects `VERSION` to 1.5.4 so it matches the automatically bumped root and compatibility manifests.
- Keeps the Skills-only package integrity checker and eight regression tests.

## 1.5.3 — Skills-only package integrity and regression gate
- Adds a Skills-only package checker for manifest/version/prompt parity, skill inventory, README consistency, no-MCP architecture and Mojang sample-index integrity.
- Adds eight synthetic regression tests; all 8 passed in the development environment.
- Retires the old MCP-registry checker from the active release workflow while retaining its source for historical reference.

## 1.5.2 — Skills-first execution repair
- Reaffirms the intentional Skills-and-instructions-only architecture; no MCP server, registry, endpoint or plugin-owned execution backend is required or configured.
- Adds `skills-first-execution` as the mandatory capability-routing, safe-editing, script-execution and evidence-reporting contract.
- Updates `bedrock-engineer-core` to prioritize the Skills-only workflow and specialist skill composition.
- Clarifies that skills do not create filesystem access, execution tools, package installation or background work.
- Preserves existing specialist authoring skills, reference corpora, Python source files and sample assets.
