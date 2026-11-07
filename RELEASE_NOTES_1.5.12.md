# Minecraft Bedrock Engineer 1.5.12 — Skills-first workflow alignment

This maintenance release aligns the Geometry & UV, UV-template authoring and visual-resource instructions with the standalone utilities actually included in the package. The docs now point to the concrete commands, canonical PNG validator and focused regression suites, and clearly distinguish static checks from Minecraft/Blockbench runtime verification.

No MCP integration or remote execution backend is introduced. Existing dormant legacy sources and all unrelated packaged assets are preserved. The current Mojang Samples index is retained unchanged by the overlay update; it is a binary asset and is not included in this partial source patch.

Verified locally: geometry analyzer and UV renderer tests (18/18), PNG validator tests (10/10), package-integrity checker tests (12/12), Python compilation, plus a synthetic end-to-end UV guide generation and PNG validation smoke test. Full-package release-gate execution, Minecraft runtime, Blockbench interoperability and in-game rendering remain unverified.
