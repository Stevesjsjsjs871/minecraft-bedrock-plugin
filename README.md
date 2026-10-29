# Minecraft Bedrock Engineer — 0.6.7

Private skills-first engineering toolkit for Minecraft Bedrock add-ons. Default target: 1.26.50 unless a task specifies another version.

## 0.6.7: MCP hardening and consistency checks

Aligns the MCP server version with the package release, caps archives at 50,000 entries in addition to the existing byte limits, and reports archive entry count separately from regular-file count so directory entries do not skew the listing truncation flag. Unit tests now check version/prompt parity, compact initialize instructions, structured tool errors and the member-count guard.

## 0.6.5: structured local MCP tools

Adds a read-only stdio MCP server exposing seven tools: `audit_pack`, `compare_baseline`, `get_resource_graph`, `validate_manifest`, `audit_geometry`, `audit_animation`, and `inspect_archive`. Tool schemas reject unknown fields, constrain the resource-graph domain, validate paths before file access, and advertise read-only/non-destructive annotations. The server wraps the existing static analyzer and returns structured JSON results and errors.

**Deployment boundary:** this package contains a local stdio MCP server, not a hosted remote service. Uploading this package does not deploy the server or make it available to ChatGPT web/mobile by itself. The target host must support and launch local stdio MCP plugins. For a remote ChatGPT integration, the tool implementation must be deployed behind a reachable and appropriately authenticated MCP endpoint and that endpoint must be configured; no fake endpoint is included.

## Existing workflows

- `bedrock-development`: safe BP/RP implementation and regression review.
- `project-audit`: evidence-backed static audits.
- `automated-validation`: archive, manifest, geometry/bone/UV, selected animation/reference checks, resource graph and baseline comparison.
- `regression-evals`: synthetic positive/negative fixtures for the analyzer report contract.
- `model-animation`: geometry, UV, texture, animation/controller and visual-debugging guidance.
- `resource-reference-graph`: definitions/uses and unresolved-reference interpretation.
- `research-versions`: version-specific research from verifiable sources.
- `project-continuity`: verified project state and continuity.
- `build-release`: candidate packaging and release gates.
- `mcp-tools`: MCP tool routing, schemas, safety boundaries and result interpretation.

## Local setup

Python 3.10+; standard library only. The root `mcp.json` launches `server/mcp_server.py` with `python3`. On Windows, use the Python executable supported by the host. The server's working directory defines the allowed archive workspace by default; set `MINECRAFT_BEDROCK_WORKSPACE` to an explicit directory if needed. Only `.mcaddon`, `.mcpack`, `.mcworld`, and `.zip` files inside that directory are accepted. Archives are inspected without extraction; pack scripts are never executed.

## Local checks

```bash
python -m py_compile server/mcp_server.py server/tests/test_mcp_server.py
python -m unittest discover -s server/tests -v
python -m py_compile skills/automated-validation/scripts/bedrock_audit.py
python -m py_compile skills/regression-evals/scripts/regression_tests.py
python skills/regression-evals/scripts/regression_tests.py --auditor skills/automated-validation/scripts/bedrock_audit.py
```

Passing these checks does not launch Minecraft and is not proof of runtime behavior. Resource-graph and UI/localization coverage is partial/heuristic.

## Official references

- [Minecraft Creator documentation](https://learn.microsoft.com/en-us/minecraft/creator/)
- [Mojang Bedrock samples](https://github.com/Mojang/bedrock-samples)
- [Bedrock Wiki](https://wiki.bedrock.dev/)

## Safety and privacy

All bundled MCP tools are read-only. The server does not extract archives, execute pack scripts, alter or delete project files, launch Minecraft, or make network requests. It bounds paths to a configured workspace and returns structured errors on invalid input. It never automatically deletes resources based on heuristic findings. Do not package tokens, credentials, private user data, or proprietary packs. This plugin remains private; the GitHub source repository has separate visibility controls.

