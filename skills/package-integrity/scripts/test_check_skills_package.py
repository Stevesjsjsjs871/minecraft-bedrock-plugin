from __future__ import annotations
import csv, gzip, hashlib, json, tempfile, unittest
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
  transfer=self.root/'skills/reference-texture-transfer'; (transfer/'scripts').mkdir(parents=True); (transfer/'SKILL.md').write_text('---\nname: reference-texture-transfer\ndescription: Transfer verified reference texture crops.\n---\n'); (transfer/'scripts/reference_transfer.py').write_text('def transfer(): pass\ndef decode_png_rgba(): pass\nallow_uv_overlap MAX_TEXEL_WRITES _exclusive_write sha256 geometry_identifier\n'); (transfer/'scripts/test_reference_transfer.py').write_text('# tests\n')
  iface={'defaultPrompt':['Create a Bedrock add-on safely.']}; rm={'name':checker.EXPECTED_NAME,'version':'1.5.10','skills':'./skills','extensions':{'com.openai':{'interface':iface}}}; cm={'name':checker.EXPECTED_NAME,'version':'1.5.10','skills':'./skills','interface':iface}
  (self.root/'plugin.json').write_text(json.dumps(rm)); (self.root/'.codex-plugin/plugin.json').write_text(json.dumps(cm)); (self.root/'VERSION').write_text('1.5.10\n'); (self.root/'README.md').write_text('# Minecraft Bedrock Engineer — 1.5.10\n\nSkills-and-instructions-only plugin. It does not use MCP.\n')
  (sample/'INDEX_METADATA.json').write_text(json.dumps({'indexed_count':2}))
  with gzip.open(sample/'mojang-samples-index.json.gz','wb') as f:f.write(json.dumps({'entries':[{},{}]}).encode())
  self.write_script_registry()
 def write_script_registry(self):
  fields=['path','sha256','level_1_discovery','level_2_syntax','level_3_dependencies','level_4_runtime','level_5_functional','level_6_plugin_integration']
  rows=[]
  for path in sorted(self.root.rglob('*.py')):
   if path.is_file():
    rows.append({'path':path.relative_to(self.root).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
     'level_1_discovery':'PRESENT','level_2_syntax':'SYNTAX_OK','level_3_dependencies':'DEPENDENCIES_OK',
     'level_4_runtime':'NOT_TESTED','level_5_functional':'NOT_TESTED','level_6_plugin_integration':'NOT_TESTED'})
  with (self.root/'SCRIPT_EXECUTION_REGISTRY.csv').open('w',encoding='utf-8',newline='') as stream:
   writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
 def tearDown(self):self.tmp.cleanup()
 def by_id(self,r,k):return next(x for x in r['checks'] if x['id']==k)
 def test_valid_package_passes(self):self.assertEqual(checker.check(self.root)['status'],'PASS')
 def test_version_mismatch_fails(self):(self.root/'VERSION').write_text('1.5.9');self.assertEqual(self.by_id(checker.check(self.root),'version-parity')['status'],'FAIL')
 def test_prompt_mismatch_fails(self):
  p=self.root/'.codex-plugin/plugin.json';d=json.loads(p.read_text());d['interface']['defaultPrompt']=['different'];p.write_text(json.dumps(d));self.assertEqual(self.by_id(checker.check(self.root),'default-prompt-parity')['status'],'FAIL')
 def test_mcp_config_rejected(self):(self.root/'.mcp.json').write_text('{}');self.assertEqual(self.by_id(checker.check(self.root),'skills-only-boundary')['status'],'FAIL')
 def test_nested_renamed_connector_config_rejected(self):
  config=self.root/'skills/creator-tools-bridge/references/connector-profile.json';config.parent.mkdir(parents=True)
  config.write_text(json.dumps({'profiles':[{'name':'local','mcpServers':{'creator-tools':{'command':'python','args':['bridge.py']}}}]}))
  result=checker.check(self.root)
  self.assertEqual(self.by_id(result,'skills-only-boundary')['status'],'FAIL')
  self.assertIn('connector-profile.json',self.by_id(result,'skills-only-boundary')['message'])
 def test_renamed_python_protocol_adapter_rejected(self):
  adapter=self.root/'skills/creator-tools-bridge/scripts/renamed_protocol_adapter.py';adapter.parent.mkdir(parents=True)
  source = 'import json\nCONTENT_LENGTH = "Content-Length"\ndef handle_message(message):\n    return {"jsonrpc": "2.0", "result": message}\n'
  adapter.write_text(source)
  self.write_script_registry()
  result=checker.check(self.root,strict_skills_only=True)
  self.assertEqual(self.by_id(result,'skills-only-boundary')['status'],'FAIL')
  self.assertIn('renamed_protocol_adapter.py',self.by_id(result,'skills-only-boundary')['message'])
 def test_empty_cloudflare_directory_is_ignored(self):
  (self.root/'cloudflare').mkdir()
  self.assertEqual(self.by_id(checker.check(self.root),'obsolete-deployment')['status'],'PASS')
 def test_obsolete_cloudflare_files_rejected(self):
  d=self.root/'cloudflare';d.mkdir();(d/'wrangler.toml').write_text('name = "old"')
  self.assertEqual(self.by_id(checker.check(self.root),'obsolete-deployment')['status'],'FAIL')
 def test_stale_tool_invocation_rejected(self):
  p=self.root/'skills/skills-only-maintenance/SKILL.md';p.write_text('---\nname: skills-only-maintenance\ndescription: Useful description.\n---\ncall `create_addon_project` now\n');self.assertEqual(self.by_id(checker.check(self.root),'skill-tool-boundary')['status'],'FAIL')
 def test_duplicate_skill_name_rejected(self):
  p=self.root/'skills/skills-only-maintenance/SKILL.md';p.write_text('---\nname: bedrock-engineer-core\ndescription: duplicate\n---\n');self.assertEqual(self.by_id(checker.check(self.root),'skill-inventory')['status'],'FAIL')
 def test_missing_frontmatter_rejected(self):(self.root/'skills/skills-only-maintenance/SKILL.md').write_text('# missing');self.assertEqual(self.by_id(checker.check(self.root),'skill-inventory')['status'],'FAIL')
 def test_bad_gzip_rejected(self):(self.root/'skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz').write_bytes(b'not gzip');self.assertEqual(self.by_id(checker.check(self.root),'mojang-index-integrity')['status'],'FAIL')
 def test_wrong_readme_version_fails(self):(self.root/'README.md').write_text('# Minecraft Bedrock Engineer — 1.5.1\nSkills-and-instructions-only. It does not use MCP.');self.assertEqual(self.by_id(checker.check(self.root),'readme-version')['status'],'FAIL')
 def test_missing_png_tests_fails(self):(self.root/'skills/visual-resource-pipeline/scripts/test_png_engine.py').unlink();self.assertEqual(self.by_id(checker.check(self.root),'required-files')['status'],'FAIL')
 def test_missing_uv_template_tests_fails(self):(self.root/'skills/geometry-uv-engine/scripts/test_uv_template_engine.py').unlink();self.assertEqual(self.by_id(checker.check(self.root),'required-files')['status'],'FAIL')
 def test_reference_transfer_missing_script_fails(self):(self.root/'skills/reference-texture-transfer/scripts/reference_transfer.py').unlink();self.assertEqual(self.by_id(checker.check(self.root),'required-files')['status'],'FAIL')
 def test_reference_transfer_legacy_import_fails(self):
  p=self.root/'skills/reference-texture-transfer/scripts/reference_transfer.py';p.write_text('from server import legacy\ndef transfer(): pass\ndef decode_png_rgba(): pass\nallow_uv_overlap MAX_TEXEL_WRITES _exclusive_write sha256 geometry_identifier\n');self.assertEqual(self.by_id(checker.check(self.root),'reference-texture-transfer')['status'],'FAIL')

 def test_legacy_server_footprint_warns_in_compatibility_mode(self):
  (self.root/'server').mkdir(); (self.root/'server/mcp_server.py').write_text('# historical\n')
  d=self.root/'skills/mcp-tools'; d.mkdir()
  self.write_script_registry()
  result=checker.check(self.root)
  self.assertEqual(self.by_id(result,'legacy-server-footprint')['status'],'WARN')
  self.assertEqual(result['status'],'PASS')
 def test_legacy_server_footprint_fails_strict_mode(self):
  (self.root/'server').mkdir(); (self.root/'server/mcp_server.py').write_text('# historical\n')
  self.write_script_registry()
  result=checker.check(self.root,strict_skills_only=True)
  self.assertEqual(self.by_id(result,'legacy-server-footprint')['status'],'FAIL')
  self.assertEqual(result['status'],'FAIL')

 def test_script_registry_hashes_and_coverage_pass(self):
  self.assertEqual(self.by_id(checker.check(self.root),'script-execution-registry')['status'],'PASS')
 def test_missing_script_registry_fails(self):
  (self.root/'SCRIPT_EXECUTION_REGISTRY.csv').unlink()
  self.assertEqual(self.by_id(checker.check(self.root),'required-files')['status'],'FAIL')
 def test_script_registry_hash_mismatch_fails(self):
  path=self.root/'skills/geometry-uv-engine/scripts/geometry_engine.py'; path.write_text(path.read_text()+'# changed\n')
  self.assertEqual(self.by_id(checker.check(self.root),'script-execution-registry')['status'],'FAIL')
 def test_script_registry_invalid_status_fails(self):
  p=self.root/'SCRIPT_EXECUTION_REGISTRY.csv'
  with p.open(encoding='utf-8',newline='') as stream: rows=list(csv.DictReader(stream))
  rows[0]['level_4_runtime']='WORKING'
  with p.open('w',encoding='utf-8',newline='') as stream:
   writer=csv.DictWriter(stream,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
  self.assertEqual(self.by_id(checker.check(self.root),'script-execution-registry')['status'],'FAIL')
 def test_script_registry_missing_path_fails(self):
  p=self.root/'SCRIPT_EXECUTION_REGISTRY.csv'
  with p.open(encoding='utf-8',newline='') as stream: rows=list(csv.DictReader(stream))
  rows=rows[1:]
  with p.open('w',encoding='utf-8',newline='') as stream:
   writer=csv.DictWriter(stream,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
  self.assertEqual(self.by_id(checker.check(self.root),'script-execution-registry')['status'],'FAIL')
 def test_script_registry_duplicate_path_fails(self):
  p=self.root/'SCRIPT_EXECUTION_REGISTRY.csv'
  with p.open(encoding='utf-8',newline='') as stream: rows=list(csv.DictReader(stream))
  rows.append(dict(rows[0]))
  with p.open('w',encoding='utf-8',newline='') as stream:
   writer=csv.DictWriter(stream,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
  self.assertEqual(self.by_id(checker.check(self.root),'script-execution-registry')['status'],'FAIL')

if __name__=='__main__':unittest.main(verbosity=2)
