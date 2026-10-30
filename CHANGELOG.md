## 1.4.0 — Cloudflare Workers MCP transport

- Adds an authenticated Cloudflare Worker HTTP MCP gateway backed by a Python container, preserving the existing Python tool handlers.
- Keeps local STDIO MCP configurations available; Cloudflare is an additional remote transport, not a replacement.
- Registers the UV texture retarget server in both MCP registries.
- Updates plugin metadata and release documentation to 1.4.0.
- Deployment requires Cloudflare Workers Paid with Containers enabled and a configured `MCP_AUTH_TOKEN` secret.
- Static checks do not constitute Cloudflare deployment or Minecraft runtime verification.

---

# Plugin package changelog

## 1.3.0 — Consolidated animation, geometry and visual-resource engineering release

This release consolidates the previously unpublished 1.2.0 RC1–RC10 work into one integrated release. No separate 1.2.0 release was published.

- **Animation authoring:** adds time-based animation clip creation and validation, plus a read-only end-to-end animation pipeline audit for geometry/clip/controller aliases, state references, transitions, animated bones and cycles.
- **Animated entity orchestration:** adds a transactional `create_animated_entity_bundle` workflow combining BP entity, RP client entity, geometry, render controller, clips and controller state machine, with validation and SHA-256 guarded rollback for newly created files.
- **Geometry UV audit:** checks classic box UV and supported per-face UV regions, including `uv_size` and `uv_rotation`, with texture bounds/dimension checks and explicit unsupported-geometry reporting.
- **UV templates and mapping:** generates labeled UV guide PNGs and builds exact, geometry-aware face inventories and source-crop transfer plans.
- **Geometry-aware texture painting:** adds deterministic paint operations targeted to exact bone/cube/face UV regions, with base-image preservation, alpha handling, bounds and overlap checks.
- **Reference texture transfer:** copies explicit source-image crops into selected geometry UV faces with controlled sampling, rotation, flips, opacity and compositing.
- **Visual reference analysis:** adds bounded connected-component segmentation and geometric shape/area candidate ranking. This is algorithmic region analysis, not semantic AI/ML recognition.
- **Human-reviewed mapping:** binds decisions to source-image and geometry hashes, requires explicit reviewer decisions and exact selectors, validates coverage/overlap and only emits a transfer request when review gates pass.
- **MCP and skills:** adds dedicated servers, schemas, examples and skills for the new animation, geometry, UV and visual-reference workflows; both MCP registries are updated consistently.
- **Validation:** 221/221 local overlay tests passed; the new reference-review tests passed 28/28; stdio MCP smoke tests, manifest/schema checks, registry parity and archive integrity passed.

**Verification limits:** the historical full base-package suite was not rerun from the overlay checkout; local overlay tests use a bounded test-local PNG validator shim for a shared validator supplied by the installed base package. The end-to-end demo uses synthetic test assets and intentionally partial UV coverage. Minecraft import/render/runtime and Blockbench interoperability remain **NOT RUN**.

---


## 1.2.0 — RC10 human-reviewed reference mapping
- Adds `minecraft-bedrock-reference-mapping-review` with read-only `review_reference_mapping`.
- Binds analyzer output to the exact PNG file using path, dimensions and SHA-256; fingerprints exact geometry JSON bytes and full transfer decisions; rejects stale/replaced source images and invalid source rectangles.
- Requires explicit approve/reject/needs_review decisions and exact bone/cube/face selectors; preserves user-authored semantic labels and notes.
- Verifies each target resolves to exactly one UV face in the current geometry; includes optional shape/area candidate score as heuristic evidence only.
- Delegates UV coverage, overlap, destination and transfer contract checks to UV Mapping Assistant; pending decisions block the final transfer request; required full coverage blocks partial transfers.
- Adds the `reference-mapping-review` skill and example; registers the 15th MCP server in both registries.
- Read-only; does not write texture files, infer semantic parts, render 3D geometry or claim Minecraft runtime verification.

## 1.2.0 — RC9 visual reference region analysis
- Adds `minecraft-bedrock-visual-reference-analyzer` with read-only `analyze_visual_reference`.
- Uses bounded run-based 4-connected segmentation in alpha-foreground or quantized-color mode; reports component bounds, area, centroid, average color/alpha, coverage and edge contact.
- Optionally ranks connected components against supported geometry UV face regions using aspect ratio (80%) and normalized area (20%) only.
- Adds explicit non-AI/ML and non-semantic scope notes, requires human confirmation before UV mapping, rejects unsafe paths/symlinks, duplicate geometry JSON keys and oversized/over-complex inputs.
- Adds `visual-reference-analysis` skill and example; registers the 14th MCP server in both registries.
- Read-only; no semantic body-part recognition, 3D projection, automatic mapping or Minecraft runtime verification is claimed.

