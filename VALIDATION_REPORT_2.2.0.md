# 2.2.0 candidate validation report

## Implemented change
- Added `reference_corpus_indexer.py` and 4 focused unit tests.
- Added metadata-only corpus index for 10 supplied archives, 110 manifest records, and a human-readable intake report.
- Added a separate Mojang `main` branch sample index. Its root manifests declare minimum engine 1.26.60; commit SHA is not embedded in the supplied ZIP.
- Updated reference-pack, compatibility and Mojang sample authoring instructions.
- Preserved 71 Skills, 14 domains, 8 workflow profiles, plugin identity and all 12 default prompts.

## Validation evidence

| Check | Result |
|---|---|
| New indexer unit tests | 4/4 PASS |
| ZIP CRC checks at source intake | 10/10 PASS |
| Unsafe path / absolute path / symlink preflight | 10/10 archives had no detected unsafe entries |
| Archive metadata index | 10 archives / 110 manifest records generated |
| Main-branch Mojang gzip index | gzip and JSON parse; index metadata matches payload |
| Python script registry | 63/63 paths, unique paths and SHA-256 verified by package checker |
| Package integrity | 20/20 PASS, 0 FAIL, 0 WARN |
| Architecture | 28/28 PASS; 14 domains; 71/71 Skills; 8 workflow profiles |
| Full Skills test suite | 31/31 test files PASS; 515/515 cases PASS (CPython 3.13.5; parallel isolated test processes) |
| Installed ChatGPT plugin host integration | NOT TESTED |
| Minecraft import / rendering / gameplay / multiplayer / performance | NOT RUN |

## Independent follow-up verification (2026-11-07)

- Re-ran all 10 supplied source archives: ZIP CRC checks 10/10 PASS; no duplicate member names, unsafe paths, symlink entries, or file/directory collisions were found. Largest observed compression ratio was 777:1 in the Mojang samples archive.
- Rebuilt the metadata index from the uploaded source files and compared it with the bundled index: all 10 archive SHA-256 values, entry counts, and manifest counts match; total 110 manifests, all parsed as valid JSON objects.
- Full local Skills test suite: 31/31 files, 515/515 test cases PASS.
- Package integrity: 20/20 PASS, 0 FAIL, 0 WARN. Architecture: 28/28 PASS; 14 domains, 71/71 Skills, 8 workflow profiles.
- Independent code review identified hardening opportunities in the new indexer: duplicate member names are reported but not rejected; the archive is hashed by reopening its path after ZIP inspection rather than hashing the same pinned file descriptor; file/directory path collisions are not rejected. None occurred in the ten supplied archives. These do not invalidate this read-only corpus snapshot, but should be fixed before treating the indexer as a hardened untrusted-archive security boundary.

## Safety and provenance

No source archive members were extracted by the new indexer or executed. The original uploaded archives remain outside the plugin package. The plugin includes only metadata indexes and written technical observations. The Cinematic Interactions archive carries an explicit redistribution restriction; other user-supplied archives with unclear license status are treated as read-only evidence. No third-party assets or source code were copied into the package.

## Release status

Candidate 2.2.0 only. Live Plugin Creator release remains unchanged. Publication requires a separate explicit user approval and a fresh live-release baseline check.
