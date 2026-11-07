# Entity authoring and pipeline audit utilities

The `entity-authoring-pipeline` Skill includes focused single-entity authoring and complete BP/RP graph workflows. This directory contains its optional dependency-free static graph checker.

Dependency-free static checker for literal BP/RP entity resource links.

```bash
python audit_entity_pipeline.py --bp-root <BP-root> --rp-root <RP-root>
python audit_entity_pipeline.py --bp-root <BP-root> --rp-root <RP-root> --entity-id example:robot --output entity-audit.json
python test_audit_entity_pipeline.py -v
```

Exit codes: `0` for PASS/WARN, `1` for FAIL, `2` for CLI usage errors. The JSON output includes inventory counts, identifier-index counts, status, and exact findings. Warnings require human review and do not alone prove a defect. This utility intentionally does not claim full Bedrock schema validation or game-runtime compatibility.
