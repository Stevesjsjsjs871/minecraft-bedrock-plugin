# Security Audit Report — 2.3.0

## Scope
Audited the baseline ZIP `minecraft-bedrock-engineer-2.2.0-verified-candidate.zip` and the two archive ingestion utilities named in the master prompt, plus the shared pinned ZIP reader and the main static Bedrock auditor. Source archives were treated as untrusted data. No archive member was executed.

## Baseline identity
- Size: 2,245,834 bytes.
- SHA-256: `694a21adc6eb31ab0d22ae764c59d4386cc3e40e10f2695fc00dda4cc3b584eb`.
- ZIP: 285 entries, CRC PASS, no duplicate raw names.
- Baseline extracted file inventory: 285 files / 4,013,711 bytes.
- Baseline version markers: `VERSION`, `plugin.json`, `.codex-plugin/plugin.json` all 2.2.0.

## Confirmed defects and fixes

### SEC-ARCH-01 — Explicit ZIP directory entries rejected by benchmark builder
- **Baseline behavior:** `real_pack_benchmark_builder.py` split `behavior_pack/` into a final empty segment and rejected the valid directory entry.
- **Fix:** directory status is checked against the trailing slash; the shared validator strips exactly one trailing slash only for directory entries and validates the normalized path and entry type.
- **Regression evidence:** explicit top-level/nested directories and files under them pass; no-explicit-directory archives pass; traversal and malformed archives fail safely. Benchmark suite: 10/10 PASS.
- **Risk:** LOW. A previously valid pack layout is accepted; malformed ambiguous paths are rejected.

### SEC-ARCH-02 — Duplicate ZIP paths accepted by corpus indexer
- **Baseline behavior:** duplicates were recorded in an output list but indexing continued.
- **Fix:** duplicate normalized path, case-fold alias and Unicode NFC alias now cause a hard failure before CRC/decompression.
- **Regression evidence:** duplicate raw names, case collisions and composed/decomposed Unicode collisions rejected. Corpus indexer suite: 10/10 PASS.
- **Risk:** LOW. Some archives with importer-dependent ambiguity now fail closed.

### SEC-ARCH-03 — File/directory namespace conflicts not rejected
- **Fix:** exact file-vs-directory collision and file-as-parent conflict detection. Explicit directories remain valid when they do not conflict.
- **Regression evidence:** both collision classes fail; normal directory trees pass.
- **Risk:** LOW.

### SEC-ARCH-04 — SHA-256 computed by reopening the archive path
- **Baseline behavior:** ZIP inspection and hash were separate opens, leaving a path replacement/TOCTOU gap.
- **Fix:** `reference_corpus_indexer.py` uses `open_bounded_zip()`; the same pinned descriptor supplies archive SHA-256, central-directory/member reads and CRC verification. `fstat` checks detect in-place changes.
- **Regression evidence:** path replaced after open; index still reads original archive bytes and hash; mutation and symlink input rejected by archive safety tests.
- **Risk:** LOW.

### SEC-ARCH-05 — Invalid UTF-8 ZIP filename exception escaped the safe boundary
- **Fix:** Unicode decoding errors from ZIP central-directory parsing are wrapped as controlled `ValueError` failures.
- **Regression evidence:** crafted invalid UTF-8 filename fixture is rejected through the safe reader.
- **Risk:** LOW.

## Shared safety controls
- ZIP archive path must be a regular file, not a symlink; O_NOFOLLOW is used where available.
- Compressed archive <=256 MiB; <=50,000 entries; <=128 MiB per member; <=512 MiB declared uncompressed; <=1000:1 compression ratio in namespace validation.
- Rejects absolute, drive-prefixed, UNC-like, backslash, traversal, empty/dot/parent and control-character names.
- Rejects symlinks, special file modes, encrypted members, inconsistent directory type markers and normalized collisions.
- CRC/decompression test occurs only after namespace and metadata preflight.
- Output creation uses exclusive `x` mode and refuses overwrites.

## Residual limits
- No hard wall-clock timeout inside ZIP decompression; size, entry and ratio limits bound input but do not prove CPU-time immunity. Run untrusted inputs in an externally time-limited process where that guarantee is required.
- No nested-archive recursive inspection; nested archives are inventoried as ordinary members, not opened.
- Python `zipfile` exposes decoded member names, not every raw central-directory byte. Invalid UTF-8 with the UTF-8 flag is rejected; CP437 names are valid ZIP encodings and are not rejected solely for being non-UTF-8.
- ZIP checks do not validate Minecraft import semantics, schema correctness, asset loading, scripts or runtime behavior.
- No claim of complete security is made from unit tests.

## Verification
- `test_archive_safety.py`: 29/29 PASS.
- `test_real_pack_benchmark_builder.py`: 10/10 PASS.
- `test_reference_corpus_indexer.py`: 10/10 PASS.
- Full package suite: 32/32 files, 546/546 cases PASS.
