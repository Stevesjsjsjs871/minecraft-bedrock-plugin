# Skills-first capability matrix

This document distinguishes bundled executable local utilities, instruction-only workflows and optional external applications. It describes the source snapshot; it does not grant the host any new capability.

## Non-negotiable execution boundary

- Minecraft Bedrock Engineer is Skills-and-instructions-only. It has no active MCP server, tool registry, remote MCP endpoint, plugin-owned writer service or background executor.
- A Skill is a procedure and knowledge package. It cannot open files, write resources, run scripts, browse the web, launch Blockbench or Minecraft, or continue after the host session ends.
- A bundled Python script is usable only when the current host provides a real Python/terminal executor and the package and project files are accessible there.
- If no authorized file-writing capability exists, return complete file contents or a reviewable patch and mark the work NOT APPLIED. If no executor exists, mark tests NOT RUN.
- Files retained under server/ are legacy migration sources. They are not registered, callable or supported as runtime services. Do not import, launch or advertise them as active capabilities.

## Bundled standalone utilities

These are local scripts, not remotely callable tools. Check the actual file and its current help/output contract before execution.

| Capability | Entry point | Actual scope | Focused tests |
|---|---|---|---|
| Geometry and cube-UV audit | skills/geometry-uv-engine/scripts/geometry_engine.py | Static .geo.json parsing, supported classic/per-face cube UV bounds and overlap findings | skills/geometry-uv-engine/scripts/test_geometry_engine.py |
| UV guide rendering | skills/geometry-uv-engine/scripts/uv_template_engine.py | Separate transparent PNG guide for supported cube UV layouts; pixel budget and no-overwrite output | skills/geometry-uv-engine/scripts/test_uv_template_engine.py |
| PNG integrity | skills/visual-resource-pipeline/scripts/png_engine.py | PNG structure, chunk CRC, IDAT decompression, scanline and dimension checks | skills/visual-resource-pipeline/scripts/test_png_engine.py |
| Procedural PNG generation | skills/visual-resource-pipeline/scripts/generate_texture.py | Deterministic procedural styles implemented by the script; not AI artwork or semantic painting | skills/visual-resource-pipeline/scripts/test_generate_texture.py |
| Entity resource-graph audit | skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py | Conservative static JSON and selected literal dependency checks across supplied BP/RP roots | skills/entity-authoring-pipeline/scripts/test_audit_entity_pipeline.py |
| General pack audit | skills/automated-validation/scripts/bedrock_audit.py | Bounded static checks implemented by the script; inspect report schema and coverage before relying on it | Use only test files actually present |
| Mojang Samples index maintenance | skills/bedrock-development/scripts/index_mojang_samples.py | Local indexing of a supplied matching source tree; it does not download arbitrary remote files | skills/bedrock-development/scripts/test_index_mojang_samples.py |
| Package integrity and provenance | skills/package-integrity/scripts/check_skills_package.py | Offline package structure, manifests, prompt parity, skill inventory, version markers, sample index and provenance checks | skills/package-integrity/scripts/test_check_skills_package.py |

The UV renderer is a current standalone script. Do not describe it as dormant or unimplemented. The existence of a script or test does not prove Minecraft runtime compatibility.

## Instruction-only authoring workflows

The following workflows provide planning, format guidance, examples and review criteria. They do not include a bundled writer, generator, analyzer or one-click transaction:

- BP/RP project scaffolding and general add-on creation.
- Entity, block, item, recipe, loot, spawn-rule, sound and particle authoring.
- Animation clip and animation-controller authoring.
- Render-controller, material and attachable authoring.
- RP UI editing and full UI dependency-graph resolution.
- Semantic visual-reference segmentation, reference-to-UV assignment, geometry-aware texture painting and texture transfer.
- Multi-file animated-entity bundle creation and automatic UV retargeting.

For these workflows, use a real, authorized host file capability if one is actually available. Otherwise provide a complete proposed file set or patch. Do not claim that a writer, validator or transfer operation ran. Static checks must be limited to the scripts listed above and their documented coverage.

## Optional external applications

Minecraft Creator Tools, Blockbench, image editors and Minecraft itself are external applications. Use them only if an actual connected capability or installed local application is available and the user has authorized the operation. Record the exact version and operation. Their absence must not be disguised as a plugin failure or silently replaced with an imagined integration.

Minecraft import, rendering, Molang execution, animation playback, UI behavior, multiplayer behavior and Blockbench interoperability are NOT RUN unless actually exercised.

## Version and provenance rules

The default target is Bedrock 1.26.50 with the exact bundled Mojang Samples corpus labelled 1.26.50.4, unless the project specifies another target. A sample is evidence of source structure, not proof of runtime behavior. Record source release/tag, commit or archive digest, exact sample path and check date when available. Mark uncertain format/API assumptions NEEDS VERIFICATION.

Do not treat a GitHub mirror as the current Plugin Creator package. Record the package release ID and source commit separately; if the mapping is unknown, say NOT ESTABLISHED.
