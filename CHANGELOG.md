# Plugin package changelog

## Unreleased — Entity geometry and animation-controller authoring
- Adds dedicated stdio MCP servers for advanced entity geometry authoring and animation-controller creation/validation.
- Adds `create_addon_entity_with_geometry` instead of reusing the existing `create_addon_entity` name; the original core tool and its input contract remain available.
- Adds `create_animation_controller` and read-only `validate_animation_controller`, including safe client-entity binding and no-overwrite behavior.
- Prefers ordered transition arrays, preserving Bedrock's transition priority; the legacy object-map input remains accepted for backward compatibility.
- Adds MCP registry checks for all five stdio servers, unique tool names, retained Creator Tools bridge tools and unchanged default prompts.
- Static authoring only. Geometry UV coverage is classic box UV; textures and animation clips are not fabricated; Molang is not executed; Minecraft runtime remains NOT RUN.

## 1.0.14 — Full PNG stream validation and bounded texture audit
- Adds shared `server/png_validation.py` to validate PNG chunks/CRCs, legal IHDR/PLTE/tRNS rules, consecutive IDAT chunks, bounded zlib decompression, exact scanline sizes/filter bytes and Adam7 passes.
- Upgrades `audit_texture_links` from header/chunk checks to full decoded scanline validation, catching files with valid chunk CRCs but broken or inconsistent compressed image data.
- Caches repeated PNG validation and applies per-audit limits for atlas entries, unique PNG files and aggregate bytes; reports `analysis_complete` and scan metrics so limited coverage is explicit.
- Adds 18 new unit/integration cases around PNG stream corruption, color formats/interlace, scan budgets and cache reuse. Auditor remains read-only; runtime validation remains NOT RUN.


## 1.0.13 — Read-only BP/RP texture-link audit
- Adds `audit_texture_links`, scanning BP block/item JSON through the matching RP terrain/item atlas to referenced PNG files.
- Supports block `minecraft:material_instances` references and item `minecraft:icon` string/object variants.
- Reports missing keys/files, malformed or duplicate-key JSON, invalid atlas paths, corrupt PNG chunks, unsafe symlinks and unused atlas entries with structured severity/path evidence.
- Adds 16 regression tests. The auditor is read-only, bounded, workspace-confined and does not claim runtime verification.

## 1.0.12 — PNG validation and atlas write safety
- Validates the decompressed PNG image stream, legal IHDR metadata, critical chunk rules/order, consecutive IDAT chunks, bounded scanline sizes and filter methods, including Adam7 passes.
- Validates generated PNGs before the MCP tool reports success.
- Adds exclusive per-atlas locks across read/modify/write, refuses active/stale lock files instead of racing or deleting them, and retains atomic JSON replacement.
- Rejects duplicate JSON object keys in existing atlas files to prevent ambiguous parse-and-rewrite data loss.
- Adds regression tests for broken IDAT data, invalid filters, decompression expansion, indexed and Adam7 PNG support, duplicate JSON keys and lock cleanup.
- Static validation only; Minecraft import/rendering remains NOT RUN.

## 1.0.11 — Safe texture-atlas registration
- Adds the `register_texture_atlas` MCP tool for block and item Resource Pack textures.
- Preserves existing atlas metadata and unrelated entries; creates a minimal atlas only when absent and refuses conflicting identifiers.
- Validates existing PNG signature, chunk boundaries and CRCs, IHDR dimensions, workspace containment, symlinks, malformed atlas JSON, oversized inputs and concurrent atlas changes.
- Adds regression tests for block/item atlas writes, idempotent repeats, conflict safety, corruption, traversal and symlink rejection.
- Does not edit BP/RP item or block definitions and does not claim in-game rendering verification.

## 1.0.10 — Dedicated procedural texture MCP tool
- Adds an independent stdio MCP server, `server/texture_generator_mcp.py`, exposing `generate_texture` while leaving the original server and dispatch untouched.
- Generates bounded RGBA PNGs inside an existing project's RP `textures/` directory; validates canonical paths and dimensions, rejects symlinks and existing destinations, and returns structured metadata plus SHA-256.
- Adds an integration/JSON-RPC regression suite for schema closure, project/path safety, no-overwrite, defaults, output metadata and error handling.
- The tool uses deterministic procedural styles, not AI image synthesis or UV-aware painting. Minecraft import/render tests remain NOT RUN.
