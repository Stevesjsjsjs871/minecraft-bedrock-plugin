# Release Notes — 2.1.3

## Faster, staged project analysis

- Adds `fast-project-analysis` for large add-ons and multi-file projects.
- Introduces staged inventory, classification, targeted reads, dependency-slice expansion and batched independent checks.
- Adds verified incremental reuse rules: changed files and reverse dependents are re-analyzed; stale or unverifiable caches are rejected.
- Reuses one compact evidence index across selected domain Skills to reduce repeated file discovery.
- Keeps full coverage mandatory for whole-project audits and release gates; skipped, unsupported and malformed files remain explicit coverage gaps.
- Preserves source files, path case, project identity, privacy and all 12 default prompts.
- Static package update does not establish Minecraft runtime behavior.
