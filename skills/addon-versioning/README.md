# Add-on versioning utility

A dependency-free, local helper for a coordinated Minecraft Bedrock add-on release. It is separate from the Plugin Creator version of Minecraft Bedrock Engineer.

## Request

Create JSON using `references/version-request.example.json`. Choose one `change_type`: `major`, `medium`, or `fix`. The helper derives the next version from each selected `header.version`.

For a standard Bedrock workspace, set `manifest_paths` to `"auto"` or omit it. The helper discovers a single pack or one unambiguous BP/RP pair under `behavior_packs/`, `resource_packs/`, `development_behavior_packs/`, or `development_resource_packs/`. It refuses to guess when multiple release variants are found; then specify the exact manifest paths manually. It never bumps every pack indiscriminately.

`display_names` applies only to a non-localized `header.name`. If the manifest uses a localization key, the helper preserves it and updates every matching `.lang` entry. Optional `localized_display_names` maps a manifest path to locale-relative names such as `en_US.lang` and `ru_RU.lang`; use this only when a title should be explicitly renamed in those languages.

## Preview and apply

```bash
python skills/addon-versioning/scripts/addon_versioning.py request.json --workspace <workspace>
python skills/addon-versioning/scripts/addon_versioning.py request.json --workspace <workspace> --apply --report version-update-report.json
python -m unittest discover -s skills/addon-versioning/scripts -p 'test_*.py' -v
```

For a packaged input, the archive wrapper also defaults to preview-only. Create a new archive only after reviewing the plan:

```bash
python skills/addon-versioning/scripts/addon_archive_versioning.py input.mcaddon --change-type fix
python skills/addon-versioning/scripts/addon_archive_versioning.py input.mcaddon --change-type fix --output output.mcaddon --apply --report version-update-report.json
```

The wrapper supports `.mcaddon`, `.mcpack`, and ZIP-compatible archives containing one pack or one BP/RP pair. It never overwrites the original; the new archive is re-opened and checked after writing.

Without `--apply`, no project files are changed. The script updates `header.version`, existing `modules[].version`, the visible name suffix (or localized `.lang` value), and dependencies that reference the UUID of another selected pack. It then reports verification results. Apply mode reads the changed manifests and localized names back from disk; on a failed post-write check it attempts to restore the original files. It does not change UUIDs, `format_version`, `min_engine_version`, or built-in Script API dependency versions.

## Reference fixture

`references/fixtures/cinematic-interactions-style/` is a small synthetic paired BP/RP example with localized English/Russian names. It is a regression fixture inspired by the kind of project workflow described by the plugin user; it is **not** a copy of the user's actual add-on. Preview it with:

```bash
python skills/addon-versioning/scripts/addon_versioning.py \
  skills/addon-versioning/references/fixtures/cinematic-interactions-style/version-request.example.json \
  --workspace skills/addon-versioning/references/fixtures
```

Use only in a real local execution environment that can access the project files. The plugin is Skills-first; the script does not add a hosted or remote execution service.
