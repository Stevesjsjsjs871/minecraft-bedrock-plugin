---
name: reference-mapping-review
description: Use after visual reference analysis to manually approve semantic source-region to Bedrock geometry UV-face assignments before texture transfer.
---

# Reference Mapping Review

## Purpose and capability boundary

This is a required **human/model visual-review step**, not an automated tool. The current package does not contain `review_reference_mapping`, `minecraft-bedrock-reference-mapping-review` or an automated semantic mapping planner. Do not call those historical names. Use the actual image-analysis output and geometry files available in the current environment; if the image or geometry cannot be inspected, mark the mapping `BLOCKED` rather than approving it from scores alone.

## Inputs

- The exact reference PNG and its SHA-256/pixel dimensions.
- Full JSON output from `skills/visual-reference-analysis/scripts/analyze_visual_reference.py`, when executed with a real local Python executor.
- Exact geometry JSON, geometry identifier, texture dimensions and UV-face inventory.
- Explicit candidate source crop rectangles and target `(bone, cube_index, face)` selectors.
- User-authored semantic labels and approval/rejection decisions.

## Manual review workflow

1. Run the analyzer only when a real executor can access both the package and project. Its component IDs are arbitrary and do not denote body parts.
2. Open the exact source PNG and inspect each proposed crop visually. Verify it is inside the image, includes the intended content, and is not an antialiasing speckle or unrelated region.
3. Inspect the selected geometry/UV guide. Verify exact bone, cube index, face, UV bounds, texture canvas and orientation. Candidate scores based on aspect ratio/area are sorting hints only.
4. For every proposed mapping, record `source_region_id` for provenance (in the review record only), exact `source_rect`, exact selector, semantic label authored by the reviewer, decision (`approve`, `reject`, `needs_review`), transformations, sampling, opacity and blend mode.
5. Reject uncertain/misaligned assignments. Keep overlapping/shared UV mappings disabled unless their intended layering/mirroring is explicitly reviewed. Do not require full geometry coverage unless the user's goal actually needs it.
6. Bind the review record to SHA-256 hashes of the reference and geometry. Any input change invalidates the approval and requires review again.
7. Only after approval, translate approved mappings into the **actual** request shape documented by `skills/uv-texture-retargeting/references/reference-transfer.example.json`. Do not pass review-only fields to the transfer script; unknown keys are rejected by its request parser.
8. Run the deterministic transfer script with a real executor, inspect the output PNG/report, then run UV, PNG and resource-link audits.

## Actual transfer boundary

The downstream implementation is `skills/uv-texture-retargeting/scripts/reference_transfer.py`, not `map_reference_texture_to_uv`. It accepts `project_directory`, `geometry_path`, optional `geometry_identifier`, `reference_image_path`, optional `base_texture_path`, `output_path`, optional `background_color`, `mappings`, and `allow_uv_overlap`. Each mapping uses a `selector`, `source_rect`, and supported transforms/options. Use its example JSON and CLI `--help` as the exact contract. The transfer utility writes a distinct output and does not perform semantic approval.

## Review integrity and interpretation

- Region IDs and geometric candidate rankings are not semantic labels or confidence.
- A source region must exist in the analysis result; source crops must remain in the verified image bounds.
- Every target selector must resolve to the intended supported cube face. Unsupported mesh/UV types stay out of scope.
- Keep a written mapping table linking analysis region, crop, semantic rationale, target selector, decision and hash provenance.
- Never state that a tool prepared a transfer request or approved a mapping; the reviewer records the decision manually.

## Required report

Return image and geometry hashes, dimensions/identifier, every reviewed crop/selector/semantic label/decision, rejected and unresolved assignments, overlap/coverage notes, transfer request path, exact static checks and runtime status. Import, face orientation, seam appearance, materials and Minecraft rendering remain `NOT RUN` until tested in the target game.
