# Minecraft Bedrock Engineer 1.9.7 — Domain-Based Hybrid architecture

## Architecture implementation

- Defines the canonical five-plane design in `ARCHITECTURE.md`: Core control, specialist domains, versioned knowledge, optional host-backed execution and evidence/quality.
- Adds a machine-readable domain registry with 14 domains and all 62 current Skills. Each Skill has one primary domain; the registry identifies lead Skills, dependency ordering, task workflow profiles and real execution routes.
- Adds `work-order.schema.json` as the shared task envelope and `domain-result.schema.json` as the specialist hand-off format. The contracts keep project identity, target version, baseline, plan, exact file changes and evidence aligned across domains.
- Updates Core and skills-first execution so they classify the request, verify real host capabilities, choose only the required domains, reuse one baseline and reconcile all specialist outputs before completion.
- Updates plugin maintenance, package integrity and release quality instructions to enforce registry/schema validation.
- Adds a standard-library, read-only architecture validator and 20 focused synthetic tests.

## Validation

- Architecture validator unit tests: 20/20 passed.
- Python compile checks: passed for the new validator and its test module.
- Domain registry JSON and both hand-off schemas: parsed successfully; registry contains 14 domains, 62 unique Skill assignments and 8 workflow profiles.
- Plugin Creator publication confirmed: current release `pluginrel_6ae62560f48c81918757072e9d5c988d`; source read-back confirmed the 1.9.7 manifests and preserved 12-prompt parity.
- Full live package-integrity checker: NOT RUN because the local working checkout was a partial overlay rather than a complete extracted package.
- Minecraft import/render/gameplay, Creator Tools and Script API runtime: NOT RUN.
