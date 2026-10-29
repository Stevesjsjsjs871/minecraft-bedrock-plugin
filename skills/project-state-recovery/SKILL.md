---
name: project-state-recovery
description: Use whenever continuing an existing Minecraft Bedrock add-on or plugin across chats/sessions, resolving conflicting project versions, preserving previous features, or recording what is actually implemented and tested.
---

# Project State Recovery

## Source-of-truth order
1. Current user instruction and explicit approved constraints.
2. Current project files and manifests directly inspected in this task.
3. Latest verified baseline archive/report, with hashes.
4. Existing `PROJECT_STATE.md` or changelog when its facts match the source.
5. Prior chat notes and older summaries, clearly marked as recovered context.

Never assume that a previously described release was installed, that a zip link means a file was imported, or that a plan means a feature exists.

## Resume sequence
1. Identify project root, BP/RP paths, target version and current source artifacts.
2. Enumerate current files and relevant identifiers, not just filenames mentioned in chat.
3. Compare candidate sources using manifest UUIDs, dependency links, resource completeness, static audit evidence and explicit user decisions.
4. Create/update `PROJECT_STATE.md` in the selected project after meaningful implementation. If no file-write destination exists, return the state record in the response and label it as not saved.
5. Record:
   - verified target version and source hashes;
   - active namespace, BP/RP IDs and linked dependencies;
   - architecture and key file references;
   - features confirmed in source versus planned/inferred;
   - user-approved requirements and prohibited changes;
   - tests run with exact commands and pass/fail/skip counts;
   - known defects, confidence and severity;
   - game-runtime status and conditions tested;
   - next implementation steps and acceptance criteria.
6. Resolve conflicts before editing. Never use a newer timestamp as the only reason to select a file.
7. Preserve all confirmed features. Do not rebuild a mod/plugin from scratch or delete unrelated systems unless expressly approved.

## Evidence discipline
Use statuses `CONFIRMED_IN_SOURCE`, `TESTED`, `UNVERIFIED`, `PLANNED`, and `NOT_RUN`. Static checks do not imply gameplay success. Do not invent test counts or report tests as passed when they did not execute. Keep private information, tokens and unrelated personal context out of the state file.

## Output
Summarize only the recovered state needed for the current task, what was verified directly, what remains uncertain, and the next concrete action. Prefer implementation over repeating a long project history.
