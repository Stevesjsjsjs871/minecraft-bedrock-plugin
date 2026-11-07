# Validation Report — Minecraft Bedrock Engineer 2.3.0

**Status:** Unpublished release candidate; local package gates PASS; target-host/runtime gates remain NOT VERIFIED / NOT RUN.

## Baseline
- Input: `minecraft-bedrock-engineer-2.2.0-verified-candidate.zip`
- Size: 2,245,834 bytes
- SHA-256: `694a21adc6eb31ab0d22ae764c59d4386cc3e40e10f2695fc00dda4cc3b584eb`
- Baseline copy preserved read-only as `BASELINE_2.2.0.zip`; original archive was not modified.
- Baseline package markers: 2.2.0 in VERSION and both plugin manifests.

## Version and package identity
- Candidate version: 2.3.0 in `VERSION`, `plugin.json`, `.codex-plugin/plugin.json`, README heading, CHANGELOG and release notes.
- Plugin identity preserved; all 12 default prompts preserved exactly.
- Skills-only boundary: PASS; no MCP/server/backend components introduced.
- 71 Skills, 14 domains, eight workflow profiles.
- 64 Python files; `SCRIPT_EXECUTION_REGISTRY.csv` covers 64/64 exact paths and SHA-256 hashes.
- Skill inventory: 71/71; activation matrix: 355 designed scenarios, five per Skill, all `NOT RUN` pending target Plugin Host activation.

## Final local verification
| Gate | Result |
|---|---:|
| Full Skills suite | **32/32 test files; 546/546 cases PASS; 0 failures; 0 timeouts** |
| Package integrity | **20/20 PASS; 0 FAIL; 0 WARN** |
| Architecture | **28/28 PASS; 14 domains; 71/71 Skills; 8 profiles** |
| Workflow profile planner smoke | **8/8 PASS** |
| Script registry | **64/64 paths and hashes** |
| Default prompt parity | **12/12 preserved** |
| Version parity | **2.3.0 / 2.3.0 / 2.3.0** |

Environment: CPython 3.13.5, Linux 6.18.57 x86_64. Full suite was run from a clean copy of the exact candidate source tree. After final ZIP creation and clean re-extraction, package and architecture gates passed again; the full suite rerun against the extracted archive exceeded the outer 300-second tool execution window, so it is not counted as a completed run. The four critical focused suites were rerun from the extracted archive and passed: archive safety 29/29, benchmark builder 10/10, corpus indexer 10/10 and JSONC parser 6/6.

## Security regression results
- Shared archive safety: 29/29 PASS.
- Benchmark builder: 10/10 PASS.
- Reference corpus indexer: 10/10 PASS.
- JSONC parser: 6/6 PASS.
- Explicit ZIP directories accepted; duplicate/case/Unicode aliases, file/directory conflicts, symlinks/special files, malformed UTF-8 names, traversal and excessive compression ratios rejected.
- Hash and member reads use one pinned descriptor; CRC/decompression checks run after metadata/path preflight.

## Reference corpus
- Ten archives; 42,876 ZIP entries (41,301 files + 1,575 directories); 110 manifest records.
- Ten of ten SHA-256 and CRC/decompression checks PASS.
- Benchmark builder successfully inventoried all ten archives.
- Five real archives received read-only static audits; no embedded scripts executed and no original archive was modified.

## Performance observations
- GameTests archive: 0.71 s / 96,272 KB max RSS.
- Microsoft Samples: 0.81 s / 101,776 KB max RSS.
- Mojang Bedrock Samples: 2.51 s / 123,952 KB max RSS.
- Single-run container observations, not statistically validated performance claims.

## Not verified / not run
- Installed Plugin Host automatic Skill activation and bundled Python execution: NOT VERIFIED.
- Windows and Android/Termux: NOT RUN.
- Minecraft import, Content Log, rendering, gameplay, multiplayer and FPS: NOT RUN.
- Blockbench / Creator Tools: NOT RUN.
- Independent real-pack benchmark precision/recall: NOT SCORED (no exhaustive ground-truth labels).
- Git state: unavailable; working tree is not a Git repository.

## Open findings
- Two duplicate-key JSON files in the Furniture source archive; external source finding, not an MBE package defect.
- 26 negative cube-size findings in Create Movement require target-schema/runtime review.
- Cinematic Interactions includes unresolved player-resource references that may be vanilla/external.
- ZIP decompression has bounded sizes/ratio but no internal wall-clock timeout; use a process-level timeout for hostile inputs.

## Release decision
`REVIEW`. Local engineering gates pass, but overall 9.5–10/10 is not justified without target-host activation, cross-domain target execution, portability tests and Minecraft runtime evidence. Live Plugin Creator remains 2.1.11 USER / PRIVATE; no publication or live mutation occurred.
