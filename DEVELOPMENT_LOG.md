# Development Log

## 2026-10-30 — Package integrity and provenance hardening

- Baseline: GitHub Skills-first source 1.5.11 at 208753f84a31ab4eae1ecfddc4a44eef7a87c7c0; Plugin Creator 1.5.12, Release ID pluginrel_6ae4b2ea22f88191a00187713b7e9b91.
- Finding: Plugin Creator package inventory has 163 files, one generated .pyc (14,282 bytes), and no BUILD_PROVENANCE.json. The GitHub mirror lacks the exact compressed Mojang Samples 1.26.50.4 index.
- Changes: safe package inventory, deterministic tar.gz builder, mandatory per-file provenance validation, archive SHA-256 sidecar, README/CHANGELOG/version parity, first-three-default-prompt preservation, bytecode/symlink/special-file rejection.
- Files: skills/package-integrity/scripts/package_provenance.py; build_skills_package.py; check_skills_package.py; test_build_skills_package.py; test_check_skills_package.py; skills/package-integrity/SKILL.md; README.md; .github/workflows/validate.yml; GITHUB_SYNC_NOTES.md.
- Local tests: compileall PASS; 32/32 package/provenance tests PASS; deterministic archive smoke test PASS.
- CI #41089549833: package/provenance step PASS; audit-benchmark step 10/12 FAIL because jsonschema was not installed. Added pinned jsonschema==4.26.0 and a workflow install step; rerun #41090000560 queued.
- NOT RUN: full package build/extracted release gate (missing exact binary index); actual Plugin Creator archive verification (archive download unavailable); Minecraft/Blockbench runtime.
- Safety: Plugin Creator unchanged; no merge or public release; original three prompts preserved; no Spatial GUI.
- Next: restore exact pinned binary index, run full extracted-package gate, then reconcile GitHub source 1.5.11 with Plugin Creator 1.5.12.
