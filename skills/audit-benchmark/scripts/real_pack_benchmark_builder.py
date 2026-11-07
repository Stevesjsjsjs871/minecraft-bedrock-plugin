#!/usr/bin/env python3
"""Build metadata-only corpus inventories from supplied Bedrock pack ZIP archives."""
from __future__ import annotations
import argparse,json,sys,zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
 sys.path.insert(0,str(ROOT))
from archive_safety import open_bounded_zip, validate_zip_member_namespace
MAX_ARCHIVES,MAX_ENTRIES,MAX_TOTAL,MAX_MEMBER,MAX_RATIO=32,50_000,512*1024**2,128*1024**2,1000
EXTS={'.mcpack','.mcaddon','.zip'}
def inventory(path:Path):
 if path.suffix.lower() not in EXTS: raise ValueError('unsupported archive extension')
 with open_bounded_zip(path) as (z,pinned):
  members=validate_zip_member_namespace(z,max_ratio=MAX_RATIO)
  bad=z.testzip()
  if bad is not None: raise ValueError(f'ZIP CRC/decompression failure at member: {bad!r}')
  entries=[]; total=int(pinned['uncompressed_bytes'])
  if len(members)>MAX_ENTRIES: raise ValueError('archive entry limit exceeded')
  for i,n,is_dir in members:
   item={'path':n + ('/' if is_dir else ''),'type':'directory' if is_dir else 'file',
         'size':i.file_size,'compressed_size':i.compress_size,'crc32':f'{i.CRC:08x}'}
   if not is_dir and n.lower().endswith('manifest.json') and i.file_size<=2*1024*1024:
    try:
     with z.open(i) as f: raw=f.read(2*1024*1024+1)
     if len(raw)>2*1024*1024: raise ValueError('manifest too large')
     m=json.loads(raw.decode('utf-8-sig')); head=m.get('header',{}) if isinstance(m,dict) else {}
     item['manifest']={'uuid':head.get('uuid') if isinstance(head,dict) else None,'name':head.get('name') if isinstance(head,dict) else None,'version':head.get('version') if isinstance(head,dict) else None,'modules':[x.get('type') for x in m.get('modules',[]) if isinstance(x,dict)] if isinstance(m,dict) else []}
    except Exception as e:item['manifest_error']=str(e)[:240]
   entries.append(item)
 return {'archive':path.name,'archive_size':int(pinned['compressed_bytes']),
         'sha256':str(pinned['sha256']),'entry_count':len(entries),
         'file_count':sum(x['type']=='file' for x in entries),
         'directory_count':sum(x['type']=='directory' for x in entries),
         'expanded_size':total,'safety':{'path_namespace':'PASS','crc':'PASS',
         'hash_source':'same_pinned_descriptor','extraction_performed':False,
         'embedded_code_executed':False},'entries':entries}

def main():
 ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('archives',nargs='+',type=Path); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
 if len(a.archives)>MAX_ARCHIVES: print('archive count limit exceeded',file=sys.stderr); return 2
 try:r={'schema_version':1,'status':'INVENTORY_ONLY','corpus':[inventory(p.expanduser()) for p in a.archives]}
 except (OSError,ValueError,zipfile.BadZipFile) as e: print(json.dumps({'status':'FAILED','error':str(e)}),file=sys.stderr); return 2
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x',encoding='utf-8',newline='\n') as stream: stream.write(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
 return 0
if __name__=='__main__': raise SystemExit(main())
