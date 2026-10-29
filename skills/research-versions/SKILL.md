---
name: research-versions
description: Use when investigating a Bedrock feature, version-specific Script API, resource format, undocumented limitation, official sample, or compatibility question that needs verifiable research.
---

# Version-Aware Bedrock Research

## Questions to resolve
- What exact Minecraft version is the target?
- Is the feature supported by Bedrock, and in which execution/resource context?
- Does it require an experiment, preview build, dependency, or third-party pack?
- Which official docs and samples support the conclusion?
- What changed between relevant versions?
- What are the practical alternatives if the requested approach is unavailable?

## Source order
1. Official Microsoft Creator documentation: https://learn.microsoft.com/en-us/minecraft/creator/
2. Official Mojang Bedrock samples and release-tagged sources: https://github.com/Mojang/bedrock-samples/releases
3. Bedrock Wiki: https://wiki.bedrock.dev/
4. Reputable community posts/issues/tutorials, with date and version caveats.

Search current sources when the fact may have changed, when documentation is niche, or when version compatibility matters. Use version-tagged sources where possible. Cite the important claims and include the exact link needed to verify them.

## Method
1. Translate the requested behavior into observable requirements.
2. Search for official documentation and matching-version samples.
3. Inspect examples, relevant JSON/JavaScript definitions, and version metadata where available.
4. Compare at least two approaches when their tradeoffs materially differ.
5. Identify blockers, experiments, unsupported behavior, and assumptions.
6. Provide a recommendation with evidence and a verification plan.
7. If asked to implement and files/tools are available, proceed to implementation rather than stopping at research.

## Confidence labels
Use CONFIRMED, STATICALLY VERIFIED, RUNTIME TESTED, INFERRED, or NEEDS VERIFICATION accurately. Do not claim exhaustive internet-wide research. If source evidence is unavailable or conflicting, say so and explain the uncertainty.

## Output
- Recommended method and why.
- Version and dependency assumptions.
- Supporting official/community links.
- Alternatives and limitations.
- Minimal implementation plan or implementation itself, depending on the user's request.
