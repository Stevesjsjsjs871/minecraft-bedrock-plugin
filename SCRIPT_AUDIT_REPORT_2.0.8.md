# Local Python utilities audit — Minecraft Bedrock Engineer 2.0.8 candidate

Date: 2026-11-07  
Baseline: Plugin Creator release `pluginrel_6aeeddbe253c8191bcef99177e2be8c2` (2.0.7); candidate source tree `2.0.8`.  
Local executor: CPython 3.13.5 in the development container.  
Scope: bundled Python files, their tests, local command interfaces and the six-level model from the supplied technical guide.

## Executive result

- 90 Python files registered in `SCRIPT_EXECUTION_REGISTRY.csv`; this includes 34 historical `server/` files. The active Skills tree contains 56 Python files (including tests) and is kept separate from historical server code.
- `compileall` for the active package: PASS.
- Skills-local test runner: **27/27 test files, 495/495 tests PASS**.
- Domain architecture validation: **28/28 PASS**, 14 domains, 65 registered/discovered Skills, 8 workflow profiles.
- Package integrity: **19 PASS / 0 FAIL / 1 WARN**. The warning is the 34-file inert historical `server/` tree. Strict Skills-only mode intentionally fails on this retained historical footprint.
- Installed ChatGPT-host execution/integration remains **NOT TESTED**. Local Python PASS does not prove that ChatGPT can execute bundled scripts or mount plugin package paths.
- No legacy MCP/server implementation was executed. The 34 historical files remain inert migration inputs; no deletion was authorized or performed.

## Six-level interpretation

The registry uses the supplied guide's levels: discovery, syntax, dependencies, local runtime, functional behavior, and integration with the installed plugin host. For current Skills scripts, discovery and syntax are confirmed by the package inventory and Python compilation. Runtime and functional status are based only on the local test runner/actual local CLI smoke runs. Integration remains NOT_TESTED throughout because no installed-plugin host script invocation was available.

## Verified command evidence

| Check | Result |
|---|---|
| `python -m compileall -q skills archive_safety.py` | PASS, exit 0 |
| `python skills/bedrock-engineer-core/scripts/validate_domain_architecture.py .` | PASS, 28/28 |
| `python skills/package-integrity/scripts/run_skill_tests.py . --json ...` | PASS, 27 files, 495 tests, 0 failed, 0 timed out |
| `python skills/package-integrity/scripts/check_skills_package.py .` | PASS, 19/20 checks, 0 failures, 1 warning |
| `python skills/bedrock-engineer-core/scripts/plan_domain_work.py --list-profiles` | PASS, 8 profiles emitted |
| `--help` smoke checks: bedrock audit, report validator, add-on archive versioner, change-impact analyzer, project-state utility, reference-pack auditor, regression harness | PASS, each returned 0 |
| `python -m unittest discover -s skills/visual-reference-analysis/scripts ...` | PASS after reconstructing the current source tree with the missing 2.0.7 script/test files |
| `python skills/version-governance/scripts/version_governance.py validate 2.0.8` | PASS, valid SemVer candidate |
| Legacy `server/` code/tests | NOT RUN by design; excluded by Skills-only boundary |

## Findings and repair priorities

1. **Archive/source discrepancy must remain visible.** The small 2.0.7 update overlay ZIP contains 30 files and intentionally omits unchanged source files; it is not a complete source archive. The full 261-file baseline upload is used as a source reconstruction only, then current 2.0.7 local state is layered on top. Plugin Creator's paginated current inventory confirms 275 files and 65 Skills. Do not use the overlay ZIP alone as a complete checkout.
2. **`run_skill_tests.py` is present in current 2.0.7 source and used for authoritative test execution.** It is absent from the older uploaded baseline ZIP, so that older tree's direct `unittest discover -s skills` command discovers zero tests. Use the current packaged runner, not root-level broad discovery.
3. **Dependency checks are environment-specific.** The registry's dependency status refers to CPython 3.13.5 in this development container. `jsonschema` is used by benchmark/report/regression paths and is installed in this environment; portable environments need that dependency documented/provisioned before those paths are run. No installation was attempted.
4. **Some Python files are libraries or compatibility shims, not standalone commands.** `geometry-uv-engine/scripts/png_engine.py` forwards into the canonical `visual-resource-pipeline/scripts/png_engine.py`; `package-integrity/scripts/check_package_integrity.py` forwards to `check_skills_package.py`; `archive_safety.py` is a shared module; test files are test entry points. Their CLI/API status should not be conflated.
5. **Legacy source remains inert.** `server/` contains historical MCP adapters and tests. Their code must not be executed under the active architecture. The read-only legacy audit classifies source and dependencies but does not authorize deletion or migration.
6. **No ChatGPT Python execution capability is established.** Skills describe optional local scripts and must route to `no_execution_route` when no genuine executor/package mount is present. Do not state that these scripts run inside the ChatGPT plugin.

## 2.0.8 utility improvements and fresh evidence

The 2.0.8 candidate hardens `reference_pack_audit.py`: single-descriptor archive pinning for both SHA-256 and ZIP reads, regular non-symlink input enforcement, raw member path validation, case-insensitive duplicate detection, file/directory collision detection, and metadata/size preflight before CRC/decompression. Six new tests cover these failure modes.

Direct local execution evidence:
- `bedrock_audit.py` on generated valid `.mcpack`: exit 0, archive_valid=true, findings=0, recommendation explicitly says runtime not verified.
- `validate_report.py` on the generated report: exit 0; on deliberately incomplete JSON: exit 1 with six schema violations.
- `analyze_change_impact.py` on a generated BP/RP project: exit 0, summary PASS, 11 graph edges, one affected consumer, no unresolved references.
- `reference_pack_audit.py` on the generated pack: exit 0/status PASS. On user-supplied `plugin (4).zip`: 261 entries, no unsafe paths, no duplicates, no JSON failures; archive SHA-256 `52031c94f3917d5e0c38e3bcd130527d49d303158f851bc8d9ceec5291c7bff5`.
- `regression_tests.py --auditor ...`: 18/18 synthetic cases PASS.
- `check_package_integrity.py` compatibility shim: exit 0; `geometry-uv-engine/scripts/png_engine.py --help`: exit 0.
- Reference archive auditor tests: 14/14 PASS; full Skills suite after changes: 27/27 files, 495/495 cases PASS.

`jsonschema` optional requirement and tested local version are documented in `OPTIONAL_PYTHON_DEPENDENCIES.md`. Host/plugin script integration remains NOT TESTED; Minecraft import/render/gameplay remains NOT RUN. Legacy `server/` code remains inert and unexecuted.
