# Minecraft Bedrock Engineer 1.9.5

## Archive-safe add-on versioning

- Adds `addon_archive_versioning.py` for `.mcaddon`, `.mcpack` and ZIP-compatible add-on inputs.
- The archive helper is preview-only by default. `--apply` creates a new output archive and never overwrites the input.
- Rejects traversal/absolute paths, symbolic-link input/output paths and members, encrypted entries, duplicate/case-colliding members, suspicious compression ratios and oversized archives. Bounded member reads validate CRCs without a separate unbounded decompression pass.
- Verifies the rebuilt archive CRCs, manifest `header.version`, visible pack title or localized `.lang` value, existing module versions and in-project pack dependency versions.

## Folder and localization fixes

- Adds safe automatic discovery for one standard pack or one unambiguous BP/RP pair.
- Fails closed on multiple pack variants instead of incrementing unrelated manifests.
- Detects localized keys from actual `.lang` content, including keys without a dot.
- Keeps localization keys in `header.name`; per-language title overrides use `localized_display_names`.
- Replaces common existing version suffixes (plain, parenthesized and bracketed) rather than appending a second suffix.
- Adds projected and post-write verification, with an attempt to restore original files if post-write checks fail.

## Regression evidence

- Add-on folder versioning + archive versioning: 31/31 tests passed.
- Python compilation: PASS.
- Cinematic Interactions-style sample preview: `DRY_RUN`, version `1.2.3 → 1.2.4`, both BP/RP manifest versions, module versions, BP→RP dependency and English/Russian visible titles all verified in the preview.
- The reference fixture is synthetic and is not a copy of the user's actual add-on.
- Full Skills-only package integrity: NOT RUN in this partial working checkout.
- Minecraft import, pack replacement, in-game pack-list titles, rendering and gameplay: NOT RUN.
