from __future__ import annotations
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"

class LegacySourceMigrationSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_skill_frontmatter_matches_stable_folder(self):
        self.assertIn("name: legacy-source-migration", self.text)
        self.assertIn("description:", self.text.split("---", 2)[1])

    def test_migration_requires_baseline_dependency_map_and_tests(self):
        for term in ("known-good baseline", "dependency map", "focused tests", "preserve the original source"):
            with self.subTest(term=term):
                self.assertIn(term.lower(), self.text.lower())

    def test_capability_and_runtime_limits_are_explicit(self):
        for term in ("NOT APPLIED", "NOT RUN", "Never execute source-project code", "does not grant filesystem access"):
            with self.subTest(term=term):
                self.assertIn(term.lower(), self.text.lower())

if __name__ == "__main__":
    unittest.main()
