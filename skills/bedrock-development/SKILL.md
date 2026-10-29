---
name: bedrock-development
description: Use when designing, implementing, extending, or debugging Minecraft Bedrock add-ons, behavior packs, resource packs, items, blocks, entities, recipes, scripts, UI, textures, or packaging.
---

# Bedrock Development Workflow

## Goal
Deliver the highest-confidence implementation the current tools and evidence allow, starting from the user's actual project and protecting existing functionality.

## Default assumptions
- Target Minecraft Bedrock Edition 1.26.50 unless the user states otherwise.
- Use JavaScript ESM for new `@minecraft/server` code.
- Keep Minecraft version, manifest format, Script API module versions, and third-party pack versions distinct.
- Treat compatibility with a particular game version as unverified until supported by relevant documentation/source evidence or runtime tests.

## Workflow
1. **Resolve scope**: identify target project, requested behavior, deliverable, target game version, and constraints from the conversation and files already available. Never ask for details already supplied.
2. **Inspect reality**: inspect available archives/files, package roots, manifests, identifiers, script imports, resource references, and relevant dependent files. Do not infer full project structure from a filename or README alone.
3. **Establish baseline**: note input version, relevant file hashes or counts where practical, existing features, and known test results. If multiple candidates exist, compare them.
4. **Research when material**: verify undocumented, niche, or version-sensitive APIs with official Creator documentation and relevant Mojang samples. Use community references as secondary evidence and explain conflicts. Sources: https://learn.microsoft.com/en-us/minecraft/creator/ ; https://github.com/Mojang/bedrock-samples/releases ; https://wiki.bedrock.dev/ .
5. **Plan minimally**: identify files and dependencies that truly need changes, expected behavior, likely regressions, and test strategy.
6. **Implement**: make direct file changes when tools permit. Prefer small patches over rewrites. Preserve IDs, UUIDs, existing mechanics, recipes, textures, models, animations, localization, and unrelated files unless a requested change requires otherwise.
7. **Validate**: run relevant checks on changed resources and the final archive. Fix safe issues introduced by the patch and rerun checks.
8. **Compare**: compare the candidate against baseline; inspect unexpected additions, removals, or changes. Never silently delete unknown resources.
9. **Package**: create a usable `.mcaddon`/`.mcpack` or project files when the environment allows. Confirm the resulting file exists and is structurally sound.
10. **Report**: explain changes, files touched, checks and actual results, unverified runtime behavior, risks, and the next useful test.

## Change safety
Do not rewrite a project from scratch, remove mechanics or recipes, regenerate IDs, replace original assets with placeholders, or delete files of uncertain purpose without the user's explicit approval. Do not ask permission for ordinary, reversible, in-scope fixes that preserve behavior. Ask before destructive or scope-expanding decisions.

## JavaScript and Script API
Use ESM, clear module boundaries where helpful, input/state checks, robust error handling, and safe lifecycle handling. Confirm API availability for target version before relying on it. Check event availability, async constraints, entity/player disconnects, dimension changes, repeated callbacks, concurrent interactions, multiplayer synchronization, and performance. Keep manifest dependencies aligned with actual APIs used; do not set API dependency versions equal to the add-on's semantic version unless that is specifically correct.

## Cross-resource consistency
When relevant, verify manifest IDs and dependencies, resource identifiers, geometry identifiers, texture paths, animation names, animation/controller references, bone names, render controllers, material names, recipes and results, loot references, localization keys, and Creative catalog registration. Syntax success alone is not proof that a resource works in game.

## User-specific project continuity
- Minecraft Bedrock Addon Studio: known baseline discussed as 0.4.1; inspect actual latest files before editing. Desired directions include BP/RP analysis, manifests, whole-folder UI understanding, version-indexed Mojang sources/docs/examples, audits/tests, specialized modes, and image-generation improvement. Use Action & Stuff 1.12 examples when relevant. Do not return to Spatial GUI. Do not publish a version without explicit approval.
- Kaleidoscope Cookery: preserve existing mechanics and data; carefully inspect recipes, scripts, manifests, Script API dependencies, localization and guidebook data. Absence from one station JSON location alone is not evidence that a recipe is safe to remove.
- CoolMod Player Interactions: when relevant, consider Bedrock 1.26.50 + Action & Stuff 1.12 compatibility. Preserve the source pack's animation graph and visual assets; don't force camera changes. Treat it as a compatibility patch when it depends on Action & Stuff. Static tests do not replace two-client runtime tests.
Treat these as separate projects; don't apply one project's files or constraints to another without a reason.

## Response
For complex tasks use: A) concise analysis, B) implementation/files changed, C) actual checks and results, D) unverified risks/runtime limitations, E) artifact link if created, F) next step. For simple questions, be concise. Answer in Russian unless the user switches language; preserve API/file names in their original spelling.
