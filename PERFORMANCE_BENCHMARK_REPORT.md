# Performance Benchmark Report — 2.3.0

## Method
Measured the hardened `reference_corpus_indexer.py` in fresh CPython 3.13.5 processes using `/usr/bin/time`. Inputs are exact supplied archives; each output was a new path. Reported memory is process maximum RSS, not a sampled allocation trace.

| Dataset | Archive bytes | Entries | Manifests | Wall time | Max RSS | Exit |
|---|---:|---:|---:|---:|---:|---:|
| Small — GameTests | 49,722 | 52 | 2 | 0.71 s | 96,272 KB | 0 |
| Medium — Microsoft Samples | 7,464,423 | 2,307 | 77 | 0.81 s | 101,776 KB | 0 |
| Large — Mojang Bedrock Samples | 169,626,102 | 22,939 | 3 | 2.51 s | 123,952 KB | 0 |

## Interpretation
- These measurements include pinned-file hashing, central-directory preflight, namespace checks, CRC/decompression test and manifest parsing.
- They are one-run observations in this container, not statistically stable performance claims.
- No Windows, Android/Termux, Plugin Host, or Minecraft runtime benchmark was performed.
- No FPS/performance claim about add-ons is inferred.
