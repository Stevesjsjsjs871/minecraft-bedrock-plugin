---
name: visual-reference-analysis
description: Use when inspecting a PNG concept/reference sheet for connected regions and preparing human-reviewed source crop candidates for Minecraft Bedrock geometry UV mapping.
---

# Visual Reference Analysis

## Purpose

Use `minecraft-bedrock-visual-reference-analyzer` / `analyze_visual_reference` before manually authoring `source_assignments` for `build_uv_mapping_plan`. It identifies connected components, summarizes their bounds and colors, and can rank candidate image regions against the aspect ratio and relative area of geometry UV faces.

## What the analyzer really does

- `alpha_components`: 4-connected foreground regions using `alpha_threshold`; useful when a reference sheet has a transparent background and detached parts.
- `color_components`: 4-connected regions of quantized RGB buckets; `color_bucket_size` controls merging. Increase it when antialiasing/noise makes too many small islands; decrease it to separate neighboring color families.
- `min_region_area` suppresses tiny speckles; `max_regions` returns the largest regions first.
- Optional `geometry_path` plus `geometry_identifier` extracts supported Bedrock cube-face UV regions and ranks image components by aspect ratio (80%) and normalized area (20%). This is strictly geometric ranking.

## Required human review

Region names (`region_001`, etc.) are arbitrary identifiers, not semantic labels. The analyzer does not recognize heads, bodies, limbs, clothing, materials, front/back, or camera perspective. It does not infer 3D projection, face orientation, mirroring, or texture seams. Inspect the source image and select the intended `source_rect` for each target face. Only then pass explicit mappings to `build_uv_mapping_plan` and `map_reference_texture_to_uv`.

## Input/output constraints

- Input is an existing PNG under `resource_packs/<project>_RP/textures/`.
- Decoder accepts validated 8-bit non-interlaced PNGs supported by the shared painter decoder; convert unsupported/interlaced or high-bit-depth images first.
- Maximum analyzer canvas: 2048 px per side and 1,048,576 total pixels; maximum 120,000 segmentation runs; maximum 96 returned components and 512 UV-face candidate rankings.
- Reads files only. It never writes a preview, texture, geometry or mapping plan.
- Symlinks, unsafe paths, duplicate geometry JSON keys and ambiguous geometry files are rejected unless an identifier disambiguates the geometry.

## Recommended workflow

1. Put the reference PNG inside the project's RP `textures/` tree.
2. Call `analyze_visual_reference` with `color_components` for opaque concept sheets or `alpha_components` for isolated transparent elements.
3. Inspect region bounds, average color and geometry-only candidate scores. Candidate scores are not semantic confidence.
4. Visually confirm each source crop; record manual semantic labels outside the analyzer if needed.
5. Supply confirmed rectangles to `build_uv_mapping_plan`; inspect UV overlap and coverage warnings.
6. Transfer into a new output PNG, then run the texture-link/UV audits and in-game import tests.

Always mark Minecraft import, face orientation, material appearance and runtime as `NOT RUN` until verified in the target build.
