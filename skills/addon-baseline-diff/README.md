# Add-on Baseline Diff

Read-only, bounded archive comparator for `.mcaddon` / `.mcpack` iterative development. It complements the single-candidate structural audit by identifying what changed between a known-good baseline and a new milestone.

It normalizes unique BP/RP pack roots, records added/removed/modified files by SHA-256, compares pack/header/module identity and versions, flags dependency/API/engine/format changes, checks visible and localized title parity for release candidates, parses strict JSON, and runs optional JavaScript syntax checks with `node --check`. It never edits either input archive and never executes add-on scripts.

Run the focused suite with:

```bash
python -m unittest discover -s skills/addon-baseline-diff/scripts -p 'test_*.py' -v
```

See `SKILL.md` for the workflow, statuses, limitations and review rules.
