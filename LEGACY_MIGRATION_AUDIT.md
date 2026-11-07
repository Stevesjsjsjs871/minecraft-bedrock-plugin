> **ARCHIVAL SNAPSHOT — superseded by package 2.1.0 (2026-11-07).** The 34 historical `server/` files described here have been removed from the shipped package after dependency review. This document is retained only to preserve the prior-state audit trail; it is not a current inventory.

# Legacy source migration audit — package snapshot supplied for 1.7.3 work

## Scope and invariants

This is a static inventory and migration note for the verified user-supplied ZIP snapshot (`plugin (3).zip`) and the Plugin Creator source of release 1.7.3. The uploaded archive contains 201 ZIP entries; `ZipFile.testzip()` returned `None`. Its `VERSION` and root/compatibility manifests all identify 1.7.3. Live Plugin Creator metadata also identified 1.7.3 as current at release ID `pluginrel_6ae5b32ac1908191b50fe43cebd18c57` on 2026-10-31.

The active plugin architecture remains Skills-and-instructions-only. No MCP service, client, registry, transport, endpoint, deployment or plugin-owned backend is to be created, configured, invoked or reintroduced. This audit describes package source and migration status, not a claim that all historical server code has already been ported.

## Package-level findings

- ZIP: 201 entries; `ZipFile.testzip()` returned `None` (archive CRC/decompression check passed).
- Both manifests contain the same 12 default prompts in the same order. The two manifests and `VERSION` identify version 1.7.3.
- The snapshot includes 59 Skills (all skill frontmatter has unique names and non-empty descriptions in the package checker).
- The full Mojang Samples index gzip/JSON is present and the package checker verifies 22,252 indexed entries against metadata.
- No `.mcp.json`, `mcp.json`, or manifest `mcpServers` declaration was found in the supplied snapshot.
- Legacy protocol-adapter sources under `server/` remain in the snapshot. Names and docstrings refer to MCP, but their presence alone does not make them active plugin capabilities. They are excluded from the active Skills-only release workflow.
- Empty placeholder directories under `skills/mcp-*`, `assets`, and `cloudflare` were present in the archive extraction and were removed from the candidate working tree because they contained no files.
- Generated `__pycache__` / `.pyc` artifacts were removed from the candidate working tree.


## 1.8.0 candidate migration update

- The domain algorithm from `server/reference_texture_transfer_mcp.py` has a new independent implementation at `skills/uv-texture-retargeting/scripts/reference_transfer.py`. The new utility does not import anything from `server/`, `*_mcp.py`, or the legacy protocol layer.
- The implementation provides direct local request-file execution, explicit source-crop mapping, bone/cube/face selectors, nearest/bilinear sampling, transforms, alpha-aware blending, optional base texture, strict PNG parsing/encoding, UV overlap/operation guards, bounded input sizes, exclusive output writes and SHA-256 reporting.
- The legacy `server/reference_texture_transfer_mcp.py` is retained as inert historical input, not an active tool. Its imports into other old server modules remain part of the dependency graph; deleting it and other `server/` files without a full dependency-cluster migration would be unsafe.
- The new standalone script has an independent synthetic test suite and is added to the Skills-only package-integrity release gate.
- The new utility does not attempt semantic face recognition, 3D projection, client-entity registration, Minecraft runtime rendering or Blockbench verification. Those remain outside its scope.

## Source classification

| Paths | Classification | Dependency notes | Candidate handling |
|---|---|---|---|
| `server/mcp_server.py` | Protocol/server adapter and orchestration | Imports shared archive safety and dispatches protocol handlers; not a domain-only utility | Retained as inert historical source; not wired into Skills |
| `server/*_mcp.py` | Mixed domain logic and protocol adapters | Several files import each other directly; removing prefixes or deleting files would break dependencies and risks losing reusable algorithms | Retained pending per-module extraction, import graph, CLI contract and independent tests |
| `server/png_validation.py` | Reusable domain validator | Similar/canonical PNG validation has already been moved to `skills/visual-resource-pipeline/scripts/png_engine.py`; parity should be verified before retiring old copy | Historical input only; canonical Skills workflow uses the standalone PNG utility |
| `server/tests/*_mcp.py` | Legacy protocol/handler tests and algorithm tests | Many tests assert handshakes, registry listing or protocol behavior; others exercise geometry/texture behavior in imported modules | Not part of current release gate; preserve until domain tests are ported or replaced |
| `archive_safety.py` | Reusable archive-safety helper | Referenced by the old server adapter; standalone reference-pack intake has its own bounded audit implementation | Retained pending comparison and direct test parity |
| `skills/package-integrity/scripts/check_package_integrity.py` | Obsolete release checker | Validates retired server/registry configuration and is contradictory to Skills-only architecture | Converted to a compatibility shim to call `check_skills_package.py` |
| `skills/package-integrity/scripts/test_check_package_integrity.py` | Obsolete checker tests | Construct old server/registry fixtures and would misrepresent release acceptance | Converted to a shim that invokes `test_check_skills_package.py` |
| `skills/geometry-uv-engine/scripts/test_png_engine.py` | Broken test forwarding wrapper | Corrects an invalid relative parent calculation in this wrapper | Repaired to call the canonical PNG test suite |
| `cloudflare/` | Empty deployment placeholder directories | No files present in the supplied snapshot | Removed empty dirs only; no active deployment code was found |
| `skills/mcp-contract-testing/`, `skills/mcp-tool-registry-integrity/`, `skills/mcp-tools/` | Empty placeholder directories | No `SKILL.md` or other files present in the archive | Removed empty dirs only |

## Import and dependency map (static)

- `server/mcp_server.py` imports `archive_safety` and coordinates multiple handlers.
- `server/geometry_uv_audit_mcp.py` imports `png_validation`.
- `server/texture_link_audit_mcp.py` imports `png_validation`.
- `server/reference_mapping_review_mcp.py` imports UV template, texture painter, reference transfer and UV mapping modules.
- `server/reference_texture_transfer_mcp.py` imports UV template, texture painter and PNG validation.
- `server/texture_painting_mcp.py` imports UV template and PNG validation.
- `server/uv_mapping_assistant_mcp.py` imports UV template, reference transfer and texture painting.
- `server/uv_texture_retarget_mcp.py` imports texture painting, visual analysis, mapping assistant and reference transfer.
- `server/visual_reference_analyzer_mcp.py` imports UV template and texture painting.
- `server/animated_entity_bundle_mcp.py` dynamically imports entity authoring, animation clip, animation controller and pipeline audit modules.

This confirms that `server/` is not a flat set of independently removable files. Domain behavior must be separated from protocol message handling before source modules are retired.

## Candidate test policy

The active release gate is the Skills-only package checker and specialist standalone script tests. Protocol/registry handshake tests under `server/tests/` are not accepted as evidence for the Skills-only architecture. The currently implemented standalone geometry, UV template, PNG validation, texture generation, reference archive audit and version governance tests are reported separately.

## Remaining migration work

1. For each legacy module, split pure domain functions from JSON-RPC/stdio handler functions.
2. Reconcile each pure function with current Skills CLI implementations and identify duplicated or missing behavior.
3. Add equivalence tests over synthetic fixtures and safe read-only real fixtures where licensed.
4. Add a standalone CLI/API only where the capability is useful and can be safely bounded; don't preserve every old command just because it existed.
5. Once an algorithm is migrated and import/reference scans plus tests prove no active dependencies, decide whether the inert source/test files should be removed in a separately reviewed cleanup.

No claim is made that all legacy algorithms have been migrated. No Minecraft runtime or Blockbench behavior is proven by this audit.
