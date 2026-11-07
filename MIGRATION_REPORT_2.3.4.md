# MBE 2.3.4 — Consolidation migration report

## Scope

Applied the requested seven domain groups in one isolated migration from the exact 2.3.3 Entity Authoring candidate. The 2.3.3 archive was copied immutably before edits.

## Consolidation results

- Geometry & UV: `geometry-uv-engine` is the canonical entry with `audit`, `render-template`, and `png-check` modes. The two narrow wrapper entries were retired; all three engines, tests and examples remain.
- Project Continuity: `project-continuity` is the resume/reconcile/recover entry. `project-state-management` remains a distinct technical procedure because the Core architecture validator explicitly requires it and it owns the detailed state utility contract. `project-state-recovery` was retired into the canonical modes. Core-owned `project_state.py` and tests remain unchanged.
- Baseline Regression: `baseline-regression-workflow` was absorbed into `addon-baseline-diff`. `project-audit` remains separate for broader resource/behavior diagnosis.
- Creator Tools: connected-host and authorized-local-CLI modes are combined in `creator-tools-bridge`. Generic orchestration duplication was retired in favor of `workflow-execution-engine`. No Creator Tools integration or phantom capability was added.
- Add-on Authoring: `addon-creation` is the canonical entry for new projects, existing-project features and multi-file bundles. Unverified historical tool names are explicitly non-authoritative. Resource-domain specialists remain separate.
- Reference Texture Transfer: `uv-texture-retargeting` is the end-to-end planning/inspection entry. `uv-mapping-assistant` was absorbed. `reference-mapping-review` remains a mandatory human approval gate, and `reference-texture-transfer` remains a distinct deterministic implementation procedure because the package's required-file/integrity contract depends on its stable path. Its script, tests and examples remain at the registered path.
- Release Engineering: `release-artifact-workflow` absorbs `build-release`; `release-quality-gate` absorbs `release-readiness`. Artifact preparation and readiness decisions remain separate. Add-on pack versioning and plugin version governance remain separate.

## Package impact

- Skills: 70 -> 59 (11 redundant entry Skills retired; specialist procedures preserved).
- Domains: 14 preserved.
- Workflow profiles: 8 preserved.
- Default prompts: all 12 preserved byte-for-byte.
- Plugin identity preserved; both manifests set to 2.3.4.
- No MCP/server/backend/runtime components added.
- Python utilities and test suites preserved; registry hashes refreshed and checked.

## Verification

- 32/32 Python test files PASS; 548/548 cases PASS.
- Architecture validator: 28/28 PASS; 14 domains, 59 registered/discovered Skills, 8 workflow profiles.
- Strict package integrity: 20/20 PASS; zero warnings.
- `compileall`: PASS.
- Script registry: 64 entries; no missing paths or SHA-256 mismatches.
- Markdown relative-link scan: 0 broken links.
- Activation matrix: 295 designed scenarios (59 Skills x 5), all NOT RUN on the target Plugin Host.
- Minecraft import/gameplay/multiplayer/performance: NOT RUN.
- Connected Creator Tools and local CLI authorization/host integration: NOT RUN.
- Live Plugin Creator publication: NOT performed.

## Limitations

The local test and package checks establish static/package-level evidence only. They do not prove Skill activation in the installed Plugin Host, access to user files in another host surface, connected Creator Tools availability, or Minecraft runtime behavior.
