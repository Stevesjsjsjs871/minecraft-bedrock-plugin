from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name("index_mojang_samples.py")
SPEC = importlib.util.spec_from_file_location("index_mojang_samples", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(mod)


class IndexMojangSamplesTests(unittest.TestCase):
    def test_rejects_path_traversal_and_windows_separators(self):
        for path in ["../escape.json", "behavior_pack\\items\\x.json", "/absolute.json",
                     "C:/evil.json", "behavior_pack//items/x.json"]:
            self.assertFalse(mod.safe_member_path(path), path)

    def test_accepts_normal_sample_paths(self):
        for path in ["behavior_pack/manifest.json", "resource_pack/models/entity/pig.geo.json",
                     "documentation/Item.html"]:
            self.assertTrue(mod.safe_member_path(path), path)

    def test_indexes_small_archive_without_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "samples.zip"
            output = root / "index.json"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("behavior_pack/items/example.json", json.dumps({
                    "format_version": "1.26.30",
                    "minecraft:item": {"description": {"identifier": "demo:example"}}
                }))
                z.writestr("resource_pack/models/entity/pig.geo.json", json.dumps({
                    "minecraft:geometry": [{"description": {"identifier": "geometry.demo_pig"}}]
                }))
                z.writestr("behavior_pack/../escape.json", "{}")
            # Unsafe archives fail closed before member payload reads.
            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = [str(SCRIPT), str(archive), "--output", str(output)]
                self.assertEqual(mod.main(), 2)
            finally:
                __import__("sys").argv = old_argv
            self.assertFalse(output.exists())

    def test_index_creates_searchable_hash_and_identifier_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "samples.zip"
            output = root / "index.json"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("behavior_pack/items/example.json", json.dumps({
                    "format_version": "1.26.30",
                    "minecraft:item": {"description": {"identifier": "demo:example"}}
                }))
                z.writestr("resource_pack/models/entity/pig.geo.json", json.dumps({
                    "minecraft:geometry": [{"description": {"identifier": "geometry.demo_pig"}}]
                }))
                z.writestr("documentation/Item.html", "<h1>Item docs</h1>")
            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = [str(SCRIPT), str(archive), "--output", str(output)]
                self.assertEqual(mod.main(), 0)
            finally:
                __import__("sys").argv = old_argv
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["archive_stats"]["indexed_count"], 3)
            item = next(x for x in data["entries"] if x["path"].endswith("example.json"))
            self.assertIn("demo:example", item["identifiers"])
            self.assertEqual(len(item["sha256"]), 64)
            self.assertTrue(data["index_policy"]["no_extraction"])

    def test_rejects_too_many_index_files_argument(self):
        old_argv = __import__("sys").argv
        try:
            __import__("sys").argv = [str(SCRIPT), "unused.zip", "--output", "unused.json", "--max-files", "40000"]
            self.assertEqual(mod.main(), 2)
        finally:
            __import__("sys").argv = old_argv



    def test_indexer_writes_gzip_index_when_requested(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "samples.zip"
            output = root / "index.json.gz"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("behavior_pack/items/example.json", json.dumps({
                    "minecraft:item": {"description": {"identifier": "demo:example"}}
                }))
            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = [str(SCRIPT), str(archive), "--output", str(output)]
                self.assertEqual(mod.main(), 0)
            finally:
                __import__("sys").argv = old_argv
            with gzip.open(output, "rt", encoding="utf-8") as stream:
                data = json.load(stream)
            self.assertEqual(data["archive_stats"]["indexed_count"], 1)
            self.assertTrue(data["entries"][0]["json_parsed"])

if __name__ == "__main__":
    unittest.main()
