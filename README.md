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

1. Start with skills/skills-first-execution/SKILL.md and select only relevant specialist skills.
2. Inspect supplied files or an actually connected workspace. Establish project root, target version and baseline before editing.
3. Use native file/code capabilities only when actually available. Otherwise provide a complete patch or exact reproducible commands and mark work NOT APPLIED / NOT RUN.
4. Preserve existing mechanics, UUIDs, identifiers, assets and unrelated files. No silent overwrite or deletion.
5. Prefer exact-version official docs and Mojang samples; cite provenance.
6. Re-open changed files and validate manifests, UUIDs, identifiers, resource references, PNG/UV/animation relationships as applicable.
7. Report exact commands, exit codes, test counts, limitations and runtime status. Static checks do not prove Minecraft import/render/gameplay.

## Maintenance and validation

Use skills/skills-only-maintenance/SKILL.md for plugin maintenance. First run the package-integrity regression tests:

```bash
python -m unittest discover -s skills/package-integrity/scripts -p 'test_*.py' -v
```

Build a deterministic candidate outside the source tree, extract it into a fresh directory, and run the strict release gate:

```bash
set -euo pipefail
mkdir -p dist
source_dir="$(mktemp -d)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$source_dir" "$tmp_dir"' EXIT
git archive HEAD | tar -x -C "$source_dir"
python skills/package-integrity/scripts/build_skills_package.py "$source_dir" dist/minecraft-bedrock-engineer.tar.gz --source-commit "$(git rev-parse HEAD)" --source-date-epoch "$(git show -s --format=%ct HEAD)"
tar -xzf dist/minecraft-bedrock-engineer.tar.gz -C "$tmp_dir"
python skills/package-integrity/scripts/check_skills_package.py "$tmp_dir"
(cd dist && sha256sum -c minecraft-bedrock-engineer.tar.gz.sha256)
```

The checker requires BUILD_PROVENANCE.json and rejects symlinks, special files, Python bytecode/cache directories, mismatched metadata, changed default prompts and altered payload hashes. A failed check blocks packaging; do not bypass it.

The current GitHub mirror is missing the exact binary Mojang Samples index included in Plugin Creator 1.5.12. Until that pinned file is restored, the extracted-package release gate is expected to fail and no release candidate may be published. Do not fabricate or partially regenerate the index.

Run only current standalone utilities and their corresponding tests. Historical changelog entries may mention retired architecture; they are retained as release history, not as active implementation. Runtime, multiplayer and Blockbench checks must be reported as NOT RUN unless actually performed.
