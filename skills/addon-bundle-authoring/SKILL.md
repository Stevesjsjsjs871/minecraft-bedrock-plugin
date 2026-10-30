---
name: addon-bundle-authoring
description: Plan and author a complete Minecraft Bedrock BP/RP feature bundle while preserving existing project resources and reporting real validation evidence.
---

# Add-on Bundle Authoring

## Capability boundary

This Skill is a coordinated authoring procedure, not a file writer or project scaffold. The plugin has no built-in BP/RP writer service. Use a real host file/workspace capability only when it is actually available and the user has authorized the selected project. Otherwise return complete proposed files or a patch and mark them NOT APPLIED. Do not imply that an external Creator Tools or Blockbench integration exists.

## Objective

Implement the requested behavior as one coherent feature bundle rather than disconnected sample files. Default target is Bedrock 1.26.50 unless the user specifies another exact version.

## Required process

1. Inspect the existing project root, BP/RP manifests, UUID dependency, namespaces, folder layout, identifiers and current resources. Never scaffold over an existing project.
2. Research the closest exact-version Mojang sample and official Creator documentation. Record the source release/tag, path and date checked. Separate confirmed fields from NEEDS VERIFICATION.
3. Plan all required files: BP definitions, RP client/render resources, geometry, textures, animations/controllers, localization, recipes, loot, spawn rules, sounds and manifest links only where the requested behavior needs them.
4. Author through the actual authorized file capability. If none exists, provide complete file contents and precise destination paths instead of claiming a write.
5. Preserve existing identifiers, UUIDs, atlas entries, language lines, manifests, definitions and unrelated files. Do not silently overwrite or delete.
6. Parse changed JSON with duplicate-key and non-finite-number rejection where the available checker supports it. Check literal resource paths, identifiers, BP/RP dependency links and image dimensions.
7. Run only the standalone audits and tests present in the package. For entity bundles, the entity-pipeline audit is a conservative static graph check, not a full Bedrock schema validator.
8. Package only with a real archive capability. Inspect the archive contents and integrity before calling it complete.

## Acceptance criteria

A feature is not complete because its main JSON exists. All planned required resources and literal references must be present, unresolved dependencies must be listed, and actual textures/models must exist at the referenced paths. Report static validation, external-tool results and Minecraft runtime separately.

## Safety

Reject path traversal and symlink escapes. Snapshot affected files before authorized writes. Never execute scripts from third-party add-on archives. Mark Minecraft import, rendering, gameplay and multiplayer NOT RUN unless actually tested.
