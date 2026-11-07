import importlib.util, pathlib, unittest, tempfile, zipfile, os
from unittest import mock
p=pathlib.Path(__file__).with_name('reference_pack_audit.py')
spec=importlib.util.spec_from_file_location('reference_pack_audit',p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class TestCommentParser(unittest.TestCase):
 def test_comments_outside_strings(self):
  self.assertEqual(m.strip_json_comments('{\n//x\n"url":"https://a/b",/*z*/"v":1\n}'),'{\n\n"url":"https://a/b",\n"v":1\n}')
 def test_region_markers(self): self.assertIn('"a":1',m.strip_json_comments('#region hi\n{"a":1}\n#endregion'))
 def test_comment_marker_in_string_preserved(self): self.assertEqual(m.strip_json_comments('{"s":"// not a comment"}'),'{"s":"// not a comment"}')
 def test_duplicate_key_rejected(self):
  with self.assertRaises(ValueError): m.parse_json_bytes(b'{"x":1,"x":2}')
 def test_strict_json(self):
  obj,mode=m.parse_json_bytes(b'{"x":1}'); self.assertEqual(obj,{'x':1}); self.assertEqual(mode,'strict')
 def test_comment_json(self):
  obj,mode=m.parse_json_bytes(b'{// hi\n"x":1}'); self.assertEqual(obj,{'x':1}); self.assertEqual(mode,'comment-aware')
 def test_unsafe_paths(self):
  for name in ('../bad','/abs','a//b','a/./b','a/../b',r'a\\b','C:/absolute',''):
   with self.subTest(name=name): self.assertTrue(m.unsafe_name(name))
  self.assertFalse(m.unsafe_name('BP/manifest.json'))
 def test_zip_audit_success_and_manifest(self):
  with tempfile.TemporaryDirectory() as td:
   zpath=pathlib.Path(td)/'ok.zip'
   with zipfile.ZipFile(zpath,'w') as z: z.writestr('manifest.json','{\"header\":{\"name\":\"fixture\",\"version\":[1,0,0]}}')
   r=m.audit(str(zpath)); self.assertEqual(r['status'],'PASS'); self.assertEqual(len(r['manifests']),1)
 def test_zip_audit_rejects_ambiguous_member_paths(self):
  for member in ('a//b.json','a/./b.json',r'a\\b.json'):
   with self.subTest(member=member), tempfile.TemporaryDirectory() as td:
    zpath=pathlib.Path(td)/'unsafe.zip'
    with zipfile.ZipFile(zpath,'w') as z: z.writestr(member,'{}')
    report=m.audit(zpath)
    self.assertEqual(report['status'],'FAIL')
    self.assertTrue(report['unsafe_paths'])
 def test_zip_audit_rejects_case_colliding_names(self):
  with tempfile.TemporaryDirectory() as td:
   zpath=pathlib.Path(td)/'case-collision.zip'
   with zipfile.ZipFile(zpath,'w') as z:
    z.writestr('Pack/manifest.json','{}'); z.writestr('pack/manifest.json','{}')
   report=m.audit(zpath)
   self.assertEqual(report['status'],'FAIL')
   self.assertEqual(len(report['duplicate_paths']),1)
 def test_zip_audit_rejects_file_directory_collision(self):
  with tempfile.TemporaryDirectory() as td:
   zpath=pathlib.Path(td)/'collision.zip'
   with zipfile.ZipFile(zpath,'w') as z:
    z.writestr('a','x'); z.writestr('a/b.json','{}')
   report=m.audit(zpath)
   self.assertEqual(report['status'],'FAIL')
   self.assertTrue(any('collision' in item for item in report['unsafe_paths']))
 def test_zip_audit_rejects_symlink_archive_path(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td); actual=root/'real.zip'; link=root/'link.zip'
   with zipfile.ZipFile(actual,'w') as z: z.writestr('manifest.json','{}')
   try: link.symlink_to(actual)
   except (OSError, NotImplementedError): self.skipTest('symlinks unavailable')
   result=m.audit(link)
   self.assertEqual(result['status'],'FAIL')
 def test_zip_audit_duplicate_paths_fails(self):
  with tempfile.TemporaryDirectory() as td:
   zpath=pathlib.Path(td)/'dup.zip'
   with zipfile.ZipFile(zpath,'w') as z:
    z.writestr('a.json','{}'); z.writestr('a.json','{}')
   r=m.audit(str(zpath)); self.assertEqual(r['status'],'FAIL'); self.assertTrue(r['duplicate_paths'])
 def test_zip_audit_preflights_size_before_integrity_scan(self):
  with tempfile.TemporaryDirectory() as td:
   zpath=pathlib.Path(td)/'large.zip'
   with zipfile.ZipFile(zpath,'w') as z: z.writestr('large.bin',b'x'*2048)
   with mock.patch.object(m,'MAX_MEMBER',32), mock.patch.object(zipfile.ZipFile,'testzip',side_effect=AssertionError('testzip must not run before metadata preflight')):
    result=m.audit(zpath)
   self.assertEqual(result['status'],'BLOCKED')
   self.assertTrue(any('size limit' in item for item in result['zip_errors']))
if __name__=='__main__': unittest.main()
