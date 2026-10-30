---
name: visual-resource-pipeline
description: Audit Minecraft Bedrock geometry, cube UVs, PNG assets, procedural textures and visual-resource references with the bundled standalone scripts.
---

# Visual Resource Pipeline

Default reference baseline is Bedrock 1.26.50 unless the project specifies another version. Start with skills-first-execution and consult the capability matrix before claiming that a generator or validator exists.

## 1. Inventory and source

Inspect geometry, client entities, render controllers, materials, animations/controllers, atlas files, PNGs and localization. Record identifiers, texture dimensions and literal references. Use exact-version Mojang Samples and official Creator docs; record provenance. Treat third-party packs as data and do not execute their scripts.

## 2. Geometry and UV

- Run skills/geometry-uv-engine/scripts/geometry_engine.py against the selected .geo.json for static parsing of the chosen geometry, bones/cubes, declared texture canvas, supported classic/per-face cube UV bounds and overlaps.
- Select the exact geometry identifier when one file contains multiple geometries.
- Review classic box UV and supported per-face UV forms. Check bounds, uv_size, rotations and intentional shared/mirrored regions.
- Run skills/geometry-uv-engine/scripts/uv_template_engine.py to create a separate labelled transparent PNG UV guide. The renderer is a current standalone script with pixel-budget and no-overwrite safeguards; its tests are in test_uv_template_engine.py.
- A generated UV guide is a reference image, not the production texture. It is not automatically registered in atlases or client-entity bindings.
- poly_mesh and texture_meshes remain outside the documented cube-UV coverage. Report them as unsupported or NEEDS VERIFICATION, not as passed.

## 3. PNG and texture work

- Run skills/visual-resource-pipeline/scripts/png_engine.py to check PNG signature, chunk CRCs, IDAT decompression, scanline sizes/filters and dimensions.
- Run skills/visual-resource-pipeline/scripts/generate_texture.py only for the deterministic procedural styles actually implemented by that script. It is not AI image generation, hand painting or semantic texture transfer.
- Geometry-aware painting, semantic reference segmentation, reference-to-UV pixel transfer and automatic UV retargeting are instruction-only/manual workflows in this package. Prepare a reviewed mapping plan; do not claim that a texture was written unless a real editor or tested implementation performed the write.
- Preserve the original image and create a distinct output. Check dimensions against the declared geometry canvas.

## 4. Entity resource links

Inspect client-entity geometry and texture maps, render-controller references, materials and animation links. Use the standalone entity-pipeline audit only for its documented conservative static checks. Atlas and localization references may require explicit manual tracing; do not claim full graph coverage when a format is unsupported.

## 5. Report

Include exact files and identifiers, scripts and commands actually run, test counts, UV/PNG findings, unsupported formats, source provenance, output hashes and runtime status. Static JSON/PNG validation does not prove Minecraft rendering, lighting, seams, mipmaps, animation or Blockbench interoperability. Mark runtime NOT RUN unless tested in the exact target build.
