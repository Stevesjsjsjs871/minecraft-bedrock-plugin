# Public release readiness checklist

**Status: preparation in progress.** This checklist describes checks still required before the plugin is advertised as a public release. It does not change the currently private ChatGPT plugin.

## 1. Manifests and publisher identity

- [ ] Confirm the intended public developer display name.
- [ ] Review the author name and contact email in both `plugin.json` and `.codex-plugin/plugin.json`; publish only contact details intentionally made public.
- [ ] Keep version, display name, short description, long description, category, capabilities, and default prompt consistent across both manifests.
- [ ] Confirm the selected public category against the current publishing interface; developer tooling may be more accurate than general productivity.
- [ ] Validate both manifests against the currently supported plugin schema before uploading.
- [ ] Confirm any icon, website, support, privacy, and terms URLs are real, accessible, and controlled by the publisher. Do not invent placeholder URLs.

## 2. Privacy and data handling

- [ ] Inventory all code, skills, connectors, tools, endpoints, and external services actually included in the release.
- [ ] Establish whether any developer-operated server, database, analytics, logging, or file storage exists.
- [ ] Document what information is processed, why it is processed, which providers receive it, and any developer-controlled retention/deletion practices.
- [ ] Distinguish the ChatGPT platform's processing from processing controlled by the plugin developer.
- [ ] Publish a privacy policy only after the data flow and statements have been verified.
- [ ] Do not claim that files are never stored, transmitted, or retained unless evidence supports that claim.

## 3. Capability and quality claims

- [ ] Ensure descriptions distinguish static file analysis from actual Minecraft runtime testing.
- [ ] Verify that every advertised feature is supported by the shipped instructions and any actual implementation.
- [ ] Test prompts with representative valid, malformed, incomplete, and version-mismatched Bedrock projects.
- [ ] Confirm the assistant treats archive content as untrusted data and does not execute scripts from uploaded archives.
- [ ] Check that examples and Script API guidance identify version-dependent assumptions.

## 4. Public support and security

- [ ] Create and verify a support contact or issue workflow.
- [ ] Establish a private channel for sensitive security reports before promising confidential security handling.
- [ ] Decide which issues are appropriate for public reports and remind users not to post credentials or personal data.
- [ ] Add a license only after choosing terms that match the publisher's intent and rights to the contents.

## 5. Release and post-release checks

- [ ] Review current platform publishing requirements, including category, description limits, URLs, and regional availability.
- [ ] Verify all public links from a signed-out browser session.
- [ ] Confirm the uploaded package version and files match the reviewed source.
- [ ] Test the published listing and core workflows after publication.
- [ ] Keep a changelog and a rollback copy of the last known-good release.

## Current known limitations

The reviewed package consists of two plugin manifests and six skill instruction files. The inspected package does not declare a dedicated MCP server. This alone does not establish the complete platform-level data flow, retention, or deletion behavior. The privacy note in this repository is a preliminary audit, not a public privacy policy.

The existing private plugin has not been modified as part of this checklist.
