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

## Procedural texture generator

A command-line example (run from the plugin root):

```bash
python skills/visual-resource-pipeline/scripts/generate_texture.py resource_packs/my-addon_RP/textures/blocks/ruby_ore.png --width 16 --height 16 --style ore_veins --base '#55545A' --accent '#9A5CDA' --seed 14
```

`scripts/generate_texture.py` is the deterministic standard-library RGBA PNG writer. It supports `pixel_noise`, `checker`, `stripes`, `solid`, `vertical_gradient`, `horizontal_gradient`, `brick`, `stone_noise`, `ore_veins`, and `wood_grain`; width/height are capped at 1024 each and 1,048,576 total pixels.

The separate `minecraft-bedrock-texture-generator` stdio MCP server exposes `generate_texture`. It writes only inside an existing project's `resource_packs/<project>_RP/textures/` directory, requires existing parent folders, refuses symlinked paths and existing destinations, validates style/color/dimensions, and returns structured output with a file hash. It does not modify manifests or texture atlases automatically.

Example MCP call arguments:

```json
{
  "project_directory": "ruby-addon",
  "output_path": "resource_packs/ruby-addon_RP/textures/blocks/ruby_ore.png",
  "width": 16,
  "height": 16,
  "style": "ore_veins",
  "base_color": "#55545A",
  "accent_color": "#9A5CDA",
  "seed": 14
}
```

This remains procedural starter art, not AI image synthesis, UV-aware entity texture painting, automatic atlas integration, or proof of Minecraft rendering. Runtime/import/rendering checks remain `NOT RUN` unless executed in-game.

## Asset discipline

- Do not invent a model or texture when the user gave an exact reference; follow the described proportions, palette, silhouette and constraints.
- Do not delete unrelated geometry, bones, animations, controllers, textures or atlas entries.
- Preserve user-provided assets and note provenance/license limits for copied examples.
- When a tool only supports entity models and item/block textures, do not imply it can make arbitrary 3D block shapes or held-item geometry.
- Explicitly distinguish generated assets, reference samples, existing user assets and placeholders.

## Output

Provide the asset/resource inventory, dependency chain, generated/changed files, sample/documentation evidence, static findings, Creator Tools results, before/after regression findings and runtime status. Mark anything not executed as `NOT RUN`.
