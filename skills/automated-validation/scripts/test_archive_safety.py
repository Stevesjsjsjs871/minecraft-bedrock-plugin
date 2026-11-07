from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / "skills" / "automated-validation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import archive_safety
import bedrock_audit


class ArchiveSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / "valid.zip"
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", '{"format_version":2}')
            zf.writestr("textures/test.txt", "small payload")

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_archive_reports_bounded_metadata(self):
        result = archive_safety.validate_zip_limits(self.archive)
        self.assertEqual(result["entry_count"], 2)
        self.assertGreater(result["compressed_bytes"], 0)
        self.assertGreater(result["uncompressed_bytes"], 0)

    def test_symlink_archive_is_rejected(self):
        link = self.root / "linked.zip"
        try:
            link.symlink_to(self.archive)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this platform")
        with self.assertRaisesRegex(ValueError, "symlink"):
            archive_safety.validate_zip_limits(link)

    def test_non_regular_file_is_rejected(self):
        with self.assertRaises(ValueError):
            archive_safety.validate_zip_limits(self.root)

    def test_invalid_zip_is_rejected(self):
        bad = self.root / "invalid.zip"
        bad.write_bytes(b"not a zip archive")
        with self.assertRaises(ValueError):
            archive_safety.validate_zip_limits(bad)

    def test_compressed_size_limit_is_checked_from_open_descriptor(self):
        with patch.object(archive_safety, "MAX_ARCHIVE_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "compressed size limit"):
                archive_safety.validate_zip_limits(self.archive)

    def test_member_count_limit_is_checked(self):
        with patch.object(archive_safety, "MAX_ARCHIVE_MEMBERS", 1):
            with self.assertRaisesRegex(ValueError, "member count"):
                archive_safety.validate_zip_limits(self.archive)

    def test_member_size_limit_is_checked(self):
        with patch.object(archive_safety, "MAX_MEMBER_BYTES", 2):
            with self.assertRaisesRegex(ValueError, "per-member limit"):
                archive_safety.validate_zip_limits(self.archive)

    def test_cumulative_size_limit_is_checked(self):
        with patch.object(archive_safety, "MAX_UNCOMPRESSED_BYTES", 5):
            with self.assertRaisesRegex(ValueError, "cumulative|declared uncompressed"):
                archive_safety.validate_zip_limits(self.archive)

    def test_swap_between_lstat_and_open_is_rejected(self):
        replacement = self.root / "replacement-before-open.zip"
        with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("replacement.txt", "different inode")
        real_open = os.open

        def replace_then_open(path, flags, *args, **kwargs):
            if Path(path) == self.archive:
                os.replace(replacement, self.archive)
            return real_open(path, flags, *args, **kwargs)

        with patch.object(archive_safety.os, "open", side_effect=replace_then_open):
            with self.assertRaisesRegex(ValueError, "path changed"):
                with archive_safety.open_bounded_zip(self.archive):
                    self.fail("the changed archive path must not be accepted")

    def test_open_reader_keeps_original_archive_after_path_replacement(self):
        replacement = self.root / "replacement.zip"
        with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("attacker.txt", "replacement archive")
        expected_hash = hashlib.sha256(self.archive.read_bytes()).hexdigest()

        with archive_safety.open_bounded_zip(self.archive) as (zf, metadata):
            os.replace(replacement, self.archive)
            self.assertIn("manifest.json", zf.namelist())
            self.assertNotIn("attacker.txt", zf.namelist())
            self.assertEqual(metadata["sha256"], expected_hash)

    def test_in_place_archive_mutation_is_detected_before_context_exit(self):
        with self.assertRaisesRegex(ValueError, "changed while its contents"):
            with archive_safety.open_bounded_zip(self.archive) as (zf, _):
                self.assertIn("manifest.json", zf.namelist())
                with self.archive.open("ab") as writer:
                    writer.write(b"concurrent mutation")

    def test_bedrock_audit_uses_the_pinned_archive_for_hash_and_member_reads(self):
        replacement = self.root / "replacement.zip"
        with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("intruder.txt", "must not replace the opened source")
        expected_hash = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        original_opener = bedrock_audit.open_bounded_zip

        @contextmanager
        def replace_path_after_open(path):
            with original_opener(path) as opened:
                os.replace(replacement, self.archive)
                yield opened

        with patch.object(bedrock_audit, "open_bounded_zip", replace_path_after_open):
            findings = []
            files, metadata = bedrock_audit.load_archive(str(self.archive), findings)

        self.assertTrue(metadata["archive_valid"])
        self.assertEqual(metadata["sha256"], expected_hash)
        self.assertIn("manifest.json", files)
        self.assertNotIn("intruder.txt", files)
        self.assertFalse(findings)


    def test_bedrock_audit_rejects_ambiguous_raw_member_paths_before_decompression(self):
        archive = self.root / "ambiguous-member.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("pack//manifest.json", "{}")
        findings = []
        with patch.object(zipfile.ZipFile, "testzip", side_effect=AssertionError("CRC pass must follow path preflight")):
            files, metadata = bedrock_audit.load_archive(str(archive), findings)
        self.assertFalse(metadata["archive_valid"])
        self.assertFalse(files)
        self.assertTrue(any(item["title"] == "Unsafe archive member path" for item in findings))

    def test_bedrock_audit_rejects_case_insensitive_duplicate_members(self):
        archive = self.root / "case-collision.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("Pack/manifest.json", "{}")
            zf.writestr("pack/manifest.json", "{}")
        findings = []
        files, metadata = bedrock_audit.load_archive(str(archive), findings)
        self.assertFalse(metadata["archive_valid"])
        self.assertFalse(files)
        self.assertTrue(any(item["title"] == "Duplicate archive path" for item in findings))

    def test_bedrock_audit_rejects_symlink_members(self):
        archive = self.root / "symlink-member.zip"
        link = zipfile.ZipInfo("pack/linked.json")
        link.create_system = 3
        link.external_attr = (0o120777 << 16)
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(link, "../outside.json")
        findings = []
        files, metadata = bedrock_audit.load_archive(str(archive), findings)
        self.assertFalse(metadata["archive_valid"])
        self.assertFalse(files)
        self.assertTrue(any(item["title"] == "Symlink archive member" for item in findings))

    def test_bedrock_audit_rejects_file_directory_collisions(self):
        archive = self.root / "file-directory-collision.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("pack", "file")
            zf.writestr("pack/manifest.json", "{}")
        findings = []
        files, metadata = bedrock_audit.load_archive(str(archive), findings)
        self.assertFalse(metadata["archive_valid"])
        self.assertFalse(files)
        self.assertTrue(any(item["title"] == "Archive file/directory path collision" for item in findings))

    def test_bedrock_audit_rejects_parent_and_dot_segments(self):
        for member in ("pack/../outside.json", "pack/./manifest.json", r"pack\manifest.json"):
            with self.subTest(member=member):
                archive = self.root / f"unsafe-{len(member)}.zip"
                with zipfile.ZipFile(archive, "w") as zf:
                    zf.writestr(member, "{}")
                findings = []
                files, metadata = bedrock_audit.load_archive(str(archive), findings)
                self.assertFalse(metadata["archive_valid"])
                self.assertFalse(files)
                self.assertTrue(any(item["title"] == "Unsafe archive member path" for item in findings))



class ZipNamespaceValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def _archive(self, entries):
        path = Path(self.temp.name) / f'namespace-{len(list(Path(self.temp.name).glob("namespace-*.zip")))}.zip'
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for name, payload, info in entries:
                if info is None:
                    zf.writestr(name, payload)
                else:
                    zf.writestr(info, payload)
        return path

    def test_explicit_directory_entries_and_nested_files_are_valid(self):
        archive = self._archive([
            ('behavior_pack/', '', None),
            ('behavior_pack/entities/', '', None),
            ('behavior_pack/entities/robot.json', '{}', None),
        ])
        with archive_safety.open_bounded_zip(archive) as (zf, _):
            rows = archive_safety.validate_zip_member_namespace(zf)
        self.assertEqual([row[2] for row in rows], [True, True, False])

    def test_archive_without_explicit_directory_entries_is_valid(self):
        archive = self._archive([('behavior_pack/manifest.json', '{}', None)])
        with archive_safety.open_bounded_zip(archive) as (zf, _):
            self.assertEqual(len(archive_safety.validate_zip_member_namespace(zf)), 1)

    def test_duplicate_member_is_rejected(self):
        archive = self._archive([('pack/a', '1', None), ('pack/a', '2', None)])
        with archive_safety.open_bounded_zip(archive) as (zf, _):
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                archive_safety.validate_zip_member_namespace(zf)

    def test_casefold_collision_is_rejected(self):
        archive = self._archive([('Pack/a', '1', None), ('pack/A', '2', None)])
        with archive_safety.open_bounded_zip(archive) as (zf, _):
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                archive_safety.validate_zip_member_namespace(zf)

    def test_unicode_normalization_collision_is_rejected(self):
        archive = self._archive([('pack/caf\u00e9.txt', '1', None), ('pack/cafe\u0301.txt', '2', None)])
        with archive_safety.open_bounded_zip(archive) as (zf, _):
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                archive_safety.validate_zip_member_namespace(zf)

    def test_file_directory_collision_is_rejected(self):
        archive = self._archive([('pack', 'file', None), ('pack/', '', None)])
        with archive_safety.open_bounded_zip(archive) as (zf, _):
            with self.assertRaisesRegex(ValueError, 'collision'):
                archive_safety.validate_zip_member_namespace(zf)

    def test_file_parent_collision_is_rejected(self):
        archive = self._archive([('pack', 'file', None), ('pack/child.txt', 'child', None)])
        with archive_safety.open_bounded_zip(archive) as (zf, _):
            with self.assertRaisesRegex(ValueError, 'collision'):
                archive_safety.validate_zip_member_namespace(zf)

    def test_symlink_and_special_file_are_rejected(self):
        link = zipfile.ZipInfo('pack/link')
        link.create_system = 3
        link.external_attr = (0o120777 << 16)
        archive = self._archive([('pack/link', '../outside', link)])
        with archive_safety.open_bounded_zip(archive) as (zf, _):
            with self.assertRaisesRegex(ValueError, 'symlink'):
                archive_safety.validate_zip_member_namespace(zf)
        device = zipfile.ZipInfo('pack/device')
        device.create_system = 3
        device.external_attr = (0o020600 << 16)
        archive = self._archive([('pack/device', '', device)])
        with archive_safety.open_bounded_zip(archive) as (zf, _):
            with self.assertRaisesRegex(ValueError, 'special'):
                archive_safety.validate_zip_member_namespace(zf)

    def test_backslash_and_absolute_paths_are_rejected(self):
        for name in ('..\\escape', '/absolute', 'C:/drive', '//server/share'):
            archive = self._archive([(name, 'x', None)])
            with archive_safety.open_bounded_zip(archive) as (zf, _):
                with self.assertRaises(ValueError):
                    archive_safety.validate_zip_member_namespace(zf)

    def test_malformed_zip_is_rejected_by_pinned_reader(self):
        malformed = Path(self.temp.name) / 'malformed.zip'
        malformed.write_bytes(b'PK\x03\x04broken-central-directory')
        with self.assertRaises(ValueError):
            archive_safety.open_bounded_zip(malformed).__enter__()

    def test_compression_ratio_limit_is_checked_before_decompression(self):
        archive = self._archive([('high-ratio.txt', 'A' * 10000, None)])
        with patch.object(archive_safety, 'MAX_COMPRESSION_RATIO', 10):
            with self.assertRaisesRegex(ValueError, 'compression ratio limit'):
                with archive_safety.open_bounded_zip(archive):
                    self.fail('high-ratio archive must be rejected before member reads')

    def test_invalid_utf8_member_name_is_rejected(self):
        malformed = Path(self.temp.name) / 'invalid-utf8.zip'
        with zipfile.ZipFile(malformed, 'w') as zf:
            zf.writestr('a.txt', 'x')
        data = bytearray(malformed.read_bytes())
        local = data.find(b'PK\x03\x04')
        central = data.find(b'PK\x01\x02')
        self.assertGreaterEqual(local, 0); self.assertGreaterEqual(central, 0)
        local_name_len = int.from_bytes(data[local+26:local+28], 'little')
        central_name_len = int.from_bytes(data[central+28:central+30], 'little')
        self.assertGreater(local_name_len, 0); self.assertGreater(central_name_len, 0)
        data[local+30] = 0xFF
        data[local+6:local+8] = (int.from_bytes(data[local+6:local+8], 'little') | 0x800).to_bytes(2,'little')
        central_name = central+46
        data[central_name] = 0xFF
        data[central+8:central+10] = (int.from_bytes(data[central+8:central+10], 'little') | 0x800).to_bytes(2,'little')
        malformed.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'central directory'):
            with archive_safety.open_bounded_zip(malformed):
                self.fail('invalid UTF-8 filename must be rejected')

if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main(verbosity=2)
