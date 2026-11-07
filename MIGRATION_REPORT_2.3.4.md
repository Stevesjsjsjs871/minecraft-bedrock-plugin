# Migration report — 2.3.4

## Scope

The 2.3.4 candidate consolidates seven domain groups into canonical Skill entry points while retaining specialist procedures, implementation contracts, local utilities, tests and approval gates.

## Inventory

- 59 Skills across 14 domains.
- 8 workflow profiles.
- 64 Python registry entries with SHA-256 values checked against packaged files.
- 295 activation scenarios designed; all remain NOT RUN on the target Plugin Host.
- 12 default prompts and plugin identity preserved.

## Consolidation groups

Geometry & UV; Project Continuity; Baseline Regression; Creator Tools; Add-on Authoring; Reference Texture Transfer; Release Engineering.

## Boundaries

This migration is Skills-only. It adds no MCP service, server, remote execution backend or new runtime. Target Plugin Host activation, packaged-script integration, connected Creator Tools and Minecraft import/render/gameplay/multiplayer/performance are NOT VERIFIED / NOT RUN.

This report describes the candidate package migration, not a completed live publication.
