---
name: mcp-tools
description: Use when Minecraft Bedrock Engineer local MCP tools are available to scaffold a BP/RP project, create starter items/blocks/recipes, or run structured read-only pack audits and reference queries.
---

Workflow priority: for a genuinely new add-on, use `create_addon_project` first and verify its output; never target an existing directory. For an unfamiliar archive or path anomalies, call `inspect_archive` first. Use `audit_pack` for general static checks; `compare_baseline` for full before/after reports; `diff_packs` for concise regressions; `get_resource_graph` for cross-resource references; and `validate_manifest`, `audit_geometry`, or `audit_animation` for focused checks. Cite paths/evidence, distinguish confirmed findings from heuristics, disclose coverage gaps, and mark game/runtime behavior `NOT RUN` unless actually tested.

# Minecraft Bedrock Engineer MCP tools

The bundled MCP server is a local stdio process. It exposes fourteen tools: four explicitly write-capable project/content creation tools and ten read-only analysis/reference tools. All have closed JSON schemas. The release version is read from package-root `VERSION`; analyzer/server and both plugin manifests are expected to use that same version.

## Project creation tools

- `create_addon_project`: creates a new directory directly under the configured workspace root. It writes a minimal `behavior_packs/<name>_BP` and `resource_packs/<name>_RP`, unique UUIDs, format-version-2 manifests, a BP dependency pointing to the RP header UUID, common content directories, `README.md`, and `PROJECT_STATE.md`. The default development target is supplied by the caller (normally Bedrock 1.26.50).
- `create_addon_item`: writes one custom item into a project made by `create_addon_project`, including BP item JSON, RP atlas mapping and localization. Conservatively merges valid shared resources and refuses collisions/malformed state. Does not generate a PNG.
- `create_addon_block`: writes a starter custom block definition and merges a texture key into a valid RP terrain atlas. Does not generate a PNG.
- `create_addon_recipe`: writes one shaped or shapeless crafting-table recipe; custom identifiers must resolve to item/block definitions in the project BP.
- All four creation tools refuse unsafe destinations and are limited to a validated project under the configured workspace root.
- The scaffold creates structure only; the item, block and recipe tools generate limited static content slices, not runtime-tested features. They do not create entity graphs, image textures, custom geometry, animations, UI or script code.
- Treat creation as a write operation and report its actual returned path and files. Do not infer that Minecraft can load it until validation/import has been performed.

## Read-only analysis and reference tools

- `audit_pack`: full static analyzer report for an archive.
- `compare_baseline`: full comparison report for candidate and baseline.
- `diff_packs`: bounded summary of file, finding, severity and resource-reference changes.
- `get_resource_graph`: static resource-reference graph by domain.
- `validate_manifest`: manifest UUID/dependency checks.
- `audit_geometry`: geometry, bones, cubes and UV checks.
- `audit_animation`: animation/controller checks.
- `inspect_archive`: archive metadata/path checks without extracting payloads.

## Content authoring after scaffold

Use the built-in `create_addon_item`, `create_addon_block`, and `create_addon_recipe` tools for their supported starter templates. For entities, custom geometry, textures, animations, UI, or script features, prefer supported Mojang Creator Tools capabilities when actually available. If using an approved local CLI, verify its installed version and help before create/add/validate/render/export workflows. Do not install, download, deploy, or overwrite content silently. Be explicit when a requested authoring feature exceeds the available tools.

## Evidence and safety

The static analyzer does not execute pack scripts, launch Minecraft or prove runtime behavior. For existing projects, inspect before editing and preserve user functionality. Never automatically delete or rewrite resources from an audit finding. For real-world quality claims, use `audit-benchmark` with independently reviewed licensed cases; synthetic tests are not real-pack accuracy metrics.

The MCP server is a local stdio process, not a hosted remote service. It is available only in hosts that launch local stdio MCP plugins and have access to the configured workspace. On Windows, the `python3` command may need to be configured to the installed Python executable.


## Mojang sample search and read (0.8.6)

The bundled `mojang-samples-index.json.gz` is an index of path, size, SHA-256 where available, resource category and a bounded list of literal identifiers from the user-provided `bedrock-samples` archive. It identifies the source archive by SHA-256 and is labelled 1.26.50.4. Use `search_mojang_samples` with a query such as `minecraft:apple`, `geometry goat`, `recipe emerald`, or a filename. Results are scored and capped at 20. If `bundled_reference` is present, `read_mojang_sample` can return that curated example without an external archive. For other indexed text files, put the original ZIP inside the configured workspace and supply its `archive_path`. The ZIP is checked against workspace and size/path constraints; no extraction occurs. Returned content is capped at 12,000 characters. A source hash mismatch is surfaced rather than silently treated as a verified match.

The index is not a full schema validator and does not imply runtime compatibility. The full 169 MB source ZIP is not packaged. Do not bundle vanilla assets into generated add-ons just because they appear in the index; respect Mojang's license and the Minecraft EULA.


## Item authoring 0.8.7

Use `create_addon_item` after a clean scaffold. It creates a namespaced BP item JSON, an RP `textures/item_texture.json` mapping, and an `en_US.lang` display-name key. Existing atlas/lang files are refused rather than rewritten; an optional existing PNG is signature-checked and mapped, but no PNG is generated. Item rendering remains `NOT RUN` until a valid texture is supplied and Minecraft is tested.


## Item authoring 0.8.8

`create_addon_item` can now conservatively merge a new texture-atlas key into a valid existing `item_texture.json` and append a new `en_US.lang` entry while retaining unrelated entries and comments. Malformed JSON, malformed localization lines, duplicate keys, an existing key/slug collision, unsafe paths, or non-regular shared files are rejected before writing any item definition. Generated outputs are staged and installed through same-directory atomic replacement; rollback is attempted if an installation step fails. Texture image generation is not included: a valid PNG at the expected path is still required for a correctly rendered in-game icon.


## Block authoring 0.8.9

`create_addon_block` creates a starter custom block JSON and adds its texture key to RP `textures/terrain_texture.json`. Existing valid `texture_data` entries and unrelated atlas metadata are preserved; malformed JSON and duplicate texture keys are rejected before the BP definition is written. A texture PNG is not synthesized; supply it at `resource_packs/<project>_RP/textures/blocks/<block_slug>.png` for rendering. Static output does not establish in-game compatibility.


## Crafting recipe authoring 0.9.0

`create_addon_recipe` writes one shaped or shapeless crafting-table recipe into the existing scaffold. For shaped recipes, supply `pattern` and `key_mapping`; each row must be 1–3 characters, rows must have equal width, and mapping keys must exactly match non-space pattern symbols. For shapeless recipes, supply 1–9 ingredient identifiers. Custom result and ingredient IDs must be defined by an item/block JSON in the same BP; `minecraft:` IDs are treated as vanilla references. The generator checks BP/RP linkage/version and refuses recipe-file collisions. It does not create recipe ingredients or textures, and cannot prove recipe unlock/engine behavior. Game tests remain `NOT RUN`.
