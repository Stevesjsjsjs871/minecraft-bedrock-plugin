# Minecraft Bedrock Engineer 1.3.0 — GitHub synchronization

This commit synchronizes the public source repository with the 1.3.0 release already published through ChatGPT Plugin Creator.

## Included
- Version metadata and MCP registries updated to 1.3.0.
- Consolidated README and CHANGELOG for the internal 1.2.0 RC1–RC10 development cycle.
- Animation clip authoring, animation pipeline auditing, and animated entity bundle orchestration.
- Geometry UV audit and UV template generation.
- Geometry-aware texture painting and reference texture transfer.
- UV mapping assistant, visual reference analysis, and human-reviewed reference mapping.
- Skills, examples, and local regression tests for the added capabilities.

## Validation evidence
The release report records 221/221 local overlay tests passing, including 28/28 Reference Mapping Review tests, plus static manifest/schema checks, MCP registry parity and stdio smoke tests.

## Known verification limits
The local overlay harness used a test-local bounded PNG validator shim because the full PNG validator is supplied by the existing base package. The historical full base-package suite was not rerun from the overlay checkout. Minecraft import/render/runtime and Blockbench interoperability tests were not run.

The 1.3.0 Plugin Creator release is published separately. This commit synchronizes the repository source and documentation; it does not create a GitHub Release object or tag.
