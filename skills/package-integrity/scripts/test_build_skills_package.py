from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from build_skills_package import build_archive
from package_provenance import PackageSafetyError, _safe_path, verify_archive


class BuildSkillsPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "package"
        self.root.mkdir()
        (self.root / "VERSION").write_text("1.5.11\n", encoding="utf-8")
        (self.root / "README.md").write_text("test package\n", encoding="utf-8")
        (self.root / "skills").mkdir()
        (self.root / "skills/example.SKILL.md").write_text("fixture\n", encoding="utf-8")
        (self.base / "out").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_and_verify_archive(self):
        archive = self.base / "out/package.tar.gz"
        result = build_archive(self.root, archive, "b" * 40, 1_700_000_000, "refs/heads/test")
        self.assertTrue(archive.is_file())
        self.assertTrue(Path(str(archive) + ".sha256").is_file())
        self.assertEqual(result["payload_file_count"], 3)
        verified = verify_archive(archive, Path(str(archive) + ".sha256"))
        self.assertEqual(verified["archive_sha256"], result["archive_sha256"])

    def test_reproducible_archive_bytes(self):
        first = self.base / "out/first.tar.gz"
        second = self.base / "out/second.tar.gz"
        build_archive(self.root, first, "c" * 40, 1_700_000_000)
        build_archive(self.root, second, "c" * 40, 1_700_000_000)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_rejects_bytecode_cache(self):
        cache = self.root / "skills/__pycache__"
        cache.mkdir()
        (cache / "bad.pyc").write_bytes(b"x")
        with self.assertRaises(PackageSafetyError):
            build_archive(self.root, self.base / "out/cache.tar.gz", "d" * 40, 0)

    def test_rejects_symlink(self):
        link = self.root / "linked"
        try:
            link.symlink_to(self.root / "README.md")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable on this runner")
        with self.assertRaises(PackageSafetyError):
            build_archive(self.root, self.base / "out/link.tar.gz", "e" * 40, 0)

    def test_rejects_invalid_commit(self):
        with self.assertRaises(PackageSafetyError):
            build_archive(self.root, self.base / "out/invalid.tar.gz", "not-a-sha", 0)

    def test_rejects_output_inside_package(self):
        with self.assertRaises(PackageSafetyError):
            build_archive(self.root, self.root / "inside.tar.gz", "f" * 40, 0)

    def test_refuses_overwrite(self):
        archive = self.base / "out/existing.tar.gz"
        build_archive(self.root, archive, "1" * 40, 0)
        with self.assertRaises(PackageSafetyError):
            build_archive(self.root, archive, "1" * 40, 0)

    def test_rejects_windows_drive_and_traversal_paths(self):
        self.assertFalse(_safe_path("C:/outside/file.txt"))
        self.assertFalse(_safe_path("../outside/file.txt"))
        self.assertFalse(_safe_path("/absolute/file.txt"))

    def test_detects_sidecar_tampering(self):
        archive = self.base / "out/tamper.tar.gz"
        build_archive(self.root, archive, "2" * 40, 0)
        Path(str(archive) + ".sha256").write_text("0" * 64 + "  tamper.tar.gz\n", encoding="ascii")
        with self.assertRaises(PackageSafetyError):
            verify_archive(archive, Path(str(archive) + ".sha256"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
