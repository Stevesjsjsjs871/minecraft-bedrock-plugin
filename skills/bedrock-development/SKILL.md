---
name: bedrock-development
description: Use when designing, implementing, extending, or debugging Minecraft Bedrock add-ons, behavior packs, resource packs, items, blocks, entities, recipes, scripts, UI, textures, or packaging.
---

# Bedrock Development Workflow

## Goal
Deliver the highest-confidence implementation the available tools and evidence allow. If the user is starting from an idea or empty workspace, build a new project deliberately. If project files already exist, inspect and preserve them rather than replacing them.

## Default assumptions
- Target Minecraft Bedrock Edition 1.26.50 unless the user states otherwise.
- Use JavaScript ESM for new `@minecraft/server` code.
- Keep Minecraft version, manifest format, Script API module versions, and third-party pack versions distinct.
- Treat compatibility with a particular game version as unverified until supported by relevant documentation/source evidence or runtime tests.

## Workflow
1. **Resolve project mode**: distinguish new-from-scratch from existing-project work using available files and the user's intent.
2. **Resolve scope**: identify the goal, target game version, deliverable, content types, external dependencies and acceptance criteria. Never ask for details already supplied.
3. **Bootstrap when new**: call `create_addon_project` only for a genuinely new folder. Verify its linked manifests and UUIDs; don't call it against existing content.
4. **Inspect reality when existing**: inspect available archives/files, package roots, manifests, identifiers, script imports, resource references and relevant dependent files. Do not infer full project structure from a filename or README alone.
5. **Establish baseline**: note existing features, file hashes or counts where practical, current version, and known test results. If multiple candidates exist, compare them.
6. **Research when material**: verify undocumented, niche, or version-sensitive APIs with official Creator documentation and relevant Mojang samples. Use community references as secondary evidence and explain conflicts.
7. **Plan minimally**: identify files and dependencies needed, expected behavior, risks, and test strategy. For new projects, start with the smallest complete playable/visible slice.
8. **Implement**: use authorized file-writing tools or verified Creator Tools capabilities. Prefer small, coherent patches. Preserve existing IDs/resources when extending existing projects. Do not invent API fields or silently substitute placeholder assets.
9. **Validate**: parse JSON, check manifest UUIDs/dependencies and cross-resource references, run relevant MCT/static checks, and inspect generated assets.
10. **Compare and package**: compare to the prior milestone/baseline. Package only with suitable tooling and inspect the final archive.
11. **Report**: explain files touched, checks and actual results, runtime behavior not tested, and next milestone.

## Change safety
For existing projects, do not rewrite from scratch, remove mechanics or recipes, regenerate IDs, replace original assets with placeholders, or delete files of uncertain purpose without explicit approval. For a new project, creating its initial BP/RP structure is expected. In both modes, ask before destructive or scope-expanding decisions.

## Cross-resource consistency
When relevant, verify manifest IDs/dependencies, resource identifiers, geometry, textures, animations/controllers, bone names, render controllers, recipes/results, loot references, localization keys, and Creative catalog registration. Syntax success alone is not proof that a resource works in game.

## User-specific project continuity
- Minecraft Bedrock Addon Studio: known historical baseline 0.4.1; inspect latest actual files before editing. Desired areas include BP/RP, manifests, complete UI-folder understanding, version-indexed Mojang sources/docs/examples, tests/audits, specialist workflows and image generation. Use Action & Stuff 1.12 examples when relevant. Do not return to Spatial GUI. Do not publish a version without explicit approval.
- Kaleidoscope Cookery: preserve mechanics; investigate recipe/guidebook differences against scripts and other recipe systems before changes; don't remove ambiguous recipes.
- CoolMod Player Interactions: Bedrock 1.26.50 + Action & Stuff 1.12 when relevant. Preserve source animation graph/assets; don't force camera changes. Treat as a compatibility patch when it depends on Action & Stuff. Static tests don't replace two-client runtime tests.
Treat these as separate projects; don't mix files or constraints between them without a reason.

## Response
For complex tasks use: A) concise analysis, B) implementation/files changed, C) actual checks/results, D) unverified risks/runtime limitations, E) artifact link if created, F) next step. For simple questions, be concise. Answer in Russian unless the user switches language; preserve API/file names.

