from __future__ import annotations
import gzip, json, tempfile, unittest
from pathlib import Path
import check_skills_package as checker
class SkillsPackageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); (self.root/'.codex-plugin').mkdir(); sample=self.root/'skills/bedrock-development/references/mojang-samples-1.26.50.4'; sample.mkdir(parents=True)
  for n in ('bedrock-engineer-core','skills-first-execution','skills-only-maintenance','geometry-uv-engine','visual-resource-pipeline'):
   d=self.root/'skills'/n; d.mkdir(parents=True,exist_ok=True); (d/'SKILL.md').write_text(f'---\nname: {n}\ndescription: Test skill {n}.\n---\n')
  (self.root/'skills/geometry-uv-engine/scripts').mkdir(parents=True); (self.root/'skills/visual-resource-pipeline/scripts').mkdir(parents=True)
  (self.root/'skills/geometry-uv-engine/scripts/geometry_engine.py').write_text('def analyze_geometry(): pass\n# duplicate JSON key UV_OUT_OF_BOUNDS UV_OVERLAP --geometry-identifier\n'); (self.root/'skills/geometry-uv-engine/scripts/test_geometry_engine.py').write_text('# tests\n')
  (self.root/'skills/geometry-uv-engine/scripts/uv_template_engine.py').write_text('def extract_regions(): pass\ndef render_template(): pass\ndef encode_png(): pass\nmax_pixels xb\n'); (self.root/'skills/geometry-uv-engine/scripts/test_uv_template_engine.py').write_text('# tests\n')
  (self.root/'skills/geometry-uv-engine/scripts/geometry_engine.py').write_text('def analyze_geometry(): pass\n# duplicate JSON key UV_OUT_OF_BOUNDS UV_OVERLAP --geometry-identifier\n'); (self.root/'skills/geometry-uv-engine/scripts/test_geometry_engine.py').write_text('# tests\n'); (self.root/'skills/geometry-uv-engine/scripts/png_engine.py').write_text('# png engine\n'); (self.root/'skills/visual-resource-pipeline/scripts/png_engine.py').write_text('# png engine\n'); (self.root/'skills/visual-resource-pipeline/scripts/test_png_engine.py').write_text('# tests\n')
  iface={'defaultPrompt':['Create a Bedrock add-on safely.']}; rm={'name':checker.EXPECTED_NAME,'version':'1.5.10','skills':'./skills','extensions':{'com.openai':{'interface':iface}}}; cm={'name':checker.EXPECTED_NAME,'version':'1.5.10','skills':'./skills','interface':iface}
  (self.root/'plugin.json').write_text(json.dumps(rm)); (self.root/'.codex-plugin/plugin.json').write_text(json.dumps(cm)); (self.root/'VERSION').write_text('1.5.10\n'); (self.root/'README.md').write_text('# Minecraft Bedrock Engineer — 1.5.10\n\nSkills-and-instructions-only plugin. It does not use MCP.\n')
  (sample/'INDEX_METADATA.json').write_text(json.dumps({'indexed_count':2}))
  with gzip.open(sample/'mojang-samples-index.json.gz','wb') as f:f.write(json.dumps({'entries':[{},{}]}).encode())
 def tearDown(self):self.tmp.cleanup()
 def by_id(self,r,k):return next(x for x in r['checks'] if x['id']==k)
 def test_valid_package_passes(self):self.assertEqual(checker.check(self.root)['status'],'PASS')
 def test_version_mismatch_fails(self):(self.root/'VERSION').write_text('1.5.9');self.assertEqual(self.by_id(checker.check(self.root),'version-parity')['status'],'FAIL')
 def test_prompt_mismatch_fails(self):
  p=self.root/'.codex-plugin/plugin.json';d=json.loads(p.read_text());d['interface']['defaultPrompt']=['different'];p.write_text(json.dumps(d));self.assertEqual(self.by_id(checker.check(self.root),'default-prompt-parity')['status'],'FAIL')
 def test_mcp_config_rejected(self):(self.root/'.mcp.json').write_text('{}');self.assertEqual(self.by_id(checker.check(self.root),'skills-only-boundary')['status'],'FAIL')
 def test_obsolete_cloudflare_rejected(self):(self.root/'cloudflare').mkdir();self.assertEqual(self.by_id(checker.check(self.root),'obsolete-deployment')['status'],'FAIL')
 def test_stale_tool_invocation_rejected(self):
  p=self.root/'skills/skills-only-maintenance/SKILL.md';p.write_text('---\nname: skills-only-maintenance\ndescription: Useful description.\n---\ncall `create_addon_project` now\n');self.assertEqual(self.by_id(checker.check(self.root),'skill-tool-boundary')['status'],'FAIL')
 def test_duplicate_skill_name_rejected(self):
  p=self.root/'skills/skills-only-maintenance/SKILL.md';p.write_text('---\nname: bedrock-engineer-core\ndescription: duplicate\n---\n');self.assertEqual(self.by_id(checker.check(self.root),'skill-inventory')['status'],'FAIL')
 def test_missing_frontmatter_rejected(self):(self.root/'skills/skills-only-maintenance/SKILL.md').write_text('# missing');self.assertEqual(self.by_id(checker.check(self.root),'skill-inventory')['status'],'FAIL')
 def test_bad_gzip_rejected(self):(self.root/'skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz').write_bytes(b'not gzip');self.assertEqual(self.by_id(checker.check(self.root),'mojang-index-integrity')['status'],'FAIL')
 def test_wrong_readme_version_fails(self):(self.root/'README.md').write_text('# Minecraft Bedrock Engineer — 1.5.1\nSkills-and-instructions-only. It does not use MCP.');self.assertEqual(self.by_id(checker.check(self.root),'readme-version')['status'],'FAIL')
 def test_missing_png_tests_fails(self):(self.root/'skills/visual-resource-pipeline/scripts/test_png_engine.py').unlink();self.assertEqual(self.by_id(checker.check(self.root),'required-files')['status'],'FAIL')
 def test_missing_uv_template_tests_fails(self):(self.root/'skills/geometry-uv-engine/scripts/test_uv_template_engine.py').unlink();self.assertEqual(self.by_id(checker.check(self.root),'required-files')['status'],'FAIL')
if __name__=='__main__':unittest.main(verbosity=2)
