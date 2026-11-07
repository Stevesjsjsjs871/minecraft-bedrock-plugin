# Minecraft Bedrock Engineer 1.6.0 — Entity pipeline and release governance

This release adds the coordinated entity authoring workflow and a standalone static dependency auditor for a BP/RP entity bundle. The auditor indexes BP entity identifiers, RP client-entity identifiers, geometry, animation clips, animation controllers and render controllers, then checks literal links and duplicate-key/invalid JSON conditions. Its results deliberately distinguish failures from review warnings and do not claim complete engine-schema or runtime coverage.

A version-governance skill and dependency-free calculator formalize the requested one-digit component rollover policy. Legacy attached release strings remain unchanged; release history is always reconciled against live Plugin Creator metadata because attachment history can include unpublished releases.

The plugin remains Skills-first. No MCP server, endpoint or remote execution backend is enabled by this update. Existing package files, specialist skills, prompts, binary sample index and dormant legacy sources are preserved by an overlay update. The only deletion is one generated Python bytecode cache file; no source modules or user assets are deleted.

Validation performed on the update payload:
- Entity pipeline audit synthetic regression tests: 5/5 PASS.
- Version governance synthetic tests: 11/11 PASS.
- Version successor calculation: `1.5.12 → 1.6.0` PASS.
- Candidate format validation: `1.6.0` PASS.
- JSON manifest parity and `defaultPrompt` equality: checked by package-preparation script.
- Full installed-package integrity suite: BLOCKED (complete archive could not be materialized in the local executor).
- Binary Mojang index gzip/JSON integrity: NOT RUN (binary content unavailable through text-source read).
- Minecraft 1.26.50 import/render/animation/gameplay, multiplayer and Blockbench interoperability: NOT RUN.
