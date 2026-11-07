---
name: uv-texture-retargeting
description: Use to plan, review and deterministically transfer reference-image pixels onto exact Minecraft Bedrock geometry UV faces.
---

# UV Texture Retargeting

## Purpose and capability boundary

This is a coordinated workflow, not a single bundled tool. The current package contains no `retarget_texture_to_entity`, `build_uv_mapping_plan` or `map_reference_texture_to_uv` tool. Use the real local scripts `analyze_visual_reference.py` and `reference_transfer.py` only when a Python executor can access the plugin package and project. Otherwise prepare a manual mapping/transfer request and mark it `NOT APPLIED`.

## Required inputs

- Existing project directory and linked RP.
- Exact `.geo.json` path and geometry identifier when more than one is present.
- Reference PNG inside the project RP textures tree.
- Optional base texture whose pixels should be preserved outside mapped regions.
- New, non-existing output PNG path under the RP textures tree.
- One or more visually reviewed pixel crop rectangles mapped to exact geometry selectors (`bone`, `cube_index`, `face`).
- Sampling, rotation/flips, opacity and blend choices where needed.

Every semantic label and source-to-face assignment must be explicitly reviewed from the image and geometry. Never derive body-part semantics from aspect-ratio/area scores.

## Workflow

1. Establish project identity, target Bedrock version, BP/RP roots and baseline. Verify the source and output paths are inside the intended RP; do not overwrite an existing output.
2. Inspect the geometry with `geometry-uv-engine` and create a UV guide with `geometry-uv-engine` when a real executor is available. Record texture dimensions, supported faces, bounds and overlaps.
3. Analyze the reference PNG with `skills/visual-reference-analysis/scripts/analyze_visual_reference.py` when executable. Record image SHA-256 and pixel dimensions. This is a read-only region inventory, not semantic recognition.
4. Complete `reference-mapping-review` manually. Approve/reject each crop-to-face mapping and record reviewer rationale plus reference/geometry hashes. Re-review if either source changes.
5. Build a JSON transfer request using the exact schema in `skills/uv-texture-retargeting/references/reference-transfer.example.json`. Valid root keys are `project_directory`, `geometry_path`, optional `geometry_identifier`, `reference_image_path`, optional `base_texture_path`, `output_path`, optional `background_color`, `mappings` and `allow_uv_overlap`. Each mapping contains `selector`, `source_rect` and optional `rotation`, `flip_x`, `flip_y`, `sampling`, `opacity`, `blend_mode`. Do not include review-only keys such as `review_confirmed`, `approved`, `source_assignments` or `require_full_coverage`; the transfer parser does not accept them.
6. Inspect the real CLI contract, then run:

```bash
python skills/uv-texture-retargeting/scripts/reference_transfer.py <request.json> --workspace <workspace-directory> --report <report.json>
```

7. Inspect the output PNG visually and verify the reported dimensions, PNG decoding, SHA-256, mapped face selectors, unmapped coverage and overlap warnings. Re-run geometry UV, PNG and resource-link audits.
8. Compare the output tree against baseline. Do not replace the original reference/base texture unless explicitly authorized.
9. Import into the exact Bedrock build and inspect every intended face, orientation, seam, alpha/material and mip behavior. Mark runtime `NOT RUN` otherwise.

## Safety and supported scope

- The downstream transfer script is `skills/uv-texture-retargeting/scripts/reference_transfer.py`; it supports classic box/per-face cube UV cases described in its Skill, not arbitrary mesh projection.
- PNG inputs are limited to the formats/depths documented in `uv-texture-retargeting/SKILL.md`; unsupported/interlaced/high-bit-depth files must be converted before transfer.
- UV overlap and duplicate target selections fail by default. Enable `allow_uv_overlap` only after explicit review.
- Output creation is exclusive; keep paths project-relative POSIX paths and reject symlinks/traversal.
- This is deterministic 2D texture-space transfer, not 3D projection, AI semantic texture synthesis or proof of Bedrock rendering.

## Required report

Report project and target version; reference/geometry/base hashes; geometry identifier and texture canvas; every source crop and target selector; review decisions; mapped/unmapped faces and overlaps; transfer command/exit code; output path, dimensions and SHA-256; PNG/UV/resource checks; baseline delta; unsupported formats; and Minecraft runtime status.

## Consolidated planning and transfer modes

This is the canonical user-facing end-to-end workflow formerly supplemented by `uv-texture-retargeting` and `uv-texture-retargeting`. Modes:

- **mapping-plan** — inventory geometry/cubes/faces, image crops, exact `(bone, cube_index, face)` selectors, texture dimensions and candidate UV mapping; record source image/geometry hashes and confidence limits.
- **reviewed-transfer** — require the separate `reference-mapping-review` human approval decision before deterministic pixel transfer. Translate only approved mapping fields into the strict transfer request schema; review-only keys such as `approved` or `review_confirmed` must never be passed to the transfer parser.
- **inspect-output** — inspect distinct output PNG, hash/dimensions, mapped/unmapped coverage, overlaps and rerun relevant UV/PNG/resource-link audits.

The deterministic implementation remains at `skills/uv-texture-retargeting/scripts/reference_transfer.py`, with its existing tests and example request; do not move or duplicate it. The request schema is strict: preserve path confinement, source hashes, no-overwrite behavior and supported UV limitations. Geometric ranking is not semantic certainty. Human approval remains mandatory for semantic face/crop decisions; never automate or bypass `reference-mapping-review`.
