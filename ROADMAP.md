# Minecraft Bedrock Engineer roadmap: 0.9.1–0.9.3

The project should keep its safety and evidence-based audit as the core, add complete cross-resource creation slices, and integrate Minecraft Creator Tools (MCT) only as an optional generator instead of duplicating the entire modelling pipeline.

## 0.9.1 — reliability and source integrity

1. Recover sample lookup from a source checkout: use the full local index when supplied; otherwise build a small index from committed curated text examples and expose reduced coverage in tool output.
2. Make checks honest and reproducible: test missing-index fallback, sample hashes, result limits and version consistency; distinguish missing optional data from a corrupt index.
3. Synchronize release metadata: VERSION, root/compatibility manifests, CI, README and changelog; inspect the actual GitHub Actions result.

Acceptance: full-index and curated-fallback modes are clearly distinguished. No runtime support is claimed without Minecraft tests.

## 0.9.2 — complete entity authoring slice

1. Plan the entity resource graph before writing: validate identifiers, BP/RP linkage, geometry IDs, animation/controller references, render-controller links and expected texture paths.
2. Add a safe entity authoring tool to generate a minimal custom BP entity plus matching RP client-entity and geometry files from version-labelled Mojang patterns. Do not ship fake PNGs or copy vanilla-only internal fields.
3. Validate the generated slice as one unit: positive/negative tests for cross-references, path confinement, collisions, malformed templates, missing textures and rollback/no-partial-write behavior.

Acceptance: generated cross-references resolve statically, existing files remain untouched, and missing textures are explicit. Geometry/animation runtime behavior remains unverified until tested in Minecraft.

## 0.9.3 — hybrid MCT handoff and evidence

1. Add optional MCT discovery/doctor support: detect local Node/npm/Creator Tools without installing packages or making network calls automatically; report discovered versions and capability gaps.
2. Build an explicit opt-in generation handoff only after the installed MCT CLI and its documented syntax are verified. Invoke without a shell, inside a user-approved workspace/project, with a timeout, bounded output and collision checks.
3. Close the loop with audits and benchmarks: audit generated output, compare against a baseline with diff_packs, and evaluate user-supplied real packs with provenance. Publish precision/recall only from reviewed labelled cases.

Acceptance: MCT remains optional; generation is followed by static validation and baseline comparison; real-pack metrics are never invented.

## Safeguards

- Preserve existing files, IDs, mechanics and assets unless the user explicitly approves destructive changes.
- Do not execute arbitrary pack scripts or invoke a shell for generator integration.
- Never download, install or execute external tools automatically without an explicit request and a verified command contract.
- Treat Mojang samples as reference material; respect the relevant Minecraft EULA and do not redistribute vanilla assets automatically.
- Report compile checks, unit tests, static checks and in-game tests separately. Use NOT RUN for runtime tests not actually performed.
