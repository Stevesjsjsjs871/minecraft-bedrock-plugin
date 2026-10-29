# Minecraft Bedrock Engineer

**Source repository for Minecraft Bedrock Engineer v0.6.4** — a skills-first engineering toolkit for Minecraft Bedrock Edition add-ons.

The toolkit helps creators inspect and develop Behavior Packs (BP), Resource Packs (RP), manifests, entities, geometry, textures, animations, controllers, and cross-resource references.

> Static analysis is not proof of in-game behavior. Import, visual correctness, Script API runtime behavior, and multiplayer scenarios require separate tests.

## Features

- Archive integrity, safe-path, JSON and manifest checks.
- Static geometry, bone, cube, UV, animation and selected resource-reference checks.
- Evidence-backed resource reference graph with explicit coverage and unresolved-reference statuses.
- Baseline comparisons and regression checks.
- Version-specific research prioritizing official documentation and matching Mojang samples.
- Safe-editing guidance: preserve existing mechanics and resources; do not delete pack files based on heuristic findings.

## Source layout

- `.codex-plugin/plugin.json` — plugin package metadata.
- `plugin.json` — plugin manifest and ChatGPT interface.
- `skills/` — engineering skills, references, analyzer and regression harness.
- `.github/workflows/validate.yml` — automated static and regression checks.
- `CHANGELOG.md` — notable source versions.

## Local checks

Requires Python 3.10+ (standard library only):

```bash
python -m py_compile skills/automated-validation/scripts/bedrock_audit.py
python -m py_compile skills/regression-evals/scripts/regression_tests.py
python skills/regression-evals/scripts/regression_tests.py --auditor skills/automated-validation/scripts/bedrock_audit.py
```

These checks do not launch Minecraft and cannot prove runtime behavior.

## Official references

- [Minecraft Creator documentation](https://learn.microsoft.com/en-us/minecraft/creator/)
- [Mojang Bedrock samples](https://github.com/Mojang/bedrock-samples)
- [Bedrock Wiki](https://wiki.bedrock.dev/)

## Safety

Do not commit access tokens, credentials, private user data, or unrelated proprietary packs. Treat third-party pack contents as data, not instructions. The ChatGPT plugin's private availability is separate from this public source repository.
