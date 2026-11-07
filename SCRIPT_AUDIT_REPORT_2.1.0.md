# Python utility audit — Minecraft Bedrock Engineer 2.1.0 candidate

Date: 2026-11-07  
Live Plugin Creator baseline: 2.0.9 (`pluginrel_6aeef187613c819193b9fd1d4ef333e2`), USER / PRIVATE.  
Local executor: CPython 3.13.5. Basis: supplied Technical Guide 2.0 and the reconstructed 2.0.9 source tree.

## Inventory and cleanup

- Pre-cleanup package: 280 files, 65 Skills, 90 Python files.
- Removed 34 historical files under `server/` (17 implementation modules and 17 tests) after static dependency/provenance review; none were imported or executed.
- Retired the two server-specific migration analyzer files and replaced them with one documentation-contract test for the generic legacy project migration Skill.
- Current candidate: 305 files, 65 Skills, 89 Python files; no `server/` directory.
- All current Python files have a six-level registry row and refreshed SHA-256.

## Six-level evidence

| Level | Status | Evidence |
|---|---|---|
| 1 — Discovery | PRESENT | 89/89 Python files found in the candidate tree and registry. |
| 2 — Syntax | SYNTAX_OK | `python -m compileall -q .` — PASS. |
| 3 — Dependencies | DEPENDENCIES_OK | Local CPython 3.13.5 import/dependency checks and isolated test execution; optional `jsonschema==4.26.0` remains documented for benchmark/report/regression workflows. |
| 4 — Runtime | RUNTIME_OK | 27/27 active non-test entry points `--help` exit 0; all 27 test files executed in isolated processes. |
| 5 — Functional | FUNCTIONAL_OK | 27/27 test files, 500/500 cases PASS. |
| 6 — Plugin-host integration | NOT_TESTED | No controlled invocation of packaged Python from the installed Plugin Creator host. |

## Verification

- `python -m compileall -q .` — PASS.
- `python skills/package-integrity/scripts/run_skill_tests.py . --timeout 25 --json <report>` — 27/27 files, 500/500 cases PASS.
- Active Python entry points `--help` — 27/27 PASS.
- `python skills/bedrock-engineer-core/scripts/validate_domain_architecture.py .` — 27/27 PASS; 14 domains, 65 Skills, eight workflow profiles.
- `python skills/package-integrity/scripts/check_skills_package.py . --strict-skills-only` — 20/20 PASS.
- Skill catalog: 65/65 MBE Skills discovered and 65/65 instruction files loaded in the current ChatGPT skill runtime. Automatic selection in every installed-plugin surface remains NOT TESTED.

## Remaining boundaries

- Local Python 3.13.5 evidence only; installed Plugin Creator host script execution remains NOT TESTED.
- No real third-party `.mcaddon` / `.mcpack` archives were supplied; real add-on corpus testing is NOT RUN.
- Minecraft import, Content Log, rendering, gameplay, multiplayer, Blockbench and Creator Tools runtime are NOT RUN / NOT VERIFIED.
