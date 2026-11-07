# Release Notes — Minecraft Bedrock Engineer 2.0.2

## Change Impact Analysis

- Adds the `change-impact-analysis` Skill in the existing `audit_validation` domain; total registry remains 14 domains and grows to 65 uniquely assigned Skills.
- Adds `analyze_change_impact.py`, a bounded static dependency analyzer with reverse traversal from changed paths.
- Traces supported BP/RP entity/client-entity bindings, geometry, texture files, animation/controller/render-controller identifiers, recipe item/block references, BP/RP manifest UUID dependencies, UI imports and relative JavaScript/TypeScript imports.
- Supports deleted/renamed file paths: explicit consumers that still reference a changed path absent from the current workspace are included in the impact closure and marked `CHANGED_DEPENDENCY_MISSING`.
- Reports direct/indirect impact, relationship type, confidence, duplicate/ambiguous identifiers, unresolved references and scan completeness. Affected files are review/test candidates, not proof of broken behavior.
- Adds `change-impact.schema.json`, a synthetic example and 32 focused analyzer tests. Extends architecture validation with analyzer, Skill, test and report-schema gates (37 architecture tests total).
- Preserves all existing Skill paths, 14 domains, plugin identity, private audience and all 12 default prompts. No MCP service, remote backend, subprocess, source execution or Minecraft runtime dependency is added.

## Validation

- Combined Core test suite: 181/181 passed (32 analyzer, 38 Domain Result integration, 44 domain planner, 30 project-state and 37 architecture validator tests).
- Python compilation: 10/10 affected Core scripts/tests passed.
- Draft 2020-12 schema meta-validation: change-impact, project-state, Work Order and Domain Result schemas passed; the synthetic report example validates.
- Manifest parity: both manifests and `VERSION` report 2.0.2; the existing 12 default prompts are identical and unchanged.
- Registry: 14 domains, 65 unique Skill assignments, all references and dependencies syntactically valid.
- Local architecture validator on the partial update overlay: 27/28 checks passed. The only failure is the expected local Skill inventory coverage gap (8/65 Skill folders present in the overlay; unchanged Skills are retained by Plugin Creator's overlay update).
- Full package-integrity checker and Minecraft/Creator Tools runtime: NOT RUN. No claim of Minecraft import/render/gameplay testing is made.
