#!/usr/bin/env python3
"""Focused tests for the version-aware compatibility skill's evidence contract."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class CompatibilitySkillTests(unittest.TestCase):
    def test_skill_has_required_frontmatter_and_sections(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: version-aware-compatibility\n"))
        for heading in ("## Required intake", "## Compatibility research", "## Implementation rules", "## Validation", "## Output"):
            self.assertIn(heading, text)

    def test_statuses_keep_beta_and_experimental_separate(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for status in ("SUPPORTED", "EXPERIMENTAL", "BETA", "DEPRECATED", "REMOVED", "UNKNOWN"):
            self.assertIn(status, text)

    def test_12650_reference_contains_strict_schema_and_stable_api_notes(self):
        text = (ROOT / "references" / "bedrock-1.26.50-change-notes.md").read_text(encoding="utf-8")
        for token in ("1.26.50", "minecraft:interact", "minecraft:projectile", "2.10.0", "2.2.0", "stable"):
            self.assertIn(token, text)

    def test_no_automatic_global_format_bump_rule(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"smallest migration")
        self.assertIn("Avoid global format-version bumps", text)

if __name__ == "__main__":
    unittest.main(verbosity=2)
