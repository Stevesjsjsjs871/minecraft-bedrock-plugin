---
name: ui-resource-audit
description: Use when auditing Bedrock RP UI screens, imports, control graphs, bindings, button mappings, localization, textures and cross-file UI dependencies.
---

# UI Resource Audit

## Inputs and scope

Read `ui-resource-engineering` and `resource-reference-graph` first. Confirm target Bedrock build, RP root, full UI-related directory layout and baseline. Include `ui/`, `ui_defs/`, custom UI roots, `.lang`, referenced PNGs and manifest/UI declarations actually present in the pack. Preserve exact path case.

## Audit workflow

1. Inventory every relevant UI file and record paths, byte sizes, duplicate case-insensitive paths and read/parse status.
2. Parse strict JSON first. If the source uses comments/region markers or JSONC-like constructs, do not rewrite it during audit; report the parser used and mark unsupported forms `NOT CHECKED` or `REVIEW`.
3. Index supported literal fields: namespace, controls, `extends`, `ui_defs`, bindings, button mappings, property bags, modifications, `control_name`, localization keys and texture references.
4. Build source file + JSON Pointer → reference kind → raw value → candidates → resolution status. Keep `resolved`, `missing`, `ambiguous`, `external/dynamic` and `not checked` distinct.
5. Follow imports only where the exact format/path convention is known. Trace localization keys into every applicable locale; distinguish same-file duplicates from intentional cross-locale overrides.
6. Inspect Subpack-specific variants and compare UI deltas with baseline. Flag removed controls/imports and changed IDs; do not propose deletion automatically.
7. Use `skills/automated-validation/scripts/bedrock_audit.py` only when the project/package files and a real Python executor are available. Its UI graph coverage is **partial and heuristic**; it does not implement the full engine UI schema, binding engine, layout semantics or Molang evaluation. Confirm current CLI arguments with `--help` before running.
8. Run Creator Tools validation only if an actual tool/CLI is exposed and authorized. Record exact tool, version, arguments and output separately from this plugin's static checks.

## Output

Return UI inventory and directories covered; parser/coverage notes; literal import/control/texture/localization counts; missing/ambiguous/dynamic references with exact pointers; changed files and baseline delta; commands and exit codes; and runtime status. UI rendering, navigation, controller mapping, scale/resolution and focus behavior are `NOT RUN` without target-game testing.

## Safety

Do not delete a UI definition, localization key, texture or control because static analysis cannot resolve it. Preserve original inputs; stage edits and inspect the final diff. Treat dynamic/Molang references and undocumented engine lookup as uncertain rather than definite defects.
