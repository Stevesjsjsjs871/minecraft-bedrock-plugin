# Release 2.0.8 — Local script audit and evidence refresh

## Scope

Audited all bundled Python files against the supplied Technical Guide 2.0 six-level model. Preserved the Skills-only architecture, all 65 Skill paths, all 12 default prompts, and 34 inert legacy server files.

## Changes

- Added `SCRIPT_AUDIT_REPORT_2.0.8.md` with factual local verification, scope boundaries and repair priorities.
- Refreshed `SCRIPT_EXECUTION_REGISTRY.csv` for all 90 Python files, with current SHA-256 hashes and clear host-integration status.
- Updated Tool Registry evidence to reflect the actual 2.0.7 source read-back and local Python executor checks.
- Clarified in documentation that local script execution does not imply execution inside the installed ChatGPT plugin host.

## Verification

- CPython 3.13.5 `compileall`: PASS.
- Skills-local test runner: 27/27 files, 495/495 tests PASS.
- Architecture validation: 28/28 PASS.
- Package integrity: 19 PASS / 0 FAIL / 1 WARN (34 retained inert historical `server/` files). Strict Skills-only gate remains blocked by that retained footprint.
- Plugin-host script integration: NOT TESTED. Minecraft runtime: NOT RUN.
- Historical `server/`/MCP code was not executed.
