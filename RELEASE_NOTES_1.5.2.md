# 1.5.2 — Skills-first execution repair

- Reaffirmed the intentional Skills-and-instructions-only architecture; no MCP servers, registries, endpoints or plugin-owned backend are part of this release.
- Added a dedicated `skills-first-execution` skill defining the actual capability boundary, native file/code execution routing, safe editing, validation and truthful reporting.
- Updated the core workflow to route tasks through specialist skills and available host capabilities rather than obsolete server tools.
- Replaced ambiguous claims about remote execution with explicit instructions: skills do not create filesystem access, tools, package installation or background execution.
- Clarified that bundled scripts may be run only when a real executor and required project files are available; otherwise the plugin must provide a patch, complete files or reproducible commands.
- No existing authoring, audit, geometry, animation, texture, UI or reference assets were intentionally removed.
