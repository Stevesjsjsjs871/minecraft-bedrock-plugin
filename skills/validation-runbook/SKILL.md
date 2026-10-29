---
name: validation-runbook
description: Use to execute and record the complete local validation suite for Minecraft Bedrock Engineer and to distinguish actual command results from unexecuted test instructions.
---

# Validation Runbook

## Run from the package root
Use the current checkout/package and its installed Python version. Do not run a stale archive or an extracted candidate whose version differs from the manifests.

1. Run the package integrity preflight (including full gzip sample-index verification):
   `python skills/package-integrity/scripts/check_package_integrity.py .`
2. Test the new preflight against positive and negative synthetic fixtures:
   `python skills/package-integrity/scripts/test_check_package_integrity.py -v`
3. Compile all shipped Python:
   `python -m py_compile archive_safety.py server/mcp_server.py server/tests/test_mcp_server.py skills/automated-validation/scripts/bedrock_audit.py skills/automated-validation/scripts/validate_report.py skills/regression-evals/scripts/regression_tests.py skills/audit-benchmark/scripts/evaluate_benchmark.py skills/audit-benchmark/scripts/test_evaluate_benchmark.py skills/bedrock-development/scripts/index_mojang_samples.py skills/bedrock-development/scripts/test_index_mojang_samples.py skills/package-integrity/scripts/check_package_integrity.py skills/package-integrity/scripts/test_check_package_integrity.py`
4. MCP test suite:
   `python -m unittest discover -s server/tests -v`
5. Benchmark evaluator suite:
   `python -m unittest discover -s skills/audit-benchmark/scripts -p 'test_*.py' -v`
6. Mojang sample-index tests:
   `python -m unittest discover -s skills/bedrock-development/scripts -p 'test_*.py' -v`
7. Analyzer regression scenarios:
   `python skills/regression-evals/scripts/regression_tests.py --auditor skills/automated-validation/scripts/bedrock_audit.py`
8. Report schema dependency:
   Check whether `jsonschema` is installed; if not, mark schema validation `BLOCKED` rather than installing packages without authorization.
9. Version consistency:
   Parse `VERSION`, `plugin.json`, `.codex-plugin/plugin.json` and load `server/mcp_server.py` to confirm a single version and preserved prompts/config.
10. Validate the packaged plugin archive and check all new/retained skills referenced by its manifests.
11. If a tool executor or runtime isn't available, record `BLOCKED`/`NOT RUN` and provide the exact command for the user. Never infer success from old development notes.

## Output discipline
Capture actual exit codes, exact pass/fail/error/skip counts and abbreviated relevant logs. If the command didn't execute, it cannot be `PASS`. Don't replace a failing test with a weaker assertion without explaining the contract change.
