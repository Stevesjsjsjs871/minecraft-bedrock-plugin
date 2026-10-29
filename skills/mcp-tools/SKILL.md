---
name: mcp-tools
description: Use when the Minecraft Bedrock Engineer local MCP tools are available and a pack needs a direct, structured, read-only audit or reference query.
---

Workflow priority: choose tools by task, not by rote. For an unfamiliar archive or a request focused on archive integrity/path anomalies, call `inspect_archive` first. Use `audit_pack` for a general static audit; `compare_baseline` for before/after regressions; `get_resource_graph` for resource-reference questions; and `validate_manifest`, `audit_geometry`, or `audit_animation` for focused checks. Cite exact paths and evidence, distinguish confirmed findings from heuristics, state coverage gaps, and mark game/runtime behavior `NOT RUN` unless actually tested. Never modify or delete pack contents automatically.

# Minecraft Bedrock Engineer MCP tools

The bundled MCP server is a local stdio process. It exposes eight read-only tools with closed JSON input schemas (`additionalProperties: false`), path and argument validation, structured JSON results/errors, and annotations identifying read-only behavior. The release version is read from package-root `VERSION`; analyzer/server and both plugin manifests are tested against this source.

## Tools

- `audit_pack`: run the complete static analyzer on an archive.
- `compare_baseline`: run the analyzer with a candidate and baseline archive and return the full report including file-level changes.
- `diff_packs`: summarize file, finding, severity and reference regressions in a bounded report without applying a patch.
- `get_resource_graph`: return the resource reference graph, optionally filtered by a fixed domain enum. Filters use actual edge fields: `source_file`, `source_pointer`, `target_domain`, `reference_kind` and `referenced_value`. An explicit `target_domain` is authoritative; string/path heuristics are used only when that field is absent, to prevent cross-domain leakage.
- `validate_manifest`: return manifest/dependency checks and related findings.
- `audit_geometry`: return geometry, bone, cube and UV checks/findings.
- `audit_animation`: return animation/controller checks and related findings.
- `inspect_archive`: list archive metadata and unsafe/duplicate path indicators without extracting files.

## Tool selection

- For creation-from-scratch or content-writing requests, state the boundary honestly: these eight MCP tools are read-only and cannot create packs or edit files. Consult `creator-tools-bridge` for an MCT handoff when a trusted local shell and an already-installed CLI are available; otherwise explain that the CLI must be set up locally with the user's authorization.
- After MCT creates or changes content, use this plugin as the independent audit/regression layer. Preserve a baseline and return a reviewed diff; never auto-apply suggested repairs from audit findings.
- For claims about finding quality, use `audit-benchmark` and reviewed real-pack labels. Synthetic regression tests are not a measurement of real-world precision.

- Do not call all eight tools by default; invoke only those needed.
- `inspect_archive` checks archive metadata and paths but does not read file payloads; it is not a substitute for `audit_pack`.
- For an overall quality review, prefer `audit_pack`; add focused tools only when useful.
- For regressions, compare the candidate to the supplied baseline before recommending changes.
- Findings should include paths/evidence and confidence. Unresolved/dynamic references and heuristics are not confirmed defects.

## Safety and interpretation

The server does not extract archives, execute pack scripts, edit files, delete resources, launch Minecraft, or make network requests. Archive paths must resolve inside the configured workspace (defaults to current working directory); set `MINECRAFT_BEDROCK_WORKSPACE` to an explicit workspace. ZIP-compatible inputs are limited to `.mcaddon`, `.mcpack`, `.mcworld`, and `.zip`.

The MCP wrapper and standalone CLI both call package-root `archive_safety.py` before reading payloads. Shared limits: 256 MiB compressed archive, 50,000 archive entries, 128 MiB per regular file member, and 512 MiB total declared uncompressed regular-file payload. These are resource-safety limits, not Minecraft format limits. `inspect_archive` reports regular-file `member_count` separately from total `entry_count`. The analyzer can report heuristic or unresolved references; such reports are not runtime proof.

The package contains a local stdio server, not a hosted remote MCP endpoint. Uploading this package does not deploy a cloud service or make the local process available on ChatGPT web/mobile by itself. The target host must support and launch local stdio MCP plugins. On Windows, change `python3` to the configured Python executable if needed.

## Report validation

The analyzer report schema is `skills/automated-validation/references/report-schema.json` (JSON Schema Draft 2020-12). Validate a report with `python skills/automated-validation/scripts/validate_report.py report.json`. The helper and regression harness require `jsonschema`. A schema-valid report is structurally consistent, not proof that resources work in game.

## Error handling

Successful analyses return structured report objects containing checks, findings, evidence, coverage and runtime status. Invalid arguments, unavailable files, invalid archives, timeouts and internal errors return structured errors instead of silently returning empty findings. Runtime status remains `NOT RUN` unless actual runtime testing occurred.


## `diff_packs` 0.8.0

Use `diff_packs` when the user asks what changed between two pack versions or which regressions may have been introduced. It runs read-only audits of both archives and returns bounded lists for file additions/removals/modifications, finding deltas, severity changes and reference-graph regressions. Each list reports its full count and whether the displayed sample is truncated. Newly unresolved links and resolution regressions may be heuristic; inspect their confidence, source file and JSON pointer before treating them as defects. `HOLD` means current high-severity findings were detected, while `REVIEW` requires manual review of medium findings, removals, new findings or reference regressions. All runtime checks remain `NOT RUN`; the tool never applies patches or modifies files. Use `compare_baseline` when the full raw analyzer report is required.
