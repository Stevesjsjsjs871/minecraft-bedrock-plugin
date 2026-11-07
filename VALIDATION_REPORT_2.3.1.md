# Validation Report — Minecraft Bedrock Engineer 2.3.1

**Status:** Unpublished release candidate. Local package gates pass; target-host and Minecraft runtime gates remain NOT VERIFIED / NOT RUN.

## Baseline and identity
- Baseline remains the verified 2.2.0 archive, SHA-256 `694a21adc6eb31ab0d22ae764c59d4386cc3e40e10f2695fc00dda4cc3b584eb`; baseline was not modified.
- 2.3.1 is a patch candidate based on 2.3.0; plugin identity, Skills-only boundary, 71 Skills, 14 domains, eight workflow profiles and all 12 default prompts are preserved.
- VERSION, plugin.json and .codex-plugin/plugin.json agree on 2.3.1.

## Change evidence
- `skills/bedrock-engineer-core/scripts/project_state.py`: inventory file hashing now opens a regular file once, uses `O_NOFOLLOW` where available, hashes through the pinned descriptor, and verifies descriptor/path identity and size/mtime/ctime stability.
- Symlink and path-replacement regression tests added to `test_project_state.py`.
- Registry contract corrected to the actual benchmark-builder limits; all 64 Python file paths and SHA-256 values pass package integrity validation.

## Final local verification
| Gate | Result |
|---|---:|
| Full Skills suite | **32/32 files; 548/548 cases PASS; 0 failures; 0 timeouts** |
| Project State focused suite | **30/30 PASS** |
| Package integrity | **20/20 PASS; 0 FAIL; 0 WARN** |
| Architecture | **28/28 PASS; 14 domains; 71 Skills; 8 profiles** |
| Script registry | **64/64 paths and hashes** |
| Default prompt parity | **12/12 preserved** |
| Version parity | **2.3.1 / 2.3.1 / 2.3.1** |

Environment: CPython 3.13.5, Linux 6.18.57 x86_64. The final 2.3.1 ZIP was cleanly re-extracted to a separate verification directory. The full 32-file / 548-case suite was then rerun from that exact extracted archive and passed with zero failures/timeouts. Package integrity (20/20) and architecture (28/28) were also rerun against the exact extracted archive. These results do not establish Plugin Host execution or Minecraft runtime behavior.

## Not verified / not run
- Installed Plugin Host automatic Skill activation and bundled Python execution: NOT VERIFIED. The 355-case activation matrix remains designed but NOT RUN.
- Windows and Android/Termux: NOT RUN.
- Minecraft import, Content Log, rendering, gameplay, multiplayer and FPS: NOT RUN.
- Blockbench / Creator Tools: NOT RUN.
- Independent real-pack benchmark precision/recall: NOT SCORED.

## Release decision
`REVIEW`. Local engineering gates pass, but 9.5–10/10 is not yet justified without target-host activation, portability and Minecraft runtime evidence. Live Plugin Creator remains 2.1.11 USER / PRIVATE; no publication or live update occurred.
