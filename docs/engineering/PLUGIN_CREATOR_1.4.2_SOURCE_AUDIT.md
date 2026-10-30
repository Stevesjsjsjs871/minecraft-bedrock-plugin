# Plugin Creator 1.4.2 — read-only source audit

**Audit date:** 2026-10-30 13:14 UTC  
**Plugin ID:** `plugins_6ae33ff6e8d8819182f246d8d3d97323`  
**Current Release ID:** `pluginrel_6ae4979a4ad081918bcae25fe4dabad3`  
**Current Plugin Creator version:** `1.4.2`  
**Scope:** read-only; no Plugin Creator files or release metadata were changed.

## Executive result

The current Plugin Creator release is not source-synchronized with the GitHub `feat/cloudflare-workers-mcp` branch or with the release-gate candidate chain. The most important verified issue is metadata drift: both plugin manifests report 1.4.2, while `VERSION`, the README title, and the newest CHANGELOG entry still report 1.4.0.

The package also contains generated Python bytecode, has no `BUILD_PROVENANCE.json`, and uses a remote-only MCP configuration. Its bundled Cloudflare implementation is the older Container-based design, whereas the GitHub feature branch contains a stateless Workers implementation with a smaller remote tool surface. The active remote endpoint could not be tested from this environment, so the deployed runtime catalog remains unverified.

## Inventory evidence

The Plugin Creator file inventory was read in two pages, with the same current Release ID confirmed on both pages.

| Measure | Result |
|---|---:|
| Files | 150 |
| Sum of listed file sizes | 2,901,131 bytes |
| First inventory page | 100 files |
| Second inventory page | 50 files |
| `BUILD_PROVENANCE.json` | Missing |
| `server/__pycache__/uv_texture_retarget_mcp.cpython-313.pyc` | Present, 25,053 bytes |
| `server/tests/__pycache__/test_uv_texture_retarget_mcp.cpython-313.pyc` | Present, 12,250 bytes |
| `cloudflare/deploy-with-secrets.mjs` | Missing |

The two bytecode files total 37,303 bytes. They are generated artifacts and should not be part of a source-built release payload.

## Version and prompt parity

| Source | Reported version |
|---|---|
| Plugin Creator metadata | 1.4.2 |
| `plugin.json` | 1.4.2 |
| `.codex-plugin/plugin.json` | 1.4.2 |
| `VERSION` | 1.4.0 |
| README title | 1.4.0 |
| Newest CHANGELOG heading | 1.4.0 |

Both manifests contain the same 12 `defaultPrompt` entries. The original first three prompts are preserved in their original order and wording. The twelfth prompt asks for `retarget_texture_to_entity`.

The release metadata gate in PR #15 is designed to reject the 1.4.2/1.4.0 mismatch when run against the actual archive or source snapshot.

## MCP and Cloudflare transport findings

The current Plugin Creator `mcp.json` and `.mcp.json` each register one `streamable-http` server pointing at the remote Worker endpoint. They do not register the 16 local Python STDIO servers as active MCP entries.

The bundled Plugin Creator Cloudflare files describe and implement the older Container-based architecture:

- `cloudflare/src/index.ts` imports `@cloudflare/containers` and forwards requests to a Container.
- `wrangler.toml` declares a Container and Durable Object binding.
- `cloudflare/container/app.py` imports 16 Python MCP modules and aggregates their tool definitions.
- The bundled `cloudflare/README.md` describes a Workers Paid + Containers deployment and claims a combined catalog of 32 tools.

By contrast, the GitHub ref `feat/cloudflare-workers-mcp` currently has:

- `VERSION` and manifests at 1.4.0;
- 11 default prompts;
- 16 local STDIO server registrations in both MCP config files;
- a stateless TypeScript Worker whose declared remote catalog contains four tools: `bedrock_generate_manifest`, `bedrock_validate_manifest`, `bedrock_read_plugin_source`, and `bedrock_plugin_capabilities`;
- a deployment helper at `cloudflare/deploy-with-secrets.mjs`.

The feature branch README describes the remote Worker as optional and explicitly states that the full Python toolset remains local. This is a materially different transport/package profile from the current Plugin Creator 1.4.2 package.

These differences may reflect intentional platform-specific packaging, but no explicit machine-readable profile contract currently explains or verifies that distinction. Do not merge the two configurations by guesswork.

## Runtime and archive verification limits

- Full private Plugin Creator archive download: **NOT RUN**. The signed archive URL was returned, but this environment could not resolve the download host (DNS failure).
- Full byte-for-byte archive parity: **NOT RUN**.
- Live Worker `/health`, MCP `initialize`, and `tools/list`: **NOT RUN**. The Worker host also failed DNS resolution from this environment.
- The Plugin Creator source API did provide the complete 150-file inventory and selected UTF-8 file contents; binary payload bytes were not available through that API.

Therefore, the inventory and selected-source findings above are verified, but no claim is made that the live deployed Worker currently serves either the 4-tool or 32-tool catalog.

## GitHub state at audit time

- `main` remains 1.3.0; no merge was performed.
- PR #15 remains open and Draft. Its previously observed CI run #41058878826 completed successfully for commit `92fcb92af9d0d8e7a2c3f4c2610a915bce4dd807`.
- PR #13 and PR #12 remain open and unmerged dependencies.
- PR #14 and PR #11 are closed as superseded.
- No open GitHub Issues were returned.
- Repository searches for TODO and FIXME returned no results.

The successful PR #15 CI run predates this audit document. A new CI run is required after the document commit.

## Recommended next step

Create an explicit, testable packaging-profile contract before any further Plugin Creator update:

1. Define the local STDIO profile and remote Streamable HTTP profile separately.
2. Record which MCP tools are actually exposed by each profile; do not infer remote capability from the presence of Python files in the archive.
3. Make the release gate validate profile-specific configs and ensure every default prompt is compatible with the selected runtime or clearly labelled as a local workflow.
4. Sync version, README, CHANGELOG, manifests, deploy helper and Worker implementation to one selected source snapshot.
5. Generate `BUILD_PROVENANCE.json` from the exact committed tree and exclude generated `.pyc` files.
6. Run an authenticated remote MCP smoke test and a local STDIO registry test before considering the package ready.

No Plugin Creator update or release was made during this audit. The current Release ID must be re-read immediately before any future guarded mutation.
