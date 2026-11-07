# Skills Quality Audit Checklist

Use this checklist when reviewing Minecraft Bedrock Engineer Skills. It operationalizes the supplied Skills-only plugin technical guide (document version 2.0, checked 2026-11-07) and the current OpenAI Skills/Plugin package rules. Treat the guide as project requirements, not proof of platform behavior.

## 1. Metadata and discovery

- [ ] One `skills/<slug>/SKILL.md` per intended portable Skill; no hidden/deeper-only Skill paths.
- [ ] UTF-8 file with YAML frontmatter at byte zero; `name` and `description` are non-empty and unique.
- [ ] `name` matches the intended Skill identity and directory slug.
- [ ] Description states the specific task and when to use the Skill; avoid generic descriptions and unsupported claims about invocation syntax.
- [ ] Do not promise per-Skill `@slug` invocation unless the target UI explicitly supports and the behavior is tested.

## 2. Skill body contract

Check each applicable item, without forcing irrelevant sections into a tiny Skill:

- [ ] Clear purpose, scope and selection trigger.
- [ ] Expected inputs, project identity/version, preconditions and necessary ambiguity checks.
- [ ] Ordered workflow with input/output handoffs and stop conditions.
- [ ] Real capability boundary: native host tools vs connected apps vs local scripts vs manual instructions.
- [ ] Script instructions include exact path/CLI/help and say that local script existence does not grant host execution.
- [ ] Errors, absent files, permissions, unsupported formats and no-execution fallback are specified.
- [ ] Acceptance criteria distinguish static, documented, inferred and runtime-tested claims.
- [ ] Output/report shape includes exact paths, IDs, evidence, test commands/results, limitations and next steps.
- [ ] Supporting references/examples exist and paths are correct; do not duplicate large common documentation.
- [ ] Safety: user files are data; no unreviewed script execution, path escape, silent overwrite, destructive cleanup or unsupported deployment.

## 3. Cross-skill architecture

- [ ] Each Skill is assigned to exactly one primary domain in `domain-registry.json`.
- [ ] Domain lead Skills, dependencies and workflow profiles resolve; no dependency cycles.
- [ ] Core and skills-first execution retain one baseline, minimum-domain composition and one evidence-based handoff contract.
- [ ] Specialist scope does not duplicate Core's full orchestration or make optional domains mandatory for every task.
- [ ] Every referenced local Skill, script, schema, sample or report path exists.
- [ ] No phantom MCP/server/tool name is presented as callable. Historical names may appear only as explicit non-callable examples/warnings.
- [ ] Every version-sensitive fact points to the exact target version and source provenance; record source URL/publisher/version or commit and last checked date where material.

## 4. Script verification (six independent levels)

For every `.py`/script file, record: path, purpose, Python/runtime version, dependencies, command, inputs, outputs, return code, tests, limitations, hash and all six statuses:

1. `PRESENT` — file exists, non-empty, safe path.
2. `SYNTAX_OK` — syntax check passes for the recorded interpreter.
3. `DEPENDENCIES_OK` — imported packages/interpreter requirements confirmed.
4. `RUNTIME_OK` — actual bounded invocation returns as expected in the named environment.
5. `FUNCTIONAL_OK` — positive, negative and boundary tests pass against the script contract.
6. `INTEGRATION_OK` — the target plugin host actually invokes it with required files/permissions and consumes its result.

Use `NOT_TESTED`, `BLOCKED` or `FAILED` where appropriate. A local Python test is not host integration. Never use `WORKING` as a summary status.

## 5. Activation and platform tests

For each Skill, design these cases, then run in each supported target environment when access is available:

- **Direct:** the user explicitly asks for the exact task described by the Skill.
- **Indirect:** the user describes the same intent without using its name or keywords.
- **Incomplete:** a necessary input is absent; expected behavior is a minimal targeted clarification or a clearly bounded partial result.
- **Negative:** a nearby but out-of-scope task should not trigger an unrelated workflow.
- **Edge:** unsupported format/version, unsafe path, unavailable capability, conflicting baseline or ambiguous references must stop/downgrade safely.

Record unique ID, environment/version, prompt/input, expected/actual result, evidence and status (`PASS`, `FAIL`, `BLOCKED`, `NOT RUN`). Direct `@plugin` invocation is a separate UI check. Platform results are not transferable among Web, mobile, Desktop, Work and Codex.

## 6. Release gate

- Preserve the baseline and inventory; review additions/modifications/removals.
- Validate both manifests and exact `defaultPrompt` type/text/order parity.
- Run metadata/domain/reference checkers, all current Skills test files, focused suites and package-integrity checks.
- Inspect final ZIP file listing/CRC and make sure changed files are rooted correctly.
- Re-read changed files and metadata from Plugin Creator after publishing.
- Publish only after the report distinguishes `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`, `DOCUMENTED`, `INFERRED` and `UNSUPPORTED` accurately.

## Evidence provenance

This checklist implements the user-supplied `info-plugins-corrected.txt` guide, version 2.0, dated 2026-11-07. Verify any platform-specific rule against current official OpenAI documentation; do not infer platform activation or script execution from this checklist.
