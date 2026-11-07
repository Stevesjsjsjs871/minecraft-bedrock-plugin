#!/usr/bin/env python3
"""Read-only bounded validation for UI references, PBR/Fog inventories and pack UUID contracts."""
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
MAX_FILES,MAX_BYTES,MAX_JSON=5000,48*1024*1024,2*1024*1024
def run(root:Path):
 root=root.resolve(strict=True)
 if not root.is_dir(): raise ValueError('root must be a directory')
 files=[]; total=0
 for p in root.rglob('*'):
  if p.is_symlink(): continue
  if p.is_file():
   total+=p.stat().st_size
   if len(files)>=MAX_FILES or total>MAX_BYTES: raise ValueError('project inventory safety limit exceeded')
   files.append(p)
 rel={p.relative_to(root).as_posix():p for p in files}; docs={}; findings=[]; refs=[]; ui=pbr=fog=0
 def add(path,code,sev,msg): findings.append({'path':path,'code':code,'severity':sev,'message':msg})
 for name,p in rel.items():
  if p.suffix.lower() not in {'.json','.ui'}: continue
  if p.stat().st_size>MAX_JSON: add(name,'JSON_TOO_LARGE','HIGH','JSON/UI exceeds 2 MiB limit'); continue
  try: data=json.loads(p.read_text(encoding='utf-8-sig'))
  except Exception as e: add(name,'INVALID_JSON','HIGH',str(e)); continue
  docs[name]=data; low=name.lower(); txt=json.dumps(data,ensure_ascii=False)
  if '/ui/' in '/'+low or low.endswith('.ui'):
   ui+=1
   for m in re.finditer(r'\b(?:ui|textures|images|controls|bindings)/[A-Za-z0-9_./-]+',txt): refs.append({'source':name,'reference':m.group(0),'kind':'ui-reference'})
   if isinstance(data,dict) and 'namespace' not in data: add(name,'UI_NAMESPACE_REVIEW','LOW','No top-level namespace key; verify this file against the target UI schema.')
  if any(x in low for x in ('material','texture_set','pbr')) or (isinstance(data,dict) and any('material' in str(k).lower() for k in data)):
   pbr+=1
   for m in re.finditer(r'"(minecraft:[^" ]*(?:texture|material)[^" ]*)"\s*:\s*"([^" ]+)"',txt): refs.append({'source':name,'reference':m.group(2),'kind':'pbr-texture','property':m.group(1)})
  if 'fog' in low or (isinstance(data,dict) and any('fog' in str(k).lower() for k in data)): fog+=1
 for item in refs:
  v=item['reference']
  if v.startswith(('textures/','ui/','images/')) and v not in rel and not any(k.endswith('/'+v) for k in rel): add(item['source'],'RESOURCE_REFERENCE_UNRESOLVED','MEDIUM',f"{item['kind']} path not found: {v}")
 uuids={}; deps=[]
 for name,data in docs.items():
  if not name.endswith('manifest.json') or not isinstance(data,dict): continue
  h=data.get('header',{}); uid=h.get('uuid') if isinstance(h,dict) else None
  if isinstance(uid,str):
   if uid in uuids: add(name,'DUPLICATE_MANIFEST_UUID','HIGH',f'duplicate UUID also in {uuids[uid]}')
   uuids[uid]=name
  for dep in data.get('dependencies',[]) if isinstance(data.get('dependencies',[]),list) else []:
   if isinstance(dep,dict) and isinstance(dep.get('uuid'),str): deps.append((name,dep['uuid']))
 for src,uid in deps:
  if uid not in uuids: add(src,'PACK_DEPENDENCY_UNRESOLVED','MEDIUM',f'dependency UUID absent from supplied project: {uid}')
 return {'schema_version':1,'status':'PARTIAL','files_scanned':len(files),'bytes_scanned':total,'json_files_parsed':len(docs),'ui_files_seen':ui,'pbr_related_files_seen':pbr,'fog_related_files_seen':fog,'references':refs,'findings':findings,'limitations':['UI binding semantics, inheritance and engine expressions are not evaluated.','PBR schemas/material compatibility need exact-version schemas/docs and game runtime.','Fog volumes, identifiers and render behavior are not simulated.','Aliases, pack-stack overrides and runtime resource resolution may not be represented by file paths.']}
def main():
 ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('project_root',type=Path); ap.add_argument('--output',type=Path); a=ap.parse_args()
 try:r=run(a.project_root)
 except (OSError,ValueError) as e: print(json.dumps({'status':'FAILED','error':str(e)}),file=sys.stderr); return 2
 s=json.dumps(r,indent=2,ensure_ascii=False)+'\n'
 if a.output:
  if a.output.exists(): print('refusing to overwrite output',file=sys.stderr); return 2
  a.output.write_text(s,encoding='utf-8')
 else: print(s,end='')
 return 0
if __name__=='__main__': raise SystemExit(main())
