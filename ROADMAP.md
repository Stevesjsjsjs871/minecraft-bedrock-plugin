# Minecraft Bedrock Engineer roadmap: 0.9.1–0.9.3

The project should keep its safety and evidence-based audit as the core, add complete cross-resource creation slices, and integrate Minecraft Creator Tools (MCT) only as an optional generator instead of duplicating the entire modelling pipeline.

## 0.9.1 — reliability and source integrity

1. Recover sample lookup from a source checkout: use the full local index when supplied; otherwise build a small index from committed curated text examples and expose reduced coverage in tool output.
2. Make checks honest and reproducible: test missing-index fallback, sample hashes, result limits and version consistency; distinguish missing optional data from a corrupt index.
3. Synchronize release metadata: VERSION, root/compatibility manifests, CI, README and changelog; inspect the actual GitHub Actions result.

Acceptance: full-index and curated-fallback modes are clearly distinguished. No runtime support is claimed without Minecraft tests.

## 0.9.2 — implemented: coordinated entity authoring

Implemented in `server/mcp_server.py` as `create_addon_entity`: one operation produces the BP entity definition, RP client-entity, geometry JSON and render controller. It checks scaffold linkage/version, keeps the generated identifiers consistent, refuses collisions and unsafe paths, validates a supplied PNG, rolls back partial writes, and reports missing texture files rather than fabricating assets. Dedicated integration/security tests are included. CI status should be checked on the exact release commit; runtime behavior is still NOT RUN.

## 0.9.3 — next: optional MCT handoff and evidence

1. Add an MCT `doctor` capability that discovers local Node/npm/Creator Tools versions without installing packages or making network calls automatically.
2. Add an explicit opt-in, allowlisted MCT CLI handoff only after verifying its documented syntax. Run without a shell, inside a user-approved workspace, with a timeout, bounded output, and collision/path controls.
3. Automatically audit generated output, compare it with a baseline using `diff_packs`, and evaluate user-supplied real add-ons with provenance. Publish precision/recall only from reviewed labelled cases.

Acceptance: MCT remains optional; generation is always followed by our static validation and baseline comparison; real-pack metrics are never invented.

## Safeguards

- Preserve existing files, IDs, mechanics and assets unless the user explicitly approves destructive changes.
- Do not execute arbitrary pack scripts or invoke a shell for generator integration.
- Never download, install or execute external tools automatically without an explicit request and a verified command contract.
- Treat Mojang samples as reference material; respect the relevant Minecraft EULA and do not redistribute vanilla assets automatically.
- Report compile checks, unit tests, static checks and in-game tests separately. Use NOT RUN for runtime tests not actually performed.
