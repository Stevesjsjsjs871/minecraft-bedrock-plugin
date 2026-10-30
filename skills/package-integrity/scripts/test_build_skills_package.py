from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_skills_package import build_archive
from package_provenance import PackageSafetyError, _safe_path, payload_sha256, verify_archive


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

    def test_rejects_windows_drive_traversal_ads_and_reserved_paths(self):
        for path in (
            "C:/outside/file.txt",
            "../outside/file.txt",
            "/absolute/file.txt",
            "assets/C:stream.png",
            "assets/NUL.txt",
            "assets/CON",
            "assets/trailing-dot.",
            "assets/trailing-space ",
        ):
            self.assertFalse(_safe_path(path), path)

    def test_detects_sidecar_tampering(self):
        archive = self.base / "out/tamper.tar.gz"
        build_archive(self.root, archive, "2" * 40, 0)
        Path(str(archive) + ".sha256").write_text("0" * 64 + "  tamper.tar.gz\n", encoding="ascii")
        with self.assertRaises(PackageSafetyError):
            verify_archive(archive, Path(str(archive) + ".sha256"))


    @staticmethod
    def _tar_info(name, mode=0o644, pax_headers=None, member_type=tarfile.REGTYPE):
        info = tarfile.TarInfo(name)
        info.mode = mode
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.type = member_type
        info.pax_headers = pax_headers or {}
        return info

    def _valid_tar_entries(self):
        payload = b"fixture package\n"
        records = [{
            "path": "README.md",
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }]
        provenance = {
            "schema_version": 1,
            "plugin": "minecraft-bedrock-engineer",
            "version": "1.5.11",
            "git_commit": "a" * 40,
            "source_date_epoch": 0,
            "archive_format": "tar.gz",
            "payload_file_count": 1,
            "payload_total_bytes": len(payload),
            "payload_sha256": payload_sha256(records),
            "provenance_file_excluded_from_payload_hash": True,
            "files": records,
        }
        provenance_bytes = (
            json.dumps(provenance, ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8")
        return [
            (self._tar_info("README.md"), payload),
            (self._tar_info("BUILD_PROVENANCE.json"), provenance_bytes),
        ]

    def _write_custom_archive(self, entries, trailing=b"", corrupt_crc=False):
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for info, data in entries:
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        compressed = gzip.compress(tar_buffer.getvalue() + trailing, mtime=0)
        if corrupt_crc:
            damaged = bytearray(compressed)
            damaged[-8] ^= 0x01
            compressed = bytes(damaged)
        archive_path = self.base / "out/custom.tar.gz"
        archive_path.write_bytes(compressed)
        sidecar_path = Path(str(archive_path) + ".sha256")
        sidecar_path.write_text(
            f"{hashlib.sha256(compressed).hexdigest()}  {archive_path.name}\n",
            encoding="ascii",
        )
        return archive_path, sidecar_path

    def test_verifier_does_not_materialize_getmembers(self):
        archive = self.base / "out/stream.tar.gz"
        build_archive(self.root, archive, "3" * 40, 0)
        with patch("tarfile.TarFile.getmembers", side_effect=AssertionError("getmembers must not be used")):
            result = verify_archive(archive, Path(str(archive) + ".sha256"))
        self.assertEqual(result["payload_file_count"], 3)

    def test_rejects_oversized_pax_header_before_reading_it(self):
        entries = self._valid_tar_entries()
        entries[0] = (
            self._tar_info("README.md", pax_headers={"comment": "x" * 128}),
            entries[0][1],
        )
        archive, sidecar = self._write_custom_archive(entries)
        with patch("package_provenance.MAX_TAR_METADATA_BYTES", 16):
            with self.assertRaisesRegex(PackageSafetyError, "PAX header"):
                verify_archive(archive, sidecar)

    def test_rejects_pax_path_traversal_after_override(self):
        entries = self._valid_tar_entries()
        entries[0] = (
            self._tar_info("safe.txt", pax_headers={"path": "../escape.txt"}),
            entries[0][1],
        )
        archive, sidecar = self._write_custom_archive(entries)
        with self.assertRaises(PackageSafetyError):
            verify_archive(archive, sidecar)

    def test_rejects_duplicate_archive_members(self):
        entries = self._valid_tar_entries()
        entries.insert(1, (self._tar_info("README.md"), b"duplicate"))
        archive, sidecar = self._write_custom_archive(entries)
        with self.assertRaisesRegex(PackageSafetyError, "duplicate"):
            verify_archive(archive, sidecar)

    def test_rejects_case_colliding_archive_members(self):
        entries = self._valid_tar_entries()
        entries.insert(1, (self._tar_info("readme.md"), b"case collision"))
        archive, sidecar = self._write_custom_archive(entries)
        with self.assertRaisesRegex(PackageSafetyError, "case-colliding"):
            verify_archive(archive, sidecar)

    def test_rejects_nonzero_data_after_tar_end_marker(self):
        archive, sidecar = self._write_custom_archive(
            self._valid_tar_entries(), trailing=b"not-zero-trailing-data"
        )
        with self.assertRaisesRegex(PackageSafetyError, "non-zero data"):
            verify_archive(archive, sidecar)

    def test_rejects_gzip_crc_corruption_even_with_matching_sidecar(self):
        archive, sidecar = self._write_custom_archive(
            self._valid_tar_entries(), corrupt_crc=True
        )
        with self.assertRaises(PackageSafetyError):
            verify_archive(archive, sidecar)

    def test_rejects_truncated_gzip_stream(self):
        archive, sidecar = self._write_custom_archive(self._valid_tar_entries())
        damaged = archive.read_bytes()[:-4]
        archive.write_bytes(damaged)
        sidecar.write_text(
            f"{hashlib.sha256(damaged).hexdigest()}  {archive.name}\n",
            encoding="ascii",
        )
        with self.assertRaises(PackageSafetyError):
            verify_archive(archive, sidecar)

    def test_enforces_decompressed_stream_budget(self):
        archive, sidecar = self._write_custom_archive(self._valid_tar_entries())
        with patch("package_provenance.MAX_ARCHIVE_STREAM_BYTES", 1024):
            with self.assertRaisesRegex(PackageSafetyError, "decompressed archive stream"):
                verify_archive(archive, sidecar)

    def test_rejects_excessive_pax_header_count(self):
        entries = self._valid_tar_entries()
        entries[0] = (
            self._tar_info("README.md", pax_headers={"comment": "small"}),
            entries[0][1],
        )
        entries[1] = (
            self._tar_info("BUILD_PROVENANCE.json", pax_headers={"comment": "small"}),
            entries[1][1],
        )
        archive, sidecar = self._write_custom_archive(entries)
        with patch("package_provenance.MAX_ARCHIVE_HEADERS", 3):
            with self.assertRaisesRegex(PackageSafetyError, "header count"):
                verify_archive(archive, sidecar)

    def test_rejects_setuid_or_group_world_writable_modes(self):
        entries = self._valid_tar_entries()
        entries[0][0].mode = 0o4755
        archive, sidecar = self._write_custom_archive(entries)
        with self.assertRaisesRegex(PackageSafetyError, "unsafe mode"):
            verify_archive(archive, sidecar)

    def test_rejects_archive_parent_symlink(self):
        archive = self.base / "out/parent-link-test.tar.gz"
        build_archive(self.root, archive, "4" * 40, 0)
        alias_dir = self.base / "linked-out"
        try:
            alias_dir.symlink_to(self.base / "out", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks are unavailable on this runner")
        alias_archive = alias_dir / archive.name
        with self.assertRaises(PackageSafetyError):
            verify_archive(alias_archive, Path(str(alias_archive) + ".sha256"))


    def test_rejects_gnu_sparse_pax_map_before_sparse_processing(self):
        entries = self._valid_tar_entries()
        entries[0] = (
            self._tar_info("README.md", pax_headers={"GNU.sparse.map": "0,1"}),
            entries[0][1],
        )
        archive, sidecar = self._write_custom_archive(entries)
        with self.assertRaisesRegex(PackageSafetyError, "GNU sparse PAX"):
            verify_archive(archive, sidecar)


if __name__ == "__main__":
    unittest.main(verbosity=2)
