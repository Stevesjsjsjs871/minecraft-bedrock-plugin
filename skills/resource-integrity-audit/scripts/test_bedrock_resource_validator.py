import importlib.util,json,tempfile,unittest
from pathlib import Path
P=Path(__file__).with_name('bedrock_resource_validator.py'); s=importlib.util.spec_from_file_location('v',P); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_invalid_json(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'x.json').write_text('{'); self.assertIn('INVALID_JSON',[x['code'] for x in m.run(Path(d))['findings']])
 def test_manifest_dependency(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'BP').mkdir(); (Path(d)/'BP/manifest.json').write_text(json.dumps({'header':{'uuid':'a'},'dependencies':[{'uuid':'missing'}]})); self.assertIn('PACK_DEPENDENCY_UNRESOLVED',[x['code'] for x in m.run(Path(d))['findings']])
 def test_oversize_json(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'x.json').write_bytes(b' '*(m.MAX_JSON+1)); self.assertIn('JSON_TOO_LARGE',[x['code'] for x in m.run(Path(d))['findings']])
if __name__=='__main__': unittest.main()
