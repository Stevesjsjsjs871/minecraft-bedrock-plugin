---
name: uv-texture-retargeting
description: Coordinate a manually reviewed reference-to-UV texture workflow for an existing Minecraft Bedrock entity without claiming one-click retargeting.
---

# UV Texture Retargeting

## Capability boundary

The package does not contain a one-click retargeting service or automatic reference-to-UV transfer implementation. This Skill coordinates planning and human review only. It does not write a PNG.

## Required inputs

- Existing BP/RP project and exact target version.
- Exact .geo.json path and geometry identifier.
- Reference image accessible to the current host.
- New output PNG path under the selected RP.
- Explicit source crop rectangles and exact bone/cube/face selectors.
- Human-reviewed semantic labels and decisions.

## Manual sequence

1. Inspect the project, geometry, texture canvas and client-entity texture references.
2. Run the standalone geometry audit and UV guide renderer only when a real executor can access the package and project files.
3. Inspect the reference image and choose source crops manually. Do not infer semantic correspondences automatically.
4. Prepare a mapping table with crop bounds, selectors, transforms, overlap decisions and reviewer approval.
5. Check source rectangles against the reference dimensions and target rectangles against supported geometry UV bounds.
6. If a real authorized image editor or separately tested transfer implementation is available, create a new PNG without replacing the source. Otherwise return the mapping plan and mark pixel transfer NOT APPLIED.
7. Validate any produced PNG and re-audit resource links. Preserve the geometry, source image and base texture.

## Limits

The available scripts do not perform semantic segmentation, 3D projection, UV unwrapping, texture transfer or Bedrock face sampling. Poly-mesh and texture-mesh formats are outside the supported cube-face UV audit. Minecraft import, visual rendering, seams, mipmaps and Blockbench interoperability remain NOT RUN until tested.
