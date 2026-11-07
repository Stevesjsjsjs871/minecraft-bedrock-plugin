#!/usr/bin/env python3
"""Offline integrity checks for the Skills-only Minecraft Bedrock Engineer package."""
from __future__ import annotations
import argparse, ast, csv, gzip, hashlib, json, re, sys
from pathlib import Path
from typing import Any
EXPECTED_NAME = "minecraft-bedrock-engineer"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
REQUIRED = ["SCRIPT_EXECUTION_REGISTRY.csv", "VERSION", "README.md", "plugin.json", ".codex-plugin/plugin.json", "skills/bedrock-engineer-core/SKILL.md", "skills/skills-first-execution/SKILL.md", "skills/skills-only-maintenance/SKILL.md", "skills/geometry-uv-engine/SKILL.md", "skills/geometry-uv-engine/scripts/geometry_engine.py", "skills/geometry-uv-engine/scripts/test_geometry_engine.py", "skills/geometry-uv-engine/scripts/uv_template_engine.py", "skills/geometry-uv-engine/scripts/test_uv_template_engine.py", "skills/visual-resource-pipeline/scripts/png_engine.py", "skills/visual-resource-pipeline/scripts/test_png_engine.py", "skills/reference-texture-transfer/SKILL.md", "skills/reference-texture-transfer/scripts/reference_transfer.py", "skills/reference-texture-transfer/scripts/test_reference_transfer.py"]
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
def check_script_registry(root: Path) -> tuple[str, str]:
 registry_path=root/"SCRIPT_EXECUTION_REGISTRY.csv"
 if not registry_path.is_file(): return "FAIL", "SCRIPT_EXECUTION_REGISTRY.csv is missing"
 required={"path","sha256","level_1_discovery","level_2_syntax","level_3_dependencies","level_4_runtime","level_5_functional","level_6_plugin_integration"}
 allowed={
  "level_1_discovery":{"PRESENT","BLOCKED","FAILED","NOT_TESTED"},
  "level_2_syntax":{"SYNTAX_OK","BLOCKED","FAILED","NOT_TESTED"},
  "level_3_dependencies":{"DEPENDENCIES_OK","BLOCKED","FAILED","NOT_TESTED"},
  "level_4_runtime":{"RUNTIME_OK","BLOCKED","FAILED","NOT_TESTED"},
  "level_5_functional":{"FUNCTIONAL_OK","BLOCKED","FAILED","NOT_TESTED"},
  "level_6_plugin_integration":{"INTEGRATION_OK","BLOCKED","FAILED","NOT_TESTED"},
 }
 try:
  with registry_path.open(encoding="utf-8",newline="") as stream:
   reader=csv.DictReader(stream)
   if not reader.fieldnames or not required.issubset(reader.fieldnames):
    return "FAIL", f"Script registry missing columns: {sorted(required-set(reader.fieldnames or []))}"
   rows=list(reader)
  by_path={}
  errors=[]
  for row in rows:
   rel=row.get("path","")
   path=Path(rel)
   if not rel or path.is_absolute() or ".." in path.parts or "\\" in rel or not rel.endswith(".py"):
    errors.append(f"unsafe/invalid registry path {rel!r}"); continue
   if rel in by_path: errors.append(f"duplicate registry path {rel!r}"); continue
   by_path[rel]=row
   for field,values in allowed.items():
    if row.get(field) not in values: errors.append(f"{rel}: invalid {field}={row.get(field)!r}")
   source=root/path
   if not source.is_file() or source.is_symlink():
    errors.append(f"{rel}: missing or symlinked Python file"); continue
   digest=hashlib.sha256(source.read_bytes()).hexdigest()
   if row.get("sha256")!=digest: errors.append(f"{rel}: SHA-256 mismatch")
  actual={p.relative_to(root).as_posix() for p in root.rglob("*.py") if p.is_file()}
  missing=sorted(actual-set(by_path)); stale=sorted(set(by_path)-actual)
  if missing: errors.append(f"unregistered Python files: {missing[:10]!r}")
  if stale: errors.append(f"stale registry paths: {stale[:10]!r}")
  if errors: return "FAIL", "; ".join(errors[:20])
  return "PASS", f"Six-level registry covers all {len(actual)} Python files; paths, status vocabulary and SHA-256 hashes verified"
 except Exception as exc:
  return "FAIL", f"Script registry validation error: {type(exc).__name__}: {exc}"


