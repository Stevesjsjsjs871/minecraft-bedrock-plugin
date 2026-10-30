# Minecraft Bedrock Engineer — 1.5.11

## Architecture

Minecraft Bedrock Engineer is a Skills-and-instructions-only plugin. It does not use MCP servers, registries, remote endpoints or a plugin-owned execution backend. Specialist skills define workflows; they do not create tools, grant filesystem access, run code or work in the background. Bundled scripts run only when the active host exposes a real executor and the package files are accessible.

## Supported workflows

- Version-aware BP/RP development and safe incremental changes to existing projects.
- Entities, blocks, items, recipes, Script API guidance, manifests and pack dependencies.
- RP UI-folder inventory, localization and cross-resource reference tracing.
- Geometry, models, a standalone classic/per-face UV analyzer and transparent UV template renderer, animation clips/controllers and entity bundle validation.
- Standalone PNG validation, static Geometry & UV parsing/auditing, transparent UV guide rendering, deterministic texture generation, geometry-aware painting plans and human-reviewed reference-to-UV mapping.
- `geometry-uv-engine` migration workflow with explicit separation between the currently executable PNG validator and UV algorithms still retained as dormant migration sources.
- Archive, package, manifest, resource integrity, baseline and regression audits.
- Mojang Samples indexing and official Creator documentation research with version/source provenance.
- Release preparation, evidence reporting and Skills-only package integrity checks.

## Execution contract

1. Start with `skills/skills-first-execution/SKILL.md` and select only relevant specialist skills.
2. Inspect supplied files or an actually connected workspace. Establish project root, target version and baseline before editing.
3. Use native file/code capabilities only when actually available. Otherwise provide a complete patch or exact reproducible commands and mark work `NOT APPLIED` / `NOT RUN`.
4. Preserve existing mechanics, UUIDs, identifiers, assets and unrelated files. No silent overwrite or deletion.
5. Prefer exact-version official docs and Mojang samples; cite provenance.
6. Re-open changed files and validate manifests, UUIDs, identifiers, resource references, PNG/UV/animation relationships as applicable.
7. Report exact commands, exit codes, test counts, limitations and runtime status. Static checks do not prove Minecraft import/render/gameplay.

## Maintenance and validation

Use `skills/skills-only-maintenance/SKILL.md` for plugin maintenance. Run the Skills-only package checker and its tests from the actual extracted package root:

```bash
python skills/package-integrity/scripts/check_skills_package.py .
python skills/package-integrity/scripts/test_check_skills_package.py -v
```

The legacy server source is not an active integration. Geometry/UV source logic is still in migration; do not claim the UV audit/template wrappers are callable. Reusable logic must be migrated to standalone utilities before legacy wrappers are removed. Runtime, multiplayer and Blockbench checks must be reported as `NOT RUN` unless actually performed.
