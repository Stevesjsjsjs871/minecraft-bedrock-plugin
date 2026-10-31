---
name: animation-pipeline-audit
description: Statically audit entity, geometry, animation and controller resource links across a Minecraft Bedrock BP/RP project.
---

# Animation and Entity Pipeline Audit

## Capability boundary

The available implementation is the standalone entity-pipeline audit script. This Skill does not expose a callable server operation and does not generate or repair resources.

## Execution

When a real Python executor can access both the package and project, run:

    python skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py --bp-root <BP> --rp-root <RP>

Run its focused tests from the package root:

    python skills/entity-authoring-pipeline/scripts/test_audit_entity_pipeline.py -v

Check the script's current help before using additional options. Do not infer undocumented flags.

## What to inspect

- BP entity JSON and matching RP client-entity identifiers.
- Geometry identifiers and literal geometry references.
- Animation and controller files exposed by the supported audit.
- Literal aliases and selected dependency edges.
- Parse failures, duplicate JSON keys, ambiguous paths and incomplete scans.

Report the exact roots, files scanned, finding paths and pointers, audit limits and completion status. Do not treat a partial scan as a clean result.

## Limits

This conservative static audit does not evaluate Molang, execute scripts, render geometry, prove animation playback or fully validate Bedrock schemas. It cannot infer all dynamic resource references.

Minecraft import, rendering, animation playback, controller transitions, multiplayer and Blockbench checks remain NOT RUN until genuinely performed in the target environment.
