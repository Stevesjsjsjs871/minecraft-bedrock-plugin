# Release notes — 2.3.4

**Status:** unpublished candidate; this GitHub branch is a staging branch, not a live Plugin Creator release.

## Consolidated areas

- Geometry & UV: `geometry-uv-engine`.
- Project continuity: `project-continuity`, with the separate `project-state-management` utility contract.
- Baseline regression: `addon-baseline-diff`.
- Creator Tools: `creator-tools-bridge`.
- Add-on authoring: `addon-creation`.
- Reference texture transfer: `uv-texture-retargeting`.
- Release engineering: `release-artifact-workflow` and `release-quality-gate`.

## Package facts

- 59 Skills, 14 domains, 8 workflow profiles.
- 64 Python registry entries with checked SHA-256 values.
- 295 target-host activation scenarios designed; all NOT RUN.
- 12 default prompts and plugin identity preserved.
- Skills-only architecture; no MCP service, server, remote execution backend or new runtime.

## Validation

- 32/32 test files and 548/548 cases PASS.
- Architecture validator 28/28 PASS.
- Strict package integrity 20/20 PASS, zero warnings.
- Python compilation PASS; Markdown relative-link scan: zero broken links.
- Plugin Host activation, packaged-script integration, Creator Tools connection and Minecraft runtime remain NOT VERIFIED / NOT RUN.

These are local candidate validation results; they are not evidence of GitHub package completeness or target-host runtime behavior.
