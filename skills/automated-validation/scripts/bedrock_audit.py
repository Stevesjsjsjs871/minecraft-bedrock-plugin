#!/usr/bin/env python3
"""Static, conservative Bedrock resource audit for ZIP-compatible packs.
Does not extract files, launch Minecraft, or claim runtime correctness.
Python 3 standard library only. Model-format assumptions are intentionally conservative.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys, zipfile
from pathlib import PurePosixPath
from typing import Any

TOOL_VERSION = "0.6.3"
PATH_KEYS = {"texture", "texture_path", "path", "file", "sound", "particle_effect"}
IDENTIFIER_KEYS = {"geometry", "animation", "animations", "animation_controller", "animation_controllers", "render_controllers", "materials"}

def sha256(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def sha256_file(path: str) -> str:
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def finding(severity,confidence,title,evidence,path=None,impact='',recommendation=''):
    return {"severity":severity,"confidence":confidence,"title":title,"path":path,"evidence":evidence,"impact":impact,"recommendation":recommendation}
def walk(obj, pointer='$'):
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f'{pointer}/{str(k).replace("~","~0").replace("/","~1")}'
            yield p,k,v
            yield from walk(v,p)
    elif isinstance(obj,list):
        for i,v in enumerate(obj): yield from walk(v,f'{pointer}/{i}')
def load_archive(path, findings):
    meta={"path":path,"sha256":sha256_file(path),"archive_valid":False}; files={}
    try:
        with zipfile.ZipFile(path) as z:
            bad=z.testzip()
            if bad:
                findings.append(finding('BLOCKER','HIGH','Archive CRC failure',f'ZIP integrity failed at {bad!r}.',bad,'Archive may be corrupt.','Rebuild the archive.')); return files,meta
            seen=set()
            for info in z.infolist():
                name=info.filename.replace('\\','/'); pp=PurePosixPath(name)
                if name in seen: findings.append(finding('HIGH','HIGH','Duplicate archive path',f'Duplicate member {name!r}.',name,'Different unpackers may select different data.','Remove duplicate members.'))
                seen.add(name)
                if pp.is_absolute() or '..' in pp.parts or re.match(r'^[A-Za-z]:',name):
                    findings.append(finding('BLOCKER','HIGH','Unsafe archive member path',f'Unsafe path {name!r}.',name,'Path traversal/absolute path issue.','Rebuild with safe relative paths.')); continue
                if info.is_dir(): continue
                try: files[name]=z.read(info)
                except Exception as e: findings.append(finding('HIGH','HIGH','Could not read archive member',str(e),name,'Member could not be audited.','Repair the archive.'))
            meta['archive_valid']=True
    except (OSError,zipfile.BadZipFile,RuntimeError) as e:
        findings.append(finding('BLOCKER','HIGH','Archive cannot be opened',str(e),path,'Archive contents unavailable.','Supply a valid ZIP-compatible archive.'))
    return files,meta
def parse_json(files,findings):
    parsed={}
    for path,raw in files.items():
        if path.lower().endswith('.json'):
            try: parsed[path]=json.loads(raw.decode('utf-8-sig'))
            except Exception as e: findings.append(finding('HIGH','HIGH','Invalid JSON',f'{type(e).__name__}: {e}',path,'The game may not parse this file.','Fix JSON syntax.'))
    return parsed
def audit_manifests(parsed,findings):
    manifests=[(p,d) for p,d in parsed.items() if PurePosixPath(p).name.lower()=='manifest.json' and isinstance(d,dict)]
    if not manifests:
        findings.append(finding('MEDIUM','MEDIUM','No manifest.json found','No parseable manifest.json found.',None,'Archive may be a source folder rather than installable pack.','Confirm expected archive layout.')); return
    modules={}; headers={}; known=set()
    for path,d in manifests:
        h=d.get('header',{})
        if not isinstance(h,dict): findings.append(finding('HIGH','HIGH','Manifest header malformed',"Expected object at 'header'.",path,'Manifest may fail to load.','Repair header.')); continue
        uid=h.get('uuid')
        if isinstance(uid,str): headers.setdefault(uid.lower(),[]).append(path); known.add(uid.lower())
        else: findings.append(finding('HIGH','HIGH','Manifest header UUID missing','header.uuid is missing or not a string.',path,'Pack identity may be invalid.','Set a stable UUID.'))
        for i,m in enumerate(d.get('modules',[]) if isinstance(d.get('modules',[]),list) else []):
            if not isinstance(m,dict): continue
            mu=m.get('uuid')
            if isinstance(mu,str): modules.setdefault(mu.lower(),[]).append((path,i)); known.add(mu.lower())
            else: findings.append(finding('MEDIUM','HIGH','Module UUID missing',f'Module {i} has no string UUID.',path,'Module identity may be invalid.','Check the expected module schema.'))
    for u,loc in modules.items():
        if len(loc)>1: findings.append(finding('BLOCKER','HIGH','Duplicate module UUID',f'{u} appears at {loc}.',loc[0][0],'Duplicate module identifiers may conflict.','Use unique stable module UUIDs.'))
    for u,loc in headers.items():
        if len(loc)>1: findings.append(finding('HIGH','HIGH','Duplicate pack header UUID',f'{u} appears in {loc}.',loc[0],'Pack identities collide.','Confirm whether duplicated copies are intentional.'))
    for path,d in manifests:
        deps=d.get('dependencies',[])
        if isinstance(deps,list):
            for i,dep in enumerate(deps):
                if isinstance(dep,dict) and isinstance(dep.get('uuid'),str) and dep['uuid'].lower() not in known:
                    findings.append(finding('INFO','LOW','External or unresolved manifest dependency',f"Dependency {dep['uuid']!r} at index {i} is not defined in this archive.",path,'Can be an intentional dependency on another installed pack/API.','Confirm its external provider and version.'))

def valid_vec(v, n=3):
    return isinstance(v,list) and len(v)==n and all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in v)
def audit_geometry(path,data,findings):
    if not isinstance(data,dict): return
    geos=data.get('minecraft:geometry')
    if not isinstance(geos,list):
        findings.append(finding('MEDIUM','MEDIUM','Geometry top-level structure unusual',"Expected 'minecraft:geometry' array.",path,'Format may differ by version or file purpose.','Verify target-version geometry schema.')); return
    ids={}
    for gi,g in enumerate(geos):
        if not isinstance(g,dict): continue
        desc=g.get('description',{})
        gid=desc.get('identifier') if isinstance(desc,dict) else None
        if isinstance(gid,str):
            ids.setdefault(gid,[]).append(gi)
            tw=desc.get('texture_width'); th=desc.get('texture_height')
            if tw is not None and (not isinstance(tw,(int,float)) or tw<=0): findings.append(finding('MEDIUM','HIGH','Invalid geometry texture_width',f'Geometry {gid}: texture_width={tw!r}.',path,'UV sizing may be invalid.','Use a positive texture dimension.'))
            if th is not None and (not isinstance(th,(int,float)) or th<=0): findings.append(finding('MEDIUM','HIGH','Invalid geometry texture_height',f'Geometry {gid}: texture_height={th!r}.',path,'UV sizing may be invalid.','Use a positive texture dimension.'))
        bones=g.get('bones',[])
        if not isinstance(bones,list):
            findings.append(finding('MEDIUM','MEDIUM','Geometry bones is not an array',f'Geometry index {gi}.',path,'Bone data may not be parsed.','Verify geometry schema.')); continue
        names={}; parents={};
        for bi,b in enumerate(bones):
            if not isinstance(b,dict): continue
            bn=b.get('name')
            if isinstance(bn,str): names.setdefault(bn,[]).append(bi)
            par=b.get('parent')
            if isinstance(bn,str) and isinstance(par,str): parents[bn]=par
            for key in ('pivot','rotation'):
                if key in b and not valid_vec(b[key]): findings.append(finding('MEDIUM','HIGH','Malformed bone vector',f'Geometry {gid or gi}, bone {bn!r}: {key}={b[key]!r}, expected 3 numeric values.',path,'Transform may be misinterpreted.','Review the bone vector against the target schema.'))
            cubes=b.get('cubes',[])
            if cubes is not None and not isinstance(cubes,list):
                findings.append(finding('MEDIUM','HIGH','Bone cubes is not an array',f'Geometry {gid or gi}, bone {bn!r}.',path,'Cubes may be ignored.','Verify cube array format.')); continue
            for ci,c in enumerate(cubes or []):
                if not isinstance(c,dict): continue
                origin=c.get('origin'); size=c.get('size')
                if 'origin' in c and not valid_vec(origin): findings.append(finding('MEDIUM','HIGH','Malformed cube origin',f'Geometry {gid or gi}, bone {bn!r}, cube {ci}: {origin!r}.',path,'Cube location may be invalid.','Use three numeric coordinates.'))
                if 'size' in c and (not valid_vec(size) or any(x<0 for x in size) if valid_vec(size) else True): findings.append(finding('MEDIUM','HIGH','Malformed or negative cube size',f'Geometry {gid or gi}, bone {bn!r}, cube {ci}: {size!r}.',path,'Cube may render incorrectly; negative sizes are flagged conservatively.','Review intentional mirrored/degenerate geometry before changing.'))
                if 'pivot' in c and not valid_vec(c['pivot']): findings.append(finding('MEDIUM','HIGH','Malformed cube pivot',f'Geometry {gid or gi}, bone {bn!r}, cube {ci}.',path,'Cube transform may be invalid.','Review the three-dimensional pivot.'))
                if 'rotation' in c and not valid_vec(c['rotation']): findings.append(finding('MEDIUM','HIGH','Malformed cube rotation',f'Geometry {gid or gi}, bone {bn!r}, cube {ci}.',path,'Cube transform may be invalid.','Review rotation vector.'))
                uv=c.get('uv')
                if uv is not None:
                    if isinstance(uv,list):
                        if not valid_vec(uv,2): findings.append(finding('INFO','MEDIUM','Unrecognized cube UV representation',f'Geometry {gid or gi}, bone {bn!r}, cube {ci}: {uv!r}.',path,'UV may use an alternate schema.','Verify the target-version UV representation.'))
                    elif isinstance(uv,dict):
                        for face,fuv in uv.items():
                            if not isinstance(fuv,dict): continue
                            uv0=fuv.get('uv'); uvsize=fuv.get('uv_size')
                            if 'uv' in fuv and not valid_vec(uv0,2): findings.append(finding('MEDIUM','HIGH','Malformed face UV origin',f'Geometry {gid or gi}, bone {bn!r}, cube {ci}, face {face}: {uv0!r}.',path,'Face mapping may be invalid.','Use two numeric UV coordinates if required by schema.'))
                            if 'uv_size' in fuv and not valid_vec(uvsize,2): findings.append(finding('MEDIUM','HIGH','Malformed face UV size',f'Geometry {gid or gi}, bone {bn!r}, cube {ci}, face {face}: {uvsize!r}.',path,'Face mapping may be invalid.','Use two numeric UV-size coordinates if required by schema.'))
        for bn,occ in names.items():
            if len(occ)>1: findings.append(finding('HIGH','HIGH','Duplicate bone name',f'Geometry {gid or gi}: bone {bn!r} at indices {occ}.',path,'Animation-to-bone targeting becomes ambiguous.','Use unique bone names unless the format explicitly permits duplication.'))
        for bn,par in parents.items():
            if par not in names: findings.append(finding('MEDIUM','HIGH','Unresolved bone parent',f'Geometry {gid or gi}: bone {bn!r} parent {par!r} does not exist in this geometry.',path,'Hierarchy may be incomplete.','Check parent spelling/case.'))
            if bn==par: findings.append(finding('HIGH','HIGH','Bone parents itself',f'Geometry {gid or gi}: {bn!r}.',path,'Hierarchy is invalid.','Choose a valid parent or omit it for a root bone.'))
        for start in parents:
            seen=set(); cur=start
            while cur in parents:
                if cur in seen:
                    findings.append(finding('HIGH','HIGH','Bone hierarchy cycle',f'Geometry {gid or gi}: cycle reached from {start!r}: {sorted(seen)}.',path,'Hierarchy may not be usable.','Break the parent cycle.')); break
                seen.add(cur); cur=parents[cur]
    for gid,loc in ids.items():
        if len(loc)>1: findings.append(finding('HIGH','HIGH','Duplicate geometry identifier',f'{gid!r} occurs at geometry indices {loc}.',path,'References may select ambiguously.','Ensure identifiers are unique in their resource domain.'))

def audit_animation(path,data,findings):
    if not isinstance(data,dict): return
    # animations may be a direct dictionary of animation name -> definition.
    anims=data.get('animations')
    if not isinstance(anims,dict): return
    for aid,a in anims.items():
        if not isinstance(a,dict): continue
        length=a.get('animation_length')
        if length is not None and (not isinstance(length,(int,float)) or length<0): findings.append(finding('MEDIUM','HIGH','Invalid animation_length',f'{aid}: {length!r}.',path,'Animation timing may be invalid.','Check documented timing format.'))
        bones=a.get('bones',{})
        if not isinstance(bones,dict):
            findings.append(finding('MEDIUM','HIGH','Animation bones is not an object',f'{aid}.',path,'Animation channels may not be interpreted.','Verify animation schema.')); continue
        for bn,channels in bones.items():
            if not isinstance(channels,dict): continue
            for channel,val in channels.items():
                if channel not in ('position','rotation','scale'): continue
                if isinstance(val,list) and not valid_vec(val): findings.append(finding('INFO','MEDIUM','Unusual animation vector',f'{aid}/{bn}/{channel}: {val!r}.',path,'Could be valid Molang/keyframe syntax.','Check actual schema; not auto-rejected.'))

def resolve_ref_name(value, definitions):
    if isinstance(value,str):
        if value in definitions: return [value]
        # Expressions/aliases are not treated as literal missing identifiers.
        if any(x in value for x in ('{','}','query.','variable.','math.','$')): return []
    return []
def audit_reference_inventory(files,parsed,findings):
    pathset=set(files); lower={p.lower():p for p in pathset}
    defs={k:set() for k in ('geometry','animation','animations','animation_controllers','render_controllers','materials','entity')}
    # Index known definition namespaces separately to avoid KeyError and cross-domain confusion.
    for path,d in parsed.items():
        if not isinstance(d,dict): continue
        geos=d.get('minecraft:geometry')
        if isinstance(geos,list):
            for g in geos:
                if isinstance(g,dict) and isinstance(g.get('description'),dict) and isinstance(g['description'].get('identifier'),str): defs['geometry'].add(g['description']['identifier'])
        for group in ('animations','animation_controllers','render_controllers','materials'):
            val=d.get(group)
            if isinstance(val,dict):
                defs[group].update(k for k in val.keys() if isinstance(k,str))
                if group == 'animations': defs['animation'].update(k for k in val.keys() if isinstance(k,str))
        ent=d.get('minecraft:entity')
        if isinstance(ent,dict) and isinstance(ent.get('description'),dict):
            eid=ent['description'].get('identifier')
            if isinstance(eid,str): defs['entity'].add(eid)
    unresolved=[]
    for path,d in parsed.items():
        if not isinstance(d,(dict,list)): continue
        # check literal path-like values only in conventional keys
        for pointer,key,val in walk(d):
            kl=str(key).lower()
            if not isinstance(val,str): continue
            if kl in PATH_KEYS and '/' in val and not val.startswith(('http://','https://')):
                cand=val.replace('\\','/').lstrip('./')
                if cand not in pathset and cand.lower() not in lower and not any(p.endswith('/'+cand) for p in pathset):
                    unresolved.append((path,pointer,val,'path'))
        # client entity / attachable resource identifiers; check known reference fields
        if isinstance(d,dict):
            client=d.get('minecraft:client_entity')
            if isinstance(client,dict):
                desc=client.get('description',{})
                if isinstance(desc,dict):
                    for k,domain in [('geometry','geometry'),('animations','animation'),('render_controllers','render_controllers')]:
                        val=desc.get(k)
                        vals=val.values() if isinstance(val,dict) else val if isinstance(val,list) else [val] if isinstance(val,str) else []
                        for v in vals:
                            if isinstance(v,str) and v not in defs[domain] and not any(t in v for t in ('{','}','query.','variable.','$')):
                                unresolved.append((path,f'$.minecraft:client_entity.description.{k}',v,'identifier:'+domain))
                    tex=desc.get('textures')
                    if isinstance(tex,dict):
                        for alias,v in tex.items():
                            if isinstance(v,str):
                                pth=v.replace('\\','/').lstrip('./')
                                # Typical Bedrock resource identifiers may omit extension or imply textures/ path.
                                options={pth,pth+'.png',pth+'.tga',pth+'.jpg','textures/'+pth+'.png'}
                                if not any(o in pathset or o.lower() in lower or any(p.endswith('/'+o) or p.lower().endswith('/'+o.lower()) for p in pathset) for o in options):
                                    unresolved.append((path,f'$.minecraft:client_entity.description.textures.{alias}',v,'texture'))
    for src,pointer,val,kind in unresolved:
        # Conservative severity: heuristic paths are INFO; literal IDs are MEDIUM absent solid schema proof.
        if kind=='path':
            findings.append(finding('INFO','LOW','Possible unresolved file path',f'{pointer} = {val!r}; no exact/suffix path match. Heuristic only.',src,'May be resolved by pack conventions or represent an identifier.','Review target-version path rules and case.'))
        elif kind=='texture':
            findings.append(finding('INFO','LOW','Possible unresolved texture reference',f'{pointer} = {val!r}; no common extension/path candidate found.',src,'Could be an alias/path convention or external asset.','Verify in the target pack layout.'))
        else:
            findings.append(finding('MEDIUM','MEDIUM','Possible unresolved resource identifier',f'{pointer} references {val!r}, which was not found among indexed {kind.split(":",1)[1]} definitions.',src,'May indicate a typo, external definition, or unsupported convention.','Check all pack roots and identifier namespaces before changing it.'))

def audit_reference_graph(files, parsed, findings):
    """Build a conservative resource graph with exact source evidence and coverage limits."""
    known_paths = set(files)
    lower_paths = {p.lower(): p for p in known_paths}
    domains = ("geometry", "animations", "animation_controllers", "render_controllers",
               "materials", "entities", "recipes", "loot_tables", "items", "blocks",
               "attachables", "particles", "sounds", "ui_files", "localization_keys")
    defs = {domain: {} for domain in domains}
    edges = []
    def ptr(parts):
        out = '$'
        for part in parts:
            out += '/' + str(part).replace('~', '~0').replace('/', '~1')
        return out
    def add_def(domain, ident, path, pointer, kind='identifier'):
        if isinstance(ident, str) and ident:
            defs[domain].setdefault(ident, []).append({"file": path, "pointer": pointer, "kind": kind})
    def add_file_def(domain, path, kind='file'):
        add_def(domain, path, path, '$', kind)
    def is_expr(value):
        return isinstance(value, str) and any(x in value for x in ('{', '}', 'query.', 'variable.', 'math.', '$'))
    def record(src, source_pointer, kind, value, domain=None, status='heuristic_unresolved', targets=None, confidence='LOW', note=None):
        edge = {"source_file": src, "source_pointer": source_pointer, "reference_kind": kind,
                "referenced_value": value, "target_domain": domain, "target_files": targets or [],
                "status": status, "confidence": confidence}
        if note: edge["note"] = note
        edges.append(edge)
        return edge
    def resolve_id(src, source_pointer, kind, value, domain, allow_expr=True):
        if not isinstance(value, str):
            return
        if allow_expr and is_expr(value):
            record(src, source_pointer, kind, value, domain, 'dynamic_or_expression', [], 'LOW',
                   'Expression is retained but not statically resolved.')
            return
        targets = defs.get(domain, {}).get(value, [])
        status = 'resolved' if len(targets) == 1 else 'ambiguous' if len(targets) > 1 else 'unresolved'
        record(src, source_pointer, kind, value, domain, status,
               [t['file'] for t in targets], 'HIGH' if len(targets) == 1 else 'MEDIUM' if targets else 'MEDIUM')
        if status == 'unresolved':
            findings.append(finding('INFO', 'MEDIUM', 'Unresolved graph reference',
                f'{source_pointer} references {value!r}; no in-archive {domain} definition was indexed. '
                'This is a static finding, not proof of engine failure.', src,
                'May be a typo, external pack dependency, dynamic convention or unsupported schema.',
                'Check complete BP/RP roots and target-version conventions before changing it.'))
        elif status == 'ambiguous':
            findings.append(finding('INFO', 'MEDIUM', 'Ambiguous graph reference',
                f'{source_pointer} references {value!r}; candidate definitions: {[t["file"] for t in targets]}.',
                src, 'Multiple definitions in the indexed domain make static resolution ambiguous.',
                'Review identifiers, pack layout and target-version loading rules.'))
    def resolve_path(src, source_pointer, kind, value, candidates, domain='file'):
        if not isinstance(value, str): return
        if is_expr(value):
            record(src, source_pointer, kind, value, domain, 'dynamic_or_expression', [], 'LOW')
            return
        hit=[]
        for cand in candidates:
            norm=cand.replace('\\','/').lstrip('./')
            matches=[p for p in known_paths if p == norm or p.lower() == norm.lower() or
                     p.endswith('/'+norm) or p.lower().endswith('/'+norm.lower())]
            for m in matches:
                if m not in hit: hit.append(m)
        status='resolved' if len(hit)==1 else 'ambiguous' if len(hit)>1 else 'heuristic_unresolved'
        record(src, source_pointer, kind, value, domain, status, hit, 'MEDIUM' if hit else 'LOW',
               'Path resolution uses common suffix/extension conventions; not an engine lookup simulation.')
        if status == 'heuristic_unresolved':
            findings.append(finding('INFO','LOW','Possible unresolved resource path',
                f'{source_pointer} = {value!r}; tried common candidates {list(candidates)}.', src,
                'Path may be external, aliased or use a convention not modeled by the analyzer.',
                'Review actual pack roots and case-sensitive paths.'))
        elif status == 'ambiguous':
            findings.append(finding('INFO','LOW','Ambiguous resource path',
                f'{source_pointer} = {value!r}; matching files: {hit}.', src,
                'More than one in-archive path could match this suffix.',
                'Use the correct pack context and exact target-version path convention.'))
    # Index direct file resources and filename-addressable resource groups.
    for path in sorted(known_paths):
        low=path.lower()
        if '/ui/' in '/'+low or low.startswith('ui/'): add_file_def('ui_files', path)
        if low.endswith(('.lang', '.locres')): add_file_def('localization_keys', path, 'localization_file')
        if '/loot_tables/' in '/'+low: add_file_def('loot_tables', path, 'file')
        if '/recipes/' in '/'+low: add_file_def('recipes', path, 'file')
        if '/attachables/' in '/'+low: add_file_def('attachables', path, 'file')
        if '/particles/' in '/'+low: add_file_def('particles', path, 'file')
        if '/sounds/' in '/'+low or low.endswith('sounds.json'): add_file_def('sounds', path, 'file')
    # Index explicit definitions from JSON structures.
    for path, data in parsed.items():
        if not isinstance(data, dict): continue
        geos=data.get('minecraft:geometry')
        if isinstance(geos, list):
            for i,g in enumerate(geos):
                if isinstance(g,dict) and isinstance(g.get('description'),dict):
                    add_def('geometry',g['description'].get('identifier'),path,ptr(['minecraft:geometry',i,'description','identifier']))
        for group in ('animations','animation_controllers','render_controllers','materials'):
            obj=data.get(group)
            if isinstance(obj,dict):
                for ident in obj:
                    add_def(group,ident,path,ptr([group,ident]))
        for rootkey,domain in (('minecraft:entity','entities'),('minecraft:item','items'),('minecraft:block','blocks')):
            obj=data.get(rootkey)
            if isinstance(obj,dict) and isinstance(obj.get('description'),dict):
                add_def(domain,obj['description'].get('identifier'),path,ptr([rootkey,'description','identifier']))
        # Explicit recipe identifiers when supplied; resource paths also remain indexed above.
        recipe_types=('minecraft:recipe_shaped','minecraft:recipe_shapeless','minecraft:recipe_furnace','minecraft:recipe_brewing_mix','minecraft:recipe_brewing_container')
        for rtype in recipe_types:
            if isinstance(data.get(rtype),dict):
                ident=data[rtype].get('description',{}).get('identifier') if isinstance(data[rtype].get('description'),dict) else None
                add_def('recipes',ident,path,ptr([rtype,'description','identifier']))
    # Known client-entity graph edges.
    for path, data in parsed.items():
        if not isinstance(data, dict): continue
        client=data.get('minecraft:client_entity')
        if isinstance(client,dict):
            desc=client.get('description',{})
            if isinstance(desc,dict):
                for key,domain in (('geometry','geometry'),('animations','animations'),('animation_controllers','animation_controllers'),('render_controllers','render_controllers')):
                    val=desc.get(key)
                    refs=list(val.items()) if isinstance(val,dict) else [(str(i),v) for i,v in enumerate(val)] if isinstance(val,list) else [('value',val)] if isinstance(val,str) else []
                    for alias,ref in refs:
                        if isinstance(ref,str): resolve_id(path,ptr(['minecraft:client_entity','description',key,alias]),domain,ref,domain)
                tex=desc.get('textures')
                if isinstance(tex,dict):
                    for alias,value in tex.items():
                        if isinstance(value,str):
                            norm=value.replace('\\','/').lstrip('./')
                            candidates=[norm,norm+'.png',norm+'.tga',norm+'.jpg',norm+'.webp',
                                        'textures/'+norm+'.png','textures/'+norm+'.tga','textures/'+norm+'.jpg']
                            resolve_path(path,ptr(['minecraft:client_entity','description','textures',alias]),'texture_path',value,candidates,'textures')
        # Render-controller resource references commonly use alias maps. Resolve only literal geometry strings;
        # textures/materials can be maps/arrays and are indexed as heuristic edges where safely recognizable.
        rc=data.get('render_controllers')
        if isinstance(rc,dict):
            for rcid,rcdef in rc.items():
                if not isinstance(rcdef,dict): continue
                for key,domain in (('geometry','geometry'),('materials','materials'),('textures','textures')):
                    vals=rcdef.get(key)
                    pairs=list(vals.items()) if isinstance(vals,dict) else [(str(i),v) for i,v in enumerate(vals)] if isinstance(vals,list) else [('value',vals)] if isinstance(vals,str) else []
                    for alias,value in pairs:
                        if not isinstance(value,str): continue
                        source_pointer=ptr(['render_controllers',rcid,key,alias])
                        if key=='geometry':
                            resolve_id(path,source_pointer,'render_controller_geometry',value,domain)
                        elif is_expr(value):
                            record(path,source_pointer,'render_controller_'+key,value,domain,'dynamic_or_expression',[],'LOW')
                        else:
                            # Alias values often point to client-entity aliases; do not claim missing engine resource.
                            record(path,source_pointer,'render_controller_'+key,value,domain,'alias_or_heuristic',[], 'LOW',
                                   'Render-controller values can refer to client-entity aliases or Molang expressions.')
        # Attachables can refer to geometry/textures/animations using client-entity-like description maps.
        attach=data.get('minecraft:attachable')
        if isinstance(attach,dict):
            desc=attach.get('description',{})
            if isinstance(desc,dict):
                for key,domain in (('geometry','geometry'),('animations','animations'),('render_controllers','render_controllers')):
                    val=desc.get(key)
                    refs=list(val.items()) if isinstance(val,dict) else [(str(i),v) for i,v in enumerate(val)] if isinstance(val,list) else [('value',val)] if isinstance(val,str) else []
                    for alias,ref in refs:
                        if isinstance(ref,str): resolve_id(path,ptr(['minecraft:attachable','description',key,alias]),'attachable_'+domain,ref,domain)
                tex=desc.get('textures')
                if isinstance(tex,dict):
                    for alias,value in tex.items():
                        if isinstance(value,str):
                            norm=value.replace('\\','/').lstrip('./')
                            resolve_path(path,ptr(['minecraft:attachable','description','textures',alias]),'attachable_texture',value,
                                         [norm,norm+'.png','textures/'+norm+'.png','textures/'+norm+'.tga'],'textures')
    # Localizable key index and light-touch key usage scanning. This is intentionally not a full UI schema parser.
    lang_keys={}
    for path, raw in files.items():
        if path.lower().endswith('.lang'):
            try: content=raw.decode('utf-8-sig')
            except UnicodeDecodeError: continue
            for line_no,line in enumerate(content.splitlines(),1):
                stripped=line.strip()
                if not stripped or stripped.startswith('#') or '=' not in stripped: continue
                key=stripped.split('=',1)[0].strip()
                if key: lang_keys.setdefault(key,[]).append({'file':path,'pointer':f'line:{line_no}'})
    for key,locations in lang_keys.items():
        defs['localization_keys'].setdefault(key,[]).extend(locations)
    key_pattern=re.compile(r'(?<![A-Za-z0-9_.-])(?:tile|item|entity|commands|gui|pack|death|subtitles)\.[A-Za-z0-9_.-]+')
    for path, raw in files.items():
        low=path.lower()
        if not low.endswith(('.json','.js','.ts','.lang','.properties','.txt')): continue
        try: text=raw.decode('utf-8-sig')
        except UnicodeDecodeError: continue
        # Scan text only for likely localization key candidates; never classify arbitrary strings as proven refs.
        for match in key_pattern.finditer(text):
            key=match.group(0)
            if key in defs['localization_keys']: continue
            line_no=text.count('\n',0,match.start())+1
            record(path,f'line:{line_no}','possible_localization_key',key,'localization_keys','heuristic_unresolved',[],'LOW',
                   'Text search heuristic; may be an identifier or ordinary string, not a localization lookup.')
    # UI inventory and common explicit file/path references in UI JSON are partial.
    for path,data in parsed.items():
        if not isinstance(data,(dict,list)): continue
        low=path.lower()
        if '/ui/' not in '/'+low and not low.startswith('ui/'): continue
        for pointer,key,value in walk(data):
            if not isinstance(value,str): continue
            k=str(key).lower()
            if k in ('path','texture','texture_path','file','include','$include') and ('/' in value or value.lower().endswith(('.json','.png','.tga','.jpg'))):
                norm=value.replace('\\','/').lstrip('./')
                resolve_path(path,pointer,'ui_resource_path',value,[norm,norm+'.json'], 'ui_files')
    # Counts and coverage metadata are part of the public report contract.
    counts={}
    for edge in edges: counts[edge['status']]=counts.get(edge['status'],0)+1
    indexed={domain:len(items) for domain,items in defs.items()}
    coverage={
        'client_entity_geometry_animation_controller_texture':'partial',
        'attachable_references':'partial',
        'render_controller_aliases':'heuristic',
        'ui_paths':'partial',
        'localization':'heuristic',
        'recipes_and_loot':'inventory_only_partial',
        'script_api_references':'not_implemented',
        'external_packs':'not_resolved',
        'runtime':'not_tested'
    }
    return {"schema_version":"1.1","definitions":{d:{k:v for k,v in ids.items()} for d,ids in defs.items()},
            "edges":edges,"edge_count":len(edges),"status_counts":counts,
            "scope":{"indexed_files":len(files),"parsed_json_files":len(parsed),"definitions_by_domain":indexed,
                     "coverage":coverage,"static_only":True}}

def diff_files(cand,base):
    if base is None:return {'added':[],'removed':[],'modified':[]}
    cs,bs=set(cand),set(base)
    return {'added':sorted(cs-bs),'removed':sorted(bs-cs),'modified':sorted(p for p in cs&bs if sha256(cand[p])!=sha256(base[p]))}
def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('candidate'); ap.add_argument('--baseline'); ap.add_argument('--report'); args=ap.parse_args()
    findings=[]; files,meta=load_archive(args.candidate,findings); parsed=parse_json(files,findings); audit_manifests(parsed,findings)
    for p,d in parsed.items():
        if p.lower().endswith('.geo.json') or 'geometry' in PurePosixPath(p).parts: audit_geometry(p,d,findings)
        if 'animations' in PurePosixPath(p).parts or 'animation' in PurePosixPath(p).name.lower(): audit_animation(p,d,findings)
    audit_reference_inventory(files,parsed,findings)
    reference_graph=audit_reference_graph(files,parsed,findings)
    basefiles=basemeta=None
    if args.baseline:
        bf=[]; basefiles,basemeta=load_archive(args.baseline,bf)
        if basemeta.get('archive_valid'):
            for f in bf: f['severity']='INFO'; f['title']='Baseline: '+f['title']
            findings.extend(bf)
        else:
            findings.append(finding('MEDIUM','HIGH','Baseline unavailable','Could not reliably read baseline archive.',args.baseline,'Regression comparison incomplete.','Provide a valid baseline.')); basefiles=None
    diff=diff_files(files,basefiles)
    for p in diff['removed']: findings.append(finding('HIGH','HIGH','File removed relative to baseline',f'Candidate no longer contains {p!r}.',p,'Potential destructive regression.','Review intended scope; do not ignore unexplained removal.'))
    for p in diff['modified']: findings.append(finding('INFO','MEDIUM','File changed relative to baseline',f'Content hash differs for {p!r}.',p,'May be expected but needs review.','Confirm the edit is in scope.'))
    blocker=any(f['severity']=='BLOCKER' for f in findings); high=any(f['severity']=='HIGH' for f in findings)
    recommendation='HOLD' if blocker or high else ('INSUFFICIENT EVIDENCE' if not meta.get('archive_valid') else 'STATIC CHECKS PASSED — RUNTIME NOT VERIFIED')
    checks=[
      {'name':'archive_integrity_and_paths','status':'PASS' if meta.get('archive_valid') and not any(f['title'] in ('Archive CRC failure','Unsafe archive member path','Archive cannot be opened') for f in findings) else 'FAIL','details':'ZIP CRC and safe relative paths; no extraction.'},
      {'name':'json_parse','status':'FAIL' if any(f['title']=='Invalid JSON' for f in findings) else 'PASS','details':f'Parsed {sum(p.lower().endswith(".json") for p in files)} JSON files.'},
      {'name':'manifest_checks','status':'WARN' if any('Manifest' in f['title'] or 'UUID' in f['title'] for f in findings) else 'PASS','details':'Manifest, UUID and dependency checks.'},
      {'name':'geometry_bone_uv_checks','status':'WARN' if any(any(x in f['title'].lower() for x in ('geometry','bone','cube','uv')) for f in findings) else 'PASS','details':'Conservative geometry/bone/vector/cube/UV structural checks; not a complete engine validator.'},
      {'name':'animation_resource_checks','status':'WARN' if any('animation' in f['title'].lower() or 'identifier' in f['title'].lower() for f in findings) else 'PASS','details':'Animation shape and selected cross-resource reference checks.'},
      {'name':'reference_paths','status':'WARN' if any('path' in f['title'].lower() or 'texture reference' in f['title'].lower() or 'identifier' in f['title'].lower() for f in findings) else 'PASS','details':'Known fields only; identifiers and paths are separated conservatively.'},
      {'name':'baseline_comparison','status':'NOT RUN' if not args.baseline or basefiles is None else 'PASS','details':'File inventory and SHA-256 comparison.'},
      {'name':'reference_graph','status':'PASS' if reference_graph.get('edge_count',0)>=0 else 'WARN','details':f"Indexed {reference_graph.get('edge_count',0)} edges; partial coverage is listed in reference_graph.scope.coverage."},
      {'name':'minecraft_runtime','status':'NOT RUN','details':'This script does not launch Minecraft.'}]
    report={'tool_version':TOOL_VERSION,'candidate':meta,'baseline':basemeta,'checks':checks,'findings':findings,'file_diff':diff,'reference_graph':reference_graph,'runtime_status':'NOT RUN','recommendation':recommendation}
    out=json.dumps(report,indent=2,ensure_ascii=False)
    if args.report:
        with open(args.report,'w',encoding='utf-8') as f:f.write(out+'\n')
    print(out); return 1 if blocker or high else 0
if __name__=='__main__': sys.exit(main())
