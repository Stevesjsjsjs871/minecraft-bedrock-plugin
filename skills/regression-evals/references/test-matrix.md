# Regression test matrix

| ID | Fixture | Expected invariant | Failure meaning |
|---|---|---|---|
| EVAL-001 | Valid BP/RP archive | Archive opens; report is parseable JSON; required report keys exist | Packaging/report contract regression |
| EVAL-002 | Geometry and animation defined and referenced | Graph contains resolved edges for literal definitions | Identifier indexing/resolution regression |
| EVAL-003 | Client entity references absent geometry | Graph retains an unresolved edge with source path/pointer | Missing-reference detection regression |
| EVAL-004 | Malformed JSON file | Invalid JSON is reported with the file path | Parser error silently ignored |
| EVAL-005 | ZIP contains `../escape.json` | Unsafe member path is reported; no extraction occurs | Archive safety regression |
| EVAL-006 | Dynamic/Molang-like reference | Edge is marked dynamic/heuristic, not a confirmed literal miss | False-positive risk |
| EVAL-007 | Report coverage metadata | Partial/not-implemented areas are explicit | Overstated coverage risk |
| EVAL-008 | Runtime status | Report says `NOT RUN` for static-only execution | False runtime-success claim |

These fixtures are intentionally synthetic. They verify analyzer contracts, not every Bedrock schema rule. Extend the matrix with real, redistributable sample packs and version-pinned fixtures when their provenance and license permit it.