## 1.2.0 — RC8 UV mapping assistant
- Adds `minecraft-bedrock-uv-mapping-assistant` with the read-only `build_uv_mapping_plan` tool.
- Inventories every supported cube-face region with exact UV bounds, normalized coordinates, conservative pixel rectangles, bone/cube/face selectors and rotation metadata.
- Expands explicit source-sheet crop assignments into exact face mappings and validates each crop against the reference PNG.
- Reports mapped/unmapped coverage, UV overlap pairs, duplicate target assignments, optional base texture dimensions and output path collisions.
- Produces a schema-validated `transfer_request` directly compatible with `map_reference_texture_to_uv`; no geometry or texture files are modified by the planner.
- Adds the `uv-mapping-assistant` skill and a reference-sheet example; registers the 13th MCP server in both registries.
- No semantic image segmentation, 3D projection or Minecraft runtime verification is claimed.


## 1.2.0 — RC7 reference-image to geometry-UV transfer
- Adds `minecraft-bedrock-reference-texture-transfer` with `map_reference_texture_to_uv`.
- Maps explicit source PNG crops onto selected bone/cube/face UV regions using nearest or premultiplied-alpha bilinear sampling.
- Adds quarter-turn rotation, flips, opacity and source-over/replace blending; optional base texture preserves all unmapped pixels.
- Adds source-rectangle bounds checks, exact canvas size, overlap/duplicate-target gating, path and symlink protection, output collision refusal and texel budgets.
- Adds `reference-texture-transfer` skill and sample request; registers the 12th MCP server in both registries.
- Does not infer 3D projection or generate AI art; Minecraft face sampling, import and runtime remain NOT RUN.

## 1.2.0 — RC6 geometry-aware texture painting
- Adds `minecraft-bedrock-texture-painter` with `paint_geometry_texture`, using the RC5 geometry UV region parser rather than guessing a generic canvas.
- Adds ordered fill, border, checker, stripes, gradient and seeded-noise operations selected by bone, cube index and/or face.
- Supports a transparent/solid starting canvas or an existing 8-bit non-interlaced PNG source (grayscale, RGB, indexed, grayscale-alpha and RGBA), preserving untouched pixels and alpha.
- Enforces exact geometry canvas dimensions, explicit opt-in for intentional UV overlap, out-of-bounds refusal, path confinement, symlink checks and exclusive no-overwrite output.
- This is deterministic 2D region painting, not AI image synthesis, full UV sampling simulation or an in-game renderer; Minecraft runtime remains NOT RUN.

## 1.2.0 — RC5 UV template generation
- Adds `minecraft-bedrock-geometry-uv-template` with `generate_geometry_uv_template`.
- Expands classic box UV layouts into six labeled face regions and supports per-face UV rectangles, negative `uv_size` flips and 90°/180°/270° `uv_rotation`.
- Generates a separate transparent PNG guide under `textures/uv_templates/`, adds a pixel grid and face labels, and marks detected intersections in magenta.
- Detects possible UV region overlap, out-of-bounds faces and fractional coordinates; overlap is a review warning because mirrored/shared texture regions can be intentional.
- Applies workspace/path/symlink protections, strict JSON parsing, bounded image dimensions and no-overwrite output creation. Source geometry and actual entity textures remain unchanged.
- Minecraft texture sampling, face orientation and in-game rendering remain NOT RUN.

## 1.2.0 — RC4 geometry UV auditor
- Adds `minecraft-bedrock-geometry-uv-auditor` with the read-only `audit_geometry_uvs` tool.
- Checks classic box UV rectangles and alternate per-face UV mappings, including `uv_size` and `uv_rotation`, against declared texture canvas dimensions.
- Deeply validates an explicitly supplied PNG with the package's existing shared PNG validator; compares declared and actual dimensions and separately detects UV rectangles outside the actual image.
- Adds bounded geometry scanning, duplicate-key JSON rejection, path/traversal and symlink protection, structured findings, and incomplete-coverage reporting for poly meshes and texture meshes.
- Adds the `geometry-uv-audit` skill and registers the new MCP server in both MCP manifests.
- The tool is read-only; pixel-level preview and Minecraft import/render tests remain NOT RUN.

