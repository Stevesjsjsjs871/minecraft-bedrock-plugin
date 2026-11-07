# Tool and Capability Registry — MBE 2.3.4 candidate

**Candidate:** 2.3.4, local and unpublished. **Live Plugin Creator snapshot:** 2.1.11, USER / PRIVATE (last recorded metadata evidence: 2026-11-07; release `pluginrel_6aef522dcae48191bd5d00fe0d8d1593`). A Skill is an instruction set, not a callable tool.

| Capability | Environment | Status | Evidence | Boundary |
|---|---|---|---|---|
| Local filesystem and Python | Current development container used for candidate validation | VERIFIED | Exact candidate archive extracted; 32/32 test files and 548/548 cases passed; package and architecture checks passed. | Does not establish installed Plugin Host access or execution. |
| Skills test runner | Local development container | VERIFIED | 32/32 test files, 548/548 cases PASS. | Executes local test code only. |
| Package integrity checker | Local development container | VERIFIED | 20/20 PASS, zero warnings. | Static package checks only. |
| Domain architecture validator | Local development container | VERIFIED | 28/28 PASS; 14 domains, 59 Skills, 8 workflow profiles. | Static registry/contract validation. |
| Script registry | Candidate package | VERIFIED | 64 Python entries; paths and SHA-256 values match packaged files. | Registry presence/hash does not prove target-host runtime. |
| Activation scenario design | Candidate package | DESIGNED / NOT RUN | 295 scenarios, five per Skill. | No controlled activation trace from installed MBE UI. |
| Plugin Host automatic Skill activation | Installed target Plugin Host | NOT VERIFIED | No target-host trace supplied. | Do not claim activation based on local validation. |
| Plugin Host bundled Python execution | Installed target Plugin Host | NOT VERIFIED | No packaged-script invocation trace supplied. | Local Python execution is not host integration. |
| Creator Tools / Blockbench integration | Target Creator Tools environment | NOT RUN | No connected integration run in this validation. | Skill guidance does not imply connection or CLI authorization. |
| Minecraft import/render/gameplay/multiplayer/performance | Minecraft client/device | NOT RUN | No game session used. | Runtime claims remain unverified. |
| Live Plugin Creator publication | Live Plugin Creator | NOT PERFORMED | Candidate was not published. | Requires separate explicit approval. |

## Routing rule

Inspect the actual current tool inventory before every operation. Use only capabilities exposed and authorized in that session. If a target environment is absent, mark the operation `BLOCKED`, `NOT VERIFIED` or `NOT RUN`; do not infer execution from Skill instructions or local test results.
