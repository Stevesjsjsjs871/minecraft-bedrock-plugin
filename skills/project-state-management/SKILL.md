---
name: project-state-management
description: Use when creating, updating, verifying, linking, or recovering durable state for an existing Minecraft Bedrock add-on project across tasks or sessions.
---

# Project State Management

## Purpose and boundary
Use the optional local utility `skills/bedrock-engineer-core/scripts/project_state.py` to keep one integrity-checked project record between sessions. It supplements the actual BP/RP source; it never replaces the project files or grants filesystem access. Run it only when a real local executor and writable project directory are available. Otherwise keep the same state contract in the current Work Order/response and explicitly mark it as not persisted.

The utility stores data in `<project-root>/.mbe/`:
- `project-state.json`: current project metadata, structured records, revision, history chain and checksum.
- `snapshots/`: immutable file inventories containing relative paths, sizes and SHA-256 hashes.
- `backups/`: prior metadata-state documents used for metadata recovery.

A snapshot is **not a file backup**. It does not contain project file contents. State restoration never rolls back, deletes, or rewrites BP/RP files.

## Required lifecycle

1. **Resolve authority first.** Read `project-continuity` and `project-state-recovery`; inspect current project files and manifests. Never initialize state from chat recollection alone. Resolve project identity, target Bedrock version, BP/RP roots, baseline and preservation constraints.
2. **Initialize once.** Run `init` only when `.mbe/project-state.json` does not already exist. Include target version, pack roots, constraints and preserved behavior when confirmed. The initial inventory is the first checkpoint.
3. **Inspect before every resume or mutation.** Run `verify` to validate the state checksum, event hash chain and snapshot/backup references. Run `inspect` to compare the current workspace against the latest complete snapshot. Treat file drift as a reason to inspect the exact paths, not as evidence that the changes are valid or user-approved.
4. **Plan and execute using one Work Order.** Keep acceptance criteria and domain assignments in the Work Order. Link it to the current state revision with `link-work-order`; refresh that link after a state mutation. The link is a revision/hash reference, not an automatic bidirectional sync.
5. **Record claims with evidence.** Use `record` for decisions, requirements, features, issues, tasks, tests and notes. Choose the narrow category and a valid status. Attach exact paths, commands, report identifiers or source citations as evidence. Use `CONFIRMED_IN_SOURCE` only after inspecting the relevant source; use `TESTED`/`PASS` only after actually executing the check. Keep hypotheses `UNVERIFIED` and future work `PLANNED`.
6. **Update rather than duplicate.** Use `update` with the record ID and current expected revision when a tracked task/issue/test status changes. Inspect after conflicts; never retry with a stale revision.
7. **Checkpoint meaningful file changes.** Run `capture` after a coherent set of source edits and relevant validation. Compare additions/modifications/deletions against the last complete snapshot. A partial scan never infers deletions. Resolve scan issues or explicitly opt in to a partial capture; partial captures do not replace the last complete baseline.
8. **Recover carefully.** Use `restore` only to restore metadata from a previous revision, with explicit `--confirm-metadata-only`. It does not restore source files. After restoration, immediately inspect workspace drift and reconcile the state against the actual files. If the current state document itself is corrupt, `recover` can create a new state generation from the newest valid metadata backup; it archives the damaged state, rotates the project ID, captures the current workspace and never rewrites source files. Recovery requires `--confirm-recovery`.

## Command contract

Run from the plugin package root, substituting the real project path:

```bash
python skills/bedrock-engineer-core/scripts/project_state.py init \
  --project-root /path/to/addon --project-name "My Add-on" \
  --target-game-version 1.26.50 \
  --pack-root behavior_packs/my_bp --pack-root resource_packs/my_rp \
  --preserve "existing recipes and entity behavior" \
  --constraint "preserve pack UUIDs"

python skills/bedrock-engineer-core/scripts/project_state.py verify --project-root /path/to/addon
python skills/bedrock-engineer-core/scripts/project_state.py recover \
  --project-root /path/to/addon --confirm-recovery
python skills/bedrock-engineer-core/scripts/project_state.py inspect --project-root /path/to/addon
python skills/bedrock-engineer-core/scripts/project_state.py record \
  --project-root /path/to/addon --expected-revision 1 \
  --category decision --title "Keep existing entity identifiers" \
  --status APPROVED --evidence "User-approved requirement in current request"
python skills/bedrock-engineer-core/scripts/project_state.py update \
  --project-root /path/to/addon --expected-revision 2 --record-id rec-... \
  --status DONE --details "Implemented and statically verified"
python skills/bedrock-engineer-core/scripts/project_state.py capture \
  --project-root /path/to/addon --expected-revision 3 \
  --message "UI and inventory fixes validated"
python skills/bedrock-engineer-core/scripts/project_state.py link-work-order \
  --project-root /path/to/addon --work-order work-order.json \
  --output work-order.linked.json
```

Every post-initialization state mutation (`record`, `update`, `capture` and `restore`) requires `--expected-revision`. `init` creates revision 1. `recover` is the explicit exception because the current revision may be unreadable; it requires `--confirm-recovery`, validates a prior metadata backup and creates a new project identity/revision chain. `link-work-order` writes only a separate Work Order output and does not mutate project state. Obtain the current revision from `verify`/`inspect`; the utility rejects stale writes. The state folder lock fails closed when another operation is active. Do not delete a lock file until confirming no process is still running. Recovery rotates the project ID and starts a new revision chain; all old Work Order state links become stale.

Statuses are category-specific:
- decision: `PROPOSED`, `APPROVED`, `REJECTED`, `SUPERSEDED`;
- requirement: `CONFIRMED`, `APPROVED`, `UNVERIFIED`, `SUPERSEDED`;
- feature: `CONFIRMED_IN_SOURCE`, `TESTED`, `PLANNED`, `UNVERIFIED`, `REMOVED`;
- issue: `OPEN`, `BLOCKED`, `RESOLVED`, `WONT_FIX`;
- task: `PLANNED`, `IN_PROGRESS`, `DONE`, `PARTIAL`, `BLOCKED`, `NOT APPLIED`;
- test: `PASS`, `FAIL`, `NOT RUN`, `BLOCKED`;
- note: `RECORDED`.

## Safety and consistency rules

- The project workspace remains the source of truth. A state file cannot upgrade planned work into implemented work.
- `verify` checks the state document, the hash-chained event history, referenced snapshots and retained metadata backups. A failed check is a blocker; do not overwrite the damaged state.
- `inspect` compares hashes, not timestamps. File additions and modifications are detected by SHA-256. Deletions are reported only after a complete scan.
- Default ignores include `.git`, `.mbe`, dependency caches and Python caches. Additional excludes are explicit. Symlinks, unreadable files, oversized files and file-count-limit cases make a scan incomplete; the utility does not follow symlinks.
- Snapshot inventories are immutable. The utility does not execute project code, fetch network data, call Minecraft, or test gameplay.
- Each state mutation creates a metadata backup and appends a hash-chained history event. State and snapshot writes use atomic replacement; a revision precondition protects against stale/concurrent edits.
- Do not put credentials, access tokens, private keys, unrelated personal information or secrets in state records.
- `restore` changes only project metadata and the selected snapshot reference. It never restores files or deletes changes. Reconcile the workspace after it.
- The Work Order `project_state` object records the project ID, revision, state checksum and snapshot reference. It becomes stale after another state mutation; re-link before delivery/integration.
- Do not claim cross-session durability unless `.mbe/project-state.json` was actually written to a persistent project location and verified in a later read.

## Delivery
Report the exact state path, revision, latest complete snapshot, hash/verification status, drift summary, recorded decisions/tasks/issues and any incomplete scan. Separate `CONFIRMED_IN_SOURCE`, `TESTED`, `PLANNED`, `UNVERIFIED` and `NOT RUN`. Do not say that snapshots back up or restore source files.