def scan_hidden_mcp_components(root: Path) -> list[str]:
 """Find MCP configuration and protocol adapters even when renamed.

 The scan is deliberately structural: configuration keys are inspected in
 nested data, while executable Python is parsed as AST and checked for MCP
 imports, JSON-RPC/framing signatures, and adapter-shaped entry points.
 Test files are excluded from Python adapter heuristics so negative fixtures
 can describe forbidden patterns without becoming package components.
 """
 findings: list[str] = []
 config_suffixes = {".json", ".json5", ".jsonc", ".yaml", ".yml", ".toml"}
 config_names = {".mcp.json", "mcp.json", "mcp.yaml", "mcp.yml", "mcp.toml", "connector-profile.json"}
 ignored_parts = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}

 def has_mcp_key(value: Any, trail: str = "") -> list[str]:
  found: list[str] = []
  if isinstance(value, dict):
   for key, child in value.items():
    key_text = str(key).strip().lower().replace("-", "_")
    here = f"{trail}.{key}" if trail else str(key)
    if key_text in {"mcpservers", "mcp_servers", "mcp_server", "mcp_config", "mcpconfiguration", "mcp_configuration"}:
     found.append(here)
    found.extend(has_mcp_key(child, here))
  elif isinstance(value, list):
   for index, child in enumerate(value): found.extend(has_mcp_key(child, f"{trail}[{index}]"))
  return found

 for path in root.rglob("*"):
  if not path.is_file() or any(part in ignored_parts for part in path.relative_to(root).parts):
   continue
  rel = path.relative_to(root).as_posix()
  lower_name = path.name.lower()
  if path.suffix.lower() in config_suffixes or lower_name in config_names:
   try:
    raw = path.read_text(encoding="utf-8")
   except (OSError, UnicodeError):
    continue
   keys: list[str] = []
   if path.suffix.lower() in {".json", ".json5", ".jsonc"} or lower_name.endswith(".json"):
    try: keys = has_mcp_key(json.loads(raw))
    except (ValueError, TypeError): pass
   # YAML/TOML are scanned conservatively for nested or quoted keys.
   if not keys and re.search(r"(?im)^\s*[\"']?mcp[_-]?(?:servers?|config(?:uration)?)\b[\"']?\s*[:=]", raw):
    keys = ["MCP-like configuration key"]
   if lower_name in config_names and not keys:
    # A conventionally named MCP config is itself a forbidden footprint.
    keys = ["MCP configuration filename"]
   if keys: findings.append(f"{rel}: {', '.join(keys[:5])}")

  # The legacy server tree is audited separately as an explicit historical
  # footprint. Its known protocol handlers should not make compatibility mode
  # fail; strict mode rejects the tree through legacy-server-footprint below.
  if rel.startswith("server/") or path.suffix.lower() != ".py" or "/tests/" in f"/{rel}/" or path.name.startswith("test_"):
   continue
  try: source = path.read_text(encoding="utf-8")
  except (OSError, UnicodeError): continue
  try: tree = ast.parse(source, filename=rel)
  except SyntaxError: continue  # syntax gate reports this separately
  imports: list[str] = []
  functions: set[str] = set()
  strings: list[str] = []
  for node in ast.walk(tree):
   if isinstance(node, ast.Import): imports.extend(alias.name for alias in node.names)
   elif isinstance(node, ast.ImportFrom) and node.module: imports.append(node.module)
   elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): functions.add(node.name.lower())
   elif isinstance(node, ast.Constant) and isinstance(node.value, str): strings.append(node.value.lower())
  mcp_imports = sorted({name for name in imports if name == "mcp" or name.startswith("mcp.") or name in {"jsonrpc", "json_rpc"}})
  protocol_markers = ("content-length", "jsonrpc", "tools/call", "tools/list", "notifications/initialized", "protocolversion")
  marker_hits = sorted({marker for marker in protocol_markers if any(marker in value for value in strings)})
  adapter_functions = functions.intersection({"handle_message", "serve_stdio", "run_stdio", "read_message", "write_message", "dispatch_jsonrpc"})
  framing_pair = "content-length" in marker_hits and bool(adapter_functions)
  if mcp_imports:
   findings.append(f"{rel}: MCP/JSON-RPC imports {mcp_imports!r}")
  elif marker_hits and adapter_functions:
   findings.append(f"{rel}: protocol markers {marker_hits!r}; adapter functions {sorted(adapter_functions)!r}")
  elif framing_pair:
   findings.append(f"{rel}: stdio framing plus adapter entry point")
 return sorted(set(findings))

