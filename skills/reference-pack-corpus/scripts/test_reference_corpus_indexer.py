import json, tempfile, unittest, zipfile
from pathlib import Path
from reference_corpus_indexer import build_index, safe_path

class ReferenceCorpusIndexerTests(unittest.TestCase):
    def test_path_safety(self):
        for bad in ('../escape', '/absolute', 'C:/drive', 'a\\b', 'a//b', 'a/./b'):
            self.assertFalse(safe_path(bad), bad)
        self.assertTrue(safe_path('pack/manifest.json'))

    def test_manifest_summary_and_api_versions(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'sample.zip'
            manifest = {'header': {'name':'Demo','version':[1,2,3],'min_engine_version':[1,21,0]},
                        'modules':[{'type':'script','language':'javascript','version':[1,0,0]}],
                        'dependencies':[{'module_name':'@minecraft/server','version':'2.0.0'},
                                        {'uuid':'1234','version':[1,2,3]}]}
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('BP/manifest.json', json.dumps(manifest))
                z.writestr('BP/scripts/main.js', 'world.sendMessage("hi")')
            result=build_index(p)
            self.assertEqual(result['manifests'][0]['script_api_dependencies'][0]['version'],'2.0.0')
            self.assertEqual(result['manifests'][0]['min_engine_version'],[1,21,0])
            self.assertFalse(result['safety']['extraction_performed'])

    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.zip'
            with zipfile.ZipFile(p,'w') as z: z.writestr('../escape.json','{}')
            with self.assertRaises(ValueError): build_index(p)

    def test_duplicate_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'dup.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('pack/a.txt','1'); z.writestr('pack/a.txt','2')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                build_index(p)


class HardenedCorpusIndexerTests(unittest.TestCase):
    def make_archive(self, td, entries, name='fixture.zip'):
        path=Path(td)/name
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as zf:
            for entry in entries:
                if len(entry)==2: zf.writestr(entry[0],entry[1])
                else: zf.writestr(entry[2],entry[1])
        return path

    def test_explicit_directory_entries_are_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            path=self.make_archive(td,[('behavior_pack/',''),('behavior_pack/entities/',''),('behavior_pack/manifest.json','{}')])
            result=build_index(path)
            self.assertEqual(result['archive_stats']['directory_count'],2)
            self.assertEqual(result['safety']['crc_test'],'PASS')

    def test_duplicate_paths_are_rejected_not_merely_reported(self):
        with tempfile.TemporaryDirectory() as td:
            path=self.make_archive(td,[('pack/a','1'),('pack/a','2')])
            with self.assertRaisesRegex(ValueError,'duplicate'): build_index(path)

    def test_case_and_unicode_collisions_are_rejected(self):
        for entries in ([('Pack/a','1'),('pack/A','2')], [('café','1'),('cafe\u0301','2')]):
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as td:
                path=self.make_archive(td,entries)
                with self.assertRaisesRegex(ValueError,'duplicate'): build_index(path)

    def test_file_directory_conflicts_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path=self.make_archive(td,[('pack','file'),('pack/child','child')])
            with self.assertRaisesRegex(ValueError,'collision'): build_index(path)

    def test_same_pinned_descriptor_supplies_hash_and_member_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path=self.make_archive(td,[('manifest.json','{"header":{"name":"original"}}')])
            replacement=Path(td)/'replacement.zip'
            self.make_archive(td,[('manifest.json','{"header":{"name":"replacement"}}')],replacement.name)
            original_hash=__import__('hashlib').sha256(path.read_bytes()).hexdigest()
            from unittest.mock import patch
            import archive_safety
            real_open=archive_safety.open_bounded_zip
            from contextlib import contextmanager
            @contextmanager
            def replace_after_open(p):
                with real_open(p) as opened:
                    import os
                    os.replace(replacement,path)
                    yield opened
            with patch('reference_corpus_indexer.open_bounded_zip',replace_after_open):
                result=build_index(path)
            self.assertEqual(result['archive_sha256'],original_hash)
            self.assertEqual(result['manifests'][0]['name'],'original')

    def test_symlink_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            zi=zipfile.ZipInfo('pack/link');zi.create_system=3;zi.external_attr=(0o120777<<16)
            path=self.make_archive(td,[('ignored','../outside',zi)])
            with self.assertRaisesRegex(ValueError,'symlink'):build_index(path)

if __name__ == '__main__': unittest.main()
