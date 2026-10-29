# Bedrock Validation Matrix

Use only checks relevant to the project and report actual execution results.

| Area | Static checks | Runtime tests |
|---|---|---|
| Archive | ZIP integrity, pack roots, expected files | Import pack into target game |
| Manifest | JSON parse, UUID uniqueness, module types, BP/RP links | World enables packs without content errors |
| Script | Syntax, imports, targeted API/source review | Run feature, error paths, repeated use, disconnect/dimension cases |
| Geometry | JSON/schema, geometry identifiers, bone references | Render entity/block and inspect offsets, culling, scale |
| Animation | Clip/controller references, bone/channel names | Trigger, blend, interrupt, finish, first/third person if relevant |
| Texture/material | File existence, dimensions, paths, material names | UV alignment, transparency, seams, render correctness |
| Recipes/items/blocks | IDs, component references, output/result references | Craft/use/break/drop and Creative visibility as applicable |
| UI/localization | JSON, texture paths, key coverage, references | Open/close, scale/resolution, locale switching |
| Multiplayer | Static sync assumptions, shared state model | Two-client timing, cancellation, disconnect, divergent state |
| Regression | Baseline diff, file hashes, additions/removals | Re-run critical old scenarios after changes |

Static validity never establishes runtime correctness. Mark unavailable runtime scenarios as `NOT RUN` and give concrete steps to execute them.
