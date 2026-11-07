# Release Notes — Minecraft Bedrock Engineer 2.0.0

## Version rollover

- Uses `2.0.0` as the immediate successor to `1.9.9`, following the plugin's version-governance rule that each numeric component is limited to 0–9 and rollover advances the next component. This is a package-version policy rollover; plugin identity, Skills-only integration and all existing Skill paths remain preserved.

## Domain Result integration

- Adds `domain-result-integration` to Core orchestration.
- Adds `integrate_domain_results.py` and 38 focused tests.
- Domain Results may now include per-file state, explicit runtime status, and evidence-backed acceptance-criterion dispositions.
- The integrator validates hand-offs against the registry and parent Work Order, merges changes/evidence, updates plan steps and computes the aggregate state.
- Reports case-only path collisions, remove-versus-write conflicts, differing file actions, and multi-domain overlapping writes. High/blocker conflicts prevent completion; no automatic merge/deletion occurs.
- Acceptance claims are `MET`, `NOT MET`, `UNVERIFIED`, or `CONFLICT`; met/not-met claims require evidence.
- Output is opt-in and atomic; prior domain results require explicit replacement. Source inputs remain unchanged.

## Validation

- Domain Result integration tests: 38/38 passed.
- Architecture validator tests: 27/27 passed; domain planner tests: 44/44 passed; combined Core architecture/planner/integrator suites: 109/109 passed. The validator now also rejects duplicated values in JSON Schema `enum` arrays.
- Python compilation, schema meta-validation and synthetic three-domain Work Order integration: PASS; the integrated Work Order validated against Draft 2020-12 with 3/3 domain results and acceptance status MET. Runtime remained NOT RUN.
- The canonical architecture validator was run against the local partial overlay: 18/19 checks passed. Its only failure was full Skill inventory coverage because the overlay contains 6 of the 63 Skill directories; unchanged Skill files are intentionally retained by Plugin Creator's overlay update.
- Full package-integrity checker and Minecraft/Creator Tools runtime are not represented as passed unless executed separately.
