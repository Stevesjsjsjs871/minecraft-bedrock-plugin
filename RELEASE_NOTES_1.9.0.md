# Minecraft Bedrock Engineer 1.9.0

## Highlights

- Formalizes the Domain-Based Hybrid layout across Core routing, specialist Skills, versioned References, optional local Scripts and regression Testing.
- Replaces vague skill selection with explicit routing for BP/add-on creation, RP/UI, entity/model/geometry, animation, textures/UV, Script API, research, audit/regression and release engineering.
- Strengthens whole-feature implementation guidance so linked BP/RP resources and dependency edges are planned and validated together.
- Clarifies evidence, provenance, third-party asset handling and the boundary between static checks and real Minecraft runtime tests.
- Fixes a PNG compatibility test launcher that could import the local shim instead of the canonical PNG validator when run from the Geometry/UV directory.
- Synchronizes the root manifest, compatibility manifest, VERSION, README, changelog and version-history markers to 1.9.0.

## Preservation and architecture

The existing plugin ID, name, description, USER scope, PRIVATE discoverability, `@Minecraft Bedrock Engineer` identity and the exact 12 default prompts are preserved. All 59 existing specialist Skills and their supporting references/scripts are retained. No MCP service, client, registry, endpoint, transport, or remote execution backend is introduced. Legacy server sources remain inert historical migration inputs pending complete dependency-cluster migration and equivalent testing.

## Validation

The full candidate package was checked using the Skills-only package checker, focused standalone suites, synthetic audit regression fixtures, version-governance tests, and Python compile checks. Exact evidence and caveats are recorded in the engineering report. Minecraft runtime, Blockbench, multiplayer and in-game rendering checks remain `NOT RUN`.
