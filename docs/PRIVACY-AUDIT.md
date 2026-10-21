# Preliminary data-handling audit

**Status: incomplete. This is an internal audit note, not a public privacy policy.**

## Scope reviewed

The current plugin package inventory contains two manifests and six ChatGPT skill instruction files. The reviewed manifests do not declare a dedicated MCP server. The skills describe static inspection of user-provided files when those files are available in the current session.

## What this review does not establish

This review does not establish the full data flow of the ChatGPT platform or any external processing outside the reviewed package. It does not establish platform-level retention periods, deletion behavior, or access by platform providers.

No independent server implementation was present in the reviewed file inventory, so server-side network and storage behavior could not be audited from this package.

## Required follow-up before publishing a privacy policy

1. Review any additional code, integrations, and build configuration, if they exist.
2. Determine whether the developer operates any server or storage service.
3. Establish which data is collected, where it is processed, and who receives it.
4. Confirm retention and deletion practices for developer-controlled systems.
5. Draft and publish a privacy policy only after these facts are verified.

Do not present this preliminary note as a completed privacy assessment or as the public privacy policy.
