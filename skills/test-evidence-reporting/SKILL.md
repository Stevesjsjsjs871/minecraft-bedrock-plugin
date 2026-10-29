---
name: test-evidence-reporting
description: Use when reporting tests, audits, Creator Tools results or release status for a Minecraft Bedrock project, especially when some checks are unavailable or not run.
---

# Test Evidence Reporting

## Principle
A statement like "passed" must point to an actually executed check. Inspected instructions, a generated plan, static reasoning and a successful packaging operation are not substitutes for test execution.

## State taxonomy
Use these values consistently:
- `PASSED`: command/tool executed and returned the expected successful result.
- `FAILED`: executed check returned a failure or found a confirmed defect.
- `BLOCKED`: the check could not start because a dependency, permission, artifact or runtime was missing.
- `NOT RUN`: no attempt was made.
- `PARTIAL`: some scenarios ran, but the required coverage was incomplete.
- `INCONCLUSIVE`: output existed but could not establish the intended property.
- `SKIPPED`: intentionally omitted, with reason; required skips block a pass.

## Required record per check
- Check identifier and purpose.
- Input artifact/hash and target version.
- Tool name/version and exact command/arguments, if executed.
- Exit status or structured result.
- Pass/fail/skip counts and representative evidence.
- Limitations and any untested domains.

## How to aggregate
- Do not collapse all checks into one green status. Report package integrity, schema/static audit, unit tests, regression fixtures, Creator Tools validation, real-pack benchmark and game-runtime tests separately.
- If any mandatory check failed or a new high-severity defect remains, recommend `HOLD`.
- If key checks are blocked or medium/heuristic findings remain, recommend `REVIEW`.
- `READY FOR USER TEST` is appropriate only when all required non-runtime gates actually passed and remaining runtime checks are explicitly pending.
- Never call a candidate fully release-ready when an engine-sensitive behavior hasn't been tested in Minecraft.
- Preserve failure evidence. Do not edit the report to turn failures into skips or remove inconvenient cases.

## User-facing summary
Start with the recommendation and number of executed checks, then show each gate's status. Include real commands and counts where available, no invented metrics and no generic "all tests passed" statement. State explicitly which checks were not run and what is needed to run them.

## Long-term test debt
Maintain a bounded list of recurring missing capabilities: no connected executor, unavailable target game/runtime, missing real pack corpus, schema coverage gaps, tests that require Windows-only or device-only behavior. Each item should identify an owner/action and acceptance test. Do not imply the plugin solved an execution limitation by adding instructions for it.
