---
name: version-governance
description: Use whenever preparing a Minecraft Bedrock Engineer plugin package version, reconciling Plugin Creator release history, validating plugin version markers, or determining the next plugin-package release number.
---

# Plugin Package Version Governance

## Scope

This skill governs **Minecraft Bedrock Engineer itself** (the Plugin Creator package). It does not govern an add-on being developed with the plugin. For an individual Bedrock add-on, use `skills/addon-versioning/SKILL.md` instead. Never apply the one-digit plugin-package sequence to the user's add-on manifests.

## Source-of-truth order

1. Read current Plugin Creator metadata and record `version` plus `current_release_id`.
2. Read attached release history. Record release IDs, versions, timestamps and current markers exactly. The endpoint can include unpublished attachments; do not call all attachments publicly published releases.
3. Read `VERSION`, both plugin manifests, `CHANGELOG.md`, `VERSION_HISTORY.md`, release notes and relevant provenance.
4. Reconcile conflicts before versioning. Never infer the current release from the largest version string, Git tag, PR number, timestamp, or an old assistant message.

## Plugin package version sequence

New plugin package versions use exactly three numeric components, each one digit from 0 through 9. Increment PATCH until 9, then carry into MINOR and reset PATCH; when MINOR is 9, carry into MAJOR and reset both lower components. Examples: `1.0.8 → 1.0.9`, `1.0.9 → 1.1.0`, `1.9.9 → 2.0.0`. Never generate a new plugin version with a component 10 or above.

Historical legacy versions with multi-digit components are immutable. When migrating a legacy PATCH overflow, carry into MINOR (`1.5.12 → 1.6.0`); when legacy MINOR exceeds 9, carry into MAJOR. If MAJOR itself exceeds 9 or no one-digit successor exists, stop and request a version-policy decision.

## Candidate discipline

- Refresh Plugin Creator metadata and release history immediately before calculating the next plugin version.
- Do not bump on every internal edit. Allocate the next package version only for a coherent plugin release candidate.
- Verify the candidate is not already attached and that `VERSION`, both manifests, README heading, changelog and release notes agree.
- Preserve every `defaultPrompt` value exactly, including its type, text and order.
- Preserve plugin identity, scope, audience, App bindings and unrelated resources.
- Publishing is a separate operation; follow the current Plugin Creator authorization workflow.

## Required workflow

1. Recover live current version and release ID.
2. Calculate the successor using `scripts/version_governance.py next <current-version>` and validate it with `validate <candidate>`.
3. Prepare all plugin package changes and tests before allocating the candidate.
4. Update package version markers and release documentation consistently.
5. Run the package-integrity checker, version-governance tests and every affected regression test.
6. Record source release ID, candidate, commit SHA (or `NOT AVAILABLE`), test evidence and publication state in `VERSION_HISTORY.md`.
7. Submit via Plugin Creator using the exact observed `current_release_id`, then read back metadata and all changed files.

## Output contract

Report current plugin version/release ID, next version calculation, changed plugin-package version files, exact test results, package-integrity status, publication state and any unverified runtime behavior. Plugin Creator update success is not proof of Minecraft runtime behavior.
