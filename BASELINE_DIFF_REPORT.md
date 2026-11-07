# Baseline Diff Report — 2.2.0 → 2.3.0

## Baseline identity
- Input: `minecraft-bedrock-engineer-2.2.0-verified-candidate.zip`
- Size: 2,245,834 bytes
- SHA-256: `694a21adc6eb31ab0d22ae764c59d4386cc3e40e10f2695fc00dda4cc3b584eb`
- Immutable baseline copy: `BASELINE_2.2.0.zip` (read-only).
- Baseline archive: 285 files; 4,013,711 uncompressed bytes; ZIP CRC PASS.
- Baseline version: 2.2.0 in VERSION and both plugin manifests.
- Git state: unavailable; source working directory is not a Git repository.

## Tree delta (exact pre-test inventory from the immutable archive)
- Baseline files: 285
- Candidate files before packaging: 303
- Added: 18
- Modified: 24
- Removed: 0

No baseline files were removed. Test-generated `.pyc` files not present in the original archive were excluded; original baseline files were preserved. `CHANGE_MANIFEST_2.3.0.csv` contains before/after SHA-256 for baseline additions/modifications (its own hash is excluded to avoid self-reference); key file hashes are recorded in `SHA256SUMS_2.3.0.txt`.

## Primary code changes
- `archive_safety.py`: shared pinned ZIP reader, bounded hashing, TOCTOU checks, compression-ratio guard and strict normalized namespace validator.
- `skills/reference-pack-corpus/scripts/reference_corpus_indexer.py`: same-descriptor hashing/member reads, CRC/decompression verification, explicit directory support, duplicate/collision rejection.
- `skills/audit-benchmark/scripts/real_pack_benchmark_builder.py`: explicit directory support, shared namespace checks, CRC verification, consistent 256 MiB / 50k entries / 128 MiB member / 512 MiB total / 1000:1 limits and exclusive output creation.
- `skills/automated-validation/scripts/bedrock_audit.py`: duplicate-key-aware strict JSON and conservative JSONC comments/trailing-comma parsing.
- Added 25 archive/security regression cases and six JSONC parser cases.

## Package and metadata changes
- Version markers moved to 2.3.0; plugin identity and 12 default prompts preserved.
- 71 Skills / 14 domains / eight workflow profiles preserved.
- Script registry refreshed to 64 Python files; Skill inventory covers 71 Skills; activation matrix has 355 designed cases (five per Skill, all NOT RUN in target host).
- Added security, Skill, domain, script, compatibility, corpus, documentation, performance, regression, environment, validation and release-quality-gate reports.

## Verification
- Full suite: 32/32 test files, 546/546 cases PASS in a clean candidate source copy.
- Package integrity: 20/20 PASS. Architecture: 28/28 PASS.
- Eight workflow profile smoke plans PASS; ten source archives / 110 manifests re-indexed; five real packs statically audited.
- Final archive re-extraction package/architecture gates PASS; four focused suites PASS from extracted archive.
- No unplanned removals; original archive remains unchanged.
