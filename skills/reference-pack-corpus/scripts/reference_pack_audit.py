#!/usr/bin/env python3
"""Read-only structural inventory for untrusted Minecraft Bedrock ZIP archives."""
from __future__ import annotations
import argparse, hashlib, json, os, re, stat, sys, zipfile
from pathlib import PurePosixPath
from collections import Counter
from typing import Any

MAX_ENTRIES=100_000
MAX_TOTAL=2*1024*1024*1024
MAX_MEMBER=512*1024*1024
MAX_RATIO=500
HASH_CHUNK=1024*1024

def _canonical_member_name(name):
    """Return a normalized ZIP member path, or raise ValueError if ambiguous/unsafe."""
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ValueError("empty or NUL-containing ZIP member name")
    # Backslashes are not accepted: different ZIP consumers normalize them differently.
    if "\\" in name:
        raise ValueError("backslash in ZIP member path")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ValueError("absolute ZIP member path")
    trimmed = name[:-1] if name.endswith("/") else name
    parts = trimmed.split("/")
    if not trimmed or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("empty, dot, or parent ZIP path segment")
    return PurePosixPath(*parts).as_posix()

def unsafe_name(name):
    try:
        _canonical_member_name(name)
        return False
    except ValueError:
        return True

def _hash_stream(stream):
    h=hashlib.sha256()
    size=0
    for block in iter(lambda:stream.read(HASH_CHUNK),b''):
        h.update(block); size+=len(block)
    return h.hexdigest(), size

def strip_json_comments(text):
    """Remove JS-style comments and Mojang #region/#endregion lines outside strings."""
    out=[]; i=0; n=len(text); in_str=False; esc=False
    while i<n:
        c=text[i]
        if in_str:
            out.append(c)
            if esc: esc=False
            elif c=='\\': esc=True
            elif c=='"': in_str=False
            i+=1; continue
        if c=='"': in_str=True; out.append(c); i+=1; continue
        if text.startswith('//',i):
            j=text.find('\n',i)
            if j<0: break
            out.append('\n'); i=j+1; continue
        if text.startswith('/*',i):
            j=text.find('*/',i+2)
            if j<0: raise ValueError('unterminated block comment')
            out.append('\n' * max(1,text[i:j+2].count('\n'))); i=j+2; continue
        # Region markers used by Mojang JSON resources are whole-line directives.
        if c=='#' and (i==0 or text[i-1]=='\n'):
            j=text.find('\n',i)
            line=text[i:] if j<0 else text[i:j]
            if re.match(r'#\s*(region|endregion)\b',line):
                out.append('\n'); i=n if j<0 else j+1; continue
        out.append(c); i+=1
    return ''.join(out)

def parse_json_bytes(raw):
    text=raw.decode('utf-8-sig')
    def pairs(items):
        d={}
        for k,v in items:
            if k in d: raise ValueError('duplicate JSON key: '+k)
            d[k]=v
        return d
    try: return json.loads(text,object_pairs_hook=pairs), 'strict'
    except Exception as strict_err:
        cleaned=strip_json_comments(text)
        obj=json.loads(cleaned,object_pairs_hook=pairs)
        return obj, 'comment-aware'

