# Release notes — 2.1.12

## Scope
- Add `script_api_analyzer.py`: bounded lexical inventory for JS/TS imports, manifest script dependencies, event subscriptions, timer calls and selected world-query calls. Output is explicitly PARTIAL; it does not claim AST/type/API/runtime validation.
- Add `bedrock_resource_validator.py`: bounded UI/PBR/Fog file inventory, literal path-like reference hints and manifest UUID/dependency checks. Engine schemas and rendering remain outside its guarantees.
- Add `real_pack_benchmark_builder.py`: safe metadata-only inventory of explicitly supplied pack archives, SHA-256 and manifest metadata. It does not label or score a benchmark.
- Harden reference transfer: pinned directory-relative file opens with `O_NOFOLLOW`, bounded reads, file identity stability check, and a 4,096-chunk PNG limit.
- Correct two stale registry test-companion claims, clarify 18 generic CLI/API contracts, and refresh SHA-256 values for all 61 Python files.
- Preserve 12 default prompts, plugin identity, USER scope and PRIVATE discoverability.

## Verification
- Focused new utilities: 4/4 + 3/3 + 3/3 tests PASS.
- Reference transfer: 29/29 tests PASS, including PNG chunk ceiling.
- Full Skills suite: 30/30 test files, 511/511 cases PASS under CPython 3.13.5 (per-file timeout 5 seconds).
- Package-integrity and architecture validator results recorded in `SCRIPT_AUDIT_REPORT_2.1.12.md`.
- Plugin-host script integration: NOT TESTED. Minecraft import/render/gameplay: NOT RUN. No real-pack corpus was supplied; benchmark accuracy metrics are NOT AVAILABLE.
