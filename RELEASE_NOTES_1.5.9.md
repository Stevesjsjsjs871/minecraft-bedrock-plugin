# Minecraft Bedrock Engineer 1.5.9

## Added
- Independent static Geometry & UV analyzer for Bedrock `.geo.json`.
- Classic box UV and per-face cube UV bounds calculations.
- Geometry identifier selection, duplicate-key rejection and finite-number validation.
- Out-of-bounds UV findings and overlap intersection reports.
- Ten dedicated regression tests.

## Scope
The analyzer is static; mesh UV projection, client-entity texture binding, UV template rendering, Blockbench interoperability and Minecraft runtime are not implemented by this CLI. Legacy modules remain preserved pending further migration.
