---
name: visuals-fog-pbr-audit
description: Use when auditing Bedrock Vibrant Visuals, PBR texture sets, fog, biome client definitions, water, lighting and atmosphere resources.
---

# Visuals, Fog and PBR Audit

## Inputs and compatibility

Confirm exact Bedrock version/build, RP root, manifest capabilities/format, requested visual system and baseline. Use matching official Creator documentation and current Mojang sample patterns for version-sensitive Vibrant Visuals, fog, biome and PBR fields. Record source/version/date; do not infer engine behavior from property names alone.

## Workflow

1. Inventory manifests, biome client definitions, fog identifiers/files, water settings, lighting/color grading and PBR Texture Set declarations/assets present in the project.
2. Parse supported JSON and index exact identifiers, namespaces, texture paths and known literal references. Reject duplicate JSON keys where supported; retain exact path case.
3. Trace known fields only. Classify edges as `resolved`, `missing`, `ambiguous`, `dynamic`, `external` or `not checked`; do not promote heuristic string matches to confirmed missing references.
4. Check duplicate identifiers, missing fog resources, namespace mismatches, invalid texture paths, Texture Set-to-PNG pairing and documented channel requirements for the target version.
5. Review `fog_start`, `fog_end`, render distance and transition parameters in context. These values alone do not prove fog is disabled or active. Inspect default and per-biome bindings including dimensions where source-backed.
6. Compare the candidate with baseline and report exact path/pointer evidence. Preserve resources; an unused or unindexed file is not permission to delete.
7. Validate image files and supported channel/dimension requirements with real available scripts/tools. Record exact commands/results and any skipped formats.
8. Do not claim FPS gains from static analysis. For performance/visual quality, define controlled before/after tests on the same device, build, world, resource order and settings.

## Output and limits

Return pack/version identity, inventory, reference graph and coverage, PBR/fog/biome findings, baseline delta, source provenance, exact tests and limitations. Static checks do not simulate shaders, lighting, fog blending, water or renderer behavior. Visual output, performance and in-game application remain `NOT RUN` unless tested in the exact target environment.
