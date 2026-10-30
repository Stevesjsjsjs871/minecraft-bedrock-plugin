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


## Follow-up after first PR CI run

The first PR workflow run, **#41062741228**, failed in the existing server regression suite after the compile step had passed (326 tests: 1 failure, 2 import errors).

Root causes were inherited from this feature branch and were not introduced by the capability manifest:

- `test_geometry_uv_audit_mcp.py` installed a `png_validation` test shim globally in `sys.modules`.
- `test_reference_texture_transfer_mcp.py` replaced that module globally with a different shim.
- This polluted later imports: `test_png_validation` could not import `validate_png_bytes`, and `test_texture_link_audit_mcp` could not import `validate_png_file`.
- `test_mcp_server` expected a versioned README subsection, but the README only had the generic `## Release overview` heading.

Corrections committed to the PR branch:

- Both shims now use `patch.dict(sys.modules, ...)` only while importing the module under test, restoring the previous global module state afterward.
- `test_png_validation` now asserts that its import resolves to the repository's real `server/png_validation.py`.
- README heading is now `## 1.4.0: Release overview`.
- `test_mcp_server` verifies that the original three default prompts remain unchanged and in order, while allowing unique extensions.
- Package Integrity now accepts 1–32 unique non-empty default prompts and has regression tests for 11 prompts and duplicates.
- README validation evidence now correctly says 16-server MCP registry parity.

The initial failure is recorded, not hidden. The corrected code was re-tested successfully in GitHub Actions runs #41063133534 and #41063171785 on head `baadf1650e671ab2296750dc9e515d6ebbcedd44`. Both runs completed with `success`.


## Final CI evidence

The corrected PR head `baadf1650e671ab2296750dc9e515d6ebbcedd44` passed two GitHub Actions runs:

- [Run #41063133534](https://github.com/Stevesjsjsjs871/minecraft-bedrock-plugin/actions/runs/41063133534) — Success.
- [Run #41063171785](https://github.com/Stevesjsjsjs871/minecraft-bedrock-plugin/actions/runs/41063171785) — Success.

Observed test results in the completed job:

| Check | Result |
|---|---:|
| Main server regression suite | 359/359 |
| Shared PNG validator | 15/15 |
| Texture-link auditor | 20/20 |
| Benchmark evaluator | 12/12 |
| Mojang sample indexer | 6/6 |
| Procedural texture generator | 12/12 |
| Package Integrity unit tests | 11/11 |
| Local/remote capability contract | 4/4 |
| Analyzer regression cases | 18/18 |
| Python compilation | PASS |
| Manifest/version/MCP checks | PASS |

Package Integrity audit completed with **WARN** (14 PASS, 1 WARN, 0 FAIL): the full generated gzip Mojang index is absent, while 14 curated source files remain available for fallback search. Runtime/Minecraft checks remain NOT RUN.

The first failed run #41062741228 remains part of the history; the failures were corrected and the two subsequent runs passed.
