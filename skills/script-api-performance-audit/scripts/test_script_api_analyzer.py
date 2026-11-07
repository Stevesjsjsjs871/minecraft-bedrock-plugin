import importlib.util,json,tempfile,unittest
from pathlib import Path
P=Path(__file__).with_name('script_api_analyzer.py'); s=importlib.util.spec_from_file_location('a',P); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_import_and_subscription(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'x.js').write_text("// import '@minecraft/no'\nimport { world } from '@minecraft/server';\nworld.afterEvents.playerSpawn.subscribe(()=>{});")
   r=m.analyze(p); self.assertEqual(len(r['script_api_imports']),1); self.assertEqual(len(r['event_subscriptions']),1)
 def test_manifest_dependency(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'manifest.json').write_text(json.dumps({'dependencies':[{'module_name':'@minecraft/server','version':'2.0.0'}]})); self.assertEqual(m.analyze(p)['manifest_script_dependencies'][0]['version'],'2.0.0')
 def test_oversize(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'x.ts').write_bytes(b'x'*(m.MAX_FILE+1))
   with self.assertRaises(ValueError): m.analyze(p)
 def test_comments_and_strings(self): self.assertNotIn('subscribe',m.strip_comments_strings("const x='subscribe('; // subscribe()\n"))
if __name__=='__main__': unittest.main()
