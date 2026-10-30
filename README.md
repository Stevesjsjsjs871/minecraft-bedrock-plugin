# Minecraft Bedrock Engineer — 1.4.0

## Release overview

Version 1.4.0 adds an optional authenticated Cloudflare Workers HTTP MCP gateway backed by a Python container. The original local STDIO MCP configuration remains supported. See `cloudflare/README.md` for deployment instructions.


Minecraft Bedrock Engineer 1.4.0 consolidates the internal 1.2.0 release-candidate work into one release. It extends the existing Bedrock add-on authoring and auditing toolkit with animation authoring, end-to-end entity animation validation, geometry-aware UV inspection, UV template creation, deterministic texture painting, reference-image transfer, UV mapping plans, bounded reference analysis and a human-reviewed mapping gate.

The plugin targets the Minecraft Bedrock 1.26.50 workflow baseline unless a project selects another version. It preserves the existing project-first model: work inside an existing project scaffold, avoid overwriting user assets, protect project boundaries, and report static checks separately from in-game verification.

## Main capabilities added in this release

### Animation authoring and validation

- `create_animation_clip` authors time-based RP animation clips with bounded keyframes, supported transform channels, loop metadata and bone-name checks where geometry is available.
- `audit_entity_animation_pipeline` statically traces client-entity geometry, animation and controller aliases, state references, transitions, animated bones and cycles.
- `create_animated_entity_bundle` orchestrates a new BP entity, RP client entity, geometry, render controller, animation clips and controller state machine. It validates the assembled graph and uses SHA-256 guarded rollback for files created by the operation.

### Geometry and UV engineering

- `audit_geometry_uvs` checks classic box UV and supported per-face UV rectangles, including `uv_size` and `uv_rotation`, for bounds and texture-dimension consistency.
- `generate_geometry_uv_template` creates a labeled PNG UV guide with face regions, pixel grid and intersection warnings.
- `build_uv_mapping_plan` inventories supported cube faces and converts explicit source-sheet crops into exact target mappings and a transfer request.

### Texture creation and reference workflow

- `paint_geometry_texture` applies deterministic paint operations to selected UV regions, can retain a supplied base image and preserves untouched pixels/alpha.
- `map_reference_texture_to_uv` transfers explicit crops from a source reference PNG to exact bone/cube/face regions with controlled sampling, rotation, flipping, opacity and blending.
- `analyze_visual_reference` performs bounded connected-component segmentation of transparent or quantized-color regions and can provide geometric shape/area candidates. It is algorithmic analysis, not semantic AI/ML recognition of body parts.
- `review_reference_mapping` binds decisions to the exact reference PNG and geometry bytes, requires explicit approve/reject/needs-review decisions, and creates an approved transfer request only after selector, coverage and overlap checks. The review tool is read-only; the separate transfer tool performs the texture write.

## Connected reference-to-texture workflow

`analyze_visual_reference` → `review_reference_mapping` → `build_uv_mapping_plan` → `map_reference_texture_to_uv` → optional `paint_geometry_texture` → UV/resource audits.

The reference workflow is human-in-the-loop. Component detection and geometric ranking do not infer semantic identity. Developers must explicitly assign and approve source regions for exact geometry faces. Partial coverage is reported; it is not represented as a finished skin unless all required UV regions are covered.

## Safety and compatibility boundaries

- Tools use bounded inputs and project-relative path checks; write tools refuse unsafe paths, symlinks and unintended overwrites.
- Static JSON/PNG/graph validation does not prove Bedrock import, rendering, face orientation, animation playback or gameplay behavior.
- The UV tools cover supported cube UV forms. Unsupported geometry forms such as poly meshes or texture meshes are reported as outside the supported analysis scope rather than silently treated as validated.
- Texture painting/transfer are deterministic 2D pixel operations. They do not provide 3D view projection, mip/seam simulation or semantic generative painting.
- The reference analyzer does not claim AI semantic recognition. Candidate scores are geometric heuristics only.
- Minecraft import, rendering, runtime and Blockbench interoperability must be tested in the target environment and are not inferred from local unit tests.

## Validation evidence

- RC10 overlay regression suite: **221/221 tests passed** across 10 local overlay test modules.
- New human-reviewed reference mapping suite: **28/28 tests passed**.
- The end-to-end synthetic demo completed: reference analysis → human mapping review → UV mapping plan → reference texture transfer. Six of 24 UV faces were mapped intentionally; the resulting test texture was 64×64 PNG.
- Python compileall, JSON manifests, JSON Schema validation, 15-server MCP registry parity, stdio initialize/tools/list/call smoke tests and ZIP integrity checks passed.
- The local overlay test harness uses a test-local bounded PNG validator shim because the shared full PNG validator is provided by the installed base package and is not duplicated in this overlay. The historical full base-package test suite was not rerun from this overlay checkout.
- Synthetic demonstration assets are not production creature textures. Minecraft runtime/import/render tests and Blockbench interoperability tests are **NOT RUN**.

## Version history

The 1.2.0 RC1–RC10 iterations were internal, unpublished development candidates. Their combined functionality is released here as 1.3.0; there was no separate published 1.2.0 release.
