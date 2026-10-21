# Minecraft Bedrock Plugin

A ChatGPT-based development assistant for Minecraft Bedrock Edition add-ons.

## What it helps with

- Plan Behavior Packs and Resource Packs.
- Review JSON files, manifests, UUIDs, and dependencies.
- Investigate recipes, entities, textures, animations, and Script API issues.
- Inspect `.mcaddon`, `.mcpack`, ZIP archives, and project files when they are available in the current ChatGPT session.
- Prepare targeted fixes, packaging guidance, and regression test checklists.

## How to use it

1. Describe the add-on or problem you want to solve.
2. Attach the relevant files when requesting a file-based review.
3. Include your Minecraft Bedrock version and platform when compatibility matters.
4. Explain the expected behavior and what actually happens.
5. Review proposed changes and test the result in Minecraft.

## Important limitations

Static inspection does not prove that an add-on imports successfully or works correctly in-game. Runtime behavior, platform-specific issues, and multiplayer compatibility may require manual testing. The assistant must not claim that a test was performed unless it actually was.

Do not upload passwords, access tokens, or other secrets in project files or messages.

## Project status

This public repository contains initial documentation for the project. The public support channel, privacy policy, and terms of use have not yet been finalized. The privacy audit document is an internal preliminary note, not a public privacy policy.

## Documentation

- [Features and limitations](docs/FEATURES.md)
- [Usage guide](docs/USAGE.md)
- [Compatibility notes](docs/COMPATIBILITY.md)
- [Preliminary privacy audit](docs/PRIVACY-AUDIT.md)
- [Bug report template](support/BUG_REPORT.md)
- [Security reporting guidance](support/SECURITY.md)

Support contact and verified policy URLs will be added after they are established.
