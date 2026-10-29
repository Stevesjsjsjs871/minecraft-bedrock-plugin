#!/usr/bin/env python3
"""Static, conservative Bedrock resource audit for ZIP-compatible packs.
Does not extract files, launch Minecraft, or claim runtime correctness.
Python 3 standard library only. Model-format assumptions are intentionally conservative.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys, zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from archive_safety import validate_zip_limits

VERSION_FILE = ROOT / "VERSION"
TOOL_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
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
    meta={"path":path,"sha256":None,"archive_valid":False}; files={}
    try:
        validate_zip_limits(path)
        meta["sha256"] = sha256_file(path)
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
    except (OSError,zipfile.BadZipFile,RuntimeError,ValueError) as e:
        findings.append(finding('BLOCKER','HIGH','Archive cannot be opened safely',str(e),path,'Archive contents unavailable or exceeded the declared resource limits.','Supply a valid ZIP-compatible archive within documented limits.'))
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

def audit_animation_controllers(path, data, findings):
    """Check literal controller state targets without evaluating Molang conditions."""
    controllers = data.get('animation_controllers') if isinstance(data, dict) else None
    if not isinstance(controllers, dict):
        return
    for controller_id, controller in controllers.items():
        if not isinstance(controller, dict):
            continue
        states = controller.get('states')
        if not isinstance(states, dict):
            findings.append(finding(
                'MEDIUM', 'MEDIUM', 'Animation controller states malformed',
                f'{controller_id}: expected an object at animation_controllers/{controller_id}/states.',
                path, 'State transitions cannot be checked because the state map is unavailable.',
                'Verify the controller against the target-version animation-controller schema.'))
            continue
        initial = controller.get('initial_state')
        if isinstance(initial, str) and initial not in states:
            findings.append(finding(
                'MEDIUM', 'HIGH', 'Unresolved animation controller initial state',
                f'{controller_id}: initial_state={initial!r} is not a key in states ({sorted(str(k) for k in states)}).',
                path, 'The controller may begin in a state that is not defined.',
                'Correct the initial_state spelling or add the intended state.'))
        for state_name, state in states.items():
            if not isinstance(state, dict):
                continue
            transitions = state.get('transitions', [])
            if transitions is None:
                continue
            if not isinstance(transitions, list):
                findings.append(finding(
                    'INFO', 'MEDIUM', 'Animation controller transitions unusual',
                    f'{controller_id}/{state_name}: transitions should be an array for this check; received {type(transitions).__name__}.',
                    path, 'Transition targets were not fully inspected.',
                    'Confirm the transition structure for the selected Bedrock version.'))
                continue
            for transition_index, transition in enumerate(transitions):
                if not isinstance(transition, dict):
                    continue
                # In the usual Bedrock form, the transition target is the key and
                # the value is a Molang condition. Never evaluate the condition.
                for target_state in transition:
                    if isinstance(target_state, str) and target_state not in states:
                        findings.append(finding(
                            'MEDIUM', 'HIGH', 'Unresolved animation controller transition state',
                            f'{controller_id}/{state_name}/transitions/{transition_index}: target state {target_state!r} is not defined in this controller.',
                            path, 'When the transition condition becomes true, its target may not exist.',
                            'Fix the target state name or add the intended state.'))


def audit_animation_bone_references(parsed, findings):
    """Report bone targets absent from all indexed geometry as INFO/LOW only."""
    geometry_bones = set()
    geometry_count = 0
    for data in parsed.values():
        if not isinstance(data, dict):
            continue
        geometries = data.get('minecraft:geometry')
        if not isinstance(geometries, list):
            continue
        for geometry in geometries:
            if not isinstance(geometry, dict):
                continue
            geometry_count += 1
            bones = geometry.get('bones', [])
            if isinstance(bones, list):
                geometry_bones.update(
                    bone.get('name') for bone in bones
                    if isinstance(bone, dict) and isinstance(bone.get('name'), str)
                )
    # No geometry means no safe in-archive comparison can be made.
    if geometry_count == 0:
        return
    for animation_path, data in parsed.items():
        if not isinstance(data, dict):
            continue
        animations = data.get('animations')
        if not isinstance(animations, dict):
            continue
        for animation_id, animation in animations.items():
            if not isinstance(animation, dict):
                continue
            bones = animation.get('bones')
            if not isinstance(bones, dict):
                continue
            for bone_name in bones:
                if not isinstance(bone_name, str) or bone_name in geometry_bones:
                    continue
                if any(token in bone_name for token in ('{', '}', 'query.', 'variable.', '$')):
                    continue
                findings.append(finding(
                    'INFO', 'LOW', 'Possible unresolved animation bone target',
                    f'animations/{animation_id}/bones/{bone_name}: bone name was not found in any of {geometry_count} indexed geometry definition(s). Cross-geometry association is not inferred.',
                    animation_path, 'This can be a typo, but the animation may belong to an external/omitted geometry or an alternate model context.',
                    'Check the animation against every geometry that can use it before changing the bone name.'))

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
    # Recognizable UI-definition import edges (heuristic path resolution only).
    for path, data in parsed.items():
        if not isinstance(data, dict) or 'ui_defs' not in data:
            continue
        refs = data.get('ui_defs')
        if not isinstance(refs, list):
            continue
        source_parent = str(PurePosixPath(path).parent)
        for index, ref in enumerate(refs):
            if not isinstance(ref, str) or not ref.strip():
                continue
            candidates = [ref]
            if not ref.lower().endswith('.json'):
                candidates.append(ref + '.json')
            candidates.extend('ui/' + cand for cand in list(candidates))
            if source_parent not in ('', '.'):
                candidates.extend(str(PurePosixPath(source_parent) / cand) for cand in list(candidates))
            resolve_path(path, ptr(['ui_defs', index]), 'ui_definition_import', ref, candidates, 'ui_files')
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
    # Localization references from known UI text properties; literal-only and heuristic.
    lang_keys = {}
    for lang_path, raw in files.items():
        if not lang_path.lower().endswith('.lang'):
            continue
        try:
            lang_text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lang_text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in stripped:
                continue
            localization_key = stripped.split('=', 1)[0].strip()
            if localization_key:
                lang_keys.setdefault(localization_key, []).append({'file': lang_path, 'pointer': f'line:{line_no}'})
    # Record possible UI localization uses in the same graph as other cross-resource refs.
    for ui_path, ui_data in parsed.items():
        low = ui_path.lower().replace('\\', '/')
        if not ('/ui/' in '/' + low or low.startswith('ui/')):
            continue
        for pointer, key_name, value in walk(ui_data):
            if str(key_name).lower() != 'text' or not isinstance(value, str):
                continue
            match = re.fullmatch(r'\$([A-Za-z0-9_.-]+)', value.strip())
            if not match:
                continue
            key_value = match.group(1)
            target_files = [loc['file'] for loc in lang_keys.get(key_value, [])]
            record(ui_path, pointer, 'ui_localization_key', key_value, 'localization_keys',
                   'resolved' if target_files else 'heuristic_unresolved', target_files, 'HIGH' if target_files else 'LOW',
                   '' if target_files else 'Literal UI lookup was not found in indexed in-archive .lang files; external/dynamic sources may satisfy it.')
    # Known client-entity graph edges.
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
    # Literal BP/RP identifier links from common item and block component fields.
    # This deliberately checks an allowlist of exact component/field paths and skips expressions.
    for path, data in parsed.items():
        if not isinstance(data, dict):
            continue
        # Items and blocks declare identifiers in BP; only resolve against explicit in-pack definitions.
        entity = data.get('minecraft:entity')
        item = data.get('minecraft:item')
        block_data = data.get('minecraft:block')
        for root_key, root_data, domain in (
            ('minecraft:item', item, 'items'),
            ('minecraft:block', block_data, 'blocks'),
            ('minecraft:entity', entity, 'entities'),
        ):
            if not isinstance(root_data, dict):
                continue
            components = root_data.get('components')
            if not isinstance(components, dict):
                continue
            for component_name, component_value in components.items():
                if not isinstance(component_value, (str, dict, list)):
                    continue
                if component_name == 'minecraft:entity' and isinstance(component_value, dict):
                    ident = component_value.get('identifier')
                    if isinstance(ident, str):
                        resolve_id(path, ptr([root_key, 'components', component_name, 'identifier']),
                                   'component_entity_identifier', ident, 'entities')
                if component_name == 'minecraft:loot':
                    # Current documentation uses {"table": "loot_tables/...json"};
                    # keep literal string values readable for legacy/custom inputs too.
                    loot_ref = component_value.get('table') if isinstance(component_value, dict) else component_value
                    if isinstance(loot_ref, str) and loot_ref.strip():
                        loot_ref = loot_ref.replace('\\', '/').lstrip('./')
                        candidates = [loot_ref]
                        if not loot_ref.lower().endswith('.json'):
                            candidates.append(loot_ref + '.json')
                        if not loot_ref.startswith('loot_tables/'):
                            candidates.append('loot_tables/' + loot_ref + ('' if loot_ref.lower().endswith('.json') else '.json'))
                        pointer_parts = [root_key, 'components', component_name]
                        if isinstance(component_value, dict):
                            pointer_parts.append('table')
                        resolve_path(path, ptr(pointer_parts),
                                     'component_loot_table_path', loot_ref, candidates, 'loot_tables')
                    elif isinstance(component_value, dict):
                        findings.append(finding('INFO', 'MEDIUM', 'Loot component table path has an unusual shape',
                            'minecraft:loot is an object but its table field is not a non-empty string.', path,
                            'The analyzer cannot resolve the intended loot-table resource from this shape.',
                            'Check the minecraft:loot component against the target-version Creator documentation.'))
                if component_name == 'minecraft:icon':
                    icon_value = component_value.get('texture') if isinstance(component_value, dict) else component_value
                    if isinstance(icon_value, str) and not is_expr(icon_value):
                        # Item icons are generally aliases in item_texture.json, so retain alias-like status.
                        record(path, ptr([root_key, 'components', component_name]), 'item_icon_alias', icon_value,
                               'textures', 'alias_or_heuristic', [], 'LOW',
                               'Icon values commonly refer to aliases in textures/item_texture.json; alias expansion is not modeled.')
                if component_name == 'minecraft:display_name' and isinstance(component_value, dict):
                    value = component_value.get('value')
                    if isinstance(value, str) and value.startswith('$') and not is_expr(value[1:]):
                        key = value[1:]
                        targets = lang_keys.get(key, [])
                        record(path, ptr([root_key, 'components', component_name, 'value']),
                               'component_localization_key', key, 'localization_keys',
                               'resolved' if targets else 'heuristic_unresolved',
                               [t['file'] for t in targets], 'HIGH' if targets else 'LOW',
                               '' if targets else 'No matching in-archive .lang key; external or alternate localization providers may exist.')
    # Nested loot-table entry references. These are literal path candidates only;
    # dynamic expressions and external packs are not resolved.
    for path, data in parsed.items():
        normalized_path = path.lower().replace('\\', '/')
        if '/loot_tables/' not in '/' + normalized_path or not isinstance(data, dict):
            continue
        pools = data.get('pools')
        if not isinstance(pools, list):
            continue
        for pool_index, pool in enumerate(pools):
            if not isinstance(pool, dict) or not isinstance(pool.get('entries'), list):
                continue
            for entry_index, entry in enumerate(pool['entries']):
                if not isinstance(entry, dict) or entry.get('type') != 'loot_table':
                    continue
                value = entry.get('name')
                if not isinstance(value, str) or not value.strip():
                    continue
                ref = value.replace('\\', '/').lstrip('./')
                candidates = [ref]
                if not ref.lower().endswith('.json'):
                    candidates.append(ref + '.json')
                if not ref.startswith('loot_tables/'):
                    candidates.append('loot_tables/' + ref + ('' if ref.lower().endswith('.json') else '.json'))
                resolve_path(path, ptr(['pools', pool_index, 'entries', entry_index, 'name']),
                             'loot_table_entry_reference', value, candidates, 'loot_tables')

    # Report cycles only when every edge in the detected cycle resolved to one
    # in-archive target. This is a bounded static graph check, not an engine simulation.
    adjacency = {}
    for edge in edges:
        if edge.get('reference_kind') != 'loot_table_entry_reference' or edge.get('status') != 'resolved':
            continue
        targets = edge.get('target_files', [])
        if len(targets) == 1:
            adjacency.setdefault(edge['source_file'], []).append(targets[0])
    visit_state = {}
    reported_cycles = set()
    all_loot_nodes = sorted(set(adjacency) | {t for targets in adjacency.values() for t in targets})
    for root_node in all_loot_nodes:
        if visit_state.get(root_node, 0) != 0:
            continue
        node_stack = [root_node]
        stack_positions = {root_node: 0}
        visit_state[root_node] = 1
        frames = [(root_node, iter(adjacency.get(root_node, [])))]
        while frames:
            node, children = frames[-1]
            try:
                target = next(children)
            except StopIteration:
                frames.pop()
                finished = node_stack.pop()
                stack_positions.pop(finished, None)
                visit_state[finished] = 2
                continue
            state = visit_state.get(target, 0)
            if state == 0:
                visit_state[target] = 1
                stack_positions[target] = len(node_stack)
                node_stack.append(target)
                frames.append((target, iter(adjacency.get(target, []))))
            elif state == 1 and target in stack_positions:
                cycle_nodes = node_stack[stack_positions[target]:]
                signature = tuple(sorted(set(cycle_nodes)))
                if signature not in reported_cycles:
                    reported_cycles.add(signature)
                    chain = cycle_nodes + [target]
                    findings.append(finding('MEDIUM', 'HIGH', 'Recursive loot-table reference cycle',
                        'Resolved in-archive loot-table references form a cycle: ' + ' -> '.join(chain) + '.',
                        node, 'Recursive loot tables can cause the referenced loot branch to return no loot.',
                        'Break the cycle or replace one nested loot_table entry with a non-recursive table.'))

    # Counts and coverage metadata are part of the public report contract.
    counts={}
    for edge in edges: counts[edge['status']]=counts.get(edge['status'],0)+1
    indexed={domain:len(items) for domain,items in defs.items()}
    coverage={
        'client_entity_geometry_animation_controller_texture':'partial',
        'animation_controller_state_targets':'literal_targets_checked_molang_not_evaluated',
        'animation_bone_targets':'heuristic_global_geometry_inventory',
        'attachable_references':'partial',
        'render_controller_aliases':'heuristic',
        'ui_paths':'partial_with_ui_defs_import_edges_and_literal_text_lookup_checks',
        'localization':'heuristic_per_file_duplicate_and_literal_ui_lookup_checks',
        'ui_control_references':'heuristic_recognizable_namespace_candidates_only',
        'bp_item_block_entity_components':'partial_allowlisted_literal_fields_only',
        'item_icon_aliases':'not_expanded_alias_or_heuristic',
        'recipes_and_loot':'partial_literal_component_and_nested_loot_table_path_checks',
        'loot_table_structure':'conservative_common_fields_only',
        'loot_table_cycles':'resolved_in_archive_nested_reference_cycles_only',
        'script_api_references':'not_implemented',
        'external_packs':'not_resolved',
        'runtime':'not_tested'
    }
    return {"schema_version":"1.1","definitions":{d:{k:v for k,v in ids.items()} for d,ids in defs.items()},
            "edges":edges,"edge_count":len(edges),"status_counts":counts,
            "scope":{"indexed_files":len(files),"parsed_json_files":len(parsed),"definitions_by_domain":indexed,
                     "coverage":coverage,"static_only":True}}


def audit_ui_localization(files, parsed, findings):
    """Conservative UI file and .lang checks; never treats heuristics as engine proof."""
    known_paths = set(files)

    def is_ui_path(path):
        low = path.lower().replace('\\', '/')
        return '/ui/' in '/' + low or low.startswith('ui/')

    def resolve_ui_path(value, source_path):
        norm = value.replace('\\', '/').lstrip('./')
        candidates = [norm]
        if not norm.lower().endswith('.json'):
            candidates.append(norm + '.json')
        # Common pack-root and UI-root path interpretations only; no extraction or I/O.
        candidates.extend('ui/' + candidate for candidate in list(candidates))
        source_parent = str(PurePosixPath(source_path).parent)
        if source_parent not in ('', '.'):
            candidates.extend(str(PurePosixPath(source_parent) / candidate) for candidate in list(candidates))
        hits = []
        for candidate in candidates:
            for path in known_paths:
                if path == candidate or path.lower() == candidate.lower() or path.lower().endswith('/' + candidate.lower()):
                    if path not in hits:
                        hits.append(path)
        return hits

    # Duplicates are checked per file, not across locale files: translations
    # routinely define the same key in en_US.lang, fr_FR.lang, and others.
    lang_keys = {}
    for path, raw in files.items():
        if not path.lower().endswith('.lang'):
            continue
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            findings.append(finding('INFO', 'MEDIUM', 'Localization file is not UTF-8',
                'Could not decode .lang file as UTF-8; key checks were skipped.', path,
                'Localization coverage is incomplete for this file.',
                'Confirm the file encoding and expected game format.'))
            continue
        seen_in_file = {}
        for line_no, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in line:
                continue
            key = line.split('=', 1)[0].strip()
            if not key:
                findings.append(finding('INFO', 'MEDIUM', 'Empty localization key',
                    f'Line {line_no} contains an assignment but the key before "=" is empty.', path,
                    'The entry cannot be addressed by a named localization lookup.',
                    'Add the intended key or remove the empty assignment.'))
                continue
            lang_keys.setdefault(key, []).append({'file': path, 'pointer': f'line:{line_no}'})
            if key in seen_in_file:
                findings.append(finding('MEDIUM', 'HIGH', 'Duplicate localization key in file',
                    f'Key {key!r} appears more than once in the same file (lines {seen_in_file[key]} and {line_no}).', path,
                    'Duplicate assignments can make the effective value dependent on parser ordering.',
                    'Keep one definition for this key in this language file.'))
            else:
                seen_in_file[key] = line_no

    namespaces = set()
    for ui_data in parsed.values():
        if isinstance(ui_data, dict) and isinstance(ui_data.get('namespace'), str) and ui_data['namespace'].strip():
            namespaces.add(ui_data['namespace'].strip())
    for path, data in parsed.items():
        if not is_ui_path(path):
            continue
        if not isinstance(data, dict):
            findings.append(finding('INFO', 'LOW', 'UI JSON top-level shape is unusual',
                f'Expected an object for common UI JSON; found {type(data).__name__}.', path,
                'The analyzer cannot reliably inspect controls or declarations in this file.',
                'Check the file against the target-version UI format; this may be a valid alternate resource.'))
            continue
        if 'namespace' in data and not isinstance(data.get('namespace'), str):
            findings.append(finding('INFO', 'MEDIUM', 'UI namespace has an unusual type',
                f'Expected a string when namespace is supplied; found {type(data.get("namespace")).__name__}.', path,
                'Namespace-based control references may not resolve as intended.',
                'Check the namespace field against the target-version UI conventions.'))
        if 'ui_defs' in data:
            ui_defs = data.get('ui_defs')
            if not isinstance(ui_defs, list):
                findings.append(finding('INFO', 'MEDIUM', 'UI ui_defs has an unusual type',
                    f'Expected an array when ui_defs is supplied; found {type(ui_defs).__name__}.', path,
                    'Imported UI definitions were not fully inspected.',
                    'Check ui_defs against the target-version UI format.'))
            else:
                seen_refs = {}
                for index, ref in enumerate(ui_defs):
                    if not isinstance(ref, str) or not ref.strip():
                        findings.append(finding('INFO', 'MEDIUM', 'UI ui_defs entry is not a path string',
                            f'ui_defs[{index}] must be a non-empty string; found {ref!r}.', path,
                            'The import entry cannot be resolved by this static checker.',
                            'Use the expected relative UI JSON path.'))
                        continue
                    # An exact repeated import entry is almost always accidental; keep it INFO until engine behavior is proven.
                    normalized_ref = ref.strip().replace('\\', '/').lower()
                    if normalized_ref in seen_refs:
                        findings.append(finding('INFO', 'MEDIUM', 'Duplicate UI definition entry',
                            f'ui_defs entry {ref!r} repeats an earlier entry at index {seen_refs[normalized_ref]} (also index {index}).', path,
                            'Repeated imports may be redundant or may alter definition precedence.',
                            'Review whether the repeated entry is intentional.'))
                    else:
                        seen_refs[normalized_ref] = index
                    hits = resolve_ui_path(ref, path)
                    if not hits:
                        findings.append(finding('INFO', 'LOW', 'Possible unresolved UI definition path',
                            f'ui_defs[{index}] references {ref!r}; no matching in-archive path was found after common relative-path variants.', path,
                            'The target may be external, injected by another pack, or use a path convention not modeled here.',
                            'Verify path spelling/case and inspect the complete resource-pack UI folder.'))
                    elif len(hits) > 1:
                        findings.append(finding('INFO', 'LOW', 'Ambiguous UI definition path',
                            f'ui_defs[{index}] references {ref!r}; candidate paths are {hits}.', path,
                            'Multiple in-archive paths match common path variants.',
                            'Confirm the intended file under target-version loading conventions.'))
        # Common control-reference patterns are only checked when they are recognizable literal strings.
        # The Bedrock UI schema is broad and varies by version, so all results stay INFO/LOW heuristics.
        control_reference_keys = {'extends', 'controls', 'control_name', 'control'}
        for pointer, key, value in walk(data):
            if str(key).lower() not in control_reference_keys:
                continue
            refs = value if isinstance(value, list) else [value]
            for ref in refs:
                if not isinstance(ref, str) or not ref.strip():
                    continue
                literal = ref.strip()
                if any(token in literal for token in ('{', '}', '$', 'query.', 'variable.', 'math.')):
                    continue
                # `controls` frequently contains arrays/maps of full control declarations;
                # do not treat arbitrary control bodies as names.
                if str(key).lower() == 'controls':
                    if not isinstance(value, list):
                        continue
                # A control name normally uses namespace.control; avoid flagging ordinary identifiers.
                if '.' not in literal or '/' in literal or literal.endswith('.json'):
                    continue
                namespace_prefix = literal.split('.', 1)[0]
                if namespace_prefix not in namespaces:
                    findings.append(finding('INFO', 'LOW', 'Possible unresolved UI control reference',
                        f'{pointer} references {literal!r}; no matching namespace was declared in indexed UI JSON files.', path,
                        'The name may be defined externally, via an implicit namespace, or with a format not modeled here.',
                        'Search all UI definitions and verify naming and namespace rules for the target version.'))
        # Keep localization checks to simple `$key` literals in `text` properties.
        # Do not treat variable expressions or arbitrary strings as missing keys.
        for pointer, key, value in walk(data):
            if str(key).lower() != 'text' or not isinstance(value, str):
                continue
            match = re.fullmatch(r'\$([A-Za-z0-9_.-]+)', value.strip())
            if not match:
                continue
            localization_key = match.group(1)
            if localization_key not in lang_keys:
                findings.append(finding('INFO', 'LOW', 'Possible unresolved UI localization key',
                    f'{pointer} uses literal localization lookup {value!r}, but no matching key was found in indexed .lang files.', path,
                    'Text may fall back to the key, or the key may be supplied by an external pack or unsupported localization format.',
                    'Check all locale files and external dependencies before adding or renaming a key.'))



def audit_loot_table_structure(parsed, findings):
    """Check common loot-table structure without claiming full versioned-schema validation."""
    def is_loot_path(path):
        low = path.lower().replace('\\', '/')
        return '/loot_tables/' in '/' + low

    def issue(title, evidence, path, recommendation):
        findings.append(finding('MEDIUM', 'HIGH', title, evidence, path,
            'The file shape conflicts with common documented Bedrock loot-table fields.', recommendation))

    for path, data in parsed.items():
        if not is_loot_path(path):
            continue
        if not isinstance(data, dict):
            issue('Loot table root has an invalid type',
                  f'Expected a JSON object for loot table; found {type(data).__name__}.', path,
                  'Use a root JSON object and verify it against the target-version loot-table format.')
            continue
        if 'pools' not in data:
            # Keep absent pools as a low-risk advisory: the analyzer doesn't model every version/context.
            findings.append(finding('INFO', 'MEDIUM', 'Loot table has no pools field',
                'No top-level pools array was found in this loot-table-like file.', path,
                'This may be an incomplete table or a schema/context not modeled by the static checker.',
                'Check the file against a version-matched loot-table example.'))
            continue
        pools = data.get('pools')
        if not isinstance(pools, list):
            issue('Loot table pools has an invalid type',
                  f'Expected top-level pools to be an array; found {type(pools).__name__}.', path,
                  'Set pools to an array of loot pool objects.')
            continue
        for pool_index, pool in enumerate(pools):
            pool_path = f'$.pools/{pool_index}'
            if not isinstance(pool, dict):
                issue('Loot table pool has an invalid type',
                      f'{pool_path} should be an object; found {type(pool).__name__}.', path,
                      'Use an object for each pool.')
                continue
            if 'entries' not in pool or not isinstance(pool.get('entries'), list):
                actual = 'missing' if 'entries' not in pool else type(pool.get('entries')).__name__
                issue('Loot table pool entries has an invalid type',
                      f'{pool_path}/entries should be an array; found {actual}.', path,
                      'Add an entries array containing loot entry objects.')
                continue
            rolls = pool.get('rolls')
            if rolls is not None:
                valid_rolls = isinstance(rolls, int) and not isinstance(rolls, bool) and rolls >= 1
                if isinstance(rolls, dict):
                    mn, mx = rolls.get('min', 1), rolls.get('max', 1)
                    valid_rolls = (isinstance(mn, int) and not isinstance(mn, bool) and mn >= 1
                                   and isinstance(mx, int) and not isinstance(mx, bool) and mx >= mn)
                if not valid_rolls:
                    issue('Loot table pool rolls has an invalid shape',
                          f'{pool_path}/rolls has unsupported value {rolls!r}; expected a positive integer or a valid min/max range.', path,
                          'Use a positive integer or an object with integer min/max values where max is at least min.')
            for entry_index, entry in enumerate(pool['entries']):
                entry_path = f'{pool_path}/entries/{entry_index}'
                if not isinstance(entry, dict):
                    issue('Loot table entry has an invalid type',
                          f'{entry_path} should be an object; found {type(entry).__name__}.', path,
                          'Use an object for each loot entry.')
                    continue
                entry_type = entry.get('type')
                if entry_type is not None and not isinstance(entry_type, str):
                    issue('Loot table entry type has an invalid type',
                          f'{entry_path}/type should be a string; found {type(entry_type).__name__}.', path,
                          'Set type to a supported loot entry string for the target game version.')
                if entry_type in ('item', 'loot_table'):
                    name = entry.get('name')
                    if not isinstance(name, str) or not name.strip():
                        issue('Loot table entry name is missing',
                              f'{entry_path} has type {entry_type!r} but no non-empty string name.', path,
                              'Supply the item identifier or loot-table path required by this entry type.')
                weight = entry.get('weight')
                if weight is not None and (not isinstance(weight, int) or isinstance(weight, bool) or weight < 1):
                    issue('Loot table entry weight has an invalid value',
                          f'{entry_path}/weight should be a positive integer; found {weight!r}.', path,
                          'Use a positive integer weight.')


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
        if isinstance(d, dict) and isinstance(d.get('animation_controllers'), dict): audit_animation_controllers(p,d,findings)
    audit_animation_bone_references(parsed,findings)
    audit_ui_localization(files,parsed,findings)
    audit_loot_table_structure(parsed,findings)
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
    blocker=any(f['severity']=='BLOCKER' for f in findings); high=any(f['severity']=='HIGH' for f in findings); medium=any(f['severity']=='MEDIUM' for f in findings)
    recommendation='HOLD' if blocker or high else ('REVIEW' if medium else ('INSUFFICIENT EVIDENCE' if not meta.get('archive_valid') else 'STATIC CHECKS PASSED — RUNTIME NOT VERIFIED'))
    checks=[
      {'name':'archive_integrity_and_paths','status':'PASS' if meta.get('archive_valid') and not any(f['title'] in ('Archive CRC failure','Unsafe archive member path','Archive cannot be opened') for f in findings) else 'FAIL','details':'ZIP CRC and safe relative paths; no extraction.'},
      {'name':'json_parse','status':'FAIL' if any(f['title']=='Invalid JSON' for f in findings) else 'PASS','details':f'Parsed {sum(p.lower().endswith(".json") for p in files)} JSON files.'},
      {'name':'manifest_checks','status':'WARN' if any('Manifest' in f['title'] or 'UUID' in f['title'] for f in findings) else 'PASS','details':'Manifest, UUID and dependency checks.'},
      {'name':'geometry_bone_uv_checks','status':'WARN' if any(any(x in f['title'].lower() for x in ('geometry','bone','cube','uv')) for f in findings) else 'PASS','details':'Conservative geometry/bone/vector/cube/UV structural checks; not a complete engine validator.'},
      {'name':'animation_resource_checks','status':'WARN' if any('animation' in f['title'].lower() or 'identifier' in f['title'].lower() for f in findings) else 'PASS','details':'Animation shape and selected cross-resource reference checks.'},
      {'name':'reference_paths','status':'WARN' if any('path' in f['title'].lower() or 'texture reference' in f['title'].lower() or 'identifier' in f['title'].lower() for f in findings) else 'PASS','details':'Known fields only; identifiers and paths are separated conservatively.'},
      {'name':'ui_localization_checks','status':'WARN' if any(('ui ' in f['title'].lower() or 'ui_' in f['title'].lower() or 'localization' in f['title'].lower()) for f in findings) else 'PASS','details':'Recognizable UI file shapes, ui_defs paths, duplicate per-file .lang keys, and literal text=$key lookups; heuristic only.'},
      {'name':'loot_table_structure','status':'WARN' if any('loot table' in f['title'].lower() for f in findings) else 'PASS','details':'Conservative checks of common loot table pools, entries, rolls and weights; not a complete versioned schema.'},
      {'name':'loot_table_reference_cycles','status':'WARN' if any('recursive loot-table reference cycle' in f['title'].lower() for f in findings) else 'PASS','details':'Checks only cycles among nested loot-table references uniquely resolved inside the archive.'},
      {'name':'baseline_comparison','status':'NOT RUN' if not args.baseline or basefiles is None else 'PASS','details':'File inventory and SHA-256 comparison.'},
      {'name':'reference_graph','status':'PASS' if reference_graph.get('edge_count',0)>=0 else 'WARN','details':f"Indexed {reference_graph.get('edge_count',0)} edges; partial coverage is listed in reference_graph.scope.coverage."},
      {'name':'minecraft_runtime','status':'NOT RUN','details':'This script does not launch Minecraft.'}]
    report={'tool_version':TOOL_VERSION,'candidate':meta,'baseline':basemeta,'checks':checks,'findings':findings,'file_diff':diff,'reference_graph':reference_graph,'runtime_status':'NOT RUN','recommendation':recommendation}
    out=json.dumps(report,indent=2,ensure_ascii=False)
    if args.report:
        with open(args.report,'w',encoding='utf-8') as f:f.write(out+'\n')
    print(out); return 1 if blocker or high else 0
if __name__=='__main__': sys.exit(main())
