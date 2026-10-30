# Minecraft Bedrock Engineer 1.4.0 — UV Retarget Pipeline

## Delivered

`retarget_texture_to_entity` turns the multi-tool reference workflow into one guarded MCP operation: image analysis → explicit human-reviewed crop/face assignments → UV planning → PNG transfer → output integrity verification. Existing lower-level tools remain available for expert/manual control.

## Hard approval and safety gates

- The caller must supply each source crop and exact bone/cube/face selector.
- Every assignment must include a semantic label and `approved: true`; the request must include `review_confirmed: true`.
- Analyzer candidates are shape/area heuristics, never semantic recognition.
- Input hashes are checked before/after planning and transfer. UV overlaps, unresolved planning conditions and output collisions stop the operation.
- Output is a new PNG; the existing transfer engine validates and refuses overwrites. The wrapper verifies dimensions and SHA-256.

## Evidence and limitations

- New isolated orchestration/contract suite: **13/13 passed** with mocked existing-module boundaries.
- New server and test files passed Python bytecode compilation.
- Full-package regression, real project end-to-end texture rendering, Minecraft import/runtime and Blockbench interoperability were not run in this isolated environment. Reported runtime status remains **NOT RUN**.
