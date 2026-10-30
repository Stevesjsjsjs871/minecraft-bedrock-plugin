---
name: skills-only-maintenance
description: Use when maintaining, auditing or releasing Minecraft Bedrock Engineer itself; keep the Skills-only architecture coherent, remove stale tool assumptions and preserve useful domain logic.
---

# Skills-only maintenance

## Architecture invariants
- The active plugin interface is skills and instructions, not MCP. Never restore MCP servers, registries, endpoints or calls.
- Skills cannot create tools, grant filesystem access, run code, access a user's local project or work in the background.
- A bundled script is a local utility only. It is executable only when the host provides a real code executor and the package files are mounted.
- Keep specialist skills, examples, sample corpus, validators and useful algorithms. Reusable PNG validation is available as `skills/visual-resource-pipeline/scripts/png_engine.py` with a standalone CLI and focused tests. Geometry/UV static parsing now exists as `skills/geometry-uv-engine/scripts/geometry_engine.py` with independent tests. UV template rasterization is now available as `skills/geometry-uv-engine/scripts/uv_template_engine.py` with pixel-budget and no-overwrite safeguards plus focused tests; mesh projections remain out of scope. Do not remove a source module until its dependencies and reusable logic have been mapped and preserved or intentionally retired.

## Maintenance loop
1. Inspect current release metadata, all package paths and all skill frontmatter.
2. Inventory every executable script and its tests; map imports, references and input/output contracts.
3. Search all `SKILL.md` files for stale tool names, impossible execution claims, contradictory architecture, stale versions and commands targeting removed files.
4. Rewrite instructions to use real host capabilities and explicit fallbacks. Mark legacy code dormant if it is retained for migration; never advertise it as an active integration.
5. Remove only unambiguously generated artifacts (bytecode/cache, temporary files) and obsolete deployment wrappers whose purpose is exclusively retired infrastructure. Preserve reusable algorithms and their tests.
6. Run package checker and synthetic tests, compile standalone scripts, run available focused test suites, validate sample-index gzip/JSON and compare file inventory before/after.
7. Update README, CHANGELOG, VERSION, both manifests and release notes together. Verify parity after publishing.
8. Do not sync GitHub until the plugin candidate is internally consistent and the user requests publication.

## Release discipline
Every check must have a real command and result. Synthetic fixtures are not real-pack benchmarks. Game runtime and external interoperability remain `NOT RUN` unless actually tested. A release is not ready merely because Plugin Creator accepted the archive.
