---
name: release-readiness
description: Use for a final candidate review that consolidates source preservation, tests, tool compatibility, artifact integrity, regression deltas and real Minecraft runtime status into an evidence-based recommendation.
---

# Release Readiness

## Review categories
1. **Source/identity**: current plugin ID/scope, manifests, version, prompts, MCP connection and full file inventory.
2. **Functionality**: each writer or analyzer capability is present in source and accurately described.
3. **Safety**: workspace/path confinement, symlink rejection, collision protection, bounded inputs, read-only integrity and safe tool annotations.
4. **Tests**: complete unit suite, benchmark tests, sample-index tests, analyzer regressions, schemas and protocol checks.
5. **Compatibility**: target Bedrock version, sample provenance, manifest dependency structure and API/version limitations.
6. **Regression**: baseline comparison with all material changes explained.
7. **Packaging**: archive opens, has expected layout/manifests, duplicate/path safety passes, hash recorded. Run `skills/package-integrity/scripts/check_package_integrity.py` on the actual full package and review warnings as well as failures.
8. **Runtime**: only checked if the exact package was imported to the target Minecraft build. Keep separate from static results.

## Decision thresholds
- `HOLD`: required tests fail, package structure is invalid, write-safety regression, serious unexplained defect, or an existing core feature is broken.
- `REVIEW`: tests or tools are blocked; meaningful findings remain heuristic; important runtime-sensitive behavior is untested.
- `READY FOR USER TEST`: required static and contract checks passed, no serious unexplained regression remains, known limitations are explicit.
- `RELEASE READY`: only if all release-required gates are proven, including any required engine/game testing specified for the deliverable. Never use this label merely because `VERSION` says 1.0.0.

## Final report
Include version/source identity, release candidate hash, per-gate status, exact test numbers and command, package-integrity JSON result, unexplained deltas, runtime status and the next action. Preserve raw failure evidence and do not hide a check to improve the aggregate result.
