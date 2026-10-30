# Cloudflare MCP profile contract and CI repair

**Date:** 2026-10-30  
**Base:** `feat/cloudflare-workers-mcp`  
**Scope:** GitHub source branch only; no Plugin Creator update or deployment.

## Baseline defects

1. `server/mcp_server.py` contained literal backslash-n characters between `SERVER_VERSION`, `MCP_SERVER_NAME`, and `MCP_TRANSPORTS` assignments on one physical line. This is invalid Python syntax and should fail the workflow's existing `py_compile` step.
2. `.github/workflows/validate.yml` still hard-coded `expected = "1.0.14"` even though this branch's `VERSION` and manifests are 1.4.0.
3. The Free Worker exposes four TypeScript-native remote tools while the local MCP configs register 16 Python STDIO servers. The README described this distinction, but no machine-readable contract or regression test protected it.

## Changes

- Restored the three server constants as separate valid Python assignments.
- Changed the workflow to derive the expected release version from `VERSION`.
- Added `cloudflare/capabilities.json` describing the Free Worker remote profile (four tools, no local Python execution, no project filesystem writes) and the full local STDIO profile (16 modules).
- Added `cloudflare/tests/test_capability_contract.py` to compare the Worker tool/module declarations with the manifest, verify both local MCP configs register all 16 scripts safely, normalize missing `env` to an empty object, and check the README's scope statements.
- Added the new contract test to CI compilation and test discovery.
- Updated `cloudflare/README.md` to identify the machine-readable contract and warn that local Python modules are not executed by the Free Worker.

## Static verification performed before PR creation

A GitHub-source consistency check confirmed:

- Worker remote tools match the manifest: 4/4.
- Worker module list matches the manifest: 16/16.
- Both local MCP configs contain 16 servers and normalize to identical command/args/env contracts.
- The malformed Python declaration is gone.
- The workflow derives its expected version from `VERSION` and runs the new test suite.
- The README lists the exact remote tools and states that the Worker does not execute the local Python handlers.

These are static source checks, not Python test execution. Python compilation and the new unittest suite remain **NOT RUN** until the PR workflow completes.

## Known limitations

- The live Cloudflare Worker endpoint could not be reached from this environment because DNS resolution failed.
- No authenticated MCP `initialize` or `tools/list` request was run.
- The Free Worker still intentionally exposes only four remote tools; full filesystem, texture, geometry, animation, archive and Creator Tools workflows remain in the local STDIO profile.
- Minecraft runtime/import and Creator Tools CLI remain **NOT RUN**.

## Next step

Review the PR and require CI to pass on its head. Only then consider syncing the source branch to a single release snapshot. Do not merge automatically or update Plugin Creator without a separately authorized release action.
