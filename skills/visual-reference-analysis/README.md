# Visual Reference Analysis

The `scripts/analyze_visual_reference.py` utility provides deterministic, read-only connected-component segmentation for Minecraft Bedrock reference PNGs and optional geometry-only candidate ranking against supported cube UV faces.

See [SKILL.md](SKILL.md) for input boundaries, CLI usage, limitations and human-review requirements.

Focused tests:

```bash
python -m unittest discover -s skills/visual-reference-analysis/scripts -p 'test_*.py' -v
```
