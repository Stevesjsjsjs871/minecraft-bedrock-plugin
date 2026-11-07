# Reference Corpus Audit — 2.3.0

Ten source archives were re-indexed using the hardened pinned-descriptor indexer. Total: **42,876 ZIP entries** (41,301 files + 1,575 explicit directories), **110 manifest records**. All ten CRC/decompression checks passed; all ten SHA-256 values match the baseline metadata. No extraction or embedded-code execution occurred.

| Archive | Entries | Manifests | SHA-256 |
|---|---:|---:|---|
| bedrock-samples-main.zip | 22939 | 3 | `2c5823a2c8f2cfe96f3a2068df8fdcf9f4bb6050d1c4d42437dafb3916cdb362` |
| minecraft-samples-main.zip | 2307 | 77 | `0acdd58b4cb76d87947d1c0b14243245bcd930c0efe4cc4241d39a38d58f8142` |
| minecraft-scripting-samples-main.zip | 411 | 19 | `121a60c8c8164294870ad5987750d5a5266c5ae1db2f0c1718698ae27a10e658` |
| minecraft-gametests-main.zip | 52 | 2 | `062e512258f79a88f0d74f1db683204db03471a034837998035a0124aeb681bb` |
| minecraft-robot-addon-main.zip | 22 | 2 | `7a17fb4d0bc1f41f6f879065d6eb262e34081fd9668212eed82871e592649e08` |
| MinUI-main.zip | 88 | 0 | `bdae6559565088515c18d9f8d1479990be1b4587442bda9083daacb8999de02f` |
| actions-stuff-1-12.mcpack.zip | 10824 | 1 | `64a4b5d60fa686dc6c0712725a447eb3527447f3671bc4755882b9ebf780a4c9` |
| FURNITURE Add-On (addon).mcaddon.zip | 5037 | 2 | `467e5c04d86c755c95c5c53fd2ef1945c7b42e5144f904f1cc631043a9deac22` |
| CinematicInteractions_Bedrock_v1_24_1.mcaddon.zip | 183 | 2 | `ef8b65ea9e52c5d39c29f2ad280694ba3126ab24a3201e6e64f5c6f1ba443ad5` |
| CreateMovement.mcaddon | 1013 | 2 | `504783df83ee584ba1a7a7cedc027b9c142be9eab5ada973bb1586ec6e61626b` |

See `source_reindex.json` for the exact per-archive ledger and `skills/reference-pack-corpus/references/REFERENCE_CORPUS_REPORT_2026-11-07.md` for provenance, version observations, real-pack static audit findings and limitations.

No independently reviewed benchmark labels exist; precision/recall is not scored. GitHub main branch ZIPs are mutable snapshots because no commit SHA was embedded. Source archives remain outside the plugin package.
