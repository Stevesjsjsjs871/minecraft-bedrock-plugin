# Minecraft Bedrock Engineer 1.5.8

## Geometry & UV migration foundation

- Added the `geometry-uv-engine` specialist skill.
- Defined a concrete static audit procedure for classic box and per-face cube UV formats, explicit output statuses and unsupported-mesh handling.
- Added shared PNG validation CLI to the Geometry & UV engine directory.
- Reworked geometry audit/template authoring instructions to distinguish preserved legacy source from active executable scripts.
- Preserved all legacy wrappers and algorithms; UV parser and template CLI migration remains unfinished.

## Verification

- PNG validator tests: 10/10 PASS.
- Package checker synthetic tests: 10/10 PASS.
- Python compilation: PASS.
- PNG CLI help: PASS.
- Geometry/UV CLI: NOT IMPLEMENTED / NOT RUN.
- Minecraft and Blockbench import/render tests: NOT RUN.
