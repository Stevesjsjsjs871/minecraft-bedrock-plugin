---
name: visual-reference-analysis
description: Manually inspect a supplied visual reference and document candidate crops for a human-reviewed Minecraft Bedrock texture workflow.
---

# Visual Reference Analysis

## Capability boundary

The package does not include a standalone visual-reference segmentation script or semantic image analyzer. This Skill describes how to inspect an image that is actually supplied and visible to the current host. It cannot independently open arbitrary local paths or fetch remote images.

## Manual inspection workflow

1. Confirm that the reference image is attached or available through a real image-viewing capability. If not, mark the analysis BLOCKED.
2. Record image dimensions and visible background/alpha characteristics only when they can be inspected reliably.
3. Identify candidate regions visually and record pixel rectangles. Use neutral labels such as region A or front-head candidate until a human confirms their meaning.
4. Do not infer that a region is a head, limb, clothing, armor or a particular face from color or shape alone.
5. Compare candidate crop aspect ratios with the supported geometry UV inventory only as a geometric aid, never as semantic confidence.
6. Ask for explicit human confirmation of every crop-to-bone/cube/face assignment before preparing a transfer plan.
7. Preserve the original image and record its hash only when a real file executor can access it.

## Output

Return image dimensions if verified, candidate crop bounds, visible uncertainties, proposed semantic labels clearly marked as unconfirmed, and the next manual review step.

## Limits

No connected-component segmentation, color clustering, semantic recognition, 3D projection, face-orientation inference or automatic mapping is implemented in this package. Do not invent region IDs, scores or analyzer output. Geometry UV scripts do not analyze the semantics of a reference image. Minecraft rendering remains NOT RUN.
