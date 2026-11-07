#!/usr/bin/env python3
"""Bounded read-only lexical inventory of Bedrock Script API usage; not an AST/type checker."""
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
MAX_FILES,MAX_FILE,MAX_TOTAL=2000,2*1024*1024,32*1024*1024
EXTS={'.js','.mjs','.cjs','.ts','.mts','.cts'}
IMPORT=re.compile(r"\b(?:from\s*|import\s*)['\"]([^'\"]+)['\"]|\bimport\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
SUB=re.compile(r'\b([\w.$]+)\.subscribe\s*\(')
TIMER=re.compile(r'\b(system\s*\.\s*run(?:Interval|Timeout|Job)|system\s*\.\s*clearRun)\s*\(')
QUERY=re.compile(r'\b(getEntities|getPlayers|getBlocks|getBlockFromRay|runCommand|runCommandAsync)\s*\(')
def strip_comments_strings(src):
 out=list(src); i=0; n=len(src)
 while i<n:
  if src.startswith('//',i):
   j=src.find('\n',i); j=n if j<0 else j
   for k in range(i,j): out[k]=' '
   i=j; continue
  if src.startswith('/*',i):
   j=src.find('*/',i+2); j=n-2 if j<0 else j
   for k in range(i,min(n,j+2)):
    if out[k]!='\n': out[k]=' '
   i=min(n,j+2); continue
  if src[i] in ('"',"'",'`'):
   q=src[i]; j=i+1
   while j<n:
    if src[j]=='\\': j+=2; continue
    if src[j]==q: j+=1; break
    j+=1
   for k in range(i,min(j,n)):
    if out[k]!='\n': out[k]=' '
   i=j; continue
  i+=1
 return ''.join(out)
def strip_comments(src):
 # Preserve string literals so import specifiers remain visible; blank comments only.
 out=list(src); i=0; n=len(src)
 while i<n:
  if src.startswith('//',i):
   j=src.find('\n',i); j=n if j<0 else j
   for k in range(i,j): out[k]=' '
   i=j; continue
  if src.startswith('/*',i):
   j=src.find('*/',i+2); j=n-2 if j<0 else j
   for k in range(i,min(n,j+2)):
    if out[k]!='\n': out[k]=' '
   i=min(n,j+2); continue
  if src[i] in ('\"',"'",'`'):
   q=src[i]; i+=1
   while i<n:
    if src[i]=='\\': i+=2; continue
    if src[i]==q: i+=1; break
    i+=1
   continue
  i+=1
 return ''.join(out)
def analyze(root:Path):
 root=root.resolve(strict=True)
 if not root.is_dir(): raise ValueError('project root must be a directory')
 files=[]; total=0
 for p in root.rglob('*'):
  if p.is_symlink(): continue
  if p.is_file() and p.suffix.lower() in EXTS:
   size=p.stat().st_size
   if size>MAX_FILE: raise ValueError(f'file exceeds 2 MiB: {p.relative_to(root)}')
   total+=size
   if len(files)>=MAX_FILES or total>MAX_TOTAL: raise ValueError('source inventory safety limit exceeded')
   files.append(p)
 imports=[]; subs=[]; timers=[]; queries=[]; findings=[]; deps=[]
 for p in sorted(files):
  rel=p.relative_to(root).as_posix(); src=p.read_text(encoding='utf-8-sig'); clean=strip_comments_strings(src)
  for m in IMPORT.finditer(strip_comments(src)): imports.append({'path':rel,'specifier':m.group(1) or m.group(2),'line':src.count('\n',0,m.start())+1,'kind':'dynamic' if m.group(2) else 'static'})
  for rx,out in ((SUB,subs),(TIMER,timers),(QUERY,queries)):
   for m in rx.finditer(clean): out.append({'path':rel,'symbol':m.group(1),'line':clean.count('\n',0,m.start())+1})
  for pat,sev,msg in [(r'\bworld\s*\.\s*getDimension\s*\([^)]*\)\s*\.\s*getEntities\s*\(','MEDIUM','Broad entity query; review frequency, filters and bounds.'),(r'\b(?:players|entities|blocks)\s*\[\s*0\s*\]','LOW','Index-zero access; verify collection is non-empty.'),(r'\bsystem\s*\.\s*runInterval\s*\([^,]+,\s*1\s*\)','LOW','One-tick interval; verify bounded work.')]:
   for m in re.finditer(pat,clean): findings.append({'path':rel,'line':clean.count('\n',0,m.start())+1,'severity':sev,'status':'HEURISTIC_REVIEW','message':msg})
 for p in root.rglob('manifest.json'):
  if p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_FILE: continue
  try: data=json.loads(p.read_text(encoding='utf-8-sig'))
  except Exception as e: findings.append({'path':p.relative_to(root).as_posix(),'severity':'HIGH','status':'INVALID_MANIFEST_JSON','message':str(e)}); continue
  for mod in data.get('dependencies',[]) if isinstance(data,dict) else []:
   if isinstance(mod,dict) and isinstance(mod.get('module_name'),str): deps.append({'path':p.relative_to(root).as_posix(),'module':mod['module_name'],'version':mod.get('version')})
 return {'schema_version':1,'status':'PARTIAL','analysis':'LEXICAL_HEURISTICS_ONLY','files_scanned':len(files),'bytes_scanned':total,'script_api_imports':[x for x in imports if x['specifier'].startswith('@minecraft/')],'all_imports':imports,'manifest_script_dependencies':deps,'event_subscriptions':subs,'timers':timers,'world_query_calls':queries,'findings':findings,'limitations':['No AST/type/control-flow/call-graph analysis.','API availability must be verified against official docs/typings for the exact game build.','No code execution, lifecycle proof or performance profiling.','Generated code and nonliteral dynamic imports may be missed.']}
def main():
 ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('project_root',type=Path); ap.add_argument('--output',type=Path); a=ap.parse_args()
 try: r=analyze(a.project_root)
 except (OSError,ValueError) as e: print(json.dumps({'status':'FAILED','error':str(e)}),file=sys.stderr); return 2
 s=json.dumps(r,indent=2,ensure_ascii=False)+'\n'
 if a.output:
  if a.output.exists(): print('refusing to overwrite output',file=sys.stderr); return 2
  a.output.write_text(s,encoding='utf-8')
 else: print(s,end='')
 return 0
if __name__=='__main__': raise SystemExit(main())
