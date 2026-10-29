# Independent real-pack case review checklist

Use this checklist before setting a benchmark case to `label_status: reviewed`.

## Artifact provenance
- [ ] Original artifact saved outside the plugin/repository workspace where appropriate.
- [ ] Exact artifact SHA-256 recorded and rechecked before each evaluation.
- [ ] Source, retrieval date, permission/license and redistribution limits documented.
- [ ] Bedrock target version and artifact/pack type recorded.

## Review scope
- [ ] `scored_rules` contains only rules the reviewer exhaustively inspected.
- [ ] Every expected finding has exact title/path and a concise evidence note.
- [ ] Both present and absent instances were reviewed within every scored rule's scope.
- [ ] Unscored resource domains are explicitly marked out of scope instead of presumed clean.
- [ ] Static facts, heuristics and game-runtime observations are distinguished.

## Reviewer quality
- [ ] Reviewer did not use the candidate auditor's output as the only source for expected findings.
- [ ] High-impact findings received independent second review or documented adjudication.
- [ ] Disagreements and rule-title/path normalization decisions are recorded.
- [ ] Labels were frozen before comparing plugin versions.

## Evaluation integrity
- [ ] Report candidate hash matches the exact artifact hash.
- [ ] Report passes the shipped report schema.
- [ ] Evaluator version and plugin `VERSION` are recorded.
- [ ] Invalid, missing or hash-mismatched reports are surfaced as invalid, not dropped.
- [ ] Precision/recall/F1 are described as scoped metrics, not overall accuracy.
