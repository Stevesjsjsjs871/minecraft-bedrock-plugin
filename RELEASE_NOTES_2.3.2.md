# Release Notes 2.3.2 — Code authoring quality and readability

## Classification
Medium improvement: shared code-quality guidance is now part of Core routing and is explicitly connected to the principal code/resource authoring workflows. Script API authoring guidance is more operational without introducing version-specific or unverified API calls.

## Changes
- Added a Core-level code authoring/maintainability contract that routes code and resource work through `references/code-quality-standard.md`.
- Added concise links to the shared standard in seven specialist authoring Skills: add-on creation, bundle authoring, content pipeline, cooking add-ons, entity authoring, entity pipeline and animated entity bundles.
- Added a version-gated Script API authoring checklist covering compatibility evidence, state/lifecycle ownership, execution model, failure behavior, tests and delivery evidence.
- Preserved the Skills-only architecture, existing Skill paths and specialist responsibilities. No bundled scripts or add-on source projects were changed.

## Validation
- Local validation completed: architecture 28/28, Core tests 183/183, full Python inventory 548/548 across 32 files, package integrity 20/20; see `VALIDATION_REPORT_2.3.2.md`.
- Minecraft Bedrock runtime, Plugin Host activation and actual Script API execution: NOT RUN.

## Compatibility / migration
Documentation-only workflow improvement. No add-on identifiers, manifests, resource paths, APIs, script behavior or runtime dependencies changed.
