from __future__ import annotations

import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from addon_archive_versioning import ArchiveVersionError, update_archive


class AddonArchiveVersioningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fixture = (
            Path(__file__).resolve().parents[1]
            / "references"
            / "fixtures"
            / "cinematic-interactions-style"
        )
        self.input = self.root / "cinematic-interactions-1.2.3.mcaddon"
        self.output = self.root / "cinematic-interactions-1.2.4.mcaddon"
        self.make_archive(self.input, self.fixture)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def make_archive(path: Path, directory: Path):
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(directory.rglob("*")):
                if item.is_file():
                    archive.write(item, item.relative_to(directory).as_posix())

    def test_mcaddon_is_repacked_with_aligned_title_manifests_and_dependencies(self):
        original = self.input.read_bytes()
        report = update_archive(self.input, self.output, change_type="fix", apply=True)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(self.input.read_bytes(), original)
        self.assertTrue(report["archive_verification"]["passed"])
        self.assertFalse(report["input_modified"])
        self.assertEqual({row["new_version"] for row in report["versions"]}, {"1.2.4"})

        with zipfile.ZipFile(self.output, "r") as archive:
            self.assertIsNone(archive.testzip())
            bp = json.loads(archive.read("behavior_packs/cinematic_bp/manifest.json"))
            rp = json.loads(archive.read("resource_packs/cinematic_rp/manifest.json"))
            self.assertEqual(bp["header"]["name"], "pack.name")
            self.assertEqual(rp["header"]["name"], "pack.name")
            self.assertEqual(bp["header"]["version"], [1, 2, 4])
            self.assertEqual(rp["header"]["version"], [1, 2, 4])
            self.assertEqual(bp["dependencies"][0]["version"], [1, 2, 4])
            self.assertEqual(bp["dependencies"][1]["version"], "2.0.0")
            self.assertIn("Cinematic Interactions v1.2.4",
                          archive.read("behavior_packs/cinematic_bp/texts/en_US.lang").decode("utf-8"))
            self.assertIn("Ресурсы Cinematic Interactions v1.2.4",
                          archive.read("resource_packs/cinematic_rp/texts/ru_RU.lang").decode("utf-8"))

    def test_existing_output_is_never_overwritten(self):
        self.output.write_bytes(b"keep-existing-output")
        with self.assertRaises(FileExistsError):
            update_archive(self.input, self.output, change_type="fix", apply=True)
        self.assertEqual(self.output.read_bytes(), b"keep-existing-output")

    def test_archive_dry_run_does_not_create_output_or_change_input(self):
        original = self.input.read_bytes()
        report = update_archive(self.input, self.output, change_type="fix")
        self.assertEqual(report["status"], "DRY_RUN")
        self.assertTrue(report["output_not_created"])
        self.assertFalse(self.output.exists())
        self.assertEqual(self.input.read_bytes(), original)
        self.assertTrue(report["verification"]["passed"])

    def test_path_traversal_member_is_rejected(self):
        malicious = self.root / "traversal.mcaddon"
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("../outside.txt", "bad")
        with self.assertRaisesRegex(ArchiveVersionError, "path traversal"):
            update_archive(malicious, self.output, change_type="fix", apply=True)
        self.assertFalse(self.output.exists())

    def test_symlink_member_is_rejected(self):
        malicious = self.root / "symlink.mcaddon"
        info = zipfile.ZipInfo("behavior_packs/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr(info, "../../outside")
        with self.assertRaisesRegex(ArchiveVersionError, "symbolic links"):
            update_archive(malicious, self.output, change_type="fix", apply=True)
        self.assertFalse(self.output.exists())

    def test_duplicate_archive_member_is_rejected(self):
        malicious = self.root / "duplicate.mcaddon"
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("manifest.json", "{}")
            archive.writestr("manifest.json", "{}")
        with self.assertRaisesRegex(ArchiveVersionError, "duplicate"):
            update_archive(malicious, self.output, change_type="fix", apply=True)
        self.assertFalse(self.output.exists())


    def test_input_symlink_is_rejected(self):
        linked = self.root / "linked-input.mcaddon"
        try:
            linked.symlink_to(self.input)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are not available on this platform")
        with self.assertRaisesRegex(ArchiveVersionError, "input archive must not be a symbolic link"):
            update_archive(linked, self.output, change_type="fix", apply=True)
        self.assertFalse(self.output.exists())

    def test_output_symlink_is_rejected_without_touching_target(self):
        protected = self.root / "protected.bin"
        protected.write_bytes(b"protected")
        linked_output = self.root / "linked-output.mcaddon"
        try:
            linked_output.symlink_to(protected)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are not available on this platform")
        with self.assertRaisesRegex(ArchiveVersionError, "output archive path must not be a symbolic link"):
            update_archive(self.input, linked_output, change_type="fix", apply=True)
        self.assertEqual(protected.read_bytes(), b"protected")

    def test_high_compression_ratio_member_is_rejected(self):
        malicious = self.root / "high-ratio.mcaddon"
        with zipfile.ZipFile(malicious, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr("payload.bin", b"\x00" * (2 * 1024 * 1024))
        with self.assertRaisesRegex(ArchiveVersionError, "suspicious compression ratio"):
            update_archive(malicious, self.output, change_type="fix", apply=True)
        self.assertFalse(self.output.exists())

    def test_multiple_pack_variants_are_rejected(self):
        source = self.root / "many-manifests.mcaddon"
        with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(self.fixture.rglob("*")):
                if item.is_file():
                    archive.write(item, item.relative_to(self.fixture).as_posix())
            alt = json.loads((self.fixture / "behavior_packs/cinematic_bp/manifest.json").read_text())
            alt["header"]["uuid"] = "66666666-6666-4666-8666-666666666666"
            archive.writestr("behavior_packs/preview_bp/manifest.json", json.dumps(alt))
        with self.assertRaisesRegex(ArchiveVersionError, "contains 3 manifests"):
            update_archive(source, self.output, change_type="fix", apply=True)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
