# CI regression report — 2026-10-30

## Baseline

- GitHub `main` before this fix: `45e44ac18ea68c0841d44b480ef43c27dcdd7ff2` (`1.3.0`).
- Latest main CI run inspected: [41035640091](https://github.com/Stevesjsjsjs871/minecraft-bedrock-plugin/actions/runs/41035640091), failed in `python-checks`.
- The job compiled successfully, then ran 326 unit tests: 1 failure and 2 import errors.
- Current Plugin Creator was independently re-read as version `1.4.0`, Release ID `pluginrel_6ae46dc1108081919af9b64db0daf321`. This run did not modify Plugin Creator.

## Root causes confirmed from CI logs

1. Several overlay tests injected different fake modules into global `sys.modules["png_validation"]` at test-module import time. Those stubs were never restored, so the production `test_png_validation` and `test_texture_link_audit_mcp` imports could receive an incomplete stub rather than `server/png_validation.py`.
2. `test_manifest_versions_sync_with_server` required a README heading matching `## 1.3.0:`, while the 1.3.0 README used the unversioned heading `## Release overview`.

## Changes in this branch

- Scope each PNG validator test shim to a `patch.dict(sys.modules, ...)` import context; always create a dedicated stub instead of inheriting a previous test module's stub.
- Add an explicit server path in the affected test modules so the import target is deterministic.
- Add a regression assertion that `test_png_validation` resolves to the repository's real `server/png_validation.py`.
- Make the README release-overview heading versioned (`## 1.3.0: Release overview`) to satisfy the existing version contract without weakening the test.

## Files changed

- `server/tests/test_geometry_uv_audit_mcp.py`
- `server/tests/test_reference_mapping_review_mcp.py`
- `server/tests/test_reference_texture_transfer_mcp.py`
- `server/tests/test_texture_painting_mcp.py`
- `server/tests/test_uv_mapping_assistant_mcp.py`
- `server/tests/test_visual_reference_analyzer_mcp.py`
- `server/tests/test_png_validation.py`
- `README.md`

## Verification

- Source changes are committed on a branch based on `45e44ac18ea68c0841d44b480ef43c27dcdd7ff2`.
- GitHub Actions for this branch: pending until the Draft PR is created.
- Local execution: NOT RUN in this environment.
- Minecraft import/runtime, Creator Tools CLI and Blockbench interoperability: NOT RUN.

## Risks / next steps

- Confirm the full Python 3.12 workflow passes after the isolation change.
- If failures remain, inspect the exact test module import order and avoid replacing the production validator with a test shim.
- The separate Plugin Creator parity work in PR #9 remains open and unmerged; this branch does not alter it.
- The current Plugin Creator 1.4.0 release and Release ID are recorded above; no Plugin Creator update or new release was performed in this run.


## Follow-up CI finding

The first PR run (`41041619223`) confirmed that the two PNG import errors were fixed: the full server suite reached 359 tests. One assertion remained too strict: it required exactly three default prompts, while the 1.3.0 manifests contain 11 prompts. The first three are the original create/audit/research prompts and match the compatibility manifest exactly.

The version contract now asserts:
- the two manifests have identical prompt arrays;
- the original three prompts remain unchanged and in their original order;
- additional prompts are allowed;
- prompt entries remain unique.

This preserves the user's three original defaults without blocking later workflow-specific prompts.


## Package-integrity follow-up

After the PNG import fixes, the full server suite passed (359/359). The package-integrity audit then exposed a second obsolete assumption: its prompt validator allowed only 1–3 entries, while the 1.3.0 manifests contain 11 unique entries and the current Plugin Creator 1.4.0 contains 12. This contradicted the project requirement to preserve the original three prompts while permitting later workflow prompts.

The package-integrity validator now accepts 1–32 unique, non-empty prompt strings and still requires exact ordered equality between root and compatibility manifests. Added regression coverage for an 11-entry prompt list and duplicate rejection.

The server contract test separately verifies that the original three create/audit/research prompts remain unchanged and are the ordered prefix of the current list.


## Workflow version-source follow-up

After the prompt validator fix, all test suites and the package-integrity audit passed, but the final workflow contract step still failed. Its inline script hard-coded `expected = "1.0.14"` even though the release synchronization had moved the repository to 1.3.0. The workflow now reads the expected version from the repository's `VERSION` marker, then checks both manifests and all three server version constants against that value. The package-integrity audit remains responsible for strict SemVer validation.


## Final verification

- Latest executable-code commit: `3b77fc87b3fa648f9f46e08c43159abb0bf93d19`; subsequent report-only commits were also validated by CI run `41042035869`.
- Final GitHub Actions run: [41041952864](https://github.com/Stevesjsjsjs871/minecraft-bedrock-plugin/actions/runs/41041952864) — **Success** on Ubuntu 24.04 / Python 3.12.15.
- Server suite: 359/359.
- PNG validator suite: 15/15.
- Texture-link auditor suite: 20/20.
- Benchmark evaluator: 12/12.
- Mojang indexer: 6/6.
- Procedural texture generator: 12/12.
- Package-integrity tests: 11/11.
- Package-integrity audit completed with a known WARN: full generated Stable gzip index is absent in this main-branch source snapshot; 14 curated files remain for fallback search. No FAIL was reported.
- Final workflow manifest/config/server-version contract: PASS at version 1.3.0.
- Python compilation: PASS.

Local test execution, Minecraft runtime/import, Creator Tools CLI, Windows and macOS: NOT RUN.


## Cross-source release observation for the next stage

A fresh read after CI completion shows Plugin Creator is now at 1.4.0 (`pluginrel_6ae46dc1108081919af9b64db0daf321`, created 2026-10-30 10:13:21 UTC), while GitHub `main` is 1.3.0 at `45e44ac18ea68c0841d44b480ef43c27dcdd7ff2` (2026-10-30 09:44:33 UTC).

- Plugin Creator inventory: 100 files, 2,690,379 declared bytes.
- Plugin Creator: 16 MCP servers, 12 prompts; both MCP configs agree, all 16 referenced server scripts exist, and the original three prompts remain the unchanged prefix.
- GitHub main: 15 MCP servers, 11 prompts; both original manifests agree.
- Primary `mcp_server.py`: Plugin Creator 111,558 bytes / 14 registered tool names; GitHub main 156,721 bytes / 19 registered tool names. Four Creator Tools bridge registrations are absent from the Plugin Creator primary server: `creator_tools_status`, `creator_tools_catalog`, `validate_with_mct`, and `create_entity_with_mct`.
- No `BUILD_PROVENANCE.json` is present in the Plugin Creator inventory.

This is a source-provenance/parity issue for the next stage, not a regression caused by this CI repair. This run did not change Plugin Creator or create a release.
