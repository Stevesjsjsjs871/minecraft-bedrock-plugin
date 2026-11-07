# Minecraft Bedrock Engineer 1.9.6

## Deterministic add-on baseline diff

- Adds `skills/addon-baseline-diff/SKILL.md` and `scripts/addon_baseline_diff.py` to compare a known-good `.mcaddon` / `.mcpack` with a candidate.
- Uses SHA-256 file deltas and normalizes unambiguous BP/RP root folder names, so renaming a pack root does not appear as wholesale deletion/addition.
- Checks pack header UUIDs, module UUID/version layout (including repeated module types), internal dependency versions, `format_version`, `min_engine_version`, Script API dependency drift, and pack version/title parity when `--release-candidate` is selected.
- Detects unsafe ZIP paths, duplicate/case-colliding entries, symlinks, encrypted members, suspicious compression ratios, duplicate JSON keys and JavaScript syntax errors. It does not execute pack scripts.
- Dotted and undotted localization keys are handled by checking actual matching `.lang` entries; every matching translation must carry the candidate version.
- Integrates the comparator into baseline regression, existing add-on routing and build/release instructions.

## Validation

- Add-on baseline diff tests: 27/27 passed.
- Folder/archive add-on versioning tests: pending full combined run.
- Python compile checks: pending final combined run.
- Full package-integrity checker: NOT RUN in the partial working checkout.
- User's WB07 archive: not read by the local runner; no WB07-specific pass is claimed.
- Minecraft import/render/gameplay/performance profiling: NOT RUN.
