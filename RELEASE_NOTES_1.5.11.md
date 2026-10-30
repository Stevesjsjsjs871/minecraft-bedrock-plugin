# Minecraft Bedrock Engineer 1.5.11

Adds the standalone UV Template Engine for supported Bedrock cube UV layouts. It renders a transparent PNG guide, labels faces with bone/cube/face identifiers, enforces a pixel budget, refuses to overwrite existing output, and reports dimensions and SHA-256. It complements the independent geometry parser and PNG validator.

Not covered: `poly_mesh`/`texture_meshes` projection, renderer face orientation and mirror sampling, client-entity bindings, actual texture-to-canvas verification, Minecraft import/rendering and Blockbench interoperability.
