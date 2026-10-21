# Features and limitations

## Supported workflows

### Add-on design
Plan behavior packs, resource packs, recipes, entities, animations, and scripts.

### Static project review
When project files are accessible in the current ChatGPT session, inspect JSON syntax, manifests, identifiers, dependencies, file paths, and references between resources.

### Debugging
Use supplied error messages, logs, reproduction steps, and project files to identify confirmed problems and evidence-based hypotheses.

### Packaging guidance
Review pack structure and provide instructions for creating or repairing `.mcpack` and `.mcaddon` packages.

## Validation boundaries

- Valid JSON is not necessarily valid for every Minecraft version.
- A static reference check does not prove that Minecraft loads a resource.
- Animation analysis does not prove that an object stays within its intended visual boundaries at runtime.
- Script examples must be checked against the target Script API version.
- In-game import, runtime, multiplayer, and platform-specific tests must not be reported as completed unless they were actually performed.

## File handling

The reviewed package contains ChatGPT skill instructions and does not declare a dedicated MCP server. The complete data flow, storage, retention, and deletion arrangements for uploaded files have not been independently established by this repository review.
