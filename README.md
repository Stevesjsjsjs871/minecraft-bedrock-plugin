# Minecraft Bedrock Engineer — 1.5.11

## Architecture

Minecraft Bedrock Engineer is a Skills-and-instructions-only project. The active architecture is based on specialist skills, bundled reference data and standalone scripts. No MCP server, registry, remote endpoint, Cloudflare worker or plugin-owned execution backend is part of this repository. Skills define workflows; they do not create tools, grant filesystem access, run code or work in the background. Scripts run only when the host provides a real executor and the package files are accessible.

The GitHub source intentionally excludes retired server wrappers and their obsolete tests. The Plugin Creator package remains the distribution artifact; this repository is the maintained Skills-first source mirror.

## Supported workflows

- Version-aware BP/RP development and safe incremental changes to existing projects.
- Entities, blocks, items, recipes, Script API guidance, manifests and pack dependencies.
- RP UI-folder inventory, localization and cross-resource reference tracing.
- Geometry, models, classic/per-face UV analysis and transparent UV template rendering.
- Standalone PNG validation, deterministic texture generation, geometry-aware painting plans and human-reviewed reference-to-UV mapping.
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

Use `skills/skills-only-maintenance/SKILL.md` for plugin maintenance. Run the active Skills-only package checker and its tests from the actual extracted package root:

```bash
python skills/package-integrity/scripts/check_skills_package.py .
python skills/package-integrity/scripts/test_check_skills_package.py -v
```

Run only current standalone utilities and their corresponding tests. Historical changelog entries may mention retired architecture; they are retained as release history, not as active implementation. Runtime, multiplayer and Blockbench checks must be reported as `NOT RUN` unless actually performed.
