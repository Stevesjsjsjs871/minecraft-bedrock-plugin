---
name: mcp-tool-registry-integrity
description: Use when auditing the MCP server's actual tool registry, schemas, safety annotations and prompt/tool documentation for consistency before release.
---

# MCP Tool Registry Integrity

## Goal
Make the MCP interface an auditable contract. Documented tools, registered tools, argument schemas and safety annotations must describe the same behavior. This procedure complements `mcp-contract-testing` and does not claim tests ran merely because the steps are documented.

## Registry audit
1. Load the actual MCP server source and locate the authoritative tool registry and dispatch table. Do not assume an old tool count or copy a historical number.
2. Derive a sorted inventory of tool names, required properties, input property names, `additionalProperties`, and safety annotations.
3. For each tool, verify:
   - registry name is unique;
   - a dispatch handler exists and is reachable;
   - every required key is defined in `properties`;
   - schemas are closed unless there is an explicitly justified extension point;
   - descriptions accurately state path scope, write behavior, output limits and runtime limitations;
   - read-only tools are marked read-only and don't mutate files;
   - writer tools have write-capable annotations and reject unsafe destinations/collisions.
4. Inspect the initialize/handshake instructions and skills that describe the server. Replace brittle hard-coded tool counts with wording that instructs the user to inspect the live registry, unless an exact versioned count is deliberately tested.
5. Verify dispatch-level behavior for unknown tools and invalid inputs returns a structured error and doesn't leak filesystem paths or tracebacks unnecessarily.
6. Add or update unit tests for any inconsistency found. Do not weaken a test solely to make the build green; first establish the intended contract.
7. Compare the live tool inventory with the baseline manifest. Record additions/removals/changed schemas as a deliberate API change with compatibility notes.
8. Run compile, protocol and full unit tests using the repository's actual setup when an executor is available. If it is not available, report source-reviewed items separately from executed tests.

## Safety annotation matrix
- Read-only inspection/search/audit: `readOnlyHint: true`, `destructiveHint: false`.
- File/project creation or edit: `readOnlyHint: false`, `destructiveHint: false` when collision-safe and non-destructive, `idempotentHint` only when repeated calls have the documented effect.
- Deletion, overwrite or mutating arbitrary project data requires stronger safeguards and should not be introduced implicitly.
- `openWorldHint` should reflect real network/external side effects; don't copy `false` blindly if an implementation invokes network tools or arbitrary executables.

## Evidence output
Include inventory hash or sorted list, registry/dispatch mismatches, schema/annotation deviations, exact tests actually executed and pass/fail counts, plus API compatibility risks. Distinguish source inspection from runtime protocol verification.
