---
name: project-continuity
description: Use when resuming an existing Minecraft Bedrock project, reconciling prior chats or library artifacts, managing known project state, tracking decisions and tests, or deciding which source version is authoritative.
---

# Project Continuity and State Management

## Purpose
Resume work from verified project evidence instead of relying on guesses or a large prompt. Keep each project separate and make uncertainty visible.

## Source-of-truth order
1. Current user instruction.
2. Files/archive explicitly supplied for the current task, after inspection.
3. Latest verified project artifact and audit report.
4. Available prior chat/library context with dates and source identifiers.
5. Older notes or inferred recollections.

A newer timestamp alone does not prove an artifact is better. Compare manifests, functional content, audit evidence, and relevant user-approved decisions. If sources conflict, explain the conflict and choose only when evidence supports a choice.

## Resume procedure
1. Identify the project and target version.
2. Search the available conversation/library files when prior context is needed.
3. Inspect the relevant source files rather than inferring their content from filenames.
4. Build a compact verified state: baseline, current version, intended outcome, existing features, approved/prohibited changes, known issues, checks already performed, and remaining tests.
5. Separate facts, user requirements, decisions, completed work, findings, hypotheses, and unresolved items.
6. Do not ask again for information already available. Ask only when an unresolved detail materially blocks a safe choice.
7. Continue implementation where possible; don't stop at summarization when the user asked for work.

## State file format
Maintain or generate `PROJECT_STATE.md` containing:
- Project identity and target Bedrock version.
- Source archive/path and verified pack versions.
- BP/RP identifiers and dependency relationships (no secrets).
- Current verified baseline and date checked.
- Key architecture and file references.
- User-approved decisions and constraints.
- Existing functionality that must be preserved.
- Known bugs with evidence and severity.
- Completed changes and test results.
- Runtime checks not yet performed.
- Prioritized next actions with acceptance criteria.

Only write claims that have evidence or label them `unverified`, `inferred`, or `needs confirmation`. Update state after meaningful project changes; don't pretend the state persists automatically if no file/storage was actually updated.

## Privacy and scope
Do not include unrelated personal details in technical state files. For this user's project review, exclude the art-focused chat when they request that exclusion. Do not claim to have searched every chat or library item unless access and search scope support that claim.

## Output
Give a concise state summary, cite/refer to the artifacts actually inspected where available, list blockers and next steps, and distinguish recovered context from verified current files.
