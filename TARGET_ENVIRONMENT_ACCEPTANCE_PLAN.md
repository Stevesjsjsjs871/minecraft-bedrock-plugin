# Target Environment Acceptance Plan — 2.3.4

## A. Installed ChatGPT Plugin Host / Skills surface — NOT VERIFIED
1. Install/use the candidate only in a test environment; preserve the live 2.1.11 release.
2. Run all 295 prompts from `SKILL_ACTIVATION_TEST_MATRIX.csv` against the installed plugin surface. The matrix contains five designed scenarios for each of the 59 current Skills; all are initially `NOT RUN`.
3. Record selected Skill, actual response, missing inputs, capability route and exact host build for every case.
4. Run negative cases: unknown Skill, ambiguous intent, conflict between domains, unavailable tool, missing file, corrupt reference, invalid game version, incompatible constraints, interrupted/partial work.
5. Verify no phantom tool invocation, no automatic claim of local Python execution, and no completion while selected domains remain incomplete.

## B. Windows — NOT RUN
- Repeat the test runner, archive safety suites and three archive-size benchmarks on a clean Windows Python 3.13.x environment.
- Include symlink tests where permissions permit, invalid UTF-8 central-directory fixture, output overwrite refusal and path separator behavior.

## C. Android / Termux — NOT RUN
- Confirm Python availability and supported filesystem flags; `O_NOFOLLOW` fallback behavior; symlink and fstat identity tests; memory limits on device.
- Do not claim support until the complete focused suite passes on a named Android/Termux version.

## D. Minecraft Bedrock — NOT RUN
- Record exact game build, platform, experiments and Content Log state.
- Import the test BP/RP packs; inspect pack activation, manifest/dependency loading, entity spawn, geometry, textures, animations/controllers, UI, Script API and multiplayer behavior.
- Test Furniture duplicate-key files only in a disposable copy after explicit fixes; do not mutate the original archive.
- Validate Create Movement negative cube-size findings against the exact engine build before any edit.

## E. Blockbench / Creator Tools — NOT RUN
- Open representative geometry/animation source in the exact supported tool build.
- Verify geometry IDs, bone names, locators, UVs and animation/controller bindings.
- Record screenshots/logs and exact source hashes.

A completed manual test must include environment, input hashes, steps, expected/actual results, logs and pass/fail disposition. Until then keep each target environment status `NOT VERIFIED` / `NOT RUN`.
