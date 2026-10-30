---
name: reference-mapping-review
description: Use after visual reference analysis when region-to-geometry assignments need explicit semantic review before transfer to Bedrock entity UV faces.
---

# Reference Mapping Review

## Purpose

Use `minecraft-bedrock-reference-mapping-review` / `review_reference_mapping` as the human-in-the-loop gate between `analyze_visual_reference` and `map_reference_texture_to_uv`.

The reviewer consumes the complete structured result from `analyze_visual_reference`, an exact `.geo.json` path and geometry identifier, an output texture path, and explicit decisions that connect a detected source region to one exact `(bone, cube_index, face)` target.

## Required workflow

1. Run `analyze_visual_reference` on the reference PNG. Optionally supply the target geometry to receive shape/area candidate rankings.
2. Inspect the source image and returned `regions`. Region IDs are arbitrary connected components, not semantic body parts.
3. For every proposed mapping, send a decision with:
   - `source_region_id` from analyzer output;
   - exact target `bone`, `cube_index` and face (`north`, `south`, `east`, `west`, `up`, `down`);
   - `decision`: `approve`, `reject` or `needs_review`;
   - an optional user-authored `semantic_label` such as `front_head` or `left_arm_outer`;
   - optional rotation, flips, nearest/bilinear sampling, opacity and blend mode.
4. Call `review_reference_mapping` and inspect all returned decisions, warnings, coverage and the `mapping_plan`.
5. Only when `review_status` is `approved` and `transfer_request` is non-null should the transfer request be passed unchanged to `map_reference_texture_to_uv`.
6. Inspect the resulting PNG, then run UV and resource audits. Import and render in the exact target Bedrock build before claiming runtime success.

## Integrity and validation

- The reviewer binds the submitted analysis result to the actual reference PNG with its SHA-256 and exact pixel dimensions. Replacing the image after analysis invalidates the review.
- It also fingerprints the exact geometry JSON bytes and the complete reviewed transfer configuration, including transformations and output/base texture settings.
- It re-reads the selected geometry and requires every target selector to resolve to exactly one supported cube face.
- A source region must exist in the analyzer result and its crop must remain inside the verified reference image.
- Every approved mapping becomes one exact selector assignment. Multiple mappings to the same target face are rejected unless intentional ordered layering is explicitly enabled; layering also requires the downstream overlap opt-in.
- `needs_review` decisions block the final `transfer_request`. `reject` decisions are retained in the review report and are never transferred.
- `require_full_coverage` prevents a transfer-ready request while any supported geometry face remains unmapped.
- A stable `review_manifest_sha256` fingerprints the reviewed decisions, geometry identity and reference image hash.
- The tool is read-only. It prepares a request but never writes or applies a texture.

## Interpretation limits

Candidate scores are only aspect-ratio and relative-area heuristics. They are not semantic confidence, image understanding or part recognition. Semantic labels and approval/rejection decisions must come from explicit human review. The workflow does not infer 3D projection, normals, seams, face orientation, texture material or runtime renderer behavior. Cube-face UVs only; poly-mesh and texture-mesh scopes remain outside these tools.

## Example

See `references/review-request.example.json`. Replace the analysis result with the full structured output from the analyzer and confirm that its image path and SHA-256 still match the file in the project.
