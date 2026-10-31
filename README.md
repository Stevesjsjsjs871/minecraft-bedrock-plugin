# Minecraft Bedrock Engineer — 1.8.0

## Architecture

Minecraft Bedrock Engineer is a Skills-and-instructions-only plugin. Its active architecture does not use MCP servers, registries, remote endpoints or a plugin-owned execution backend. Specialist skills define repeatable engineering workflows; they do not create tools, grant filesystem access, run code or work in the background. Bundled scripts are optional local utilities and run only when the host exposes a real executor and the package files are accessible. Historical server-side source files remain inert migration material and are not advertised as callable capabilities.

## Supported workflows

- Version-aware BP/RP development and safe incremental changes to existing projects.
- Entity authoring across BP behavior, RP client entity, model geometry, textures, animation clips, animation controllers and render controllers.
- Entity resource-graph auditing with a standalone, conservative static JSON/alias validator.
- Blocks, items, recipes, Script API guidance, manifests and pack dependencies.
- RP UI-folder inventory, localization, bindings, button mappings, control graphs and cross-resource reference tracing.
- Reference-pack analysis for UI, Subpacks, Skin Packs, PBR/Vibrant Visuals, fog/biomes, cooking add-ons, entity AI and Script API performance.
- Geometry, models, classic/per-face UV analysis, transparent UV-guide rendering, texture painting and reviewed reference-to-UV mapping.
- Archive, package, manifest, resource integrity, baseline and regression audits.
- Mojang Samples indexing and official Creator documentation research with version/source provenance.
- Release preparation, version governance, evidence reporting and Skills-only package integrity checks.

## Execution contract

1. Start with `skills/skills-first-execution/SKILL.md` and select only relevant specialist skills.
2. Inspect supplied files or an actually connected workspace. Establish project root, target version and baseline before editing.
3. Use native file/code capabilities only when actually available. Otherwise provide a complete patch or exact reproducible commands and mark work `NOT APPLIED` / `NOT RUN`.
4. Preserve existing mechanics, UUIDs, identifiers, assets and unrelated files. No silent overwrite or deletion.
5. Prefer exact-version official docs and Mojang samples; cite provenance. Bedrock 1.26.50 is the default target unless the user specifies otherwise.
6. Re-open changed files and validate manifests, UUIDs, identifiers, resource references, PNG/UV/animation relationships as applicable.
7. Report exact commands, exit codes, test counts, limitations and runtime status. Static checks do not prove Minecraft import/render/gameplay.

## Entity pipeline audit

From a package checkout, run:

```bash
python skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py --bp-root <BP> --rp-root <RP>
python skills/entity-authoring-pipeline/scripts/test_audit_entity_pipeline.py -v
```

The entity audit checks JSON integrity and selected literal dependency edges. It is not a full Bedrock schema validator, does not evaluate Molang and does not prove runtime rendering or behavior.

## Maintenance and validation

Use `skills/skills-only-maintenance/SKILL.md` for plugin maintenance and `skills/version-governance/SKILL.md` for version decisions. Run the package checker and regression suite from the actual extracted package root:

```bash
python skills/package-integrity/scripts/check_skills_package.py .
python skills/package-integrity/scripts/test_check_skills_package.py -v
```

The compressed Mojang Samples index and all unchanged binary assets are retained from the verified 1.7.3 source archive. Package integrity is checked from the full source checkout. Runtime, multiplayer and Blockbench checks must be reported as `NOT RUN` unless actually performed.

## Legacy-source migration status

Historical `server/` Python sources are retained solely as migration inputs. They are not registered, launched or invoked by the active plugin. Their dependency graph and algorithm reuse status are documented in `LEGACY_MIGRATION_AUDIT.md`. The old package-integrity entry points now delegate to the Skills-only checker. Do not treat retained protocol handlers or their tests as live capabilities.

## Reference pack corpus and specialist audits

Use `skills/reference-pack-corpus/SKILL.md` before analyzing user-supplied `.mcpack`/`.mcaddon`/ZIP reference materials. The read-only structural tool is `skills/reference-pack-corpus/scripts/reference_pack_audit.py`; run `--help` before use. It enforces archive path/expansion limits, records SHA-256, inspects manifests and distinguishes strict JSON from comment-aware JSON. It does not execute pack scripts, prove importability or measure FPS. The corpus inventory is a domain index, not certification that every uploaded archive has been exhaustively audited.

Specialist workflows: `ui-resource-audit`, `subpack-engineering`, `visuals-fog-pbr-audit`, `script-api-performance-audit`, `skin-pack-engineering` and `cooking-addon-engineering`.
