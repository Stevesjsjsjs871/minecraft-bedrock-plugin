# Release Notes — 2.0.5

## Visual reference analysis, now available as a bundled local utility

- Ports deterministic, 4-connected alpha/color component segmentation into `skills/visual-reference-analysis/scripts/analyze_visual_reference.py`.
- Adds optional candidate ranking against supported classic-box and per-face cube UV rectangles, using aspect ratio (80%) and normalized area (20%). It never assigns semantic meaning to a region or automatically chooses a crop.
- Produces a structured stdout report with source dimensions, bounds, centroids, average colors, edge contact, geometric hints, warnings and the reference PNG SHA-256.
- Reuses the packaged PNG validator, texture-painter decoder and Geometry & UV Engine instead of importing historical `server/` modules.
- Adds strict project-relative file boundaries, symlink rejection, duplicate JSON-key rejection, bounded PNG/geometry sizes, 120,000-run segmentation budget, and caps on returned regions and UV candidate matches.
- Updates the Skill instructions with a local CLI workflow and explicit limitations. Adds 13 focused tests for segmentation, deterministic ranking, geometry selection, path safety, duplicate keys, symlinks and read-only behavior.

## Validation evidence

- Focused visual-reference suite: 13/13 passed.
- Full Skills suite: 27/27 test files and 486/486 test cases passed under local Python 3.13.5.
- Domain-Based Hybrid architecture validator: 28/28 checks passed; 14 domains, 65 Skills and 8 workflow profiles.
- Compatibility package checker: 19 passed, 0 failed, 1 warning. The only warning is the retained historical `server/` footprint (34 files).
- Script registry: 90 Python files covered with SHA-256 parity.
- Both manifests and `VERSION` set to 2.0.5; root/compatibility manifest identity and all 12 default prompts preserved.
- Strict Skills-only gate remains BLOCKED while legacy server source remains. No historical source files were deleted.
- Installed ChatGPT-host script execution: NOT VERIFIED. Minecraft import/render/gameplay: NOT RUN.

## Release lineage

- Update base inspected through Plugin Creator: version 2.0.4, release `pluginrel_6aeec9f1334081918688cb9d4cd63c54`.
- Existing plugin identity retained: `minecraft-bedrock-engineer` / `plugins_6ae33ff6e8d8819182f246d8d3d97323`; USER scope and PRIVATE audience unchanged.