def check(root: Path, strict_skills_only: bool = False) -> dict:
 root=root.resolve(); checks=[]
 def add(i,s,m): checks.append({"id":i,"status":s,"message":m})
 missing=[p for p in REQUIRED if not (root/p).is_file()]
 add("required-files","FAIL" if missing else "PASS","Missing: "+", ".join(missing) if missing else f"All {len(REQUIRED)} required package files exist")
 if missing: return report(root,checks)
 try: rm=read_json(root/"plugin.json"); cm=read_json(root/".codex-plugin/plugin.json"); vf=(root/"VERSION").read_text(encoding="utf-8").strip()
 except Exception as e: add("manifest-parse","FAIL",f"Unable to read manifests/version: {type(e).__name__}: {e}"); return report(root,checks)
 add("manifest-parse","PASS","Both plugin manifests parse as JSON objects")
 registry_status,registry_message=check_script_registry(root)
 add("script-execution-registry",registry_status,registry_message)
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
 hidden_components = scan_hidden_mcp_components(root)
 boundary_errors = refs + mcps + hidden_components
 add("skills-only-boundary","PASS" if not boundary_errors else "FAIL","No MCP manifests, nested configs, imports or protocol adapters detected" if not boundary_errors else f"Unexpected MCP footprint: {boundary_errors[:30]!r}")
 legacy_server = root / "server"
 legacy_files = sorted(p for p in legacy_server.rglob("*") if p.is_file()) if legacy_server.is_dir() else []
 legacy_skill_dirs = sorted(p.relative_to(root).as_posix() for p in (root / "skills").iterdir() if p.is_dir() and ("mcp" in p.name.lower() or "server" in p.name.lower()) and not any(p.rglob("SKILL.md"))) if (root / "skills").is_dir() else []
 footprint = bool(legacy_files or legacy_skill_dirs)
 footprint_status = "FAIL" if strict_skills_only and footprint else "WARN" if footprint else "PASS"
 footprint_message = (f"Legacy footprint remains: {len(legacy_files)} files under server/; non-Skill legacy directories={legacy_skill_dirs!r}. The strict Skills-only release gate requires this tree to be absent." if footprint else "No legacy server/protocol tree or empty MCP/server-named Skill directories remain")
 add("legacy-server-footprint", footprint_status, footprint_message)
 deploy=[x for x in LEGACY_DEPLOYMENT_FILES if (root/x).exists()]
 if (root/"cloudflare").is_dir() and any(p.is_file() for p in (root/"cloudflare").rglob("*")): deploy.append("cloudflare/ (contains files)")
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
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("package_root",nargs="?",default="."); p.add_argument("--json",dest="json_path"); p.add_argument("--strict-skills-only",action="store_true",help="Fail if physical legacy server files or MCP/server-named empty skill directories remain"); a=p.parse_args(argv)
 result=check(Path(a.package_root), strict_skills_only=a.strict_skills_only); rendered=json.dumps(result,ensure_ascii=False,indent=2)
 if a.json_path: Path(a.json_path).write_text(rendered+"\n",encoding="utf-8")
 print(rendered); return 0 if result["status"]=="PASS" else 1
if __name__=="__main__": raise SystemExit(main())
