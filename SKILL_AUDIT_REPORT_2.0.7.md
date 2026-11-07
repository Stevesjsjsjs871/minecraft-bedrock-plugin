# Skill Quality Audit — Minecraft Bedrock Engineer 2.0.7

**Audit date:** 2026-11-07  
**Baseline:** Plugin Creator version 2.0.6, release `pluginrel_6aeed67929008191bf56e690123be1f3`, backend ID `plugins_6ae33ff6e8d8819182f246d8d3d97323`, scope USER, audience PRIVATE.  
**Guide basis:** user-supplied `info-plugins-corrected.txt`, Technical Guide version 2.0, checked 2026-11-07.  
**Target architecture:** Domain-Based Hybrid / Skills-only; no MCP server, connection or plugin-owned backend.

## Executive result

- Reviewed the full 65-file `skills/<slug>/SKILL.md` inventory against the supplied guide: metadata, scope, input assumptions, workflow/capability truth, safety, hand-off/report quality, local references, and placement in the domain registry.
- 65/65 Skill frontmatter records parse; names are unique; every name matches its directory slug; every Skill is assigned exactly once in the 14-domain registry.
- Found and corrected six Skills that described historical MCP functions as if they were callable; corrected inaccurate claims about missing bundled writers/tools; removed a duplicated cooking-versioning instruction; expanded five thin domain Skills with required inputs, safe workflow, acceptance/output and limitations.
- Replaced a phantom automated semantic-mapping tool procedure with an explicit human-review gate and aligned the retarget example JSON to the actual local texture-transfer request contract.
- Added a reusable maintenance checklist and a 325-case activation-test design matrix. The matrix records prompts and expected outcomes; **all activation cases remain NOT RUN** because target-host activation was not exercised.
- No Skill paths were renamed or removed. No MCP components, tools, servers or APIs were added. The 34 historical `server/` files were preserved as inert migration inputs.

## Package and architecture inventory

| Check | Evidence | Result |
|---|---:|---|
| Portable Skills | 65 files under `skills/<slug>/SKILL.md` | PASS |
| Domain registry | 14 domains; 65 unique assignments | PASS |
| Workflow profiles | 8 declared profiles | PASS (static) |
| Package files | 275 source files after adding audit/checklist/matrix/release notes; excludes generated local bytecode caches | INVENTORIED |
| Historical server files | 34 retained | WARN / retained intentionally |
| Python files | 90 | REGISTERED |
| Skill references/assets | 59 reference files plus 2 asset-like files | INVENTORIED |
| Active Skills test files | 27 | See test results below |

## Skill-by-Skill disposition

`UPDATED` means a confirmed defect or meaningful documentation gap was corrected. `REVIEWED / RETAINED` means no blocking static issue was found in this pass; it does not mean activation or runtime has been tested.

| Skill | Disposition | Audit note |
| `addon-baseline-diff` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `addon-creation` | UPDATED | UPDATED — Removed unsupported claim that Bedrock Engineer has general-purpose file writers; native Creator Tools only when actually exposed. |
| `addon-creation` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `addon-versioning` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `animated-entity-bundle-authoring` | UPDATED | UPDATED — Removed non-existent bundle generator claims; replaced with coordinated manual BP/RP authoring and real entity-pipeline audit route. |
| `animation-clip-authoring` | UPDATED | UPDATED — Removed fictitious create/validate tools and invented generator limits; documented manual file workflow and real graph-audit boundary. |
| `animation-controller-authoring` | UPDATED | UPDATED — Removed fictitious controller create/validate tools; documented manual state-machine authoring and static/runtime boundaries. |
| `animation-pipeline-audit` | UPDATED | UPDATED — Replaced phantom MCP audit function with the actual `audit_entity_pipeline.py` CLI and precise coverage/limits. |
| `audit-benchmark` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `automated-validation` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `addon-baseline-diff` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `addon-creation` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `bedrock-development` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `bedrock-engineer-core` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `release-artifact-workflow` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `change-impact-analysis` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `cooking-addon-engineering` | UPDATED | UPDATED — Removed duplicate version-gate paragraph and expanded transaction, interruption, cleanup and test requirements. |
| `creator-tools-bridge` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `creator-tools-bridge` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `workflow-execution-engine` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `dependency-closure-audit` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `domain-result-integration` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `end-to-end-validation-matrix` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `entity-authoring` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `entity-authoring-pipeline` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `geometry-uv-engine` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `geometry-uv-engine` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `geometry-uv-engine` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `legacy-source-migration` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `model-animation` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `mojang-samples-authoring` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `package-integrity` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `project-audit` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `project-continuity` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `project-continuity` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `project-continuity` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `recipe-authoring` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `reference-mapping-review` | UPDATED | UPDATED — Replaced phantom automated reviewer and transfer calls with explicit manual human-review gate and real downstream transfer-script contract. |
| `reference-pack-corpus` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `uv-texture-retargeting` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `regression-evals` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `release-artifact-workflow` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `release-quality-gate` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `release-quality-gate` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `research-versions` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `resource-integrity-audit` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `resource-reference-graph` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `script-api-performance-audit` | UPDATED | UPDATED — Expanded import graph, lifecycle, optional-value safety, exact-version source provenance and controlled profiling guidance. |
| `skills-first-execution` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `skills-only-maintenance` | UPDATED | UPDATED — Added a maintained per-Skill quality checklist and separate, honest activation-test tracking. |
| `skin-pack-engineering` | UPDATED | UPDATED — Expanded input, manifest, texture, geometry, localization, baseline and output/limitations requirements. |
| `subpack-engineering` | UPDATED | UPDATED — Expanded version-specific manifest inspection, per-mode inventory, override analysis, localization and runtime limits. |
| `test-evidence-reporting` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `texture-painting-pipeline` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `ui-resource-audit` | UPDATED | UPDATED — Expanded scope, parser rules, explicit reference-state model, exact analyzer boundary and report contract. |
| `ui-resource-engineering` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `uv-texture-retargeting` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `uv-texture-retargeting` | UPDATED | UPDATED — Replaced phantom one-call orchestration with the actual analyzer → review → transfer sequence; removed unsupported JSON request fields. |
| `v100-release-engineering` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `validation-runbook` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `version-aware-compatibility` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `version-governance` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `visual-reference-analysis` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `visual-resource-pipeline` | REVIEWED / RETAINED | REVIEWED / RETAINED — metadata, domain ownership, capability boundaries, references and task/report scope checked; no blocking static issue identified in this audit. |
| `visuals-fog-pbr-audit` | UPDATED | UPDATED — Expanded exact-version source checks, reference graph states, PBR/fog validation and performance evidence limits. |

