# Source Migration Policy — Skills-only Package

**Current status:** Active for Minecraft Bedrock Engineer 2.1.0 and later.

## Package boundary

The plugin ships Skills, references, assets, and optional bounded local utilities only. It contains no MCP configuration, server/client transport, protocol adapter, plugin-owned API, or historical server source tree. Do not reintroduce retired protocol infrastructure as a workaround for unavailable local execution.

## User-supplied legacy projects

Existing `.mcaddon`, `.mcpack`, BP/RP folders, scripts, and third-party source archives are untrusted data. Inspect them statically. Never execute their scripts during migration review. Keep the source immutable and use a separate destination or output archive.

## Migration acceptance

1. Record source and destination identities, target game version, baseline hashes, and requested scope.
2. Inventory manifests, assets, scripts, identifiers, imports, dependencies, localization and resource references.
3. Build a dependency closure and identify collisions, ambiguous mappings, incompatible formats and unresolved references.
4. Preserve UUIDs, identifiers, assets, localization and unrelated mechanics unless an explicit change is approved.
5. Apply only through a real host-provided or explicitly authorized file/code route. A Skill is not a file writer or executor.
6. Test successful, malformed, boundary and failure cases for any modified utility.
7. Compare the destination against its known-good baseline and review every removal.
8. Version and package only at a coherent delivery boundary; reopen the final archive and verify its contents.
9. Report static checks separately from Minecraft import, rendering, Content Log, gameplay, multiplayer and performance tests.

## Historical cleanup

The 34-file historical `server/` source and test tree present through 2.0.9 was removed from the package in 2.1.0 after static dependency/provenance review. `LEGACY_SERVER_DEPENDENCY_AUDIT.md` and `LEGACY_MIGRATION_AUDIT.md` are retained as archival evidence of the prior package state only; they do not describe current shipped files or runtime capabilities.
