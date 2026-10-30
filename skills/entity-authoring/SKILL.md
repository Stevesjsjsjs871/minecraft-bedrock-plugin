---
name: entity-authoring
description: Design and manually author the coordinated BP entity and RP client-entity resources for a Minecraft Bedrock entity.
---

# Entity Authoring

## Capability boundary

This Skill provides a file-authoring procedure, not an automatic entity generator. Use an actual authorized file/workspace capability. Otherwise provide complete JSON files and mark them NOT APPLIED.

## Workflow

1. Confirm the exact target Bedrock version, BP/RP roots and linked manifest UUIDs.
2. Inspect existing namespaces, identifiers, entity files, client-entity definitions, geometry, textures, render controllers, animations, spawn rules and loot resources.
3. Define the namespaced entity identifier once and use it consistently in BP and RP resources.
4. Add only the behavior components required by the request. Verify each component and version-sensitive property against official documentation and matching Mojang Samples.
5. Define the client entity's geometry, texture, material, render-controller and animation references only when the corresponding files exist.
6. Preserve existing resources and aliases. Do not silently replace a vanilla or project identifier.
7. Parse changed JSON and run the standalone entity-pipeline audit when its script and project roots are accessible.

## Limits

The static audit checks selected literal resource links; it is not a full Bedrock schema validator and does not evaluate Molang or spawn behavior. Minecraft import, spawn, rendering and gameplay remain NOT RUN until tested.
