# Minecraft Bedrock Plugin

**A ChatGPT-powered development assistant for Minecraft Bedrock Edition add-ons** — including Behavior Packs (BP), Resource Packs (RP), .mcpack and .mcaddon projects.

This project provides workflows and tools for building, diagnosing, auditing, versioning, and packaging Minecraft Bedrock add-ons. It is intended for creators working with Minecraft Bedrock on Windows, Android, iOS, and other supported platforms.

## Features

- **Build and repair add-ons:** plan and edit Behavior Packs, Resource Packs, entities, items, recipes, animations, textures, and Script API projects.
- **Manifest validation:** inspect manifest.json, UUIDs, module types, versions, dependencies, and minimum engine version.
- **Version consistency:** keep BP/RP manifest versions, dependency references, visible pack names, and exported filenames aligned when releasing a new version.
- **Archive checks:** inspect .mcaddon, .mcpack, and ZIP structure, JSON syntax, file paths, and packaging layout.
- **Reference diagnostics:** trace links among entity definitions, geometry, textures, render controllers, animation files, and scripts; heuristic findings are marked for review rather than automatically treated as errors.
- **Repair workflow:** preserve the original project, apply targeted fixes, produce a separate output archive when file tools are available, and re-check the result.
- **Practical reports:** list exact paths, evidence, severity, checks performed, remaining uncertainties, and a manual in-game test checklist.

## How to use it

1. Open ChatGPT and use the Minecraft Bedrock Plugin if it is available to your account.
2. Describe the task in plain language, such as “Fix my Bedrock add-on and give me the corrected .mcaddon file.”
3. Attach the .mcaddon, .mcpack, ZIP, or relevant project files for file-based tasks.
4. Include the exact Bedrock version/build and platform when compatibility matters.
5. For a repair, ask for a separate fixed archive and a brief report of the checks run.
6. Import and test the resulting pack in Minecraft on the target device.

## Important limitations

- Static analysis is not the same as launching Minecraft. A clean archive scan does not prove that a pack imports or behaves correctly in-game.
- Results depend on the files and tools available in the current ChatGPT session.
- Version-specific schema and Script API claims should be checked against official Minecraft Creator documentation.
- The assistant must not claim that an archive was repaired, a file was generated, or an in-game test passed unless that action actually occurred.
- This repository is the project's public source/documentation repository. Public visibility of the ChatGPT plugin itself is a separate setting and is not implied by this GitHub repository being public.

## Project and documentation

- [Features and limitations](docs/FEATURES.md)
- [Usage guide](docs/USAGE.md)
- [Compatibility notes](docs/COMPATIBILITY.md)
- [Public release readiness checklist](docs/PUBLIC-RELEASE-CHECKLIST.md)
- [Archive audit plan](docs/ARCHIVE-AUDIT-PLAN.md)
- [Bug report template](support/BUG_REPORT.md)
- [Security reporting guidance](support/SECURITY.md)

## Official references

- [Minecraft Creator documentation](https://learn.microsoft.com/minecraft/creator/)
- [Minecraft Bedrock samples by Mojang](https://github.com/Mojang/bedrock-samples)
- [Bedrock Wiki](https://wiki.bedrock.dev/)

## Search keywords

Minecraft Bedrock Edition add-on tool, Minecraft Bedrock plugin, Bedrock add-on validator, behavior pack validator, resource pack validator, .mcaddon analyzer, .mcpack checker, manifest.json validation, Minecraft Bedrock scripting, animation debugging, add-on packaging, BP RP versioning.

## License and support

Check the repository's license and support files before reusing or redistributing project contents. Do not upload passwords, API keys, access tokens, or other secrets in project files or messages.
