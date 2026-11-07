---
name: skills-only-maintenance
description: Use when maintaining, auditing or releasing Minecraft Bedrock Engineer itself; preserve the approved Domain-Based Hybrid/Skills-only architecture, migrate useful algorithms safely and keep version/release evidence coherent.
---

# Skills-only maintenance

## Architecture invariants
- The canonical architecture is Domain-Based Hybrid with Skills-only integration. `ARCHITECTURE.md` describes its planes and lifecycle; `skills/bedrock-engineer-core/references/domain-registry.json` is authoritative for domain IDs, primary Skill membership, entry Skills, ordering dependencies and workflow profiles.
- Core orchestration owns routing and reconciliation; each domain Skill owns its specialist procedure. Versioned references/schemas/examples form the knowledge plane, bounded scripts are optional local utilities, and tests/evidence form the quality plane.
- Every discovered `skills/<slug>/SKILL.md` must be assigned to exactly one primary domain. Keep existing portable Skill paths stable; group them logically in the registry, not nested directories.
- The active plugin interface is Skills and instructions only. Do not create, configure, launch, invoke or depend on MCP servers, clients, registries, endpoints, transports or plugin-owned backends.
- Skills cannot create tools, grant filesystem access, execute code, access a user's local project or run in the background. A bundled script is executable only when the host provides a real code executor and the package files are mounted.
- Keep specialist Skills, examples, sample corpus and validated standalone utilities. Canonical PNG validation is `skills/visual-resource-pipeline/scripts/png_engine.py`; geometry/UV analysis is `skills/geometry-uv-engine/scripts/geometry_engine.py`; UV guide rasterization is `skills/geometry-uv-engine/scripts/uv_template_engine.py`.
- Do not ship historical server/protocol source trees, MCP configurations, or retired deployment adapters. The 2.1.0 cleanup removed the complete 34-file historical tree after dependency review. User-supplied legacy project files are separate, untrusted inputs and must never be executed during static review.

## Architecture change procedure
1. Read live Plugin Creator metadata, exact current release ID and full source inventory.
2. Read `ARCHITECTURE.md`, the Core Skill, skills-first execution contract and current domain registry.
3. Before adding/removing/renaming a Skill, reconcile the registry against the full `skills/*/SKILL.md` inventory. Check for exactly one primary domain assignment, valid lead Skill and valid domain dependency graph.
4. For changes to schemas or hand-off fields, update the Work Order and Domain Result schemas together with Core/skills-first instructions and their tests.
5. Keep `plan_domain_work.py` deterministic and non-executing: it expands only a caller-selected registry profile, resolves dependency closure, emits a planned Work Order and includes only domain lead Skills by default. Explicit specialist Skills must belong to selected domains. It must not infer intent, inspect projects, invoke Skills or invent host capabilities.
6. Classify domain dependencies and workflow profiles. Keep routing minimal; do not make every domain a mandatory dependency of every task.
6. Port useful historical pure algorithms into focused `skills/<domain>/scripts/` utilities only where their behavior is needed. Keep CLI contracts bounded, safe and independently tested.
7. Run the architecture validator and focused architecture tests, then the canonical Skills-only package checker and every relevant specialist suite.

## Maintenance loop

1. Inspect source identity, current release ID, plugin scope and audience.
2. Use `references/skills-quality-checklist.md` for per-Skill metadata/body/architecture/script/activation review. Maintain an activation matrix separately from static checks; designed prompts are not PASS evidence until tested in the exact target host.
3. Inspect both manifests and exact defaultPrompt parity; build a full inventory and hashes where practical.
4. Audit Skill frontmatter, stale tool instructions, script imports, schemas, test references, generated caches and deployment artifacts.
5. For user-supplied legacy sources, classify modules as reusable algorithm, host adapter, orchestration, test fixture, documentation or generated/deployment artifact; do not copy protocol/server infrastructure into the Skills-only package.
6. Remove empty placeholders and bytecode/cache artifacts; remove deployment remnants only after verifying they have no contents or active references.
7. Run:
   - `python skills/bedrock-engineer-core/scripts/validate_domain_architecture.py .`
   - `python -m unittest discover -s skills/bedrock-engineer-core/scripts -p 'test_*.py' -v`
   - `python skills/bedrock-engineer-core/scripts/plan_domain_work.py --list-profiles`
   - Smoke-test each declared workflow profile and validate emitted Work Orders against the JSON Schema.
   - `python skills/package-integrity/scripts/check_skills_package.py .`
   - `python skills/package-integrity/scripts/test_check_skills_package.py -v`
   - relevant version-governance and specialist test suites.
8. Compile changed Python sources; verify full Mojang index integrity when package files are available.
9. Synchronize README, ARCHITECTURE, CHANGELOG, VERSION, both manifests, version policy, release notes and history. Preserve plugin identity, scope, audience and every default prompt string/order.
10. After Plugin Creator update, re-read changed files, metadata, release ID and full skill inventory. Distinguish saved package state from host/runtime behavior actually tested.

## Release discipline
- Use the exact immediate successor under the package's existing version scheme; inspect attached releases immediately before update.
- Do not bump for every internal edit; publish only a coherent, tested architecture increment.
- A Plugin Creator update being accepted is not proof of Minecraft behavior.
- Historical protocol tests are not Skills-only acceptance tests.
- Minecraft import, rendering, gameplay, multiplayer, Blockbench and Script API runtime are `NOT RUN` unless actually tested.
- Do not sync external repositories or publish a shared release without the relevant authorization.
