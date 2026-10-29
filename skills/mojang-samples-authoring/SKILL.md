---
name: mojang-samples-authoring
description: Use when creating new Minecraft Bedrock add-on content and selecting version-matched examples from the indexed Mojang bedrock-samples 1.26.50.4 corpus.
---

# Mojang Samples–Driven Authoring

Use the user-provided Mojang `bedrock-samples` archive as a version-specific reference when creating content. It is a reference corpus, not a blanket permission to redistribute vanilla assets. Pair this skill with `addon-creation` for project setup and `automated-validation` for independent static checks.

## Source identity
The archive index in `references/mojang-samples-1.26.50.4/INDEX_METADATA.json` records the uploaded archive SHA-256. If the user supplies another archive or changes its contents, build a new index with `skills/bedrock-development/scripts/index_mojang_samples.py` and record its hash. Do not conflate release samples with preview samples.

## Authoring method
1. Resolve target game version and requested type (item, block, recipe, entity, geometry, animation, controller, UI, localization, loot table, or script).
2. Search the index for the closest same-domain example and its identifiers. Consult the corresponding bundled example and offline documentation page. For version-sensitive details, check official Creator documentation and source examples for the exact game version.
3. Before creating a file, make a compact comparison: sample path, `format_version`, relevant schema sections, dependency/identifier relationships, texture/model/material links, and target-version evidence.
4. Author under the add-on's own namespace. Generate unique BP/RP UUIDs and ensure the BP dependency uses the actual RP header UUID and the matching version.
5. Add only resources needed for the requested behaviour. Keep vanilla-only internal fields out of custom content unless official documentation explicitly documents them. Never copy a vanilla item/entity/block file wholesale as a mod template.
6. For textures/models, check actual availability and licensing. Prefer user assets, original generated assets or appropriate licensed references. Never silently copy whole vanilla atlases, sounds, models or entities into generated packs.
7. Validate JSON syntax, manifest references, identifier uniqueness, namespace/path consistency and resolvable resource links. Distinguish static checks from in-game behaviour.
8. Report files changed, exact sample sources used, documentation evidence, checks and limitations. Keep Minecraft import/gameplay `NOT RUN` unless actually tested.

## Version policy
Default target is Bedrock 1.26.50. The uploaded archive is labelled 1.26.50.4, which is a closely related patch sample set but does not prove every field is compatible with every 1.26.50 runtime. For version-sensitive behaviour, compare official version-specific docs/schema and test in the requested game build. A `format_version` alone does not verify compatibility.

## Rebuild the index
`python skills/bedrock-development/scripts/index_mojang_samples.py <archive.zip> --output <index.json.gz> --target-version 1.26.50.4` creates a searchable JSON index without extracting members or executing embedded files. It uses bounded size/entry limits and rejects unsafe archive paths. It parses strict JSON only; commented JSON entries are left unparsed and need separate handling if relevant.
