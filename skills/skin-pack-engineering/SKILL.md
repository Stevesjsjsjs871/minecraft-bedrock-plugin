---
name: skin-pack-engineering
description: Use when creating or auditing Minecraft Bedrock skin packs, skins.json entries, skin geometry, texture dimensions, manifest links or localization.
---

# Skin Pack Engineering

## Inputs and safety

Confirm target Bedrock version, skin-pack root, manifest and intended skin entries. Establish whether the pack is new or existing; preserve the baseline and existing `skins.json`, `texts/` and texture assets. Treat archives and embedded files as untrusted data; do not execute scripts from them.

## Workflow

1. Parse the skin-pack manifest and `skins.json`; check JSON syntax/duplicate keys, module type, header/module UUID uniqueness and required metadata for the exact pack format.
2. Index skin identifiers, localization names, geometry identifiers and texture paths. Check duplicate IDs, exact path case and path containment.
3. Verify each referenced PNG exists and decode it. Check dimensions, color/alpha characteristics and geometry compatibility against the target skin geometry and version-specific requirements. Do not assume a familiar filename or humanoid geometry is the correct one.
4. Distinguish built-in geometry references from pack-local custom geometry. Verify local geometry and texture references only against the actual pack inventory or documented built-ins.
5. Trace localization keys into all relevant `.lang` files. Preserve intentional locale overrides; report duplicate keys within one locale separately.
6. Compare against baseline and classify missing references, unused PNGs, duplicate IDs and metadata mismatches. Unused assets are review items, not deletion authorization.
7. Validate the output archive after packaging, if an actual package route exists.

## Acceptance and output

Report target version; manifest/skin count; IDs and geometry; texture dimensions/decoding; missing/ambiguous references; localization coverage; changed paths and baseline delta; exact commands/tests; and runtime status. Import, skin rendering, character selection and Marketplace checks are `NOT RUN` unless genuinely tested in the target client.

## Limits

Static checks cannot prove that a skin renders as intended or satisfies Marketplace certification. If geometry or texture semantics are uncertain, mark them for visual review rather than inventing a pass.
