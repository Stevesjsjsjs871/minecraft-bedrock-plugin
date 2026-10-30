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
