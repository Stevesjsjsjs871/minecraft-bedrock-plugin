# Regression test matrix — 0.7.8

| ID | Fixture | Expected invariant | Failure meaning |
|---|---|---|---|
| EVAL-001 | Valid BP/RP archive | Archive opens; report is parseable JSON and passes the report schema | Packaging/report contract regression |
| EVAL-002 | Geometry and animation defined and referenced | Graph contains resolved edges for literal definitions | Identifier indexing/resolution regression |
| EVAL-003 | Client entity references absent geometry | Graph retains an unresolved edge with source file/pointer | Missing-reference detection regression |
| EVAL-004 | Malformed JSON file | Invalid JSON is reported; report still conforms to schema | Parser/report contract regression |
| EVAL-005 | ZIP contains `../escape.json` | Unsafe member path is reported; no extraction occurs | Archive safety regression |
| EVAL-006 | Dynamic/Molang-like reference | Edge is marked dynamic/heuristic, not a confirmed literal miss | False-positive risk |
| EVAL-007 | Report coverage metadata | Partial/not-implemented areas are explicit and schema-valid | Overstated coverage/schema regression |
| EVAL-008 | Runtime status | Static-only report says `NOT RUN` | False runtime-success claim |
| EVAL-009 | Resource graph filters | Geometry, animations, controllers, textures, UI and localization filters select edges by real schema fields | Filter contract regression |
| EVAL-010 | Shared archive safety | CLI and MCP use common compressed/member/per-member/total size limits before reading payloads | Resource-exhaustion protection regression |
| EVAL-011 | Single version source | Root manifest, compatibility manifest, MCP initialize response, analyzer report and README agree with `VERSION` | Version drift |
| EVAL-012 | Golden graph projection | Valid synthetic pack produces exactly the expected source pointers, edge kinds, target domains, statuses and counts | Silent reference-graph semantic regression |
| EVAL-013 | Domain filter isolation | Explicit `target_domain` is authoritative; UI paths cannot leak into geometry/textures merely because text matches | Cross-domain false positives |

The fixtures are synthetic and only prove the encoded scenarios. Add redistributable, provenance-tracked, version-pinned real packs when licensing permits. Do not imply full Bedrock engine compatibility from these tests.

| EVAL-014 | Animation references nonexistent bone | Emit INFO/LOW heuristic only when no indexed geometry contains the bone | Bone-target regression or false-positive severity drift |
| EVAL-015 | Animation-controller transition target | Report a literal missing state without evaluating Molang | State transition wiring regression |
| EVAL-016 | Animation-controller initial state | Report initial_state absent from this controller's state map | Invalid initial state missed |

| EVAL-017 | `ui_defs` points to a missing file | Emit INFO/LOW possible unresolved UI path after common path variants | UI import path regression; not proof of an engine error |
| EVAL-018 | Same `.lang` key appears twice in one file | Report duplicate localization key with line evidence | Duplicate key regression |
| EVAL-019 | UI `text` has a simple `$key` absent from indexed `.lang` files | Emit INFO/LOW possible unresolved localization key | UI translation lookup regression; external/dynamic sources remain possible |

UI/localization fixtures are deliberately synthetic. They do not exercise Minecraft's UI renderer, all versioned JSON schemas, resource-pack priority, or external language providers.

| EVAL-020 | `ui_defs` repeats the same literal path | Emit an INFO duplicate-import heuristic | Duplicate UI import regression; not proof of loader behavior |
| EVAL-021 | UI control extension names an absent namespace | Emit INFO/LOW possible unresolved control reference | Control namespace heuristic regression; external/implicit namespace may be valid |

The additional UI fixtures test only recognized literal forms and do not validate Bedrock's complete UI control/reference semantics.

| EVAL-022 | Literal UI `$key` to `.lang` index | Graph resolves a present key and leaves a missing in-archive key heuristic-unresolved at LOW confidence | Localization graph link/severity regression |


| EVAL-023 | Block component references an in-archive loot table | Resolve documented literal `minecraft:loot.table` object paths (and recognized string-form values) | BP resource-link regression |
| EVAL-024 | Block component references a missing loot table | Emit a LOW-confidence heuristic unresolved path edge for the documented `table` field | Missing loot table link or severity drift |

Component coverage is intentionally allowlisted and partial. These fixtures do not validate the complete versioned item/block component schemas or prove game loading.



| EVAL-025 | Nested loot table references another in-archive table | Record resolved graph edges for `type: loot_table` and report a resolved recursion cycle | Nested loot-table linking/cycle regression |
| EVAL-026 | Loot table contains invalid pool/entries/rolls shapes | Report malformed common structural fields with source path | Loot-table shape regression |

Loot-table checks validate common fields only; they do not replace the complete target-version schema or execute loot conditions/functions.

| EVAL-027 | More than 1000 nested loot-table nodes | Cycle detection completes without Python recursion-depth failure | Graph traversal resource-safety regression |
| EVAL-028 | Medium-severity loot-table structure finding | Report recommendation is `REVIEW`, not static-checks-passed | Misleading release recommendation regression |


| EVAL-029 | Reviewed real-pack benchmark report | Manifest/report schemas and artifact hash are validated before metrics are emitted | Benchmark validity or denominator-integrity regression |
| EVAL-030 | Pending benchmark labels | Pending cases are counted as skipped, not treated as clean or included in metrics | Unreviewed truth labels contaminate metrics |
| EVAL-031 | Analyzer version pinned during benchmark | Any mismatched report version invalidates aggregate metrics | Cross-version benchmark mixing |

Benchmark-harness unit tests use synthetic test reports only. They validate evaluator behavior and are not real-pack benchmark results.


## Benchmark evaluator tests 0.7.9

| ID | Fixture | Expected invariant | Failure meaning |
|---|---|---|---|
| BENCH-001 | Artifact symlink points outside `--artifacts-dir` | Run is INVALID and metrics are withheld | Input-root confinement regression |
| BENCH-002 | Report symlink points outside `--reports-dir` | Run is INVALID and metrics are withheld | Report-root confinement regression |
| BENCH-003 | Invalid UTF-8 in benchmark manifest | Return INVALID without traceback | Input decoding robustness regression |
| BENCH-004 | Duplicate reviewed expected `(title, path)` | Reject ambiguous labels before scoring | Golden-label ambiguity regression |

## Pack-to-pack diff MCP contract 0.8.0

| ID | Fixture | Expected invariant | Failure meaning |
|---|---|---|---|
| DIFF-001 | Two archives with added, removed and modified files | Return accurate full counts and bounded path samples | File-diff summary regression |
| DIFF-002 | Finding disappears or severity increases | Report new/no-longer-reported findings and severity deltas separately | Finding regression comparison error |
| DIFF-003 | Graph edge changes from resolved to unresolved | Report reference regression with source pointer and confidence | Resource graph regression missed |
| DIFF-004 | More than 100 changed files | Return at most 100 examples while retaining full count and `truncated` | Output size bound regression |
| DIFF-005 | Input archives are compared | Both archives remain byte-for-byte unchanged and runtime is `NOT RUN` | Read-only safety contract regression |
