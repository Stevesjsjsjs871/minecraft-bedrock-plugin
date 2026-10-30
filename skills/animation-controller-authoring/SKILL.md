---
name: animation-controller-authoring
description: Design and manually author Minecraft Bedrock RP animation-controller state machines with consistent aliases and transitions.
---

# Bedrock Animation Controller Engineering

## Capability boundary

This Skill is an instruction and review procedure. The package does not include an active controller writer or dedicated controller validator. Use an actual authorized file capability or provide complete proposed JSON and mark it NOT APPLIED.

## Controller model

- An animation controller is an RP state machine with an initial state and named states.
- State animation references must resolve to aliases exposed by the linked client entity.
- Transition destinations must name states defined in the same controller.
- Molang conditions, entry/exit expressions and blend behavior are version-sensitive. Verify their exact syntax and semantics against target-version Creator documentation and matching Samples.
- A JSON parser does not evaluate Molang or prove state-machine behavior.

## Safe authoring workflow

1. Confirm the RP root, client entity and exact target Bedrock version.
2. Inventory current controller identifiers, client-entity animation aliases and referenced clip files.
3. Build a state table containing state name, animation aliases, transition destinations, condition text, optional entry/exit behavior and blend intent.
4. Verify every alias and destination before producing the controller JSON.
5. Update the client-entity binding only when required. Preserve unrelated aliases and existing behavior.
6. Parse changed JSON and run the entity pipeline audit when its actual script and project files are accessible. Report the exact files and edges checked.
7. Re-open all changes and compare them with the baseline.

## Limits

The available static entity audit does not execute Molang, simulate state transitions, measure blend timing or validate every engine-specific controller rule. Minecraft import, transitions, interruption, looping, blending and multiplayer behavior remain NOT RUN until tested in the requested game build.
