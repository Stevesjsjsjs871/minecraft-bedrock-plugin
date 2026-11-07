# Release 2.1.7 — Correctness-first code review

- Expanded the shared code quality standard with explicit contracts, preconditions, postconditions and invariants.
- Added targeted checks for boundary values, numeric units/ranges, state transitions, duplicate events, async failures, partial mutations and data/resource integrity.
- Added a failure-handling protocol that avoids silent catches and undocumented fallbacks.
- Added contract-derived test coverage for normal, boundary, invalid, repeated, stale-object, partial-failure and regression paths.
- Strengthened Bedrock authoring, Script API auditing and staged project analysis with a correctness-first pass.
- Preserved project conventions, public identifiers, unrelated files and the existing 12 default prompts.

This release improves review guidance; it does not claim measured defect-rate reduction or Minecraft runtime verification.
