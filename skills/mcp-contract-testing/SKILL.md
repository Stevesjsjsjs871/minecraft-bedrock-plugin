---
name: mcp-contract-testing
description: Use after editing the Minecraft Bedrock Engineer MCP server, adding/removing tools, changing tool schemas or annotations, changing version metadata, or before a package release.
---

# MCP Contract Testing

## Goal
Verify the public MCP contract matches the actual implementation. A tool must not be described as available unless it is registered and callable. This process checks schemas and routing in addition to Python syntax.

## Test layers

### 1. Version and package consistency
- Parse `plugin.json` and `.codex-plugin/plugin.json`.
- Confirm package name, strict semantic version and preserved default-prompt type/order.
- Confirm both manifests and root `VERSION` agree.
- Load the MCP server and confirm its `SERVER_VERSION` matches `VERSION`.

### 2. Registry and schema contracts
- List the actual registered tools from the server's registry function.
- Assert expected tool names exactly once.
- Confirm every tool schema is an object schema with `additionalProperties: false`.
- Confirm all `required` entries refer to declared properties.
- Check annotations accurately: writers are not read-only; audit/reference tools are read-only and non-destructive.
- Ensure descriptions state input/output limitations and do not promise unsupported behavior.
- Snapshot a deterministic, sorted tool inventory for release-to-release comparison.

### 3. Protocol-level behavior
- Use the project's supported test/client API to perform `initialize`, list tools and call representative tools.
- Validate structured error responses for missing required fields, unknown properties, malformed paths, unsupported suffixes and out-of-workspace paths.
- Test success cases in temporary directories/workspaces only. Never point tests at the user's real add-on by default.
- Check that read-only calls do not modify source files or archive bytes.
- For writer tools, verify expected files are created, collisions fail closed, unrelated files remain unchanged and paths cannot escape the workspace.

### 4. Regression contracts
- Exercise the new feature's positive and negative cases.
- Confirm tool count changes are intentional when a tool is added, and update brittle tests only after verifying the intended new contract.
- Compare output keys and annotations, not only the successful return value.
- Add the new cases to the complete unittest suite and CI.
- Run the whole suite, not just the new test file. Report exact results and all skips.

## Release acceptance
- Python compilation passes for server and tests.
- Full MCP test suite, benchmark evaluator tests and analyzer regression harness pass.
- Version manifest checks pass.
- No accidental tool additions/removals or unsafe annotation/schema changes.
- Minecraft runtime behavior is still `NOT RUN` unless a game test was actually performed.

## Reporting
Provide actual command lines, tool inventory delta, exact pass/fail/skip counts and any missing execution layer. If the host cannot launch local MCP tests, distinguish inspected schemas from executed tests; don't call the contract verified.
