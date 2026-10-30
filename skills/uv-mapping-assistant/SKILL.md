---
name: uv-mapping-assistant
description: Prepare a human-reviewed mapping plan between supported Bedrock geometry cube faces and texture-space regions.
---

# UV Mapping Assistant

## Capability boundary

This Skill prepares a mapping plan only. The package does not contain an automatic UV mapping planner or a reference-to-UV pixel-transfer implementation. It does not infer semantic correspondences or write a texture.

## Workflow

1. Inspect the exact .geo.json and select the intended geometry identifier.
2. Use the standalone geometry engine to inventory supported cube-face UV bounds and overlaps.
3. Use the standalone UV template renderer to create a separate labelled guide when a real executor can access the files.
4. Record the target texture canvas, bone names, cube indices, face names and UV rectangles.
5. For a supplied reference image, select source crops manually and record their pixel bounds. Require explicit human confirmation of every semantic mapping.
6. Produce a mapping table with source rectangle, target selector, transform, overlap status, reviewer decision and unresolved uncertainty.
7. Do not apply pixel changes unless an actual authorized image editor or separately tested local implementation is available. Otherwise return the plan and mark transfer NOT APPLIED.

## Limits

The current geometry tools cover documented cube UV formats only. They do not perform mesh projection, semantic segmentation, automatic unwrapping, face-orientation simulation or Minecraft rendering. Mark unsupported formats and runtime checks explicitly.
