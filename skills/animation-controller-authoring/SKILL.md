---
name: animation-controller-authoring
description: Use when creating or auditing Minecraft Bedrock animation controllers, including state machines, animation aliases, transitions, Molang conditions, entry/exit commands, blending and client-entity bindings.
---

# Bedrock Animation Controller Engineering

## Target compatibility and evidence
- Default target is Minecraft Bedrock 1.26.50 unless the user specifies another version.
- Check the matching Mojang sample release and official Creator documentation before relying on format-sensitive behavior. A bundled example or accepted JSON shape is not proof of engine compatibility.
- Report `STATICALLY VERIFIED`, `NEEDS VERIFICATION`, and `RUNTIME TESTED` distinctly. Never claim a Molang expression was evaluated by static validation.

## Controller model
- An animation controller is an RP state machine under `animation_controllers/` with one or more named states and an `initial_state`.
- Each state's `animations` list references aliases exposed by the linked client entity's `description.animations`, not arbitrary file paths. Entries may be plain alias strings or single-key objects such as `{ "walk": "query.modified_move_speed" }` to blend an animation by a Molang expression.
- `transitions` map destination state names to Molang conditions. Every target must exist in the same controller.
- `on_entry` and `on_exit` values are Molang command strings. `blend_transition` is a numeric blend duration; check exact engine semantics for the target build.
- The client entity binds the controller identifier under `description.animations` and activates its alias through `description.scripts.animate` (either unconditional alias or alias-to-Molang mapping).

## Safe authoring workflow
1. Confirm the project has a linked BP/RP scaffold and identify the intended RP client entity file.
2. Inventory its animation aliases before building state definitions. Never invent missing animation clips or aliases.
3. Design a state table: state name, animation aliases, transition targets/conditions, optional entry/exit commands, and blend duration.
4. Use `create_animation_controller` to create one new controller and bind it to the client entity. Existing files and unrelated aliases must be preserved.
5. Run `validate_animation_controller` and then the broader pack/resource graph audit. Check that actual animation definitions exist and targeted bones match the model.
6. Import the pack into the requested Bedrock version and test transition behavior, condition truth, blend timing, looping and interruption at runtime.

## Safety and limits
- Never overwrite an existing controller file or remap an existing client-entity alias to a different resource.
- Reject symlinks, path traversal, malformed/duplicate-key JSON, unresolved state targets and animation aliases not present on the client entity.
- Molang strings receive bounded text validation only, including animation blend expressions. This is not a Molang parser or interpreter.
- The authoring tool updates two RP files. It stages the client-entity replacement, refuses concurrent changes detected during the operation, and removes the newly created controller if the client-entity update fails.

## Required report
Include target version, project/entity/controller identifiers, initial state, states and transitions count, referenced animation aliases, files created/updated, checks actually run, Molang/runtime caveats and in-game test plan. Mark Minecraft runtime behavior `NOT RUN` unless it was actually tested.


## Animation blending and transition ordering
- Animation entries may be alias strings or single-key alias-to-Molang objects. The alias must already exist in the client entity; the expression is bounded and checked for printable text only.
- Example: `["base_pose", { "walk": "query.modified_move_speed" }]` preserves the blend expression in generated Bedrock JSON.
- `validate_animation_controller` inspects the alias and expression shape but does not execute Molang.

## Transition ordering and input compatibility
- Prefer an ordered array of one-key objects, for example `[{ "walking": "query.modified_move_speed > 0.01" }, { "idle": "query.is_sprinting" }]`. Bedrock evaluates transition entries in order and processes at most one transition per frame.
- The tool still accepts the original object-map shorthand for backward compatibility; Python preserves the parsed insertion order, but an array is the explicit and recommended way to express priority.
- The generated controller file always serializes `transitions` as an array of single-key objects.
- Official reference: https://learn.microsoft.com/en-us/minecraft/creator/documents/animations/animationcontroller?view=minecraft-bedrock-stable
