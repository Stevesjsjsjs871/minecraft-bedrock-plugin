---
name: package-integrity
description: Use before publishing or updating Minecraft Bedrock Engineer to verify Skills-only package manifests, version parity, prompt parity, skill inventory, no-MCP architecture and bundled Mojang sample-index integrity.
---

# Skills-only Package Integrity Audit

Run from the root of the extracted plugin package:

```bash
python skills/package-integrity/scripts/check_skills_package.py .
python skills/package-integrity/scripts/test_check_skills_package.py -v
```

The checker is standard-library-only and read-only. It verifies:
- Required package files and both plugin manifests parse as JSON.
- Strict version parity across `plugin.json`, `.codex-plugin/plugin.json` and `VERSION`.
- Plugin identity and exact default-prompt parity between manifests.
- Both manifests point to `./skills`.
- The Skills-only boundary: no MCP server declarations or `.mcp.json` / `mcp.json` configuration files.
- Every `SKILL.md` has valid basic frontmatter with a unique skill name and non-empty description.
- README version heading and explicit Skills-only architecture statement.
- The bundled Mojang sample index decompresses and parses as JSON, with entry-count consistency when the index exposes a countable entries/files collection.

The checker emits a JSON report and exits non-zero on failure. It does not install dependencies, execute add-on scripts, contact remote services, or launch Minecraft. The bundled regression tests use synthetic fixtures; they validate the checker, not game behavior.

Legacy `check_package_integrity.py` and its tests validate the retired server/registry architecture and are retained only as historical source. Do not use them as the release gate for current Skills-only releases.

Static package checks do not prove Minecraft import, rendering, gameplay, multiplayer, Blockbench interoperability or Script API runtime behavior. Report those as `NOT RUN` unless actually tested.