def audit(path):
    display=os.fspath(path)
    report={'archive':os.path.basename(display),'size_bytes':None,'sha256':None,'status':'PASS','entry_count':0,'unsafe_paths':[],'duplicate_paths':[],'zip_errors':[],'resource_counts':{},'manifests':[],'json':{'strict_valid':0,'comment_aware_valid':0,'failed':[]},'packaging_warnings':[]}
    # Pin one regular-file descriptor before hashing or parsing. ZIP reads and
    # SHA-256 therefore refer to the same opened file, even if its path changes.
    flags=os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd=os.open(display, flags)
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            os.close(fd)
            raise ValueError('archive must be a regular non-symlink file')
        with os.fdopen(fd,'rb') as pinned:
            report['size_bytes']=st.st_size
            digest, hashed_size=_hash_stream(pinned)
            if hashed_size != st.st_size:
                raise ValueError('archive changed while hashing')
            report['sha256']=digest
            pinned.seek(0)
            try:
                z=zipfile.ZipFile(pinned)
            except Exception as e:
                report['status']='FAIL'; report['zip_errors'].append(str(e)); return report
            with z:
                infos=z.infolist(); report['entry_count']=len(infos)
                if not infos:
                    report['status']='FAIL'; report['zip_errors'].append('archive contains no entries'); return report
                if len(infos)>MAX_ENTRIES:
                    report['status']='BLOCKED'; report['zip_errors'].append('entry limit exceeded'); return report
                total=0; seen={}; files=set(); directories=set(); counts=Counter(); manifests=[]
                # Metadata preflight MUST precede any decompression/CRC pass.
                for info in infos:
                    name=info.filename
                    try:
                        canonical=_canonical_member_name(name)
                    except ValueError as exc:
                        report['unsafe_paths'].append(f'{name} [{exc}]')
                        continue
                    key=canonical.casefold()
                    if key in seen:
                        report['duplicate_paths'].append(name)
                    else:
                        seen[key]=name
                    mode=(info.external_attr>>16)&0xffff
                    if stat.S_ISLNK(mode):
                        report['unsafe_paths'].append(name+' [symlink]')
                    if info.is_dir(): directories.add(key)
                    else: files.add(key)
                    total+=info.file_size
                    if info.file_size>MAX_MEMBER or total>MAX_TOTAL:
                        report['status']='BLOCKED'; report['zip_errors'].append('expanded size limit exceeded'); return report
                    if info.file_size and not info.compress_size:
                        report['status']='BLOCKED'; report['zip_errors'].append('invalid zero compressed size for non-empty member: '+name); return report
                    if info.compress_size and info.file_size/info.compress_size>MAX_RATIO:
                        report['status']='BLOCKED'; report['zip_errors'].append('compression ratio limit exceeded: '+name); return report
                    if info.flag_bits & 0x1:
                        report['zip_errors'].append('encrypted member is not inspectable: '+name)
                        report['status']='PARTIAL'
                        continue
                    if info.is_dir(): continue
                    ext=PurePosixPath(canonical).suffix.lower() or '[no extension]'; counts[ext]+=1
                    if PurePosixPath(canonical).name.lower()=='manifest.json': manifests.append((name, info))
                # Reject file/directory aliasing and file-as-parent collisions.
                conflicts=files & directories
                for file_key in files:
                    parts=file_key.split('/')
                    for i in range(1,len(parts)):
                        parent='/'.join(parts[:i])
                        if parent in files:
                            conflicts.add(parent)
                for conflict in sorted(conflicts):
                    report['unsafe_paths'].append(f'{seen.get(conflict, conflict)} [file/directory path collision]')
                report['expanded_bytes']=total; report['resource_counts']=dict(counts)
                if report['unsafe_paths'] or report['duplicate_paths']:
                    report['status']='FAIL'
                if report['status']=='FAIL':
                    return report
                # Integrity pass is bounded by the validated declared sizes.
                try:
                    bad_member=z.testzip()
                except Exception as exc:
                    report['status']='FAIL'; report['zip_errors'].append('ZIP integrity check failed: '+str(exc)); return report
                if bad_member is not None:
                    report['status']='FAIL'; report['zip_errors'].append('CRC/decompression failure in member: '+bad_member); return report
                for m,info in manifests:
                    try:
                        obj,mode=parse_json_bytes(z.read(info)); h=obj.get('header',{}) if isinstance(obj,dict) else {}
                        modules=obj.get('modules',[]) if isinstance(obj,dict) else []
                        report['manifests'].append({'path':m,'parse_mode':mode,'name':h.get('name'),'version':h.get('version'),'min_engine_version':h.get('min_engine_version'),'modules':[{'type':x.get('type'),'version':x.get('version')} for x in modules if isinstance(x,dict)],'dependencies':obj.get('dependencies',[]) if isinstance(obj,dict) else [],'capabilities':obj.get('capabilities',[]) if isinstance(obj,dict) else []})
                    except Exception as e:
                        report['manifests'].append({'path':m,'error':str(e)}); report['status']='FAIL'
                for info in infos:
                    if info.is_dir() or not info.filename.lower().endswith('.json') or unsafe_name(info.filename): continue
                    try:
                        _,mode=parse_json_bytes(z.read(info))
                        report['json']['strict_valid' if mode=='strict' else 'comment_aware_valid']+=1
                    except Exception as e:
                        report['json']['failed'].append({'path':info.filename,'error':str(e)[:500]})
                roots={m.split('/')[0] for m,_ in manifests if '/' in m}
                if manifests and all('/' in m for m,_ in manifests): report['packaging_warnings'].append('All manifests are nested below wrapper directories; check whether the delivered pack is import-rooted correctly.')
                if report['json']['failed'] and report['status']=='PASS': report['status']='PARTIAL'
            after=os.fstat(pinned.fileno())
            if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (st.st_size, st.st_mtime_ns, st.st_ctime_ns):
                report['status']='FAIL'
                report['zip_errors'].append('archive changed while its contents were being inspected')
    except (OSError, ValueError) as exc:
        report['status']='FAIL'; report['zip_errors'].append(str(exc))
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('archives',nargs='+'); ap.add_argument('--output')
    a=ap.parse_args(); results=[]
    for p in a.archives:
        try: results.append(audit(p))
        except Exception as e: results.append({'archive':p,'status':'ERROR','error':str(e)})
    payload={'tool':'reference_pack_audit.py','version':'1.0.0','results':results}
    out=json.dumps(payload,ensure_ascii=False,indent=2)
    if a.output:
        with open(a.output,'x',encoding='utf-8') as f: f.write(out+'\n')
    else: print(out)
    return 1 if any(x.get('status') in ('FAIL','ERROR','BLOCKED') for x in results) else 0
if __name__=='__main__': sys.exit(main())
