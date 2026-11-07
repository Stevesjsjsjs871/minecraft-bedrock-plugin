# Minecraft Bedrock Engineer 1.7.0 — Reference corpus and resource-domain audits

This update extends the Skills-first plugin using the reference domains represented by the user's supplied Bedrock packs. It adds a safe, read-only archive intake workflow and focused guidance for UI, Subpacks, PBR/Vibrant Visuals/fog, Script API performance, Skin Packs and cooking add-ons.

## Added
- `reference-pack-corpus`: archive trust, provenance, intake, comparison and evidence standards.
- `reference_pack_audit.py`: bounded ZIP inspection, path checks, SHA-256, manifest summary, duplicate JSON key rejection and conservative comment-aware parsing.
- Focused specialist skills: `ui-resource-audit`, `subpack-engineering`, `visuals-fog-pbr-audit`, `script-api-performance-audit`, `skin-pack-engineering`, `cooking-addon-engineering`.
- Reference inventory describing the supplied source domains without embedding third-party code/assets.

## Boundaries
- Uploaded third-party scripts are never executed by the corpus auditor.
- Comment-aware parsing does not change original files and is not an endorsement of arbitrary JSON5 syntax.
- Static manifest/reference checks do not prove Minecraft import, rendering, gameplay or FPS gains.
- Previously reported archive findings must be reproduced against the original archive before being treated as fresh release evidence.

## Validation
Run `python skills/reference-pack-corpus/scripts/test_reference_pack_audit.py -v` and `python skills/reference-pack-corpus/scripts/reference_pack_audit.py --help` from the package root. Run the standard Skills-only package checker and regression suites. Minecraft runtime checks are not included in this release.
