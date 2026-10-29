# Minecraft Bedrock Engineer roadmap: 0.9.1–0.9.3

The project should keep its safety and evidence-based audit as the core, add complete cross-resource creation slices, and integrate Minecraft Creator Tools (MCT) only as an optional generator instead of duplicating the entire modelling pipeline.

## 0.9.1 — reliability and source integrity

1. Recover sample lookup from a source checkout: use the full local index when supplied; otherwise build a small index from committed curated text examples and expose reduced coverage in tool output.
2. Make checks honest and reproducible: test missing-index fallback, sample hashes, result limits and version consistency; distinguish missing optional data from a corrupt index.
3. Synchronize release metadata: VERSION, root/compatibility manifests, CI, README and changelog; inspect the actual GitHub Actions result.

Acceptance: full-index and curated-fallback modes are clearly distinguished. No runtime support is claimed without Minecraft tests.

## 0.9.2 — implemented: coordinated entity authoring

Implemented in `server/mcp_server.py` as `create_addon_entity`: one operation produces the BP entity definition, RP client-entity, geometry JSON and render controller. It checks scaffold linkage/version, keeps the generated identifiers consistent, refuses collisions and unsafe paths, validates a supplied PNG, rolls back partial writes, and reports missing texture files rather than fabricating assets. Dedicated integration/security tests are included. CI status should be checked on the exact release commit; runtime behavior is still NOT RUN.

## 0.9.3 — implemented: hybrid MCT orchestration

1. `creator_tools_status` discovers locally installed tools; `creator_tools_catalog` lists the actual MCT gallery identifiers and types. Neither installs dependencies or runs `npx`.
2. `validate_with_mct` invokes the installed CLI on a temporary copy. `create_entity_with_mct` requires a specific `entityType` gallery ID, runs in staging, rejects modifications/removals to existing BP/RP files, audits a before/after bundle with `diff_packs` logic, and merges only new files when no new HIGH/BLOCKER issue or severity escalation is present.
3. MCT remains optional. The CLI may access its gallery/cache even with `--offline`; the integration does not claim network isolation, and it does not automatically install MCT or deploy to Minecraft.

Acceptance status: implementation and mocked unit coverage are committed. Actual local MCT CLI execution, gallery availability and Minecraft runtime remain `NOT RUN`.

## Safeguards

- Preserve existing files, IDs, mechanics and assets unless the user explicitly approves destructive changes.
- Do not execute arbitrary pack scripts or invoke a shell for generator integration.
- Never download, install or execute external tools automatically without an explicit request and a verified command contract.
- Treat Mojang samples as reference material; respect the relevant Minecraft EULA and do not redistribute vanilla assets automatically.
- Report compile checks, unit tests, static checks and in-game tests separately. Use `NOT RUN` for runtime tests not actually performed.
