---
name: visual-resource-pipeline
description: Use when a Bedrock feature includes geometry, textures, materials, render controllers, animations or animation controllers, especially when multiple resources must be generated and connected consistently.
---

# Visual Resource Pipeline

## Purpose

Build and validate the Resource Pack visual dependency chain as one feature. Use the exact target game version (default `1.26.50`) and prefer the bundled version-labelled Mojang Samples plus official Creator documentation.

## Expected dependency chain

For custom entities, verify as relevant:
`BP entity identifier → RP client entity → geometry identifier → material/render controller → texture path → animation definitions → animation controller → controller/animation references`.

For items and blocks, verify:
`BP definition → icon/terrain atlas entry → texture file → display localization → recipe or behavior references`, with geometry/material files added only where supported by the target resource type.

## Workflow

1. Inventory existing geometry, animation, animation-controller, render-controller, material and texture files. Locate all definitions and references rather than guessing path names.
2. Search version-matched Mojang samples for the closest geometry and animation patterns. Record source paths and whether fields are confirmed for the selected version.
3. If visual assets must be created, use the available Minecraft Creator Tools `design-model` capability for supported entity geometry, textures, item icons and block textures. Use `create-mob`, `create-item` or `create-block` for supported feature scaffolds, followed by the visual pass. Availability must be checked; never fabricate a successful delegation.
4. Ensure identifiers match exactly, paths use the pack's actual layout, and every non-dynamic reference resolves uniquely. Do not invent render-controller aliases or assume a file reference is an engine-supported feature.
5. Validate geometry identifiers, bone hierarchy, cube/vector shapes, UV structure, animation names and controller state transitions with the static checks that exist. Run Creator Tools validation when available.
6. Compare against the baseline and report newly unresolved links, changed definitions, resource removals and severity changes. Inspect visual and JSON changes together; never treat a JSON-only green result as proof that the model looks correct.
7. Import into the target game when possible. Check missing textures, geometry/rendering, animation state transitions and the actual entity/item/block behavior. Record the game build and scenario.

## Procedural texture starter

The bundled `scripts/generate_texture.py` uses only the Python standard library to create valid RGBA PNGs. It supports ten deterministic styles: `pixel_noise`, `checker`, `stripes`, `solid`, `vertical_gradient`, `horizontal_gradient`, `brick`, `stone_noise`, `ore_veins`, and `wood_grain`. Dimensions are capped at 1024 per side and 1,048,576 total pixels. RGB colors use six-digit hex; seed and alpha are explicit; output metadata is JSON; existing files are refused by default.

Example:

```bash
python skills/visual-resource-pipeline/scripts/generate_texture.py resource_packs/my-addon_RP/textures/blocks/ruby_ore.png --width 16 --height 16 --style ore_veins --base '#55545A' --accent '#9A5CDA' --seed 14
python -m unittest discover -s skills/visual-resource-pipeline/scripts -p 'test_*.py' -v
```

This produces a procedural starter pattern, not AI image synthesis, a UV-aware entity texture painter, or proof of Minecraft rendering. The generator is a standalone script and is **not currently registered or dispatched as an MCP `generate_texture` tool**. Do not claim that capability until server registration, workspace-confined path validation, dispatch and MCP integration tests are implemented and run.

## Procedural texture generation

The MCP `generate_texture` tool creates deterministic RGBA PNGs inside an existing linked Resource Pack at a relative path under `textures/`. Destination parent folders must already exist; traversal, symlink escapes and overwrites are rejected. It supports `pixel_noise`, `checker`, `stripes`, `solid`, `vertical_gradient`, `horizontal_gradient`, `brick`, `stone_noise`, `ore_veins` and `wood_grain`, with bounded dimensions, RGB hex colors, seed and alpha. This is procedural starter art, not AI image synthesis or UV-aware entity texture painting. Every result reports Minecraft runtime status as `NOT RUN`.

## Asset discipline

- Do not invent a model or texture when the user gave an exact reference; follow the described proportions, palette, silhouette and constraints.
- Do not delete unrelated geometry, bones, animations, controllers, textures or atlas entries.
- Preserve user-provided assets and note provenance/license limits for copied examples.
- When a tool only supports entity models and item/block textures, do not imply it can make arbitrary 3D block shapes or held-item geometry.
- Explicitly distinguish generated assets, reference samples, existing user assets and placeholders.

## Output

Provide the asset/resource inventory, dependency chain, generated/changed files, sample/documentation evidence, static findings, Creator Tools results, before/after regression findings and runtime status. Mark anything not executed as `NOT RUN`.
