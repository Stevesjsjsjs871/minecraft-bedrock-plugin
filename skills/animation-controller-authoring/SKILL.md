---
name: animation-controller-authoring
description: Use when creating or auditing Bedrock RP animation-controller state machines, states, transitions, aliases, Molang conditions, and client-entity bindings.
---

# Bedrock Animation Controller Engineering

## Capability boundary

This is a file-authoring and review procedure. The current Skills-only package does not include live `create_animation_controller` or `validate_animation_controller` tools. Do not call old MCP names or describe a nonexistent generator/validator. Use an actual connected file/code route; without one, return a reviewable patch and mark it `NOT APPLIED`.

## Target compatibility

Default target is Minecraft Bedrock 1.26.50 only when the user has not given a target. Confirm the exact build and check matching official Creator documentation and Mojang samples before relying on controller format, transition, blend or Molang semantics. A bundled example or accepted JSON shape is not proof of engine compatibility.

## Controller model

- An animation controller is an RP state machine in `animation_controllers/` with an identifier, states and an `initial_state`.
- Each state's `animations` entries reference aliases exposed by the linked client entity's `description.animations`, not arbitrary filenames.
- `transitions` map destination state names to Molang conditions; each destination must exist in the same controller.
- `on_entry` and `on_exit` contain target-version-supported Molang command expressions.
- `blend_transition` and other timing fields must follow the exact target-version semantics; do not infer behavior from numeric shape alone.
- The client entity registers the controller identifier in `description.animations` and activates its alias through `description.scripts.animate`.

## Safe authoring workflow

1. Confirm the existing BP/RP project, target version, selected entity and client-entity JSON. Establish a baseline.
2. Inventory existing animation aliases, controller aliases, clip identifiers and controller files. Never invent a clip/alias that is not present or planned in the same coordinated change.
3. Prepare a state table: state name, animation aliases, transition targets/conditions, entry/exit actions, blend values and intended fallback state.
4. Validate the graph on paper before writing: unique states; valid initial state; every transition destination exists; every state animation alias exists on the client entity; the client entity references this controller; and referenced clips/geometry/bones exist.
5. Write one new controller file and make the minimal client-entity alias/activation change using a real file capability. Do not overwrite existing controller or remap unrelated aliases.
6. Parse JSON and run `python skills/entity-authoring-pipeline/scripts/audit_entity_pipeline.py --bp-root <BP> --rp-root <RP> [--entity-id namespace:name]` when the package and project are accessible to a real executor. This audit checks literal graph edges; it does not evaluate Molang or prove the controller schema is accepted by the engine.
7. Compare exact before/after paths and identifiers. Review every removed or changed binding.
8. Import into the exact Bedrock build and test condition truth, transitions, entry/exit behavior, looping, blend timing, interruption, reload and multiplayer scenarios.

## Safety and limits

Reject traversal/symlink escapes, malformed or duplicate-key JSON, unresolved state destinations and aliases not present in the client entity. Treat dynamic Molang references conservatively. Static checks do not parse/evaluate Molang, simulate controller execution or guarantee engine compatibility. Never delete an animation/alias because a static graph cannot resolve a dynamic expression.

## Required report

Include target version, project/entity/controller identifiers, initial state, state and transition counts, referenced animation aliases, files changed, exact checks and commands, unresolved/dynamic references, Molang evaluation status, baseline delta, and runtime status. Mark Minecraft runtime `NOT RUN` unless the target game was actually launched and tested.
