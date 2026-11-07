---
name: visual-reference-analysis
description: Use when segmenting a Minecraft Bedrock reference PNG into connected regions and ranking human-reviewed crop candidates against geometry cube UV faces.
---

# Visual Reference Analysis

## Purpose

Use the bundled read-only utility `scripts/analyze_visual_reference.py` to inspect an existing PNG concept/reference sheet before manually authoring source-to-UV mappings. It finds connected regions, summarizes their bounds and colors, and can rank candidate image regions against supported Bedrock cube-face UV rectangles.

This is a local Python utility packaged with the Skill. It is not an MCP server or a ChatGPT-host tool; a successful local run does not prove that an installed ChatGPT host can execute arbitrary package scripts.

## Run

From the plugin package root:

```bash
python skills/visual-reference-analysis/scripts/analyze_visual_reference.py \
  ./forest-addon \
  resource_packs/forest-addon_RP/textures/references/forest_guardian_concept.png \
  --mode color_components \
  --color-bucket-size 16 \
  --min-region-area 12 \
  --geometry resource_packs/forest-addon_RP/models/entity/forest_guardian.geo.json \
  --geometry-identifier geometry.forest_guardian
```

The utility prints a structured JSON report to stdout and does not write project files. Omit `--geometry` to perform image segmentation only. Use `--geometry-identifier` when the file contains multiple geometry entries.

## Segmentation and matching

- `alpha_components`: 4-connected foreground regions using `--alpha-threshold`; useful when a reference sheet has a transparent background and detached parts.
- `color_components`: 4-connected regions of quantized RGB buckets; `--color-bucket-size` controls merging. Increase it when antialiasing/noise produces too many small islands; decrease it to separate neighboring color families.
- `--min-region-area` suppresses tiny speckles; `--max-regions` returns the largest regions first.
- Optional `--geometry` extracts supported classic-box and per-face cube UV rectangles through the shared Geometry & UV Engine. Candidate rank combines aspect ratio (80%) and normalized source/target area (20%). This is strictly geometric ranking.

## Required human review

Region names (`region_001`, etc.) are arbitrary identifiers, not semantic labels. The analyzer does not recognize heads, bodies, limbs, clothing, materials, front/back, or camera perspective. It does not infer 3D projection, face orientation, mirroring, or texture seams. Candidate scores are not semantic confidence. Inspect the source image and select the intended `source_rect` for each target face. Only then pass explicit mappings to the uv-texture-retargeting workflow.

## Input/output constraints

- Input is an existing PNG under `resource_packs/<project>_RP/textures/` in the selected project root.
- Decoder validates PNG structure and accepts supported 8-bit non-interlaced PNGs; convert unsupported/interlaced or high-bit-depth images first.
- Maximum analyzer canvas: 2048 px per side and 1,048,576 total pixels; maximum file size 16 MiB; maximum 120,000 segmentation runs; maximum 96 returned components and 512 UV-face candidate rankings.
- Optional geometry input must be JSON under `resource_packs/<project>_RP/models/entity/` and is limited to 2 MiB.
- Symlinks, unsafe paths, duplicate geometry JSON keys and ambiguous geometry files are rejected unless an identifier disambiguates the geometry.
- Mesh UVs are not part of this cube-face candidate ranker. Unsupported mesh scope is reported as a finding when surfaced by the geometry analyzer.
- The report includes the reference PNG SHA-256 for provenance. It never modifies the source image, geometry or mapping plan.

## Recommended workflow

1. Put the reference PNG inside the project's RP `textures/` tree.
2. Run `analyze_visual_reference.py` with `color_components` for opaque concept sheets or `alpha_components` for isolated transparent elements.
3. Inspect region bounds, average color and geometry-only candidate scores. Do not interpret candidate ranks as semantic matches.
4. Visually confirm each source crop; record manual semantic labels and confidence in the mapping review.
5. Supply confirmed rectangles to the uv-texture-retargeting workflow; inspect UV overlap and coverage warnings.
6. Transfer into a new output PNG, then run the texture-link/UV audits and in-game import tests.

Always mark Minecraft import, face orientation, material appearance and runtime as `NOT RUN` until verified in the target build.

## Tests

```bash
python -m unittest discover -s skills/visual-reference-analysis/scripts -p 'test_*.py' -v
```

The focused suite covers alpha/color segmentation, 4-connectivity, quantization, deterministic candidate ranking, geometry selection, duplicate-key rejection, path/symlink safety and read-only behavior.