## 1.2.0 — RC3 animated entity bundle
- Adds `minecraft-bedrock-animated-entity-authoring` with `create_animated_entity_bundle`, composing the existing entity, animation-clip, animation-controller and pipeline-audit MCP modules.
- Creates a fresh BP entity + RP client entity, geometry, render controller, 1–16 time-based clips and a controller state machine in one validated workflow.
- Validates animation bone names against supplied geometry and controller state aliases/transitions before writing; then runs clip, controller and end-to-end graph validators.
- Adds SHA-256 guarded rollback for files created by the operation; concurrent edits that no longer match the last written hash are preserved and surfaced as rollback conflicts.
- Adds `animated-entity-bundle-authoring` skill and registers its MCP server in both package configurations.
- Texture PNGs, spawn rules, gameplay scripts, Molang evaluation and Minecraft runtime tests are not included; runtime remains NOT RUN.

## 1.2.0 — RC2 animation pipeline audit
- Adds `audit_entity_animation_pipeline` for static traversal of client-entity aliases, animation clips, controller states, transitions, geometry identifiers and animated bone references.
- Reports duplicate/missing/ambiguous references, external/dynamic references, confidence, severity and incomplete-scan state.
- Adds bounded scans and read-only validation; no assets are modified.

## 1.2.0 — RC1 animation clip authoring
- Adds time-based RP animation clip authoring and validation for rotation, position and scale keyframes.
- Registers clip aliases on client entities without changing controller-owned playback.
- Minecraft runtime and Molang evaluation remain NOT RUN.

## 1.1.1 — Animation-controller state machines
- Adds `minecraft-bedrock-animation-controller-authoring` as a dedicated stdio MCP server.
- Adds `create_animation_controller` to generate RP state-machine JSON from an initial state, state animation aliases, transition destinations/conditions, optional entry/exit commands and blend durations.
- Binds the controller into an existing client entity using `description.animations` and `description.scripts.animate`, preserving unrelated client entity resources.
- Adds read-only `validate_animation_controller` for state/transition/reference/binding checks.
- Enforces linked scaffold manifests, workspace confinement, safe RP paths, symlink and duplicate-JSON rejection, animation alias existence and no-overwrite behavior. The two-file authoring operation cleans up its new controller if updating the entity fails.
- Molang text is bounded but not parsed or executed. Minecraft runtime behavior remains NOT RUN.

## 1.1.0 — First-pass custom entity authoring
- Adds the `minecraft-bedrock-entity-authoring` stdio MCP server and `create_addon_entity` tool.
- Creates linked BP entity, RP client entity, geometry and render-controller JSON from an explicit bounded bone/cube model input.
- Validates bone names and parent graphs, finite coordinates, classic box-UV bounds, project manifests, entity identifier uniqueness and path safety.
- Refuses output collisions and symlinks; rolls back the files created by the operation if a write fails partway through.
- Does not fabricate textures, animations, animation controllers or spawn rules. Minecraft import/spawn/render testing remains NOT RUN.

## 1.0.14 — Full PNG stream validation and bounded texture audit
- Adds shared `server/png_validation.py` to validate PNG chunks/CRCs, legal IHDR/PLTE/tRNS rules, consecutive IDAT chunks, bounded zlib decompression, exact scanline sizes/filter bytes and Adam7 passes.
- Upgrades `audit_texture_links` to validate decompressed PNG scanlines and catches valid-CRC but corrupt compressed image data.
- Caches repeated PNG validation and applies per-audit limits for atlas entries, unique PNG files and aggregate bytes; reports `analysis_complete` and scan metrics.
- Auditor remains read-only; runtime validation remains NOT RUN.

## 1.0.13 — Read-only BP/RP texture-link audit
- Adds `audit_texture_links`, scanning BP block/item JSON through matching RP atlases to referenced PNG files.
- Reports missing keys/files, malformed or duplicate-key JSON, invalid atlas paths, corrupt PNGs, unsafe symlinks and unused atlas entries.
- Uses bounded scans and remains read-only, workspace-confined and runtime-unverified.

## 1.0.12 — PNG validation and atlas write safety
- Validates PNG image data, legal IHDR metadata, chunk ordering, consecutive IDAT chunks, bounded scanline sizes, filter methods and Adam7.
- Validates generated PNGs, serializes atlas updates with exclusive locks and rejects duplicate JSON keys.
- Static validation only; Minecraft import/rendering remains NOT RUN.

## 1.0.11 — Safe texture-atlas registration
- Adds `register_texture_atlas` for block and item Resource Pack textures.
- Preserves unrelated atlas entries and refuses conflicts, corrupt PNGs, unsafe paths and concurrent changes.

## 1.0.10 — Dedicated procedural texture MCP tool
- Adds the separate `minecraft-bedrock-texture-generator` stdio MCP server with `generate_texture`.
- Generates bounded RGBA PNG starter textures using deterministic procedural styles; it is not AI image synthesis or UV-aware painting.
