# Skills-first capability matrix

This matrix describes the bundled package, not capabilities granted by the host. It is the source of truth for distinguishing installed local scripts, instruction-only workflows, optional external applications and inert legacy files. Re-check the actual host tools for every task.

## Non-negotiable execution boundary

- Minecraft Bedrock Engineer uses Skills, instructions, references and optional local scripts. It does not expose an active plugin-owned MCP server, remote tool registry, remote MCP endpoint, file writer service or background executor.
- A Skill is a procedure and knowledge package. It cannot by itself open a user's filesystem, write resources, run Python, invoke a CLI, launch Blockbench or Minecraft, or continue after the host session ends.
- A bundled Python script is usable only when a real Python/terminal executor is available and the package and project files are accessible there.
- If no authorized write capability exists, return complete file contents or a reviewable patch and mark the work NOT APPLIED. If there is no executor, mark tests NOT RUN.
- Files retained under `server/` are legacy migration material. They are not registered or callable runtime services. Do not import, launch or advertise them as active capabilities.

## Bundled standalone utilities

These are local scripts, not remote tools. Confirm that the listed file exists in the exact package and inspect its current help/output contract before relying on it.

| Capability | Entry point | Actual scope | Focused tests |
|---|---|---|---|
| Geometry and cube-UV audit | `skills/geometry-uv-engine/scripts/geometry_engine.py` | Static .geo.json parsing, selected geometry, supported classic/per-face cube UV bounds and overlap findings | `skills/geometry-uv-engine/scripts/test_geometry_engine.py` |
| UV guide rendering | `skills/geometry-uv-engine/scripts/uv_template_engine.py` | Separate transparent PNG guide for supported cube UV layouts; pixel budget and no-overwrite output | `skills/geometry-uv-engine/scripts/test_uv_template_engine.py` |
| PNG integrity | `skills/visual-resource-pipeline/scripts/png_engine.py` | PNG signature, chunk CRC, IDAT decompression, scanline and dimension checks | `skills/visual-resource-pipeline/scripts/test_png_engine.py` |
| Procedural PNG generation | `skills/visual-resource-pipeline/scripts/generate_texture.py` | Deterministic procedural styles implemented by the code; not AI artwork or semantic painting | `skills/visual-resource-pipeline/scripts/test_generate_texture.py` |
| Entity resource-graph audit | `skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py` | Conservative static JSON and selected literal dependency checks across supplied BP/RP roots | `skills/entity-authoring-pipeline/scripts/test_audit_entity_pipeline.py` |
| General pack audit | `skills/automated-validation/scripts/bedrock_audit.py` | Bounded static checks implemented by the script; inspect report schema and coverage | Use only test files actually present |
| Mojang Samples index maintenance | `skills/bedrock-development/scripts/index_mojang_samples.py` | Local indexing of a supplied matching source tree; does not download arbitrary remote files | `skills/bedrock-development/scripts/test_index_mojang_samples.py` |
| Package integrity and provenance | `skills/package-integrity/scripts/check_skills_package.py` | Offline package structure, manifests, prompt parity, skill inventory, version markers, sample index and provenance checks | `skills/package-integrity/scripts/test_check_skills_package.py` |

UV renderer is a current standalone utility, not a dormant feature. A script's presence or test pass does not prove Minecraft runtime compatibility.

## Instruction-only authoring workflows

These are procedures, examples and review criteria. They do not provide a built-in writer, generator, semantic analyzer or one-click transaction:

- BP/RP project scaffolding and general add-on creation.
- Entity, block, item, recipe, loot, spawn-rule, sound and particle authoring.
- Animation clip and animation-controller authoring.
- Render-controller, material, attachable and RP UI authoring.
- Full RP UI dependency-graph resolution.
- Semantic visual-reference segmentation and reference-to-UV assignment.
- Geometry-aware semantic texture painting and texture transfer, unless a separately verified local utility exists in the exact package inventory.
- Multi-file animated-entity bundle authoring and automatic UV retargeting.

Use only an actual authorized host file capability. Otherwise provide a complete proposed file set or patch and mark NOT APPLIED. Limit static claims to the scripts and coverage listed above.

## Optional external applications

Minecraft Creator Tools, Blockbench, image editors and Minecraft itself are external applications. Use them only when a real connected capability or installed local application is available and the operation is authorized. Record exact version and action. Their absence must not be disguised as plugin failure or replaced with an imagined integration.

Minecraft import, rendering, Molang execution, animation playback, UI behavior, multiplayer and Blockbench interoperability are NOT RUN unless actually exercised.

## Version and provenance

- Default reference target: Bedrock 1.26.50 and bundled Mojang Samples corpus 1.26.50.4, unless the project specifies otherwise.
- A sample is evidence of source structure, not proof of runtime behavior. Record release/tag, commit or archive digest, exact path and check date when available.
- Do not treat a GitHub mirror as the current Plugin Creator package. Record Plugin Creator package version/release ID and source commit separately. When the mapping is unknown, state NOT ESTABLISHED.
