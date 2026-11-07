# Release 2.1.8 — Pre-runtime contract and conflict detection

## Added
- A mandatory producer/consumer contract pass for cross-system features, tracing registration and triggers through state/data flow, effects and cleanup.
- Explicit checks for identifier/value-shape mismatches, duplicate registration, dependency/version conflicts, invalid state transitions, stale references, partial updates and missing cleanup.
- Evidence rules that distinguish deterministic two-sided conflicts from inferred, dynamic, Molang and external-pack edges.
- End-to-end validation now requires contract-edge coverage for multi-system changes; unresolved dynamic edges remain visible rather than being guessed.

## Preserved
- Skills-only architecture, private plugin identity, existing prompts and all unrelated files.
- Static analysis remains distinct from Minecraft runtime validation.
