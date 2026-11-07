from __future__ import annotations

import unittest

from version_governance import VersionError, next_version, validate_new_version


class VersionGovernanceTests(unittest.TestCase):
    def test_live_171_release_advances_exactly_to_172(self):
        self.assertEqual(next_version("1.7.1"), "1.7.2")

    def test_patch_increments_until_nine(self):
        self.assertEqual(next_version("1.0.8"), "1.0.9")

    def test_patch_nine_rolls_minor(self):
        self.assertEqual(next_version("1.0.9"), "1.1.0")

    def test_minor_patch_rollover(self):
        self.assertEqual(next_version("1.1.9"), "1.2.0")

    def test_minor_nine_rolls_major(self):
        self.assertEqual(next_version("1.9.9"), "2.0.0")

    def test_legacy_patch_fourteen_rolls_minor(self):
        self.assertEqual(next_version("1.0.14"), "1.1.0")

    def test_current_legacy_release_rolls_to_one_six_zero(self):
        self.assertEqual(next_version("1.5.12"), "1.6.0")

    def test_legacy_minor_rolls_major(self):
        self.assertEqual(next_version("1.10.0"), "2.0.0")

    def test_new_version_accepts_only_single_digit_components(self):
        self.assertEqual(str(validate_new_version("1.6.0")), "1.6.0")
        with self.assertRaises(VersionError):
            validate_new_version("1.0.10")

    def test_multi_digit_major_requires_user_decision(self):
        with self.assertRaises(VersionError):
            next_version("10.0.0")

    def test_maximum_version_has_no_successor(self):
        with self.assertRaises(VersionError):
            next_version("9.9.9")

    def test_malformed_versions_are_rejected(self):
        for malformed in ("1.2", "v1.2.3", "1.2.3-beta", "01.2.3", "1..3"):
            with self.subTest(version=malformed), self.assertRaises(VersionError):
                next_version(malformed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
