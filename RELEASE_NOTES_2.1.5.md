# Release 2.1.5 — Junk-aware project analysis

## Added
- High-confidence filtering of obvious OS metadata, editor leftovers, caches, VCS internals and proven redundant build output from expensive semantic parsing.
- Explicit re-inclusion rules for references, manifests, build configuration, release artifacts, baseline deltas, security/integrity work and user-requested scope.
- Inventory/ledger accounting for excluded paths, reasons, counts and bytes; excluded files remain visible and can be reopened when evidence requires it.
- T2/T3 package-safety and integrity checks remain applicable even when semantic parsing is skipped.

## Safety invariants
- No blanket extension blacklist; unknown, binary, empty, small or merely unreferenced files are not automatically junk.
- No automatic deletion or modification of excluded files.
- Exclusion reduces expensive semantic work, not required coverage or evidence quality.
