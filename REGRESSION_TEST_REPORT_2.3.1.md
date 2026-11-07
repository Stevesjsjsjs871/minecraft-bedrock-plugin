# Regression Test Report — 2.3.1

## Full Skills suite
- Command: `python skills/package-integrity/scripts/run_skill_tests.py . --timeout 60 --json <report>`
- Environment: CPython 3.13.5, Linux x86_64.
- Result: **32/32 test files PASS; 548/548 cases; 0 failures; 0 timeouts.**
- New Project State tests: symlink hash rejection and path-identity replacement rejection; Project State suite 30/30 PASS.

The same complete suite was rerun from a clean extraction of the final candidate ZIP: 32/32 files and 548/548 cases PASS.

## Package and architecture gates
- Strict package integrity: 20/20 PASS, 0 FAIL, 0 WARN.
- Architecture validator: 28/28 PASS; 14 domains, 71 Skills, eight profiles.
- Python registry: 64/64 exact paths and hashes, verified by package integrity checker.
- Version markers: VERSION, plugin.json and .codex-plugin/plugin.json all 2.3.1.
- Default prompts: 12/12 preserved exactly.

## Target environment
Installed Plugin Host activation and bundled-script execution are NOT VERIFIED. Windows/Android portability and Minecraft runtime are NOT RUN.
