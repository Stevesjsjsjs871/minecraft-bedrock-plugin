# Minecraft Bedrock Engineer — 2.3.4

**Status:** unpublished consolidated candidate. This package is Skills-and-instructions-only and does not use MCP. The live Plugin Creator release remains **2.1.11 (USER / PRIVATE)**; this package has not been published.

## What changed in 2.3.4

Seven requested areas were consolidated into canonical Skill entry points while preserving distinct specialist procedures and their implementation contracts:

- **Geometry & UV:** `geometry-uv-engine` provides audit, UV-template and PNG-check modes.
- **Project Continuity:** `project-continuity` coordinates resume, reconcile and recovery; `project-state-management` remains the separate state utility contract.
- **Baseline Regression:** baseline comparison is routed through `addon-baseline-diff`; broad project auditing remains separate.
- **Creator Tools:** `creator-tools-bridge` distinguishes an actually connected host from explicitly authorized local CLI use.
- **Add-on Authoring:** `addon-creation` is the entry point for new add-ons, existing-project features and coordinated bundles.
- **Reference Texture Transfer:** `uv-texture-retargeting` coordinates the workflow; human mapping approval and deterministic transfer remain separate procedures.
- **Release Engineering:** `release-artifact-workflow` prepares artifacts; `release-quality-gate` evaluates readiness. Add-on and plugin version governance remain distinct.

## Current package facts

- **59 Skills**, **14 domains**, **8 workflow profiles**.
- **64 Python registry entries** with SHA-256 values checked against the packaged files.
- **295 activation scenarios** (five per Skill) are designed; all remain `NOT RUN` on the target Plugin Host.
- All **12 default prompts** and plugin identity are preserved.
- No MCP service, server, remote execution backend or new runtime was added.

## Validation evidence

- Python test suite: **32/32 files, 548/548 cases PASS**.
- Architecture validator: **28/28 PASS**.
- Strict package integrity: **20/20 PASS**, zero warnings.
- Python compilation: PASS; Markdown relative-link scan: zero broken links.
- Plugin Host activation, packaged-script integration, connected Creator Tools and Minecraft import/render/gameplay/multiplayer/performance: **NOT VERIFIED / NOT RUN**.

See `RELEASE_NOTES_2.3.4.md`, `MIGRATION_REPORT_2.3.4.md`, `VALIDATION_REPORT_2.3.4.md`, and `DOCUMENTATION_CONSISTENCY_REPORT_2.3.4.md`. The authoritative domain membership and routing source is `skills/bedrock-engineer-core/references/domain-registry.json`.

## Release boundary

This is a local candidate only. Do not treat local static tests as proof of target-host activation or Minecraft runtime behavior. Live publication requires separate explicit approval.
