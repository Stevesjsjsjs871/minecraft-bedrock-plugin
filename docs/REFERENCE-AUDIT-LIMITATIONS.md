# Resource reference audit: scope and limitations

The reference scanner is intentionally conservative and heuristic. It searches parsed JSON string values for explicit path-like strings ending in known file extensions. It is useful for triage, but it is not a complete Bedrock pack validator.

## Current checks

- Reads JSON members from a ZIP-compatible archive without extracting them.
- Uses the shared JSON diagnostic parser.
- Looks for explicit references to common image, audio, JSON, shader, language, and material extensions.
- Compares candidates against archive paths case-insensitively using archive-root, source-relative, and suffix checks.
- Emits source file and JSON pointer for each candidate.
- Limits displayed unresolved examples to 100.

## Known limitations

- Bedrock formats use different roots and semantics; a generic string scanner cannot resolve every path correctly.
- Geometry, animation, controller, render-controller, particle, sound, item, block, and texture identifiers often refer to names rather than explicit file paths.
- Built-in Minecraft assets, aliases, generated files, subpacks, and separately installed packs can look unresolved.
- Case-insensitive checks can hide case-sensitivity issues on some platforms.
- The scanner does not verify schema rules, texture dimensions, geometry semantics, render-controller bindings, or Script API version compatibility.
- Recovery parsing of comments/trailing commas is diagnostic only. The target file's format determines whether those constructs are allowed.
- A clean result is not proof that a pack imports or runs in Minecraft.

## Safe interpretation

Treat each unresolved candidate as a review item. Before calling it a defect, check the file format, expected root, pack version, subpack selection, and whether the identifier is engine-provided. Runtime verification must record exact Minecraft version, platform, enabled experiments, and steps to reproduce.
