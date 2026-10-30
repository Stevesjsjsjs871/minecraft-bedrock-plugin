---
name: validation-runbook
description: Use to run and report the current Skills-only Minecraft Bedrock Engineer package validation suite without relying on retired MCP/server tests.
---

# Skills-only validation runbook

Run from the root of the exact extracted candidate package. First confirm the package version in `VERSION` and both manifests.

## 1. Package preflight
```bash
python skills/package-integrity/scripts/check_skills_package.py .
python skills/package-integrity/scripts/test_check_skills_package.py -v
```
The checker tests package structure and sample-index integrity. Its synthetic tests test the checker itself; they do not prove Bedrock runtime behavior.

## 2. Compile current standalone utilities
```bash
python -m py_compile   skills/automated-validation/scripts/bedrock_audit.py   skills/automated-validation/scripts/validate_report.py   skills/regression-evals/scripts/regression_tests.py   skills/audit-benchmark/scripts/evaluate_benchmark.py   skills/bedrock-development/scripts/index_mojang_samples.py   skills/package-integrity/scripts/check_skills_package.py   skills/visual-resource-pipeline/scripts/generate_texture.py \
  skills/visual-resource-pipeline/scripts/png_engine.py
```

## 3. Focused unit suites
```bash
python -m unittest discover -s skills/audit-benchmark/scripts -p 'test_*.py' -v
python -m unittest discover -s skills/bedrock-development/scripts -p 'test_*.py' -v
python -m unittest discover -s skills/visual-resource-pipeline/scripts -p 'test_*.py' -v
```
Run only suites whose files are present in this candidate. Do not use stale `server/tests` or MCP registry suites as the current Skills-only release gate.

## 4. Project audit and regression
Inspect `bedrock_audit.py --help` before choosing arguments. Run the auditor against a supplied test pack or candidate, then run the regression harness with its documented options. Validate the report schema only if the required validator is already available; do not silently install dependencies.

## 5. Final checks
- Parse both manifests and compare version, identity, skill path and default prompts.
- Verify every `SKILL.md` has unique frontmatter name and a non-empty description.
- Search current skill instructions for stale calls to unavailable tools and contradictory architecture claims.
- Check the compressed Mojang Samples index and metadata.
- Inspect ZIP contents and hashes if a release archive was built.
- Record Minecraft import/render/gameplay, multiplayer and Blockbench checks as `NOT RUN` unless performed.

## Evidence discipline
Capture exact commands, interpreter version, exit codes, pass/fail/error/skip counts and relevant output. If the package is not accessible to the current executor, report `BLOCKED` and provide commands for a real checkout. Never mark an unexecuted test as `PASS`.
