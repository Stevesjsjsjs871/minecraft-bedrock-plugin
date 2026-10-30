---
name: bedrock-content-pipeline
description: Plan a coherent Minecraft Bedrock BP/RP feature across behavior, visuals, dependencies and validation without inventing unavailable generators.
---

# Bedrock Content Pipeline

## Purpose and capability boundary

Turn a feature request into a coherent BP/RP implementation plan and reviewable file set. This Skill does not provide built-in project scaffolding, safe writer tools or a remote execution backend. Use only a real authorized host file capability. If none exists, return complete proposed files or a patch and mark them NOT APPLIED.

Default target is Bedrock 1.26.50 unless the user specifies another version. A bundled sample labelled 1.26.50.4 is source evidence, not proof that every field works in every 1.26.50 runtime.

## Work in feature bundles

For an entity, plan only the resources required by the requested behavior: BP entity definition and verified components; RP client-entity definition with matching namespaced identifier; geometry/model, texture, material and render-controller references; animation clips and controller states; optional spawn, loot, sounds and language entries; manifest/dependency links and all resource-reference paths.

For items and blocks, plan the definition, icon or texture, atlas entries, localization, recipe and supporting BP/RP resources as needed. Do not claim an asset is complete because a JSON reference exists.

## Orchestration order

1. Inspect project roots, manifests, UUID dependency, identifiers and current files. Never recreate an existing project.
2. Research exact-version Mojang Samples and official Creator documentation. Record provenance and distinguish confirmed fields from NEEDS VERIFICATION.
3. Produce a resource graph and file-by-file change plan before authoring.
4. Author through an actual authorized file capability, or return complete file contents and mark them NOT APPLIED.
5. Preserve existing resources and merge atlas, localization and manifest changes carefully. No silent overwrites or deletions.
6. Parse JSON, validate literal paths and identifiers, and run only the standalone audits whose documented coverage applies.
7. Re-open changed files, compare the baseline and package only after the archive has been inspected.

## Optional external applications

An external Creator Tools CLI, Blockbench, image editor or Minecraft installation may be used only when actually available and authorized. Record exact versions and operations. Do not imply that this plugin has a built-in connector to them.

## Completion report

Separate proposed files, files actually written, static checks, external-tool checks, package integrity and in-game results. Minecraft import, rendering, behavior, UI, multiplayer and performance remain NOT RUN unless actually tested.