## Confirmed repairs and safeguards

### Phantom callable functions corrected
- `animated-entity-bundle-authoring`: no bundled animated-entity generator; manual coordinated authoring and existing static graph audit are now explicit.
- `animation-clip-authoring`: `create_animation_clip` / `validate_animation_clip` are not available; removed as active procedure. No made-up generator limits remain.
- `animation-controller-authoring`: `create_animation_controller` / `validate_animation_controller` are not available; removed as active procedure.
- `animation-pipeline-audit`: points to existing `skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py` and documents its limitations.
- `reference-mapping-review`: no automated review tool exists; semantic region/crop/face approvals are explicitly human decisions.
- `uv-texture-retargeting`: no single retarget tool/planner exists; actual analyzer and reference-transfer scripts are sequenced with manual review.

### Contract and consistency corrections
- `addon-creation` no longer claims a general-purpose Bedrock Engineer writer layer.
- `cooking-addon-engineering` no longer repeats the same add-on version gate twice.
- `uv-texture-retargeting/references/retarget-request.example.json` now matches `uv-texture-retargeting` actual accepted field names; review-only fields (`review_confirmed`, `approved`, `source_assignments`, `require_full_coverage`) are excluded from the transfer request.
- `ui-resource-audit` now points to the actual `bedrock_audit.py` and discloses partial/heuristic UI coverage.
- `TOOL_REGISTRY.md` and `.csv` now separate current Plugin Creator and local development capabilities from unverified installed-host and Minecraft runtime behavior.
- `SCRIPT_EXECUTION_REGISTRY.csv` now marks the reviewed stdlib-only archive versioning module dependency layer as `DEPENDENCIES_OK`; no host integration status was promoted.

## Activation test matrix

`SKILL_ACTIVATION_TEST_MATRIX.csv` contains five designed prompts per Skill: direct intent, indirect intent, incomplete inputs, negative/out-of-scope intent and an edge/safety/capability case. It contains 325 rows. Every row is `NOT RUN`; no target-host activation evidence was available. The cases are ready for execution in the actual installed plugin host and must not be counted as passing tests.

## Script evidence (six independent levels)

`SCRIPT_EXECUTION_REGISTRY.csv` contains 90 Python-file rows with SHA-256 values. File/path/hash consistency was checked. Recorded states from the baseline registry are retained unless specifically described above. Local syntax/test execution does not establish plugin-host integration. The 34 historical `server/` source/test files remain inert; they are not invoked by the Skills-only workflow.

## Verification results

| Verification | Result | Meaning |
|---|---:|---|
| Architecture validator | 28/28 PASS | Domain assignments, workflow graph and architecture contracts |
| Current Skills-local tests after edits | 490/490 PASS across 27 test files | All active Skills test files completed locally after candidate edits |
| Core suite after edits | 181/181 PASS | Domain planner, project state, architecture, integration and impact suites |
| Version-governance suite after edits | 12/12 PASS | Version policy tests |
| Compatibility package checker after edits | 19 PASS / 0 FAIL / 1 WARN | Single warning: 34 retained historical server files |
| Package checker tests after edits | 25/25 PASS | Checker regression tests |
| Target-host Skill activation | NOT RUN | 325-case matrix is designed, not executed |
| Installed plugin host script execution | NOT TESTED | Local Python does not prove host execution |
| Creator Tools / Minecraft import-render-gameplay | NOT RUN | No live Bedrock runtime session in this audit |

## Change scope and preservation

- Existing plugin ID, name, USER scope and PRIVATE audience are to remain unchanged.
- Root and compatibility manifests keep all 12 `defaultPrompt` strings, type and order unchanged; only version changes for this release.
- All 65 Skill names, paths and domain registry assignments remain unchanged.
- 34 historical `server/` files are retained; no destructive cleanup was attempted.
- No active MCP, server, API, endpoint, transport or hosted backend was added.

## Release gate decision

**Static candidate decision: PASS WITH WARNING for a private package update.** The compatibility checker has one known warning: 34 retained historical `server/` files. The strict Skills-only gate remains blocked by this retained footprint; no legacy files are removed by this release. Target-host activation, installed-plugin script execution and Minecraft runtime remain NOT RUN/NOT TESTED and are not prerequisites claimed as passed by this static report.

## Provenance

- Requirements source: user-provided `info-plugins-corrected.txt`, Technical Guide 2.0, 2026-11-07.
- Platform documentation consulted separately: official OpenAI Skills guide and Agent Plugin packaging guide; platform-specific behavior still requires host testing.
- This report distinguishes static source review and local test evidence from target-host activation and Minecraft runtime claims.
