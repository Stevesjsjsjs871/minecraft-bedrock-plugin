> **ARCHIVAL SNAPSHOT — superseded by package 2.1.0 (2026-11-07).** The 34 historical `server/` files described here have been removed from the shipped package after dependency review. This document is retained only to preserve the prior-state audit trail; it is not a current inventory.

# Legacy Server Dependency & Provenance Audit — 2.0.2 candidate

**Baseline:** `plugin (4).zip`  
**SHA-256:** `52031c94f3917d5e0c38e3bcd130527d49d303158f851bc8d9ceec5291c7bff5`  
**Audit date:** 2026-11-07

## Summary

- Implementation modules: **17**
- Legacy test modules: **17**
- Transport/protocol adapters: **16**
- Pure-logic candidates requiring review: **1**
- Mixed/dependent modules: **0**
- All inventoried legacy modules remain `INERT_HISTORICAL`; no deletion is authorized by this audit.
- Analysis is static; no legacy module was imported or executed.

## Module inventory

| Source path | Classification | Local server dependencies | Test companion | Deletion |
|---|---|---|---|---|
| `server/animated_entity_bundle_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | server.animation_clip_mcp, server.animation_controller_mcp, server.animation_pipeline_audit_mcp, server.entity_authoring_mcp | `server/tests/test_animated_entity_bundle_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/animation_clip_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | — | `server/tests/test_animation_clip_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/animation_controller_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | — | `server/tests/test_animation_controller_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/animation_pipeline_audit_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | — | `server/tests/test_animation_pipeline_audit_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/entity_authoring_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | — | `server/tests/test_entity_authoring_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/geometry_uv_audit_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | server.png_validation | `server/tests/test_geometry_uv_audit_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/geometry_uv_template_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | — | `server/tests/test_geometry_uv_template_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/mcp_server.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | — | `server/tests/test_mcp_server.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/png_validation.py` | `PURE_LOGIC_CANDIDATE_REVIEW_REQUIRED` | — | `server/tests/test_png_validation.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/reference_mapping_review_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | server.geometry_uv_template_mcp, server.reference_texture_transfer_mcp, server.texture_painting_mcp, server.uv_mapping_assistant_mcp | `server/tests/test_reference_mapping_review_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/reference_texture_transfer_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | server.geometry_uv_template_mcp, server.png_validation, server.texture_painting_mcp | `server/tests/test_reference_texture_transfer_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/texture_generator_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | — | `server/tests/test_texture_generator_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/texture_link_audit_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | server.png_validation | `server/tests/test_texture_link_audit_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/texture_painting_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | server.geometry_uv_template_mcp, server.png_validation | `server/tests/test_texture_painting_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/uv_mapping_assistant_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | server.geometry_uv_template_mcp, server.reference_texture_transfer_mcp, server.texture_painting_mcp | `server/tests/test_uv_mapping_assistant_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/uv_texture_retarget_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | server.reference_texture_transfer_mcp, server.texture_painting_mcp, server.uv_mapping_assistant_mcp, server.visual_reference_analyzer_mcp | `server/tests/test_uv_texture_retarget_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |
| `server/visual_reference_analyzer_mcp.py` | `TRANSPORT_OR_PROTOCOL_ADAPTER` | server.geometry_uv_template_mcp, server.texture_painting_mcp | `server/tests/test_visual_reference_analyzer_mcp.py` | `NOT_AUTHORIZED_NOT_REQUESTED` |

## Existing migration evidence

- `server/png_validation.py` is the only pure-logic candidate under this static classification. `skills/visual-resource-pipeline/scripts/png_engine.py` is the standalone canonical counterpart. This maintenance step hardened the standalone validator with exact IHDR-derived decompression bounds, chunk-order/type checks, image dimension/pixel limits and symlink-safe file reads. Its independent functional tests pass; exact semantic equivalence with the retired source has **not** been claimed, and the historical module remains inert.
- `server/reference_texture_transfer_mcp.py` has an independent standalone counterpart at `skills/uv-texture-retargeting/scripts/reference_transfer.py`, documented in the historical migration report. This is not proof that every old wrapper behavior has been ported.
- The other legacy modules are protocol/MCP-named adapters or contain mixed domain and protocol behavior. Their internal imports form dependency clusters; direct deletion or mechanical renaming is unsafe.
- The static analyzer records import declarations and dynamic import literals. Dynamic behavior, runtime import resolution, and filesystem assumptions still require manual source review.

