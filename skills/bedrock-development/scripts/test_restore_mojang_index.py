from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
import unittest

from restore_mojang_index import RestoreIndexError, restore_index


class RestoreMojangIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.archive = self.root / "bedrock-samples-v1.26.50.4-full.zip"
        self.metadata = self.root / "INDEX_METADATA.json"
        self.indexer = Path(__file__).with_name("index_mojang_samples.py")
        self.output = self.root / "mojang-samples-index.json.gz"
        sample = json.dumps({"minecraft:item": {"description": {"identifier": "demo:sample"}}}).encode("utf-8")
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("behavior_pack/items/example.json", sample)
        self.metadata_data = {
            "source_archive": self.archive.name,
            "source_release_tag": "v1.26.50.4",
            "source_asset_name": self.archive.name,
            "source_asset_url": f"https://github.com/Mojang/bedrock-samples/releases/download/v1.26.50.4/{self.archive.name}",
            "target_version": "1.26.50.4",
            "zip_sha256": hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            "entry_count": 1,
            "indexed_count": 1,
            "declared_uncompressed_bytes": len(sample),
            "category_counts": {"item": 1},
        }
        self.write_metadata()

    def tearDown(self):
        self.tmp.cleanup()

    def write_metadata(self):
        self.metadata.write_text(json.dumps(self.metadata_data), encoding="utf-8")

    def test_restores_and_verifies_index_from_exact_archive(self):
        result = restore_index(self.archive, self.metadata, self.indexer, self.output)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["entry_count"], 1)
        self.assertEqual(result["indexed_count"], 1)
        self.assertTrue(self.output.is_file())
        self.assertEqual(len(result["index_sha256"]), 64)

    def test_rejects_archive_hash_mismatch(self):
        self.metadata_data["zip_sha256"] = "0" * 64
        self.write_metadata()
        with self.assertRaises(RestoreIndexError):
            restore_index(self.archive, self.metadata, self.indexer, self.output)
        self.assertFalse(self.output.exists())

    def test_rejects_archive_filename_mismatch(self):
        self.metadata_data["source_archive"] = "another.zip"
        self.write_metadata()
        with self.assertRaises(RestoreIndexError):
            restore_index(self.archive, self.metadata, self.indexer, self.output)

    def test_rejects_index_statistics_mismatch(self):
        self.metadata_data["indexed_count"] = 2
        self.write_metadata()
        with self.assertRaises(RestoreIndexError):
            restore_index(self.archive, self.metadata, self.indexer, self.output)
        self.assertFalse(self.output.exists())

    def test_rejects_category_mismatch(self):
        self.metadata_data["category_counts"] = {"geometry": 1}
        self.write_metadata()
        with self.assertRaises(RestoreIndexError):
            restore_index(self.archive, self.metadata, self.indexer, self.output)
        self.assertFalse(self.output.exists())

    def test_refuses_output_overwrite(self):
        self.output.write_bytes(b"existing")
        with self.assertRaises(RestoreIndexError):
            restore_index(self.archive, self.metadata, self.indexer, self.output)
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_rejects_symlink_archive(self):
        link = self.root / "linked.zip"
        try:
            link.symlink_to(self.archive)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable on this runner")
        self.metadata_data["source_archive"] = link.name
        self.metadata_data["source_asset_name"] = link.name
        self.metadata_data["source_asset_url"] = f"https://github.com/Mojang/bedrock-samples/releases/download/v1.26.50.4/{link.name}"
        self.write_metadata()
        with self.assertRaises(RestoreIndexError):
            restore_index(link, self.metadata, self.indexer, self.output)

    def test_rejects_generated_index_hash_mismatch(self):
        self.metadata_data["index_sha256"] = "0" * 64
        self.write_metadata()
        with self.assertRaises(RestoreIndexError):
            restore_index(self.archive, self.metadata, self.indexer, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
