# User-provided reference archive inventory

This file records archives supplied in the current project conversation. It is an intake index, not a claim that every archive has received a complete source-level audit. Refer to exact original filenames when available. Third-party materials remain in user-provided uploads and are not redistributed in this plugin.

## Domains represented

| Domain | Supplied examples | Intended use |
|---|---|---|
| UI and UI modifications | Fast-Craft Fast-Loot v3.8; Animated Days Played v1.2.0; Faithful 32x/64x | UI tree inventory, imports, bindings, button mappings, localization, archive-based UI payloads |
| Skin packs | Blackout Pack 24 Skins; Pink Dreams 18 Skins | skins.json, geometry, texture and localization validation |
| PBR / Vibrant Visuals / atmosphere | Prizma Visuals 2.2; GlowCraft; Dark Fantasy Visuals; Vibrant Visuals Extreme 2.4.8; Dark Visuals RP 1.5.9 | PBR, fog, biome client definitions, water, lighting, Subpacks |
| Fog | No Fog Ultra v2.2; Dark Visuals variants | fog identifiers, biome bindings, distance and transition semantics |
| Performance-oriented RP | FPS Booster v2.4.1; FPS Optimizer v2.9.0; Lithium FPSbooster v5; XiaoBoost Ultimate v1.7.2; Performance Optimizer v2.6.2; Sodium v1.2; no-particle-and-animation-texture | manifest settings, Subpacks, particles, resource overrides; performance claims still need in-game benchmarks |
| Cooking/gameplay | Kaleidoscope Cookery 1.6.4 and 2.6.0; Farmer's Delight Bedrock 15.0.4; Kaleidoscope Immersive Eating 1.1.0 | BP/RP architecture, cooking stations, recipes, block interaction, animation integration |
| Entities / Script API | Enhanced Mob AI; DoubleHands 5.6.0; Realistic Biomes 1.3; Realism Craft | entity behavior, item interactions, script organization and versioned API review |
| Models / animation / furniture | Action and Stuff 1.12; FAnimation Update 7; FURNITURE Add-On; Fabulous Furniture | model and animation reference patterns, controller wiring, functional furniture |
| Dynamic lighting | Lilium Dynamic Light 2.1.0; Realism Craft | scheduling, entity/block light handling, performance review |
| Other resources | A Magic Way Resource 1.9; Explorer's Title 1.7.0; Faithful packs | localization, UI, effects, manifests, general resource graph |

## Important intake caveats

- Historical assistant summaries mention analyses of some archives, but a summary alone is not a substitute for re-reading the archive bytes. Re-run relevant checks before citing exact findings in a new audit.
- `Kaleidoscope_Cookery_v2.6.0.mcaddon.zip` was observed as a wrapper containing two inner `.mcpack` files. Its BP/RP manifests and internal assets must be audited from those inner archives, not by treating the outer wrapper as a direct flat pack.
- At least one previously inspected archive had a `.mcpack`-suffixed wrapper directory above its manifest. Report this as a packaging concern and confirm actual import behavior separately.
- Archive filenames and README claims are not authoritative for internal manifest versions. Always inspect the actual manifests.
- These references do not certify Minecraft compatibility, API availability, or FPS improvement.
