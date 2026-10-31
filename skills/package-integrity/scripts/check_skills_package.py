#!/usr/bin/env python3
"""Offline integrity checks for the Skills-only Minecraft Bedrock Engineer package."""
from __future__ import annotations
import argparse, gzip, json, re, sys
from pathlib import Path
from typing import Any
EXPECTED_NAME = "minecraft-bedrock-engineer"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
REQUIRED = ["VERSION", "README.md", "plugin.json", ".codex-plugin/plugin.json", "skills/bedrock-engineer-core/SKILL.md", "skills/skills-first-execution/SKILL.md", "skills/skills-only-maintenance/SKILL.md", "skills/geometry-uv-engine/SKILL.md", "skills/geometry-uv-engine/scripts/geometry_engine.py", "skills/geometry-uv-engine/scripts/test_geometry_engine.py", "skills/geometry-uv-engine/scripts/uv_template_engine.py", "skills/geometry-uv-engine/scripts/test_uv_template_engine.py", "skills/visual-resource-pipeline/scripts/png_engine.py", "skills/visual-resource-pipeline/scripts/test_png_engine.py", "skills/reference-texture-transfer/SKILL.md", "skills/reference-texture-transfer/scripts/reference_transfer.py", "skills/reference-texture-transfer/scripts/test_reference_transfer.py"]
LEGACY_MCP_FILES = [".mcp.json", "mcp.json"]
LEGACY_DEPLOYMENT_FILES = ["Dockerfile", "wrangler.toml", "package.json"]
FORBIDDEN_ACTIVE_CALLS = ["create_addon_project", "create_addon_item", "create_addon_block", "create_addon_recipe", "create_addon_entity", "search_mojang_samples", "read_mojang_sample", "audit_texture_links", "diff_packs"]
def read_json(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8"))
def interface(manifest: dict, compat: bool) -> dict:
 value=manifest.get("interface",{}) if compat else manifest.get("extensions",{}).get("com.openai",{}).get("interface",{})
 return value if isinstance(value,dict) else {}
def skill_frontmatter(path: Path):
 text=path.read_text(encoding="utf-8")
 if not text.startswith("---\n"): return None,None,"missing opening YAML frontmatter"
 end=text.find("\n---",4)
 if end<0: return None,None,"missing closing YAML frontmatter"
 block=text[4:end]; name=re.search(r"(?m)^name:\s*([^\n#]+)\s*$",block); desc=re.search(r"(?m)^description:\s*(.+?)\s*$",block)
 if not name or not desc: return None,None,"frontmatter requires non-empty name and description"
 return name.group(1).strip().strip("\"'"),desc.group(1).strip().strip("\"'"),None
def check(root: Path) -> dict:
 root=root.resolve(); checks=[]
 def add(i,s,m): checks.append({"id":i,"status":s,"message":m})
 missing=[p for p in REQUIRED if not (root/p).is_file()]
 add("required-files","FAIL" if missing else "PASS","Missing: "+", ".join(missing) if missing else f"All {len(REQUIRED)} required package files exist")
 if missing: return report(root,checks)
 try: rm=read_json(root/"plugin.json"); cm=read_json(root/".codex-plugin/plugin.json"); vf=(root/"VERSION").read_text(encoding="utf-8").strip()
 except Exception as e: add("manifest-parse","FAIL",f"Unable to read manifests/version: {type(e).__name__}: {e}"); return report(root,checks)
 add("manifest-parse","PASS","Both plugin manifests parse as JSON objects")
 if not isinstance(rm,dict) or not isinstance(cm,dict): add("manifest-shape","FAIL","Both manifests must be JSON objects"); return report(root,checks)
 versions=[rm.get("version"),cm.get("version"),vf]; sem=all(isinstance(v,str) and SEMVER.fullmatch(v) for v in versions); same=len(set(versions))==1
 add("version-parity","PASS" if sem and same else "FAIL",f"Version markers: root={versions[0]!r}, compatibility={versions[1]!r}, VERSION={versions[2]!r}")
 ids=[rm.get("name"),cm.get("name")]; add("plugin-identity","PASS" if ids==[EXPECTED_NAME,EXPECTED_NAME] else "FAIL",f"Plugin identities: {ids!r}")
 rp,cp=interface(rm,False).get("defaultPrompt"),interface(cm,True).get("defaultPrompt")
 pok=isinstance(rp,list) and bool(rp) and rp==cp and all(isinstance(x,str) and x.strip() for x in rp)
 add("default-prompt-parity","PASS" if pok else "FAIL","Default prompts match exactly" if pok else "Root and compatibility default prompts differ or are invalid")
 sp=[rm.get("skills"),cm.get("skills")]; add("skills-path","PASS" if sp==["./skills","./skills"] and (root/"skills").is_dir() else "FAIL",f"Skill paths: {sp!r}")
 refs=[]
 for label,m in (("root",rm),("compatibility",cm)):
  if "mcpServers" in m: refs.append(label+".mcpServers")
 mcps=[x for x in LEGACY_MCP_FILES if (root/x).exists()]
 add("skills-only-boundary","PASS" if not refs and not mcps else "FAIL","No MCP manifests/configuration are present" if not refs and not mcps else f"Unexpected MCP configuration: {refs+mcps!r}")
 deploy=[x for x in LEGACY_DEPLOYMENT_FILES if (root/x).exists()]
 if (root/"cloudflare").exists(): deploy.append("cloudflare/")
 add("obsolete-deployment","PASS" if not deploy else "FAIL", "No retired Cloudflare/container deployment scaffolding" if not deploy else f"Retired deployment artifacts remain: {deploy!r}")
 sf=sorted((root/"skills").rglob("SKILL.md")); names={}; bad=[]
 for p in sf:
  try: n,d,e=skill_frontmatter(p)
  except Exception as ex: bad.append(f"{p.relative_to(root)}: {type(ex).__name__}"); continue
  if e: bad.append(f"{p.relative_to(root)}: {e}"); continue
  if n in names: bad.append(f"duplicate skill name {n!r}: {names[n]} and {p.relative_to(root)}")
  else: names[n]=str(p.relative_to(root))
  if not d: bad.append(f"{p.relative_to(root)}: empty description")
 add("skill-inventory","PASS" if sf and not bad else "FAIL",f"Discovered {len(sf)} skills / {len(names)} unique names"+("; "+"; ".join(bad[:12]) if bad else "; frontmatter valid and names unique"))
 stale=[]
 for p in sf:
  body=p.read_text(encoding="utf-8")
  for tool in FORBIDDEN_ACTIVE_CALLS:
   if re.search(r"(?i)\b(?:call|invoke)\s+`"+re.escape(tool)+r"`",body): stale.append(f"{p.relative_to(root)} invokes {tool}")
  if re.search(r"(?i)actual MCP registry|MCP connection|MCP unit suite",body): stale.append(f"{p.relative_to(root)} contains active MCP release instructions")
 add("skill-tool-boundary","PASS" if not stale else "FAIL","No stale calls to retired tools in skill instructions" if not stale else "; ".join(stale[:20]))
 readme=(root/"README.md").read_text(encoding="utf-8"); h=re.search(r"(?m)^# Minecraft Bedrock Engineer — (\S+)\s*$",readme)
 geometry_script=root/"skills/geometry-uv-engine/scripts/geometry_engine.py"
 geometry_test=root/"skills/geometry-uv-engine/scripts/test_geometry_engine.py"
 geometry_text=geometry_script.read_text(encoding="utf-8") if geometry_script.is_file() else ""
 geometry_contract=all(token in geometry_text for token in ("analyze_geometry", "duplicate JSON key", "UV_OUT_OF_BOUNDS", "UV_OVERLAP", "--geometry-identifier"))
 geometry_ok=geometry_script.is_file() and geometry_test.is_file() and geometry_contract
 add("geometry-engine","PASS" if geometry_ok else "FAIL","Standalone geometry/UV analyzer, test suite and expected static-analysis contract are present")
 template_script=root/"skills/geometry-uv-engine/scripts/uv_template_engine.py"
 template_test=root/"skills/geometry-uv-engine/scripts/test_uv_template_engine.py"
 template_text=template_script.read_text(encoding="utf-8") if template_script.is_file() else ""
 template_contract=all(token in template_text for token in ("extract_regions", "render_template", "encode_png", "max_pixels", "xb"))
 template_ok=template_script.is_file() and template_test.is_file() and template_contract
 add("uv-template-engine","PASS" if template_ok else "FAIL","Standalone transparent UV template renderer, pixel budget, exclusive output creation and focused tests are present")
 png_script=root/"skills/visual-resource-pipeline/scripts/png_engine.py"
 png_test=root/"skills/visual-resource-pipeline/scripts/test_png_engine.py"
 png_ok=png_script.is_file() and png_test.is_file()
 add("png-engine","PASS" if png_ok else "FAIL","Canonical PNG validator and focused tests are present")
 transfer_script=root/"skills/reference-texture-transfer/scripts/reference_transfer.py"
 transfer_test=root/"skills/reference-texture-transfer/scripts/test_reference_transfer.py"
 transfer_text=transfer_script.read_text(encoding="utf-8") if transfer_script.is_file() else ""
 transfer_contract=all(token in transfer_text for token in ("def transfer(", "decode_png_rgba", "allow_uv_overlap", "MAX_TEXEL_WRITES", "_exclusive_write", "sha256", "geometry_identifier"))
 transfer_imports=re.search(r"(?im)^\s*(?:from|import)\s+(?:server|.*_mcp|mcp(?:\.|\s))", transfer_text) is None
 transfer_ok=transfer_script.is_file() and transfer_test.is_file() and transfer_contract and transfer_imports
 add("reference-texture-transfer","PASS" if transfer_ok else "FAIL","Standalone reference-transfer CLI, guarded PNG/UV pipeline, tests and no legacy server/MCP import dependencies" if transfer_ok else "Reference transfer script/tests, required contracts or independence check missing")
 add("readme-version","PASS" if h and versions[0]==h.group(1) else "FAIL",f"README heading version: {h.group(1) if h else 'missing'}")
 rok="Skills-and-instructions-only" in readme and "does not use MCP" in readme
 add("readme-architecture","PASS" if rok else "FAIL","README documents the intentional Skills-only architecture" if rok else "README must explicitly say Skills-and-instructions-only and does not use MCP")
 mp=root/"skills/bedrock-development/references/mojang-samples-1.26.50.4/INDEX_METADATA.json"; ip=root/"skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz"
 try:
  meta=read_json(mp)
  with gzip.open(ip,"rb") as f: payload=f.read()
  dec=json.loads(payload.decode("utf-8")); count=len(dec) if isinstance(dec,list) else len(dec.get("entries",dec.get("files",[]))) if isinstance(dec,dict) else 0
  exp=meta.get("indexed_count"); ok=bool(payload) and (not exp or not count or count==exp)
  # A reduced overlay may omit unchanged binary sample corpus files. Do not mistake
  # an explicit empty placeholder for the full index; verify declared inventory.
  sample_root=root/"skills/bedrock-development/references/mojang-samples-1.26.50.4"
  listed=[p for p in sample_root.rglob("*") if p.is_file() and p.name not in {"INDEX_METADATA.json","mojang-samples-index.json.gz"}]
  if count == 0 and listed:
   ok=False
   detail=f"Compressed index is empty but {len(listed)} sample assets are present; full index is required"
  elif count == 0:
   ok=False
   detail="Compressed sample index is empty; full sample corpus must be retained"
  else:
   detail=f"Gzip/JSON valid; indexed entries={count}, metadata expected={exp}"
  add("mojang-index-integrity","PASS" if ok else "FAIL",detail)
 except Exception as e: add("mojang-index-integrity","FAIL",f"Sample index verification failed: {type(e).__name__}: {e}")
 test_path=root/"skills/visual-resource-pipeline/scripts/test_png_engine.py"
 add("png-engine-tests","PASS" if test_path.is_file() else "FAIL","Focused PNG validator test file present" if test_path.is_file() else "PNG validator tests are missing")
 return report(root,checks)
def report(root,checks):
 failed=sum(c["status"]=="FAIL" for c in checks); warn=sum(c["status"]=="WARN" for c in checks)
 return {"package":root.name,"checks":checks,"summary":{"total":len(checks),"passed":sum(c["status"]=="PASS" for c in checks),"failed":failed,"warnings":warn},"status":"FAIL" if failed else "PASS","runtime_status":"NOT RUN"}
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("package_root",nargs="?",default="."); p.add_argument("--json",dest="json_path"); a=p.parse_args(argv)
 result=check(Path(a.package_root)); rendered=json.dumps(result,ensure_ascii=False,indent=2)
 if a.json_path: Path(a.json_path).write_text(rendered+"\n",encoding="utf-8")
 print(rendered); return 0 if result["status"]=="PASS" else 1
if __name__=="__main__": raise SystemExit(main())
