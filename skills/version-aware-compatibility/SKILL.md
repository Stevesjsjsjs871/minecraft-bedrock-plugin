---
name: version-aware-compatibility
description: Use when deciding whether Bedrock BP/RP JSON, Script API modules, UI resources, entity components, blocks, items, or creator features are compatible with a specific Minecraft Bedrock game version, especially when changing format_version or migrating an existing add-on.
---

# Version-aware compatibility and migration

## Goal

Prevent version drift: game version, JSON `format_version`, Script API module version, manifest `min_engine_version`, experiment requirements, and Creator Tools version are separate compatibility dimensions. Never treat them as interchangeable.

## Required intake

1. Record the exact game build and platform when known. For server/client parity, record both. If the user has not selected a build, ask once only when the choice changes the implementation; otherwise use the project's declared baseline and label it.
2. Inventory BP/RP manifests, module types, dependencies, `min_engine_version`, script `dependencies`, entity/block/item/recipe/resource JSON `format_version`, experiments, and any version-specific folders.
3. Identify each feature or component being created or migrated. Preserve the existing format version unless the requested feature requires a newer one.
4. Record source provenance: official Creator documentation URL, exact Mojang Samples release/commit and file path, and date checked. Community sources are secondary and must not override conflicting official evidence without explanation. Distinguish pinned release samples from moving `main` branch snapshots; record archive SHA-256 when a commit SHA is unavailable. The bundled metadata-only corpus report may guide sample discovery, but an observed manifest declaration is not proof of API availability or stable support.

## Compatibility research

- Check official release notes for the target build and the corresponding stable reference documentation.
- Check matching-version Mojang samples, not only the default branch or latest samples.
- For Script API, verify each `@minecraft/*` module version against the target game release and stable/beta status. Do not infer API availability from TypeScript typings alone.
- For JSON content, verify the schema and behavior under the resource's own `format_version`. A game update can tighten a schema even if a pack still parses as JSON.
- Separate `SUPPORTED`, `EXPERIMENTAL`, `BETA`, `DEPRECATED`, `REMOVED`, `UNKNOWN`, and `NOT_APPLICABLE` statuses. A feature documented as experimental must not be represented as stable.
- Record breaking changes, stricter validation, renamed fields, changed value types, defaults, migration notes, and experiment/toggle requirements.
- For RP UI, verify actual file/control/import conventions and the target build. Static UI references do not prove layout or navigation runtime behavior.

## Implementation rules

1. Build a compatibility matrix: feature/resource path, current declaration, target requirement, evidence URL/sample, status, migration action, risk and validation.
2. Prefer the smallest migration that satisfies the target. Avoid global format-version bumps.
3. Preserve identifiers, UUIDs, dependencies, event names, Molang expressions, UI namespaces, animations, assets and unrelated behavior.
4. For stricter schemas, validate every affected instance, not just the first representative file. Use exact JSON paths in findings.
5. Keep stable and beta dependencies explicit. Never silently replace a stable dependency with beta or vice versa.
6. Do not add experimental toggles unless the feature's target-version evidence requires them and the user accepts the tradeoff.
7. If evidence is incomplete, keep the implementation conservative and mark the exact uncertainty. Do not fabricate compatibility.

## Validation

- Parse all changed JSON with duplicate-key detection where practical; reject non-finite numbers.
- Check manifest UUID uniqueness and BP/RP dependency closure.
- Check feature-specific schema/contract rules and exact target-version documentation.
- Compare before/after inventory and identifiers. Report unexpected removals or changes.
- Run unit/static tests available in the package. Record exact commands and counts.
- Mark import, rendering, gameplay, multiplayer, and Script API runtime checks `NOT RUN` unless performed in the actual target game/server.

## Output

Provide the exact target build; compatibility matrix; source URLs and exact samples; changed paths; migration reasoning; static test evidence; beta/experimental caveats; runtime status; and remaining blockers. Use confidence labels `CONFIRMED`, `STATICALLY VERIFIED`, `RUNTIME TESTED`, `INFERRED`, and `NEEDS VERIFICATION` accurately.
