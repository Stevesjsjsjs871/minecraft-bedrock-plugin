# Geometry UV local CLI migration — 2026-10-30

## Source state

- Base branch: fix/cloudflare-profile-contract-and-ci-20261030
- Base commit: 92353c6debb6f1f4eb2c6dac649c8f161ce26abd
- Dependency: draft PR #16, whose executable-code head baadf1650e671ab2296750dc9e515d6ebbcedd44 passed GitHub Actions runs 41063133534 and 41063171785.
- Current Plugin Creator release inspected separately: 1.5.8, Release ID pluginrel_6ae4aa9690388191b2df2db5f93b468a. No Plugin Creator files were changed.

## Work

- Added a local CLI adapter for the existing geometry UV audit and template functions.
- Kept the MCP server modules and tool names unchanged.
- Added output PNG structural validation and SHA-256 re-verification after template generation.
- Added CLI regression coverage for valid audits, out-of-bounds findings, incomplete canvas, traversal, ambiguous geometry selection, overwrite refusal, environment restoration, missing backend, overlap warnings and output validation.
- Updated geometry skills to expose the CLI as an alternative when a real local executor is available.
- Verified the official Microsoft Learn geometry v1.21.0 reference. It documents per-face UVs, uv_size, uv_rotation values 0/90/180/270, texture_width/texture_height and mesh structures. The tool continues to mark poly_mesh and texture_meshes outside cube-UV coverage.

## Files

- skills/geometry-uv-engine/SKILL.md
- skills/geometry-uv-engine/scripts/geometry_uv_cli.py
- skills/geometry-uv-engine/scripts/test_geometry_uv_cli.py
- skills/geometry-uv-engine/scripts/README.md
- skills/geometry-uv-audit/SKILL.md
- skills/geometry-uv-template-authoring/SKILL.md
- .github/workflows/validate.yml

## Acceptance criteria

- CLI invokes the existing tested functions without starting MCP transport.
- Audit command remains read-only.
- Template command writes only a new file under textures/uv_templates.
- Existing geometry and texture files remain unchanged.
- Generated PNG is reopened, structurally validated and SHA-256 checked.
- Traversal, symlink escapes, ambiguous geometry and output collisions fail closed.
- Existing MCP integration and all three default prompts remain unchanged.

## Limitations

- The geometry algorithms are still implemented in the preserved server modules; this is a transitional CLI adapter, not a complete pure-library extraction.
- Minecraft import/render, Blockbench interoperability and gameplay are NOT RUN.
- Plugin Creator 1.5.8 was not modified and no new release was created.


## Follow-up hardening

- Isolated PNG-shim test imports under a private module name and removed temporary painter/transfer modules from the global import cache. This prevents the CLI from accidentally reusing a test stub instead of the full PNG validator.
- Added a regression assertion that the CLI loads server/png_validation.py from the repository package.
- Execution metadata now represents mcp_transport_started as a JSON boolean, not a string.
