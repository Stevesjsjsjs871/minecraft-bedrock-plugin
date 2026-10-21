# Archive audit regression tests

These tests describe behavior expected from the archive audit helper. They are written as a checklist so they can be run manually now and converted into automated fixtures later.

## Required fixtures

Create synthetic, redistributable fixtures rather than checking copyrighted third-party packs into the repository:

- `valid-minimal.mcpack.zip`: one valid `manifest.json` and a tiny text asset.
- `bom-manifest.mcpack.zip`: same manifest with a UTF-8 BOM.
- `commented-controller.mcpack.zip`: comments in a fixture explicitly designated as comment-tolerant for the test.
- `strict-json-comment-error.mcpack.zip`: comment in a file designated strict JSON; should not be labeled valid just because a recovery parser can read it.
- `trailing-comma.json`: trailing comma fixture.
- `duplicate-uuid.mcaddon.zip`: two manifests sharing a UUID.
- `external-dependency.mcaddon.zip`: dependency UUID intentionally absent from the archive; should be review/info, not an automatic error.
- `unsafe-member-path.zip`: path traversal member; should be detected and never extracted.
- `corrupt-member.zip`: bad CRC/member content; should fail integrity validation.
- `large-archive.zip`: synthetic size/member-count stress fixture under controlled limits.

## Acceptance criteria

- The tool never extracts or executes archive members.
- Strict parse results are reported separately from recovery parse results.
- Strings containing `//`, `/*`, `*/`, or comma-plus-closing-bracket sequences are not corrupted by diagnostic preprocessing.
- Duplicate UUIDs list every affected manifest/module location.
- Missing-in-archive dependency UUIDs are labeled as review candidates because dependencies can be external.
- Every output is valid UTF-8 JSON and includes explicit limitations.
- Archive path safety findings never result in filesystem writes.
- No test claims runtime success without a manual game test record.
