# Regression Test Report — 2.3.0

## Full Skills suite
- Command: `python skills/package-integrity/scripts/run_skill_tests.py . --timeout 180 --json <report>`
- Environment: CPython 3.13.5, Linux x86_64.
- Result: **32/32 test files PASS; 546/546 cases; 0 failures; 0 timeouts.**

## Focused new/changed suites
- ZIP namespace/shared archive safety: 29/29 PASS.
- Benchmark builder: 10/10 PASS.
- Reference corpus indexer: 10/10 PASS.
- JSONC parser: 6/6 PASS.

## Package and architecture gates
- Strict package integrity: 20/20 PASS, 0 FAIL, 0 WARN.
- Architecture validator: 28/28 PASS; 14 domains, 71 Skills, eight profiles.
- Eight workflow profile smoke plans: 8/8 PASS.
- Python registry: 64/64 exact paths and hashes.

## Target environment
Installed Plugin Host activation and bundled-script execution are NOT VERIFIED. Minecraft import/render/gameplay/multiplayer and Creator Tools/Blockbench are NOT RUN.