## Dependency clusters observed

- `geometry_uv_audit_mcp.py` and `texture_link_audit_mcp.py` depend on `png_validation.py`.
- `reference_mapping_review_mcp.py` depends on UV template, reference transfer, texture painting and UV mapping modules.
- `reference_texture_transfer_mcp.py` depends on UV template, texture painting and PNG validation.
- `texture_painting_mcp.py` depends on UV template and PNG validation.
- `uv_mapping_assistant_mcp.py` depends on UV template, reference transfer and texture painting.
- `uv_texture_retarget_mcp.py` depends on reference transfer, texture painting, UV mapping and visual reference analysis.
- `visual_reference_analyzer_mcp.py` depends on UV template and texture painting.
- `animated_entity_bundle_mcp.py` dynamically imports entity authoring, animation clip, animation controller and animation pipeline audit modules.
- `mcp_server.py` coordinates legacy handlers and references root archive safety utilities.

## Decision

Do not delete any legacy source or test file in this step. Keep the `server/` tree inert, use the new analyzer to refresh hashes and dependency evidence, and require a separate reviewed deletion authorization after all reusable behavior has an independent Skill utility and focused tests. The strict package checker is intentionally expected to fail while this footprint remains.

## Artifacts

- `SCRIPT_EXECUTION_REGISTRY.csv` — six-level status for all 85 Python files.
- `TOOL_REGISTRY.md` / `TOOL_REGISTRY.csv` — session-scoped tool evidence.
- `skills/legacy-source-migration/scripts/audit_legacy_server.py` — reproducible static inventory generator.
- `skills/legacy-source-migration/scripts/test_audit_legacy_server.py` — focused tests proving import-free analysis and dependency/reference mapping.


## 2.0.2 hardening continuation — PNG validator

- Improved `skills/visual-resource-pipeline/scripts/png_engine.py` as the active standalone PNG validator; no legacy server module was imported or executed.
- Added bounded IDAT decompression based on the exact IHDR scanline size, maximum chunk count, maximum dimensions/pixels, PNG chunk type/reserved-bit checks, critical-chunk rejection, PLTE/tRNS ordering checks, and regular non-symlink file validation with read-size consistency.
- Added focused synthetic tests for normal RGBA/RGB, ancillary chunks, indexed palette requirements, CRC corruption, truncation, trailing data, dimensions/pixel caps, malformed filters, Adam7 mismatch, unknown critical chunks, symlink rejection and file-path handling.
- Validation: 15/15 focused tests passed under the local Python runtime. This is standalone utility verification only; ChatGPT Skill integration and Minecraft import/rendering remain NOT RUN.
- `server/png_validation.py` remains `INERT_HISTORICAL`; this change does not authorize deletion or assert full legacy semantic parity.


## Script registry refresh — 2026-11-07

- Registry now covers all 85 Python files with SHA-256 parity and the six status levels required by the technical guide. Each row includes purpose, command, inputs, outputs, return-code evidence, test evidence and known limitations.
- 85/85 files are PRESENT and SYNTAX_OK. Dependency status: 84 DEPENDENCIES_OK, 1 NOT_TESTED. Local runtime and functional evidence: 43 RUNTIME_OK / FUNCTIONAL_OK; 42 remain NOT_TESTED. Plugin integration: 51 NOT_TESTED, 34 BLOCKED because those are inert historical server/protocol files excluded by the Skills-only architecture.
- The package checker now enforces registry coverage, allowed status vocabulary and exact file hashes.
