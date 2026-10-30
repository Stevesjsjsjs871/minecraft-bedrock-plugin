# Plugin Creator archive parity checker

This repository-only release-QA utility compares a Plugin Creator package archive
with the plugin source tree checked out at the intended release commit.

It supports ZIP and tar/tar.gz archives and **never extracts** the supplied
archive. It compares the package root files plus every regular file under
`server/` and `skills/`, then checks:

- `VERSION`, `plugin.json`, and `.codex-plugin/plugin.json` agree;
- the two manifests retain exactly three matching default prompts;
- `.mcp.json` and `mcp.json` expose the same stdio server names;
- every referenced `${PLUGIN_ROOT}` Python server script exists in the archive;
- archive paths, duplicate entries, symlinks, case-insensitive collisions, and
  declared uncompressed sizes are safe;
- repository package files cannot traverse symlinked parent directories, and ZIP directory records must have directory file types.

## Usage

Run this against the exact source checkout used to build the candidate package,
not an unrelated branch or newer `main`:

```powershell
python .github/scripts/check_plugin_creator_parity.py --archive "C:\\Downloads\\current.tar.gz" --repo-root .
```

Write a machine-readable report:

```powershell
python .github/scripts/check_plugin_creator_parity.py --archive "C:\\Downloads\\current.tar.gz" --repo-root . --json-output reports\\plugin-creator-parity.json
```

Exit code is `0` only when all package files are byte-identical and metadata,
MCP configuration, and archive-safety checks pass. Exit code `1` indicates
drift or an invalid/unsafe archive.

## Scope and limitations

- This checks source/package parity; it does not install the plugin or execute
  MCP servers.
- The plugin ID and current Plugin Creator Release ID are external metadata and
  must be checked separately in Plugin Creator before any guarded update.
- A passing result does not prove Minecraft runtime behavior, Creator Tools CLI
  availability, or game-version compatibility.
- CI runs synthetic ZIP and tar.gz fixtures. It does not fetch a private live
  Plugin Creator archive.