## Mojang sample corpus (1.26.50.4)
- Prefer `search_mojang_samples` to find version-labelled examples by path, resource domain and selected literal identifiers. Use `read_mojang_sample` for curated excerpts or for an indexed text file only when the original full ZIP is present inside the configured workspace.
- The GitHub source includes `mojang-samples-index.json.gz`, a metadata-only index of 22,252 entries (paths, categories, sizes, eligible content hashes and selected literal identifiers). It is reproducibly generated from Mojang's official `v1.26.50.4` **full** release asset by `.github/workflows/build-mojang-samples-index.yml`; the workflow pins the asset SHA-256 and size, checks every ZIP member CRC, validates archive/category counts, records the generated index SHA-256/size and runs the package audit before committing.
- The full source ZIP and its binary textures/sounds are **not** bundled. The index can find binary asset paths and metadata, but it does not contain their bytes. To read a non-curated text file, place the original full ZIP in the configured workspace; the MCP server does not download samples at runtime. If the generated index is absent and no digest is pinned, the server reports `index_mode: curated_fallback`; this smaller fallback is not equivalent to the full index. A corrupt present index fails closed rather than silently falling back.
- Samples are references, not mod-ready files. Create custom namespaces/UUIDs, remove vanilla-only internal fields unless documented for custom packs, and verify formats against exact target-version documentation. Do not automatically redistribute vanilla textures, sounds or models.
- The sample release label is `1.26.50.4`; the default game target remains `1.26.50`. Do not infer compatibility between the patch-labelled source archive and every 1.26.50 runtime without version-matched documentation or runtime evidence.


## 0.9.3 — optional MCT CLI orchestration

- Use `creator_tools_status` to discover only already-installed Node.js/npm/MCT commands. Do not auto-install packages or invoke `npx`.
- Use `creator_tools_catalog` to inspect the actual MCT gallery IDs and types. Select an item explicitly marked as `entityType` for `create_entity_with_mct`; shorthand `add entity` is interactive and must not be used for unattended generation.
- `validate_with_mct` runs against a temporary copy and writes reports to a temporary output folder.
- `create_entity_with_mct` runs the MCT add operation in a size-bounded staging copy. It hashes pack files before/after, refuses any modification or removal of existing pack files, creates baseline/candidate archives for our own static diff, and refuses merge for new HIGH/BLOCKER findings or critical severity escalations.
- Only new files inside the expected BP/RP roots can be merged. Output paths are checked, collisions are refused, writes are exclusive, and newly created files/directories are rolled back on failure. The source project is never used as MCT's scratch directory.
- MCT may load its gallery or use networked resources; `--offline`/ `--isolated` are passed, but the official CLI notes that some operations may still access the network. The tool never installs MCT or deploys into Minecraft.
- Local MCT execution is not exercised by CI; tests mock the external executable. Runtime status remains `NOT RUN` until validated with the installed CLI and Minecraft.

## 0.9.2 — coordinated custom entity slice

`create_addon_entity` writes four linked resources into an existing generated BP/RP scaffold: BP `entities/<slug>.json`, RP `entity/<slug>.entity.json`, RP `models/entity/<slug>.geo.json`, and RP `render_controllers/<slug>.render_controllers.json`. It checks BP-to-RP UUID dependency and target version before any write, uses one consistent custom identifier/geometry/controller set, rejects output collisions and unsafe/symlinked paths, validates a supplied PNG signature, and rolls back new outputs on write failure. It deliberately does not create placeholder textures. The basic model/AI template is a starting point only; validate version-specific schemas and test import, rendering and behavior in Minecraft before claiming runtime compatibility.

## 0.8.7 — first content-writing slice

For a new scaffold, `create_addon_item` creates one custom item: BP item JSON, RP item texture atlas mapping, and `en_US.lang` display-name key. It follows the version-labelled Mojang item example without copying vanilla identifiers. The tool stops if the target atlas or language file already exists; it does not merge them yet. No PNG is generated, so rendering is not complete until a real texture with a valid PNG signature is supplied at `resource_packs/<project>_RP/textures/items/<slug>.png`. Runtime status remains `NOT RUN`.
