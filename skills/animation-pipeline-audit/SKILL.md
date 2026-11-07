---
name: animation-pipeline-audit
description: Use when auditing the end-to-end Bedrock entity animation graph linking client-entity aliases, animation clips, controller states, geometry identifiers and model bone names.
---

# End-to-end Entity Animation Pipeline Audit

## Purpose and real implementation

Use the bundled read-only utility `skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py` when a real Python executor can access the package and the selected BP/RP project. This Skill does not expose an MCP tool named `audit_entity_animation_pipeline` and does not provide a hosted file scanner. If the script or project is unavailable, perform a bounded manual inspection or report the check `BLOCKED`/`NOT RUN`.

## Inputs and command

Required: exact BP root and RP root from one linked project. Optional: an exact `namespace:entity` filter. From the plugin package root:

```bash
python skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py \
  --bp-root <behavior-pack-root> \
  --rp-root <resource-pack-root> \
  --entity-id namespace:entity \
  --output animation-pipeline-report.json

python skills/entity-authoring-pipeline/scripts/test_audit_entity_pipeline.py -v
```

Omit `--entity-id` to audit all entities covered by the utility. Inspect `--help` and the script source before use if the installed package differs. The test command checks the utility itself; it does not validate the user's pack.

## Current static coverage

The utility parses supported JSON and inventories literal entity/client-entity, geometry, texture, animation, controller and render-controller relationships. It checks client-entity `description.animations`, `description.geometry` and `scripts.animate`; literal clip/controller/geometry identifiers and aliases; controller state animation aliases and transition destinations; nested controller references; and clip bone names against declared geometry variants. It reports duplicate, missing, ambiguous and uncertain/external references conservatively.

## Interpretation

- `HIGH`: strong evidence of exact missing/ambiguous resources, invalid literal graph edges or unsafe/malformed input.
- `WARNING`: potential bone mismatches, suspicious cycles or questionable structure; review context before changing anything.
- `INFO`: dynamic, external or nonstandard references the static analyzer cannot resolve.
- `analysis_complete=false`: a limit, unsafe path or parse error reduced coverage. Do not present it as a clean audit.
- Vanilla assets outside the RP and other-pack dependencies may be external. Namespace heuristics are not proof of ownership.

## Limits and next checks

This is not a complete Bedrock schema validator. It does not evaluate Molang, infer dynamic resource names, execute scripts, render geometry, simulate interpolation/blending, inspect runtime controller priority, validate all PNG data or launch Minecraft. Pair it with geometry/UV, PNG, dependency-closure and full pack audits where relevant. Runtime remains `NOT RUN` until the exact target build is tested.

## Required report

Return entity filter, BP/RP roots, files parsed/scanned by category, resolved and unresolved alias counts, controller state/transition counts, findings with exact paths and JSON pointers, `analysis_complete`, skipped/unsupported cases, command and exit code, utility test result (separate from pack result), Molang status and Minecraft runtime status. Never delete resources solely because this audit cannot resolve them.
