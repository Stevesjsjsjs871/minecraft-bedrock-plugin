---
name: release-readiness
description: Use for a final review of a Minecraft Bedrock Engineer candidate covering source identity, Skills-only architecture, tests, compatibility, packaging, regression and runtime evidence.
---

# Release readiness

## Review categories
1. **Source/identity:** plugin ID/scope, manifests, version, prompts, complete file inventory and release ID.
2. **Architecture:** Skills-only manifests, no active MCP configuration or remote backend, no skill instructions invoking unavailable tools, and no obsolete deployment wrappers.
3. **Functionality:** every advertised capability is supported by a real workflow/script or clearly labelled as guidance/planned work.
4. **Safety:** path confinement, symlink rejection, collision protection, bounded inputs, read-only audits and no untrusted script execution.
5. **Tests:** package checker, synthetic checker tests, focused script suites, sample-index tests, analyzer regressions and schemas where dependencies exist.
6. **Compatibility:** target Bedrock version, sample provenance, manifest dependencies and API/version limitations.
7. **Regression:** baseline comparison with all material changes explained.
8. **Packaging:** archive opens, expected layout/manifests, no duplicate/unsafe paths, hash recorded. Run `check_skills_package.py` on the actual extracted package.
9. **Runtime:** only claim tested when the exact package was imported into the exact Minecraft build and scenario.

## Decision thresholds
- `HOLD`: required test failure, invalid package, unsafe write, serious unexplained defect or broken core workflow.
- `REVIEW`: blocked tests/tools, heuristic findings, incomplete coverage or untested runtime-sensitive behavior.
- `READY FOR USER TEST`: required static checks passed, no serious unexplained regression remains and limitations are explicit.
- `RELEASE READY`: only when all release-required gates, including required engine tests, are proven.

## Final report
Include version/source identity, candidate hash, per-gate status, exact commands and test counts, package-checker output, unexplained deltas, runtime status and next action. Preserve raw failure evidence.
