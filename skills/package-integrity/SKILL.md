---
name: package-integrity
description: Use before changing, packaging or releasing Minecraft Bedrock Engineer to verify Skills-only manifests, domain registry coverage, script evidence, legacy source boundaries, Work Order/Domain Result contracts and sample-index integrity.
---

# Skills-only Package Integrity Audit

Run the architecture checks and the package checks from the extracted plugin package root:

```bash
python skills/bedrock-engineer-core/scripts/validate_domain_architecture.py .
python skills/bedrock-engineer-core/scripts/plan_domain_work.py --list-profiles
python skills/package-integrity/scripts/check_skills_package.py .
python skills/package-integrity/scripts/check_skills_package.py . --strict-skills-only  # mandatory release gate
python skills/package-integrity/scripts/run_skill_tests.py . --json skill-test-results.json
python -m compileall -q .
```

The architecture validator verifies the Domain-Based Hybrid identity, Skills-only boundary, exact one-domain assignment for every discovered top-level Skill, matching Skill frontmatter, unique domain IDs, valid lead Skills, an acyclic domain dependency graph, valid workflow profiles, real capability-route options, Work Order/Domain Result contract schemas, the operational domain planner and its focused test suite, and the root architecture document. The planner must remain deterministic and must not depend on remote services or execute project code.

`plan_domain_work.py` expands an explicitly selected workflow profile into a dependency-safe domain order and shared Work Order. It includes only lead Skills by default; optional specialist Skills must be explicitly selected and must belong to a selected domain. It does not classify user intent, inspect projects, verify tools or execute domain work. Smoke-test each declared profile and validate an emitted Work Order against `work-order.schema.json` when the extracted package and a local executor are available.

The read-only package checker verifies required files, JSON manifests, identity, semantic-version parity, exact `defaultPrompt` parity, `./skills` paths, absence of MCP configuration declarations and protocol adapters, unique Skill frontmatter, stale tool invocations, retired deployment artifacts, README version/architecture, full Mojang sample-index gzip/JSON count, and required geometry/UV/PNG utilities/tests. Use `--strict-skills-only` as the mandatory release gate; it must pass before a package update.

The historical `check_package_integrity.py` path is only a compatibility shim to `check_skills_package.py`. It does not validate or launch a remote service.

For user-supplied legacy project migration, use the `legacy-source-migration` Skill to inventory files, hashes, manifests, dependencies, conflicts and preservation requirements without executing source code. Use the isolated Skills test runner for the full Skills test set; it launches each test file from its own directory to preserve sibling imports and avoid duplicate module-name collisions. The runner rejects symlinked Skills roots/test files and bounds timeout and test-file count. It executes package test code, so review the source before running it. Run focused tests for changed scripts. Static package checks do not prove Minecraft import, rendering, gameplay, multiplayer, Blockbench interoperability or Script API runtime; report those as `NOT RUN` unless actually tested.
