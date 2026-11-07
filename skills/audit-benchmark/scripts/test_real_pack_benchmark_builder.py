import importlib.util,tempfile,unittest,zipfile
from pathlib import Path
P=Path(__file__).with_name('real_pack_benchmark_builder.py'); s=importlib.util.spec_from_file_location('b',P); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_manifest_inventory(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.mcpack'
   with zipfile.ZipFile(p,'w') as z:z.writestr('manifest.json','{"header":{"uuid":"u","name":"Pack"},"modules":[{"type":"resources"}]}')
   self.assertEqual(m.inventory(p)['entries'][0]['manifest']['uuid'],'u')
 def test_traversal(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.mcpack'
   with zipfile.ZipFile(p,'w') as z:z.writestr('../bad','x')
   with self.assertRaises(ValueError):m.inventory(p)
 def test_extension(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.txt';p.write_text('x')
   with self.assertRaises(ValueError):m.inventory(p)

class DirectoryAndNamespaceTests(unittest.TestCase):
 def make(self, entries):
  td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
  p=Path(td.name)/'sample.mcpack'
  with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:
   for name,data in entries: z.writestr(name,data)
  return p
 def test_explicit_directory_entries_are_supported(self):
  p=self.make([('behavior_pack/',''),('behavior_pack/entities/',''),('behavior_pack/manifest.json','{}')])
  result=m.inventory(p)
  self.assertEqual(result['directory_count'],2)
  self.assertEqual(result['file_count'],1)
 def test_nested_paths_without_directory_entries_are_supported(self):
  p=self.make([('behavior_pack/entities/robot.json','{}')])
  self.assertEqual(m.inventory(p)['file_count'],1)
 def test_duplicate_paths_are_rejected(self):
  p=self.make([('a.txt','1'),('a.txt','2')])
  with self.assertRaisesRegex(ValueError,'duplicate'): m.inventory(p)
 def test_file_directory_conflict_is_rejected(self):
  p=self.make([('pack','file'),('pack/child','child')])
  with self.assertRaisesRegex(ValueError,'collision'): m.inventory(p)
 def test_case_unicode_collisions_are_rejected(self):
  p=self.make([('Pack/A','1'),('pack/a','2')])
  with self.assertRaisesRegex(ValueError,'duplicate'): m.inventory(p)
 def test_symlink_is_rejected(self):
  td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup); p=Path(td.name)/'link.mcpack'
  zi=zipfile.ZipInfo('link'); zi.create_system=3; zi.external_attr=(0o120777<<16)
  with zipfile.ZipFile(p,'w') as z:z.writestr(zi,'../outside')
  with self.assertRaisesRegex(ValueError,'symlink'):m.inventory(p)
 def test_malformed_zip_is_rejected(self):
  td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup); p=Path(td.name)/'bad.mcpack';p.write_bytes(b'bad')
  with self.assertRaises(ValueError):m.inventory(p)

if __name__=='__main__':unittest.main()
