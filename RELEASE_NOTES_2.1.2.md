# Release Notes — 2.1.2

## Intent understanding and adaptive clarification

- Adds an ambiguity protocol for short, informal, incomplete and referential requests.
- Requires internal intent analysis using wording, conversation context, project files and known constraints without exposing private chain-of-thought.
- Distinguishes genuinely ambiguous requests from merely brief but clear requests; avoids unnecessary questioning.
- Adds concise multiple-choice clarification with an always-available free-form answer and safe skip/default paths for non-blocking choices.
- Revises the same shared plan after each answer or new discovery; supports narrower follow-up questions without repeated or endless intake.
- Integrates the protocol into Core's mandatory task workflow while preserving existing Skills and behavior.
- Host activation and Minecraft runtime behavior remain separate validation items; Minecraft runtime is NOT RUN unless actually tested.
