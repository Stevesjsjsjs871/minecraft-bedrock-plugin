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
archive="$tmp_dir/bedrock-samples-v1.26.50.4-full.zip"
index="$tmp_dir/mojang-samples-index.json.gz"
curl --fail --location --output "$archive" \
  https://github.com/Mojang/bedrock-samples/releases/download/v1.26.50.4/bedrock-samples-v1.26.50.4-full.zip
PYTHONDONTWRITEBYTECODE=1 python skills/bedrock-development/scripts/restore_mojang_index.py "$archive" \
  --metadata skills/bedrock-development/references/mojang-samples-1.26.50.4/INDEX_METADATA.json \
  --indexer skills/bedrock-development/scripts/index_mojang_samples.py --output "$index"
git archive HEAD | tar -x -C "$source_dir"
cp "$index" "$source_dir/skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz"
PYTHONDONTWRITEBYTECODE=1 python skills/package-integrity/scripts/build_skills_package.py "$source_dir" dist/minecraft-bedrock-engineer.tar.gz --source-commit "$(git rev-parse HEAD)" --source-date-epoch "$(git show -s --format=%ct HEAD)"
tar -xzf dist/minecraft-bedrock-engineer.tar.gz -C "$tmp_dir"
PYTHONDONTWRITEBYTECODE=1 python skills/package-integrity/scripts/check_skills_package.py "$tmp_dir"
(cd dist && sha256sum -c minecraft-bedrock-engineer.tar.gz.sha256)
```

The checker requires BUILD_PROVENANCE.json and rejects symlinks, special files, Python bytecode/cache directories, mismatched metadata, changed default prompts and altered payload hashes. Run the builder and extracted checker with \`PYTHONDONTWRITEBYTECODE=1\`; the package gate still rejects any cache directory that is present. A failed check blocks packaging; do not bypass it.

The provenance file and SHA-256 sidecar provide integrity metadata, not a digital signature or independent identity attestation. Verify the recorded Git commit and successful CI run against a trusted repository before distributing a candidate.

The generated Mojang Samples index is restored from the official v1.26.50.4 full release asset. The upstream ZIP SHA-256 is pinned as \`c0b6151f5f9a0c31ebe3c909dfc82d97f12473ed2c6e039aa7e22d667042026c\`; the deterministic regenerated gzip is pinned as 1,128,406 bytes with SHA-256 \`48429d64391157553e6760b7f568e5e6d5d05fa6517427b5a1156c8bc18e61fc\`. It contains 22,252 indexed entries from 22,859 ZIP entries, with all category totals checked. Plugin Creator 1.5.12's stored gzip is 1,128,413 bytes; its bytes were not retrieved for direct comparison, so byte-for-byte parity is not claimed. The GitHub candidate is independently pinned to the deterministic generated index hash.

Run only current standalone utilities and their corresponding tests. Historical changelog entries may mention retired architecture; they are retained as release history, not as active implementation. Runtime, multiplayer and Blockbench checks must be reported as NOT RUN unless actually performed.
