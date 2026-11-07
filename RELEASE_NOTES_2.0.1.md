# Release Notes — Minecraft Bedrock Engineer 2.0.1

## Project State Management

- Adds `project-continuity`, a dedicated continuity Skill and `project_state.py`, an optional standard-library local utility for writable project roots.
- Stores a versioned state document under `.mbe/project-state.json` with a stable project UUID, revision counter, typed evidence records, hash-chained event history and a SHA-256 integrity field.
- Adds records for decisions, requirements, features, issues, tasks, tests and notes. Category-specific statuses distinguish approved decisions, confirmed-in-source versus tested features, planned/completed tasks and actual test outcomes.
- Adds immutable SHA-256 file-inventory snapshots, drift inspection, bounded scan limits and explicit incomplete-scan reporting. Symlinks are not followed; ignored/cache directories are excluded by default.
- Every mutation requires `--expected-revision`; state writes use a lock and atomic replacement. Stale writes fail instead of overwriting newer state.
- Adds state verification, backup metadata verification, metadata-only restore and explicit recovery of damaged metadata. Restore/recovery never writes, deletes or rolls back project files. Recovery archives the damaged state and rotates the project UUID before a new capture.
- Adds `project_state` to the Work Order as an optional strict link to the exact project UUID, state revision, state path/hash and latest snapshot ID/hash. Domain Result integration validates and preserves this link.

## Safety boundaries

- Snapshots are file inventories (path, size, SHA-256), not file-content backups.
- Incomplete scans do not infer deletions; only complete inventories can classify additions/removals against the previous complete snapshot.
- State metadata is local to the selected project. No cloud synchronization, cross-device persistence, background process or Minecraft runtime test is implied.
- Without an actual writable project directory and local executor, the Skill must keep the state unsaved and say so.

## Validation

- Project-state unit tests: 28/28 passed.
- Domain Result integrator tests: 40/40 passed, including two project-state link cases.
- Architecture validator: updated to check the state utility, tests, Skill, schema and Work Order link.
- Combined Core unit suite: 144/144 passed (project state 28, Domain Result integration 40, domain planner 44, architecture validator 32).
- Python compilation: all 8 affected Core scripts/modules passed. Draft 2020-12 meta-validation passed for Project State, Work Order and Domain Result schemas; the Project State example validates with zero errors.
- Synthetic end-to-end scenario: PASS — state initialized, a decision recorded, revisioned snapshot captured, state verified, Work Order generated and linked, 3/3 domain results integrated to COMPLETE, state link preserved, Work Order schema validation returned zero errors, and an external file addition was detected as drift. Runtime remained NOT RUN.
- The local architecture validator reports 23/24 checks on the partial update overlay; its only failure is full Skill-tree coverage because the overlay contains 7 of the 64 Skill folders. Unchanged Skills are retained in the live Plugin Creator release during overlay updates. Full package-integrity checker remains NOT RUN.
- Minecraft import/render/gameplay/multiplayer and Creator Tools runtime: NOT RUN.
