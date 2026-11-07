# Validation Report — Minecraft Bedrock Engineer 2.3.2

## Candidate summary
- Base: 2.3.1 extracted candidate; this is a distinct 2.3.2 candidate.
- Classification: medium documentation/workflow improvement.
- Plugin identity: `minecraft-bedrock-engineer` preserved in both manifests.
- Version markers: `VERSION`, `plugin.json`, `.codex-plugin/plugin.json`, README heading all 2.3.2.
- Skills: 71 discovered and 71 registered; 14 domains; 8 workflow profiles.
- Default prompts: all 12 preserved exactly; root/compatibility parity PASS.
- Architecture: Domain-Based Hybrid / Skills-only preserved; no MCP/backend integration added.
- Python utilities: no Python source changed; six-level registry remains valid for all 64 registered Python files.

## Implemented improvements
1. Core now routes all code/resource authoring and refactoring through the shared `references/code-quality-standard.md` contract.
2. Seven specialist authoring Skills now point to that shared standard without duplicating its content.
3. `bedrock-development` adds an exact-version Script API authoring checklist for compatibility evidence, state/lifecycle ownership, execution model, failure behavior, test coverage and runtime evidence.

## Local validation evidence
Environment: CPython 3.13.5, Linux x86_64.

| Check | Result |
|---|---:|
| `python -m compileall -q skills` | PASS |
| Domain architecture validator | 28/28 PASS |
| Core architecture test suite | 183/183 PASS |
| Full packaged Python test inventory | 32/32 test files; 548/548 cases PASS |
| Strict Skills-only package integrity | 20/20 PASS, 0 warnings |
| Domain workflow profile listing | PASS; 8 profiles listed |
| Plugin manifest JSON parsing and version parity | PASS |
| Default prompt parity | PASS; exact strings/order preserved |
| Script execution registry | PASS; 64 Python files covered, hashes verified |

## Not tested / limitations
- Plugin Creator save/update and installed Plugin Host activation: NOT RUN.
- Automatic Skill routing/activation in ChatGPT clients: NOT RUN; designed prompts are not activation evidence.
- Minecraft import, rendering, gameplay, multiplayer, Blockbench, Creator Tools and Script API runtime: NOT RUN.
- Formatter/linter/type checker: NOT RUN; no compatible repo-wide style tool/config was introduced.

## Scope and preservation
No bundled Python implementation, Minecraft add-on, manifest UUID, resource identifier, Script API dependency, Skill path, domain registry membership or runtime behavior was changed. Existing 2.3.1 candidate and live Plugin Creator 2.1.11 remain untouched. This archive is an unpublished candidate, not a live release.
