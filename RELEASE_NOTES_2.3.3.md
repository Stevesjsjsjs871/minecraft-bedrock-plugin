# Release Notes — Minecraft Bedrock Engineer 2.3.3

## Entity Authoring consolidation

- Consolidates focused `entity-authoring` instructions into `entity-authoring-pipeline` with two scopes: focused entity authoring and complete BP/RP resource graph authoring/audit.
- Preserves the former basic geometry example and existing static audit utility/tests.
- Updates domain membership, Core routing, Skill inventory, activation scenario design and dependent Skill references.
- Retains 14 domains, eight workflow profiles, plugin identity and 12 default prompts. Skill count changes from 71 to 70.

## Verification

- 32/32 Python test files passed; 548/548 test cases passed.
- Domain architecture: 28/28 checks passed.
- Strict package integrity: 20/20 checks passed.
- Python compileall passed.
- Entity-animation planner smoke generated a valid `PLANNED` Work Order.
- Plugin Host activation and Minecraft runtime: NOT RUN.

This is an unpublished candidate. No live Plugin Creator update was performed.
