# Documentation Consistency Report — MBE 2.3.4

## Findings corrected

1. `README.md` described the 2.3.3 Entity Authoring migration as the current 2.3.4 change set and reported the pre-consolidation 70-Skill inventory. Rewritten to describe all seven 2.3.4 groups and current package facts.
2. `ARCHITECTURE.md` reported 70 current Skills. Updated to 59 and labeled the current candidate status.
3. Core `SKILL.md` still said 71 Skills and contained a manually duplicated domain table with repeated Skill slugs. Replaced the table with the registry-as-single-source-of-truth rule and updated the current count.
4. `TARGET_ENVIRONMENT_ACCEPTANCE_PLAN.md` still referred to 355 scenarios and version 2.3.0. Updated to 2.3.4 and 295 scenarios.
5. `TOOL_REGISTRY.md` and `.csv` described a 2.3.1/71-Skill audit snapshot. Replaced with 2.3.4 evidence and explicit NOT VERIFIED / NOT RUN boundaries.
6. The 2.3.4 CHANGELOG and release notes lacked sufficient current inventory and validation detail. Expanded them with the exact 59/14/8/12/64/295 package facts and evidence statuses.

## Canonical current facts

- Package version: 2.3.4 in `VERSION`, `plugin.json` and `.codex-plugin/plugin.json`.
- Skill inventory: 59; domains: 14; workflow profiles: 8.
- Activation matrix: 295 designed cases (59 × 5), all NOT RUN.
- Python registry: 64 entries; hashes match packaged sources.
- Local tests: 32/32 files, 548/548 cases PASS.
- Architecture: 28/28 PASS. Package integrity: 20/20 PASS, zero warnings.
- Live Plugin Creator remains 2.1.11 USER / PRIVATE; 2.3.4 is unpublished.

## Historical evidence policy

Older release reports, old release notes, prior-version SHA manifests and migration reports retain their original counts and dates. They are historical evidence and must not be rewritten to resemble 2.3.4. Current-facing documents link to the 2.3.4 report instead.
