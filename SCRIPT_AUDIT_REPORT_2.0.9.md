# Local Python utilities audit — Minecraft Bedrock Engineer 2.0.9 candidate

Date: 2026-11-07  
Verified Plugin Creator baseline: `minecraft-bedrock-engineer` 2.0.8, USER / PRIVATE, release `pluginrel_6aeee6028f38819198fb3c3d6a9b613a`.  
Candidate: 2.0.9. Local executor: CPython 3.13.5. Basis: supplied Technical Guide 2.0 and current plugin source inventory.

## Scope and inventory

- 90 Python files are present and registered: 56 active package files (55 under `skills/` plus shared root `archive_safety.py`) and 34 retained historical `server/` files.
- The 34 historical files were statically compiled but their code and tests were not executed. They remain inert migration material.
- All 90 files have six-level registry rows and current SHA-256 values. The package integrity checker verifies full path coverage, allowed status vocabulary and hash parity.
- Two incomplete texture-painter registry cards were completed. Two false dependency failures for visual-reference analysis were corrected: its package-local sibling modules are added to `sys.path` by the script and resolve in the complete package.

## Six-level evidence

| Level | Scope | Evidence / status |
|---|---|---|
| 1 — Discovery | All 90 Python files | PRESENT; exact paths and hashes in registry |
| 2 — Syntax | All package Python files | `python -m compileall -q .` — PASS |
| 3 — Dependencies | Active Skills utilities | CPython 3.13.5 imports resolve; optional `jsonschema==4.26.0` remains documented for benchmark/report/regression workflows |
| 4 — Runtime | 28 active Skills non-test entry points | `--help` smoke checks: 28/28 exit 0; full test runner executes each test file in isolated processes |
| 5 — Functional | 27 active test files | 27/27 files, 500/500 cases PASS |
| 6 — Plugin-host integration | Installed ChatGPT plugin | NOT TESTED; no actual installed-host invocation or package-mount proof |

Legacy `server/` entries remain `NOT_TESTED` for runtime/functional and `BLOCKED` for integration by the Skills-only architecture. Local compilation is syntax evidence only, not permission to execute legacy server code.

## Improvements in 2.0.9

`bedrock_audit.py` previously normalized backslashes and relied on exact-string duplicate detection. It also performed CRC/decompression before validating the member namespace. It now validates raw member names before decompression and rejects:

- NUL, absolute, drive-qualified, backslash, empty, dot and parent path segments;
- case-insensitive duplicate ZIP paths;
- Unix symbolic-link members;
- file/directory collisions and files used as parent directories.

Archives with structural path issues are not decompressed or marked `archive_valid`. The implementation reuses the existing pinned, bounded archive reader. Five new adversarial cases were added to `test_archive_safety.py`; focused suite is 17/17 PASS.

## Verification results

- `python -m compileall -q .` — PASS (syntax-only; no script execution implied).
- `python skills/package-integrity/scripts/run_skill_tests.py . --json ...` — 27/27 test files, 500/500 cases, 0 failures, 0 timeouts.
- All 28 non-test Skills Python entry points invoked with `--help` — 28/28 exit 0. This confirms CLI initialization only, not full scenario correctness.
- `python skills/bedrock-engineer-core/scripts/validate_domain_architecture.py . --json ...` — 28/28 checks PASS; 14 domains, 65 Skills, 8 workflow profiles.
- `python skills/package-integrity/scripts/check_skills_package.py . --json ...` — 19 PASS / 0 FAIL / 1 WARN. The single warning is the retained 34-file historical `server/` tree.
- `test_archive_safety.py` — 17/17 PASS; `test_reference_pack_audit.py` — 14/14 PASS; `regression_tests.py --auditor ...` — 18/18 synthetic cases PASS.

## Remaining boundaries

- `jsonschema==4.26.0` is optional and must be explicitly installed in environments running benchmark/report/regression validation. No automatic installation occurs.
- Some scripts are library modules or compatibility shims; they are not independent end-user tools. Their registry cards identify the canonical implementation and invocation boundaries.
- A passing local Python run does not establish script execution from an installed ChatGPT plugin.
- Minecraft import, rendering, Content Log and gameplay are NOT RUN.
- No MCP server, API endpoint, background executor or remote backend was introduced.

## Candidate decision

The source-level Python review and local regression gate pass. The candidate is suitable for guarded package update from 2.0.8 after the overlay is built and read back. It is not evidence of ChatGPT-host integration or Minecraft runtime readiness.
