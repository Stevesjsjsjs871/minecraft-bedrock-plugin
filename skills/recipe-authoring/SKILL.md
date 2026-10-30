---
name: recipe-authoring
description: Design and manually author Minecraft Bedrock Behavior Pack recipe JSON with verified identifiers, ingredients and result data.
---

# Recipe Authoring

## Capability boundary

This Skill is format guidance, not a recipe writer or in-game recipe validator. Use an actual authorized file capability. Otherwise return the complete proposed recipe JSON and mark it NOT APPLIED.

## Workflow

1. Confirm the exact Bedrock target version and BP root.
2. Inspect existing recipes and the item/block identifiers used by ingredients and results.
3. Choose the recipe family required by the behavior and verify its exact fields against official Creator documentation and matching Mojang Samples.
4. Check identifiers, counts, tags, station/category fields and any version-sensitive properties. Do not invent schema keys.
5. Write a new recipe file without overwriting existing content. Preserve unrelated recipes and manifest data.
6. Parse JSON, reject duplicate keys where supported and verify literal referenced identifiers against the project inventory.
7. Re-open the file and report unresolved references and assumptions.

## Limits

A valid JSON document is not proof that Minecraft accepts or unlocks the recipe. Import the BP into the exact target build and test recipe discovery, ingredients, output and behavior before claiming runtime success.
