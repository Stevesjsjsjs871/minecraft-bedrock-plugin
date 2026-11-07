# Release 2.0.7 — Skill quality audit and capability-truth repairs

## Scope

Reviewed the complete 65-Skill inventory against the user-supplied Technical Guide 2.0. Kept the Domain-Based Hybrid / Skills-only design, all 14 domain assignments, portable Skill paths and 12 default prompts.

## Improvements

- Removed six Skills' unsupported historical MCP/tool calls and replaced them with real local script routes or explicit manual workflows.
- Made animated entity creation, animation clip/controller authoring and end-to-end animation audit accurately reflect which implementations exist and what they can verify.
- Replaced the nonexistent automated reference-mapping reviewer with a documented human approval gate; aligned the retarget example with the actual transfer parser.
- Removed unsupported claims about general-purpose Bedrock Engineer writers; removed duplicate cooking version-gate text.
- Expanded skin-pack, Subpack, Script API, UI audit and Vibrant Visuals/fog/PBR procedures.
- Added a reusable Skill quality checklist, full Skill-by-Skill audit report and 325-case activation test design matrix.
- Rebuilt Tool Registry distinctions and kept local Python vs installed-plugin host/runtime evidence separate.

## Verification

The full post-edit local suite, architecture validator, package-integrity checker, frontmatter/domain/reference checks, prompt parity, ZIP integrity and Plugin Creator read-back are reported separately. The activation matrix is `NOT RUN` until tested against the actual installed ChatGPT plugin host. Creator Tools and Minecraft import/render/gameplay are `NOT RUN` in this audit.

## Preserved

No Skill paths were removed or renamed. No MCP component or remote backend was added. The 34 historical `server/` files remain retained/inert pending migration closure and explicit authorization.
