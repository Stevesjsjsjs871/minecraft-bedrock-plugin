# Minecraft Bedrock Engineer — 1.5.13

## Architecture

Minecraft Bedrock Engineer combines specialist Skills, versioned references, standalone validators, **16 local STDIO MCP server processes**, a Creator Tools CLI bridge and a separately connected Cloudflare Streamable HTTP gateway. The local servers are declared in `mcp.json` and `.mcp.json`; their working directory and `MINECRAFT_BEDROCK_WORKSPACE` are scoped to `${PLUGIN_DATA}`. Local STDIO requires a host that can launch Python 3 processes and expose their tools.

The core local server exposes 19 tools, including `creator_tools_status`, `creator_tools_catalog`, `validate_with_mct` and `create_entity_with_mct`. Specialist servers cover textures, entities, animations, geometry/UV and reference transfer. The separately connected remote Worker at `https://minecraft-bedrock-plugin.msg2026.workers.dev/mcp` exposes four tools for manifest generation/validation, bounded public source reads and capability reporting; it does not access local files or invoke MCT CLI. Its Bearer credential remains client-managed and is never stored in this repository.

Skills define workflows but do not themselves grant filesystem access, execution or background work. Verify live MCP connections and tool lists; a config file alone is not proof of a running server.

## Supported workflows

- Version-aware BP/RP development and safe incremental changes to existing projects.
- Entities, blocks, items, recipes, Script API guidance, manifests and pack dependencies.
- RP UI-folder inventory, localization and cross-resource reference tracing.
- Geometry, models, classic/per-face UV analysis and transparent UV template rendering.
- Standalone PNG validation, deterministic texture generation, geometry-aware painting plans and human-reviewed reference-to-UV mapping.
- Archive, package, manifest, resource integrity, baseline and regression audits.
- Mojang Samples indexing and official Creator documentation research with version/source provenance.
- MCP-assisted authoring and audits, Creator Tools CLI status/catalog/validation handoff, release preparation, evidence reporting and package integrity checks.

## Execution contract

1. Start with skills/skills-first-execution/SKILL.md; verify actual MCP availability, then select only relevant specialist skills.
2. Inspect supplied files or an actually connected workspace. Establish project root, target version and baseline before editing.
3. Use local STDIO MCP only when the host has started the server and the workspace is available; use the remote Worker only for its four declared capabilities. Otherwise use native file/code capabilities or provide a patch and mark work NOT APPLIED / NOT RUN.
4. Preserve existing mechanics, UUIDs, identifiers, assets and unrelated files. No silent overwrite or deletion.
5. Prefer exact-version official docs and Mojang samples; cite provenance.
6. Re-open changed files and validate manifests, UUIDs, identifiers, resource references, PNG/UV/animation relationships as applicable.
7. Report exact commands, exit codes, test counts, limitations and runtime status. Static checks do not prove Minecraft import/render/gameplay.

## Maintenance and validation

Use skills/plugin-maintenance/SKILL.md for plugin maintenance. First run the package-integrity regression tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s skills/package-integrity/scripts -p 'test_*.py' -v
```

Build a deterministic candidate outside the source tree, extract it into a fresh directory, and run the strict release gate:

```bash
set -euo pipefail
mkdir -p dist
source_dir="$(mktemp -d)"
tmp_dir="$(mktemp -d)"
extract_dir="$(mktemp -d)"
trap 'rm -rf "$source_dir" "$tmp_dir" "$extract_dir"' EXIT
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
tar -xzf dist/minecraft-bedrock-engineer.tar.gz -C "$extract_dir"
PYTHONDONTWRITEBYTECODE=1 python skills/package-integrity/scripts/check_skills_package.py "$extract_dir"
(cd dist && sha256sum -c minecraft-bedrock-engineer.tar.gz.sha256)
```

The checker requires BUILD_PROVENANCE.json and rejects symlinks, special files, Python bytecode/cache directories, mismatched metadata, changed default prompts and altered payload hashes. Run the builder and extracted checker with \`PYTHONDONTWRITEBYTECODE=1\`; the package gate still rejects any cache directory that is present. A failed check blocks packaging; do not bypass it.

The provenance file and SHA-256 sidecar provide integrity metadata, not a digital signature or independent identity attestation. Verify the recorded Git commit and successful CI run against a trusted repository before distributing a candidate.

The generated Mojang Samples index is restored from the official v1.26.50.4 full release asset. The upstream ZIP SHA-256 is pinned as \`c0b6151f5f9a0c31ebe3c909dfc82d97f12473ed2c6e039aa7e22d667042026c\`; the deterministic regenerated gzip is pinned as 1,128,406 bytes with SHA-256 \`48429d64391157553e6760b7f568e5e6d5d05fa6517427b5a1156c8bc18e61fc\`. It contains 22,252 indexed entries from 22,859 ZIP entries, with all category totals checked. Plugin Creator 1.5.12's stored gzip is 1,128,413 bytes; its bytes were not retrieved for direct comparison, so byte-for-byte parity is not claimed. The GitHub candidate is independently pinned to the deterministic generated index hash.

Run current standalone utilities, the local MCP registry/server tests and the remote Worker contract tests. Historical changelog entries describe earlier migrations; the current architecture is Skills plus local MCP and a separately connected remote Worker. Runtime, multiplayer and Blockbench checks must be reported as NOT RUN unless actually performed.
