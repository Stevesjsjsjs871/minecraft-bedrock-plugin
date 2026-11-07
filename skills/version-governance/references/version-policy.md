# Minecraft Bedrock Engineer plugin-package version policy

This file governs the **plugin package** only. For a user's Minecraft Bedrock add-on version, visible pack title and BP/RP `manifest.json` values, use `skills/addon-versioning/SKILL.md`.

The live Plugin Creator current-release marker is the source of truth. New plugin package versions use one-digit `MAJOR.MINOR.PATCH` components: increment PATCH through 9, then carry into MINOR, then MAJOR. Do not infer current version from the largest historical attachment. Historical multi-digit releases remain immutable; the version-governance skill documents migration rules.

Refresh live metadata and release history before each candidate. Preserve `defaultPrompt` exactly in both manifests. Synchronize `VERSION`, `plugin.json`, `.codex-plugin/plugin.json`, README heading, changelog and release notes.
