---
name: addon-versioning
description: Use whenever finishing a coherent change set to an existing Minecraft Bedrock add-on, preparing an add-on build or release, or coordinating BP/RP pack titles and manifest versions.
---

# Add-on Versioning (the user's project, not this plugin)

This workflow controls the version of the **Minecraft Bedrock add-on being developed**. It is not the Minecraft Bedrock Engineer Plugin Creator version. Keep those tracks separate.

## Mandatory release-boundary behavior

When you finish a coherent implementation change set and are returning an updated add-on project, pack, or release candidate, version the add-on before delivery unless the user explicitly says not to. Do not wait for the user to remind you. Do not bump for inspections, research-only answers, plans, or intermediate edits that are not being delivered as a new coherent build. If the user asks to continue implementation across several turns, accumulate the work and bump at the completion/delivery boundary for that batch.

Before changing files:

1. Read the current BP and RP `manifest.json` files and the project's release notes/version history. Record the baseline version, UUIDs, module versions, pack dependencies, manifest names and target Minecraft version.
2. Classify the actual completed changes as `major`, `medium`, or `fix` using this skill. Do not classify by changed-file count.
3. Calculate the next add-on version from the existing project version. Do not reset a mature project to `0.x.x`, and do not confuse the add-on version with Minecraft game version, `format_version`, `min_engine_version`, or Script API module versions.
4. Prepare one coordinated update for every pack in the release. BP and RP should use the same new add-on version unless the project explicitly documents independent tracks.

For a conventional project layout, let the helper discover pack manifests when `manifest_paths` is omitted or set to `"auto"`. It accepts one unambiguous pack or one BP/RP pair. If it finds multiple pack variants, it must stop and list the candidate paths; choose only the packs that belong to this release rather than bumping every pack in the workspace.

## Version meanings and increments

Use `MAJOR.MINOR.PATCH`:

- **Major**: substantial new system, major feature set, or significant structural/content expansion: `1.2.3 → 2.0.0`.
- **Medium**: meaningful feature or improvement that does not justify a major release: `1.2.3 → 1.3.0`.
- **Fix**: bug fix, compatibility correction, small balance adjustment, missing asset/reference repair: `1.2.3 → 1.2.4`.

Increment exactly one component according to the chosen category and reset lower components only when incrementing MAJOR or MINOR. This add-on policy uses normal numeric SemVer and does not inherit the separate one-digit component limit used by the Plugin Creator package.

If the repository documents a different established scheme, preserve it and explain the mapping instead of silently migrating.

## Mandatory manifest and visible-title updates

For each explicitly included BP/RP pack manifest, update together:

- `header.version` to the new add-on version, preserving its existing representation (`[major, minor, patch]` or a stable `"major.minor.patch"` string).
- Every existing `modules[].version` to the same pack release version. Do not invent missing fields; report them.
- `header.name` so the version is visible in Minecraft's pack list, using the convention `<existing pack title> vMAJOR.MINOR.PATCH`. If a version suffix already exists, replace it rather than appending a duplicate.
- Every in-project pack dependency `dependencies[].version` whose `uuid` refers to one of the packs being released, so BP → RP links match the RP's new `header.version`.

If `header.name` is a localization key (for example `pack.name` or `cinematicPackName`), **keep the key in the manifest** and update the value for that key in every matching `texts/*.lang` language file. Detection checks actual `.lang` content as well as common key syntax. Do not replace the localization key with raw English text. A `display_names` override is only for a non-localized `header.name`; localized packs may use `localized_display_names` keyed by locale file to set a per-language base title while preserving the localization key. If no translation is found, stop and locate the real translation resource rather than guessing a key or locale.

Preserve `header.uuid`, module UUIDs, pack identifiers, dependencies on built-in API modules (such as `@minecraft/server`), `min_engine_version`, `format_version`, experiments and all unrelated manifest content. Do not bump Script API dependency versions just because the add-on release version changed. A pack version change is not a Minecraft engine requirement change.

When BP/RP current versions differ, stop by default and report the mismatch. Only use separate version tracks when the project explicitly authorizes and documents that choice.

## Deterministic helper

When the bundled script is accessible to a real local executor, create a request based on `references/version-request.example.json` and run a dry preview first:

```bash
python skills/addon-versioning/scripts/addon_versioning.py request.json --workspace <workspace>
```

Review the report. Then apply only after the input paths, version category, visible titles, and pack set are confirmed:

```bash
python skills/addon-versioning/scripts/addon_versioning.py request.json --workspace <workspace> --apply --report version-update-report.json
```

The helper edits only the selected manifests and matching `.lang` title entries within the named project. It can auto-discover the standard `behavior_packs/`, `resource_packs/`, and development-pack roots when the request uses `manifest_paths: "auto"`; multiple candidates are a hard stop, not an invitation to update all of them. It rejects path traversal, symlinks, malformed/duplicate-key JSON, invalid versions, duplicate manifests, and BP/RP version mismatches. It preserves the JSON version representation, localization keys, UUIDs, engine/format versions and script API dependencies. Its verification report checks every selected `header.version`, every existing `modules[].version`, visible title/localization suffixes and selected pack dependency versions. In apply mode it reads the written files back and attempts to restore the originals if post-write verification fails. It defaults to dry-run; never claim it ran unless a real executor returned evidence.

When the user supplied only an installable `.mcaddon`/`.mcpack` archive rather than an extracted project, use the archive wrapper after inspecting the ZIP layout:

```bash
# Preview only; the input archive is never modified.
python skills/addon-versioning/scripts/addon_archive_versioning.py input.mcaddon --change-type fix

# Create a distinct, verified output archive after reviewing the preview.
python skills/addon-versioning/scripts/addon_archive_versioning.py input.mcaddon \
  --change-type fix --output output.mcaddon --apply --report version-update-report.json
```

The archive wrapper extracts into a temporary copy, accepts a single pack or one BP/RP pair, rejects ambiguous multi-variant archives and unsafe ZIP entries, applies the same manifest/localization rules, rebuilds a new archive without overwriting the input, and verifies the final archive's CRCs, manifests, module versions, dependency versions and localized titles. If the project contains more than two manifest files, stop and identify the release packs rather than guessing.

If the package script cannot be executed, perform the same coordinated edits through the actual available file-edit capability and independently validate them. A Skill is not itself a tool or filesystem permission.

## Release notes and acceptance

Record the version transition, classification/reason, affected packs and manifest paths, visible-title changes, dependency changes, compatibility impact, and migration notes in the add-on's changelog/release notes. Reopen every modified manifest and localization file. Validate JSON; confirm BP/RP header versions and visible suffixes; confirm module and pack-dependency versions; confirm UUIDs and API module versions are unchanged; inspect the final archive listing. When a `.mcaddon`/`.mcpack` is returned, inspect the actual packaged manifests and localized titles inside that archive, not only the staging directory. A release handoff is blocked if the version is in the manifest but missing from the visible pack title, or vice versa.

At delivery, state the exact new version and show that it appears both in the pack title and `header.version`. If runtime installation/import/rendering was not tested, state `NOT RUN`.
