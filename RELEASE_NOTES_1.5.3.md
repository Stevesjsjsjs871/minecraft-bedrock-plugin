# 1.5.3 — Skills-only package integrity and regression gate

- Adds a new standard-library-only package checker designed for the current Skills-only architecture.
- Validates both manifests, version and prompt parity, skills path, unique skill frontmatter, README version, no-MCP configuration boundary and bundled Mojang sample-index integrity.
- Adds eight synthetic regression tests covering valid packages and critical failure conditions.
- Reclassifies the old MCP-registry package checker and its tests as historical; they are not the release gate for current versions.
- No authoring skills, reference data, or source assets were removed.
