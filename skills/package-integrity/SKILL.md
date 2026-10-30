---
name: package-integrity
description: Use before publishing or updating Minecraft Bedrock Engineer to verify Skills-only package manifests, original prompt preservation, version parity, filesystem hygiene, provenance and bundled Mojang sample-index integrity.
---

# Skills-only Package Integrity and Provenance Gate

Run the regression suite from the repository or extracted package:

```bash
python -m unittest discover -s skills/package-integrity/scripts -p 'test_*.py' -v
```

For a release candidate, build and verify a deterministic archive from a clean tracked Git snapshot. This avoids test-generated cache files without deleting anything from the working tree:

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
(cd dist && sha256sum -c minecraft-bedrock-engineer.tar.gz.sha256)
```

Do not publish or install a candidate unless every check passes. A missing BUILD_PROVENANCE.json is a hard failure, not a warning.

## What is checked

- Required package files and both plugin manifests parse as strict JSON.
- SemVer parity across plugin.json, .codex-plugin/plugin.json, VERSION, README heading and newest versioned CHANGELOG heading.
- Stable plugin identity and exact parity of the two default-prompt arrays.
- The first three original default prompts are preserved verbatim and in order; adding later prompts is allowed.
- Both manifests point to ./skills; the Skills-only package contains no active MCP configuration or retired deployment scaffolding.
- Every SKILL.md has basic frontmatter with a unique non-empty name and description.
- No symlinks, special files, __pycache__, .pyc or .pyo files; bounded file count, individual file size and total package size.
- The pinned Mojang Samples gzip index decompresses and parses as JSON within a 64 MiB decompressed-size limit; count metadata is checked when available.
- BUILD_PROVENANCE.json is mandatory and must match the exact file inventory, per-file SHA-256 values, byte totals, package version, plugin identity and canonical payload digest.
- The archive builder writes normalized tar metadata and a fixed gzip timestamp, refuses existing outputs, and writes a sidecar SHA-256 for the exact archive bytes.

## Provenance contract

BUILD_PROVENANCE.json uses schema version 1. It records the full Git object ID, source date epoch, package version, file paths, byte sizes and SHA-256 hashes. payload_sha256 is the SHA-256 of the canonical, sorted JSON file inventory (path, size and per-file hash); it is not the hash of the compressed archive. The adjacent .sha256 sidecar hashes the exact .tar.gz bytes. The provenance file is excluded from its own payload inventory to avoid a recursive hash.

The provenance file and SHA-256 sidecar provide integrity metadata, not a digital signature or independent identity attestation. Verify the recorded Git commit and successful CI run against a trusted repository before distributing a candidate.

The builder excludes repository-only .git, .github, docs/engineering, dist, GITHUB_SYNC_NOTES.md and DEVELOPMENT_LOG.md. Run the builder and extracted checker with \`PYTHONDONTWRITEBYTECODE=1\` so their imports do not create a cache inside the package snapshot; the checker must still reject any cache that is present. It does not silently remove bytecode or symlinks: it refuses to package them.

The generated mojang-samples-index.json.gz is intentionally not committed. CI restores it from the exact official Mojang v1.26.50.4 full release asset, verifies the ZIP SHA-256, regenerates the index, and checks source archive name/hash, target version, ZIP totals, indexed count, category counts, compressed size and generated index SHA-256. The current deterministic index is 1,128,406 bytes with SHA-256 \`48429d64391157553e6760b7f568e5e6d5d05fa6517427b5a1156c8bc18e61fc\`. Plugin Creator 1.5.12's stored index is 1,128,413 bytes; direct byte comparison was unavailable, so byte-identical parity is not claimed.

The checker is standard-library-only and read-only. The builder writes only a new archive and its sidecar, outside the package root, and never overwrites existing paths. Static package checks do not prove Minecraft import, rendering, gameplay, multiplayer, Blockbench interoperability or Script API runtime behavior; report those as NOT RUN unless actually tested.

Legacy check_package_integrity.py and its tests validate the retired server/registry architecture. They are historical source, not the release gate for current Skills-only packages.
