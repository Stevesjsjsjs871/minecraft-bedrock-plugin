# Plugin package changelog

## Unreleased — Skills capability-boundary correction
- Adds a canonical capability matrix distinguishing standalone local scripts from instruction-only authoring workflows and optional external applications.
- Rewrites animation, entity-bundle, reference-mapping, texture-transfer, texture-painting and add-on authoring Skills so they no longer claim unavailable writer, analyzer or server operations.
- Corrects the visual-resource workflow to use the existing standalone UV guide renderer and its focused tests.
- Extends the package checker to reject retired server-tool identifiers in any Skill and to detect stale UV-renderer instructions.
- No plugin version bump or release candidate is assigned by this source-only maintenance change.

## 1.5.11 — Standalone UV template renderer
- Adds `uv_template_engine.py`, a separate transparent PNG UV guide generator for classic box and supported per-face cube UV.
- Adds pixel-scale and total-pixel budget controls, labeled bone/cube/face regions, output SHA-256 and exclusive no-overwrite file creation.
- Adds eight focused renderer tests and updates Geometry & UV/visual-resource instructions with the real CLI contract.
- Explicitly records remaining limits: mesh projection, actual UV orientation/mirror sampling, client-entity bindings, texture-canvas matching and Minecraft/Blockbench runtime checks remain outside scope.

## 1.5.10 — Geometry analyzer hardening
- Corrects package integrity coverage to check the geometry analyzer and PNG validator exactly once each.
- Repairs checker regression fixtures so they include actual geometry engine source/test placeholders rather than testing only a text token.
- Clarifies which geometry checks are implemented and which remain outside the static CLI (mesh projections, client-entity bindings, PNG/canvas matching and game rendering).
- Keeps UV template rasterization dormant until its dependencies and tests are separated into an independent CLI.

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
- Keeps template rasterization dormant pending its own migration; retains all legacy source.


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
