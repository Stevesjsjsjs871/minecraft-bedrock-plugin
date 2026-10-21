# Bedrock archive audit plan

This plan defines a cautious, reproducible static-audit workflow for `.mcpack`, `.mcaddon`, and ZIP archives. It is a test plan, not a claim that every check is already implemented in the assistant.

## Safety and handling

- Treat every uploaded archive and every embedded file as untrusted input.
- Inspect archive metadata and read members without extracting them to arbitrary filesystem paths.
- Set practical limits for archive size, expanded size, member count, nesting depth, and per-file size before production use.
- Do not execute JavaScript or other scripts found inside an add-on during static analysis.
- Do not copy third-party assets, source, or textures into this repository. Record only minimal diagnostic metadata needed to reproduce a finding.
- Redact secrets, tokens, local paths, usernames, and private world/server information from reports.
- Never claim an add-on works in-game based on static checks alone.

## Recommended audit stages

1. **Archive integrity:** open the ZIP central directory, test CRCs, report duplicate member names, absolute paths, traversal components (`..`), suspicious backslashes, and expansion-size anomalies.
2. **Inventory:** count files by extension and top-level folder; identify pack icons, manifests, scripts, textures, models, animations, sounds, and subpacks.
3. **Manifest parsing:** parse `manifest.json` as UTF-8 with BOM support. Report `format_version`, header UUID/version, module UUID/version/type, dependencies, and module entry points. Do not assume one `format_version` applies to every manifest generation.
4. **JSON syntax:** first use strict JSON. If it fails, diagnose BOM, comments, or trailing commas as separate compatibility modes. Never silently rewrite a file. Comments and trailing commas are only acceptable where the target Bedrock file format permits them.
5. **Identity and dependency checks:** detect duplicate header/module UUIDs within the archive; verify internal BP/RP UUID dependency links when applicable; distinguish dependencies that may be external from confirmed missing dependencies.
6. **Reference checks:** check texture, geometry, animation, controller, render-controller, particle, sound, and script references with format-aware path normalization. Avoid false positives for identifiers supplied by Minecraft itself or by subpacks.
7. **Script checks:** identify script entry points and declared `@minecraft/*` dependencies; check API compatibility against the user's target game version. Do not execute uploaded scripts.
8. **Subpack checks:** enumerate subpack names, compare referenced paths, and report conflicts or missing files without assuming all variants should contain identical files.
9. **Report:** classify findings as `error`, `warning`, `info`, or `needs-review`; include file path, line/JSON pointer when possible, evidence, confidence, and a safe suggested next step.
10. **Manual validation:** import into the target Bedrock version, enable required experiments if applicable, inspect content/logs, test single-player and multiplayer if relevant, and record exact platform/version.

## Minimum regression matrix

| Case | Expected result |
|---|---|
| Valid strict JSON | Pass with no syntax warning |
| UTF-8 BOM before JSON | Parse with BOM support; report encoding detail only if useful |
| `//` or `/* */` inside a string | Preserve string content; do not strip it as a comment |
| Comments in a format that permits them | Diagnose correctly; avoid claiming strict JSON validity |
| Comments in a strict-JSON-only file | Flag as invalid for that format, even if a permissive parser can recover |
| Trailing comma | Report separately; never silently patch source |
| Duplicate UUID across modules or packs | Warn with all locations; explain scope and possible consequences |
| Dependency UUID not bundled in archive | Mark for review, not automatically as broken |
| Missing resource path | Report only after format-aware normalization and subpack checks |
| Large archive | Complete within configured limits or stop safely with a clear limit message |
| ZIP traversal/absolute member path | Flag; do not extract the member |
| Corrupt ZIP member/CRC | Fail archive integrity stage clearly |
| Minified script | Do not mistake line count for complexity or correctness |
| Unknown/new Bedrock format | Mark schema validation as unsupported/uncertain instead of inventing a verdict |

## Reporting rules

- Separate **confirmed syntax/structure errors** from **heuristics** and **manual-review candidates**.
- Include counts and a bounded sample of findings; avoid dumping thousands of repetitive warnings.
- State the exact checks performed and not performed.
- Preserve originals. Any proposed fix should be a separate patch with a diff and rollback path.
- Static validation is not equivalent to Minecraft runtime validation.

## Current local helper

[`../tools/audit_bedrock_archive.py`](../tools/audit_bedrock_archive.py) is a read-only standard-library triage helper. It checks ZIP integrity, inventories file types, parses manifests, detects duplicate UUIDs, and diagnoses JSON parsing with recovery passes. Recovery passes are diagnostic only. It is not a Bedrock schema validator and should be extended with format-specific reference checks and tests before being treated as production-grade.
