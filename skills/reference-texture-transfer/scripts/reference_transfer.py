#!/usr/bin/env python3
"""Transfer explicit reference PNG crops onto selected Minecraft Bedrock cube-face UVs.

Local deterministic utility. No network, plugin-host, MCP, registry, or background
service. Geometry/reference/base inputs are read-only; output is exclusive/no-overwrite.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, re, struct, zlib
from pathlib import Path, PurePosixPath
from typing import Any

FACES = ("north", "south", "east", "west", "up", "down")
PROJECT_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_JSON_BYTES, MAX_PNG_BYTES = 2 * 1024 * 1024, 16 * 1024 * 1024
MAX_DIMENSION, MAX_PIXELS = 4096, 16_777_216
MAX_MAPPINGS, MAX_REGIONS, MAX_TEXEL_WRITES = 256, 6000, 16_777_216

class TransferError(ValueError):
    """Invalid, unsupported, or unsafe reference-transfer input."""


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise TransferError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _safe_relpath(value: Any, label: str, minimum_parts: int = 1) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise TransferError(f"{label} must be a non-empty relative POSIX path (max 512 characters)")
    if "\\" in value or "\x00" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise TransferError(f"{label} must be a safe relative POSIX path")
    parts = value.split("/")
    if len(parts) < minimum_parts or any(p in {"", ".", ".."} for p in parts) or PurePosixPath(value).is_absolute():
        raise TransferError(f"{label} contains an invalid or traversal path segment")
    return value


def _resolve_project(project_name: str, workspace: Path):
    if not PROJECT_RE.fullmatch(project_name) or "--" in project_name:
        raise TransferError("project_directory must be one lowercase kebab-case name")
    workspace = workspace.resolve(strict=True)
    if not workspace.is_dir(): raise TransferError("workspace must be a directory")
    candidate = workspace / project_name
    if candidate.is_symlink(): raise TransferError("project directory must not be a symlink")
    project = candidate.resolve(strict=True)
    if project.parent != workspace or not project.is_dir(): raise TransferError("project must be directly inside workspace")
    container, rp = project / "resource_packs", project / "resource_packs" / f"{project_name}_RP"
    for item in (container, rp):
        if item.is_symlink(): raise TransferError(f"unsafe symlink in Resource Pack path: {item.name}")
    cr, rr = container.resolve(strict=True), rp.resolve(strict=True)
    try: cr.relative_to(project); rr.relative_to(cr)
    except ValueError as exc: raise TransferError("Resource Pack path resolves outside project") from exc
    if not cr.is_dir() or not rr.is_dir(): raise TransferError("Resource Pack directories are missing")
    manifest = rr / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file(): raise TransferError("Resource Pack manifest.json is missing or unsafe")
    return project, rr


def _resolve_file(project: Path, relative: str, label: str) -> Path:
    current = project
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink(): raise TransferError(f"{label} contains a symlink")
    try:
        resolved = current.resolve(strict=True); resolved.relative_to(project)
    except (OSError, ValueError) as exc:
        raise TransferError(f"{label} is missing or resolves outside project") from exc
    if not resolved.is_file(): raise TransferError(f"{label} is not a regular file")
    return resolved


def _new_destination(project: Path, relative: str) -> Path:
    parts = relative.split("/"); current = project
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink() or not current.exists() or not current.is_dir():
            raise TransferError("output parent directory is missing, unsafe, or not a directory")
        try: current.resolve(strict=True).relative_to(project)
        except ValueError as exc: raise TransferError("output parent resolves outside project") from exc
    destination = current / parts[-1]
    if destination.exists() or destination.is_symlink(): raise FileExistsError(f"output already exists: {relative}")
    try: destination.parent.resolve(strict=True).relative_to(project)
    except ValueError as exc: raise TransferError("output parent resolves outside project") from exc
    return destination


def _is_num(v): return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))

def _pair(value, label):
    if not isinstance(value, list) or len(value) != 2 or not all(_is_num(v) for v in value):
        raise TransferError(f"{label} must be a two-number array")
    return float(value[0]), float(value[1])

def _size3(value, label):
    if not isinstance(value, list) or len(value) != 3 or not all(_is_num(v) for v in value):
        raise TransferError(f"{label} must be a three-number array")
    result = tuple(float(v) for v in value)
    if any(v < 0 for v in result): raise TransferError(f"{label} cannot contain negative dimensions")
    return result


def _region(bone, bi, ci, face, x, y, w, h, mapping, rotation=0):
    if not all(math.isfinite(v) for v in (x, y, w, h)) or w == 0 or h == 0:
        raise TransferError(f"invalid or zero-area UV rectangle: {bone}[{ci}].{face}")
    return {"bone": bone, "bone_index": bi, "cube_index": ci, "face": face,
            "bounds": (min(x, x+w), min(y, y+h), max(x, x+w), max(y, y+h)),
            "mapping": mapping, "uv_rotation": rotation}


def extract_face_regions(geometry: dict[str, Any]):
    bones = geometry.get("bones")
    if not isinstance(bones, list): raise TransferError("selected geometry must contain a bones array")
    regions, findings, cube_count = [], [], 0
    axes = {"north": (0,1), "south": (0,1), "east": (2,1), "west": (2,1), "up": (0,2), "down": (0,2)}
    for bi, bone in enumerate(bones):
        if not isinstance(bone, dict) or not isinstance(bone.get("name"), str) or not bone["name"]:
            findings.append({"code":"INVALID_BONE", "bone_index":bi}); continue
        name = bone["name"]; cubes = bone.get("cubes", [])
        if not isinstance(cubes, list): findings.append({"code":"INVALID_CUBES", "bone":name}); continue
        for ci, cube in enumerate(cubes):
            cube_count += 1
            if not isinstance(cube, dict): findings.append({"code":"INVALID_CUBE", "bone":name, "cube_index":ci}); continue
            size = _size3(cube.get("size"), f"{name}.cubes[{ci}].size"); uv = cube.get("uv")
            if isinstance(uv, list):
                u,v = _pair(uv, f"{name}.cubes[{ci}].uv"); x,y,z=size
                faces = {"up":(u+z,v,x,z), "down":(u+z+x,v,x,z), "west":(u,v+z,z,y),
                         "north":(u+z,v+z,x,y), "east":(u+z+x,v+z,z,y), "south":(u+2*z+x,v+z,x,y)}
                for face,(rx,ry,rw,rh) in faces.items(): regions.append(_region(name,bi,ci,face,rx,ry,rw,rh,"classic_box_uv"))
            elif isinstance(uv, dict):
                for face, entry in uv.items():
                    if face not in FACES: findings.append({"code":"UNKNOWN_UV_FACE", "bone":name, "cube_index":ci, "face":face}); continue
                    if not isinstance(entry, dict): raise TransferError(f"{name}.cubes[{ci}].uv.{face} must be an object")
                    u,v = _pair(entry.get("uv"), f"{name}.cubes[{ci}].uv.{face}.uv")
                    us = entry.get("uv_size")
                    if us is None: w,h = (size[axes[face][0]], size[axes[face][1]])
                    else: w,h = _pair(us, f"{name}.cubes[{ci}].uv.{face}.uv_size")
                    rot = entry.get("uv_rotation",0)
                    if isinstance(rot,bool) or not isinstance(rot,int) or rot not in (0,90,180,270):
                        raise TransferError(f"{name}.cubes[{ci}].uv.{face}.uv_rotation must be 0, 90, 180 or 270")
                    if rot in (90,270): w,h = h,w
                    if w < 0 or h < 0: findings.append({"code":"UV_AXIS_FLIP", "bone":name, "cube_index":ci, "face":face})
                    regions.append(_region(name,bi,ci,face,u,v,w,h,"per_face_uv",rot))
            else: findings.append({"code":"MISSING_OR_UNSUPPORTED_UV", "bone":name, "cube_index":ci})
            for unsupported in ("poly_mesh","texture_meshes"):
                if unsupported in cube: findings.append({"code":"UNSUPPORTED_MESH_UV", "bone":name, "cube_index":ci, "resource":unsupported})
    if len(regions) > MAX_REGIONS: raise TransferError(f"geometry exceeds {MAX_REGIONS} supported UV regions")
    return regions, cube_count, findings


def _intersects(a,b): return min(a[2],b[2]) > max(a[0],b[0]) and min(a[3],b[3]) > max(a[1],b[1])


def decode_png_rgba(data: bytes):
    if not isinstance(data, bytes) or not 45 <= len(data) <= MAX_PNG_BYTES or data[:8] != PNG_SIGNATURE:
        raise TransferError("PNG signature or file-size validation failed")
    pos=8; ihdr=None; idat=bytearray(); palette=b""; trns=b""; idat_started=False; idat_ended=False; ended=False
    while pos < len(data):
        if pos+12 > len(data): raise TransferError("truncated PNG chunk header")
        n=struct.unpack(">I",data[pos:pos+4])[0]; kind=data[pos+4:pos+8]; end=pos+n+12
        if end>len(data): raise TransferError(f"truncated PNG {kind!r} chunk")
        payload=data[pos+8:pos+8+n]; crc=struct.unpack(">I",data[pos+8+n:end])[0]
        if zlib.crc32(kind+payload)&0xffffffff != crc: raise TransferError(f"PNG CRC mismatch in {kind!r}")
        if ihdr is None:
            if kind != b"IHDR" or n != 13: raise TransferError("IHDR must be the first 13-byte chunk")
            ihdr=struct.unpack(">IIBBBBB",payload)
        elif kind==b"IHDR": raise TransferError("duplicate PNG IHDR")
        if kind==b"PLTE": palette=payload
        elif kind==b"tRNS": trns=payload
        elif kind==b"IDAT":
            if idat_ended: raise TransferError("PNG IDAT chunks must be consecutive")
            idat_started=True; idat.extend(payload)
        elif idat_started and kind!=b"IEND": idat_ended=True
        if kind==b"IEND":
            if n or end!=len(data): raise TransferError("IEND must be empty and final")
            ended=True; break
        pos=end
    if not ended or ihdr is None or not idat: raise TransferError("PNG is missing IHDR, IDAT, or IEND")
    w,h,depth,color,comp,filt,interlace=ihdr
    if not (1<=w<=MAX_DIMENSION and 1<=h<=MAX_DIMENSION) or w*h>MAX_PIXELS: raise TransferError("PNG dimensions exceed safety limits")
    if depth!=8 or color not in (0,2,3,4,6) or comp or filt or interlace: raise TransferError("only 8-bit non-interlaced PNG color types 0/2/3/4/6 are supported")
    if color==3 and (not palette or len(palette)%3 or len(palette)>768): raise TransferError("indexed PNG requires valid PLTE")
    channels={0:1,2:3,3:1,4:2,6:4}[color]; row_bytes=w*channels; expected=h*(row_bytes+1)
    try:
        dec=zlib.decompressobj(); raw=dec.decompress(bytes(idat),expected+1)
        if len(raw)>expected or dec.unconsumed_tail: raise TransferError("PNG decompresses beyond declared scanline size")
        raw += dec.flush(expected+1-len(raw))
    except zlib.error as exc: raise TransferError(f"invalid PNG IDAT stream: {exc}") from exc
    if len(raw)!=expected or not dec.eof or dec.unused_data or dec.unconsumed_tail: raise TransferError("PNG scanline stream length mismatch")
    decoded=bytearray(row_bytes*h); cur=0
    for y in range(h):
        ft=raw[cur]; cur+=1; row=bytearray(raw[cur:cur+row_bytes]); cur+=row_bytes; prev=(y-1)*row_bytes
        for x in range(row_bytes):
            left=row[x-channels] if x>=channels else 0; up=decoded[prev+x] if y else 0; ul=decoded[prev+x-channels] if y and x>=channels else 0
            if ft==1: row[x]=(row[x]+left)&255
            elif ft==2: row[x]=(row[x]+up)&255
            elif ft==3: row[x]=(row[x]+(left+up)//2)&255
            elif ft==4:
                p=left+up-ul; pa,pb,pc=abs(p-left),abs(p-up),abs(p-ul); pred=left if pa<=pb and pa<=pc else up if pb<=pc else ul; row[x]=(row[x]+pred)&255
            elif ft!=0: raise TransferError(f"unsupported PNG filter {ft}")
        decoded[y*row_bytes:(y+1)*row_bytes]=row
    rgba=bytearray(w*h*4)
    for i in range(w*h):
        j=i*channels
        if color==6: pixel=decoded[j:j+4]
        elif color==2:
            r,g,b=decoded[j:j+3]; a=0 if len(trns)>=6 and (r,g,b)==tuple(int.from_bytes(trns[k:k+2],"big") for k in (0,2,4)) else 255; pixel=(r,g,b,a)
        elif color==0:
            g=decoded[j]; a=0 if len(trns)>=2 and g==int.from_bytes(trns[:2],"big") else 255; pixel=(g,g,g,a)
        elif color==4: g,a=decoded[j:j+2]; pixel=(g,g,g,a)
        else:
            idx=decoded[j]
            if idx*3+2>=len(palette): raise TransferError("PNG palette index exceeds PLTE")
            r,g,b=palette[idx*3:idx*3+3]; pixel=(r,g,b,trns[idx] if idx<len(trns) else 255)
        rgba[i*4:i*4+4]=bytes(pixel)
    return w,h,bytes(rgba)


def _chunk(kind,payload): return struct.pack(">I",len(payload))+kind+payload+struct.pack(">I",zlib.crc32(kind+payload)&0xffffffff)

def encode_rgba_png(w,h,rgba):
    if not (1<=w<=MAX_DIMENSION and 1<=h<=MAX_DIMENSION) or w*h>MAX_PIXELS or len(rgba)!=w*h*4: raise TransferError("invalid output PNG dimensions or RGBA buffer")
    rows=bytearray(); stride=w*4
    for y in range(h): rows.append(0); rows.extend(rgba[y*stride:(y+1)*stride])
    ihdr=struct.pack(">IIBBBBB",w,h,8,6,0,0,0)
    return PNG_SIGNATURE+_chunk(b"IHDR",ihdr)+_chunk(b"IDAT",zlib.compress(bytes(rows),9))+_chunk(b"IEND",b"")


def _blend(dst,off,src,mode):
    sr,sg,sb,sa=src
    if mode=="replace": dst[off:off+4]=bytes(src); return
    if sa<=0: return
    dr,dg,db,da=dst[off:off+4]; oa=sa+(da*(255-sa)+127)//255
    if oa<=0: dst[off:off+4]=b"\0\0\0\0"; return
    for c,sc,dc in ((0,sr,dr),(1,sg,dg),(2,sb,db)):
        pm=sc*sa+(dc*da*(255-sa)+127)//255; dst[off+c]=max(0,min(255,(pm+oa//2)//oa))
    dst[off+3]=oa


def _nearest(src,sw,rect,u,v):
    x=rect["x"]+min(rect["width"]-1,max(0,int(math.floor(u*rect["width"]))))
    y=rect["y"]+min(rect["height"]-1,max(0,int(math.floor(v*rect["height"]))))
    i=(y*sw+x)*4; return tuple(src[i:i+4])

def _bilinear(src,sw,rect,u,v):
    fx=rect["x"]+u*rect["width"]-.5; fy=rect["y"]+v*rect["height"]-.5; x0,y0=math.floor(fx),math.floor(fy); x1,y1=x0+1,y0+1; tx,ty=fx-x0,fy-y0
    x0=max(rect["x"],min(rect["x"]+rect["width"]-1,x0)); x1=max(rect["x"],min(rect["x"]+rect["width"]-1,x1)); y0=max(rect["y"],min(rect["y"]+rect["height"]-1,y0)); y1=max(rect["y"],min(rect["y"]+rect["height"]-1,y1))
    samples=[(src[(y0*sw+x0)*4:(y0*sw+x0)*4+4],(1-tx)*(1-ty)),(src[(y0*sw+x1)*4:(y0*sw+x1)*4+4],tx*(1-ty)),(src[(y1*sw+x0)*4:(y1*sw+x0)*4+4],(1-tx)*ty),(src[(y1*sw+x1)*4:(y1*sw+x1)*4+4],tx*ty)]
    alpha=sum(p[3]*k for p,k in samples)
    if alpha<=0: return (0,0,0,0)
    rgb=[max(0,min(255,round(sum(p[c]*p[3]*k for p,k in samples)/alpha))) for c in range(3)]
    return (*rgb,max(0,min(255,round(alpha))))

def _transform(u,v,m):
    r=m["rotation"]
    if r==90: u,v=v,1-u
    elif r==180: u,v=1-u,1-v
    elif r==270: u,v=1-v,u
    if m["flip_x"]: u=1-u
    if m["flip_y"]: v=1-v
    return max(0,min(1,u)),max(0,min(1,v))


def validate_request(raw):
    if not isinstance(raw,dict): raise TransferError("request must be a JSON object")
    allowed={"project_directory","geometry_path","geometry_identifier","reference_image_path","base_texture_path","output_path","background_color","mappings","allow_uv_overlap"}
    if set(raw)-allowed: raise TransferError(f"unexpected request fields: {sorted(set(raw)-allowed)}")
    required={"project_directory","geometry_path","reference_image_path","output_path","mappings"}
    if required-set(raw): raise TransferError(f"missing request fields: {sorted(required-set(raw))}")
    project=raw["project_directory"]
    if not isinstance(project,str) or not PROJECT_RE.fullmatch(project) or "--" in project: raise TransferError("project_directory must be lowercase kebab-case")
    geo=_safe_relpath(raw["geometry_path"],"geometry_path",5)
    if geo.split("/")[:4] != ["resource_packs",f"{project}_RP","models","entity"] or not geo.endswith(".json"): raise TransferError("geometry_path must be in the project's RP models/entity folder")
    def tex(key):
        value=raw.get(key)
        if value is None: return None
        p=_safe_relpath(value,key,5); parts=p.split("/")
        if parts[:3] != ["resource_packs",f"{project}_RP","textures"] or not p.endswith(".png"): raise TransferError(f"{key} must be a PNG under the project's RP textures folder")
        if key in ("output_path","base_texture_path") and parts[3] != "entity": raise TransferError(f"{key} must be inside RP textures/entity/")
        return p
    ref,out,base=tex("reference_image_path"),tex("output_path"),tex("base_texture_path")
    if len({x for x in (ref,out,base) if x is not None}) != len([x for x in (ref,out,base) if x is not None]): raise TransferError("reference, base and output paths must be distinct")
    gid=raw.get("geometry_identifier")
    if gid is not None and (not isinstance(gid,str) or not gid or len(gid)>128): raise TransferError("geometry_identifier must be non-empty and <=128 characters")
    bg=raw.get("background_color")
    if bg is not None:
        if not isinstance(bg,str) or not re.fullmatch(r"#?[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?",bg): raise TransferError("background_color must be RRGGBB or RRGGBBAA")
        rawbg=bg.lstrip("#"); bg=tuple(bytes.fromhex(rawbg+ ("FF" if len(rawbg)==6 else "")))
    if base and bg is not None: raise TransferError("background_color cannot be combined with base_texture_path")
    overlap=raw.get("allow_uv_overlap",False)
    if not isinstance(overlap,bool): raise TransferError("allow_uv_overlap must be boolean")
    entries=raw["mappings"]
    if not isinstance(entries,list) or not 1<=len(entries)<=MAX_MAPPINGS: raise TransferError(f"mappings must contain 1..{MAX_MAPPINGS} entries")
    maps=[]
    for i,e in enumerate(entries):
        if not isinstance(e,dict) or set(e)-{"selector","source_rect","rotation","flip_x","flip_y","sampling","opacity","blend_mode"}: raise TransferError(f"mappings[{i}] is malformed or contains unknown keys")
        s=e.get("selector")
        if not isinstance(s,dict) or not s or set(s)-{"bone","cube_index","face"}: raise TransferError(f"mappings[{i}].selector must identify bone/cube_index/face")
        if "bone" in s and (not isinstance(s["bone"],str) or not s["bone"] or len(s["bone"])>64): raise TransferError("selector bone must be non-empty and <=64 characters")
        if "cube_index" in s and (isinstance(s["cube_index"],bool) or not isinstance(s["cube_index"],int) or not 0<=s["cube_index"]<=255): raise TransferError("selector cube_index must be 0..255")
        if "face" in s and s["face"] not in FACES: raise TransferError(f"selector face must be one of {FACES}")
        r=e.get("source_rect")
        if not isinstance(r,dict) or set(r)!={"x","y","width","height"}: raise TransferError("source_rect must contain x, y, width, height")
        for k,v in r.items():
            if isinstance(v,bool) or not isinstance(v,int) or v<(1 if k in ("width","height") else 0): raise TransferError(f"source_rect.{k} is invalid")
        rot=e.get("rotation",0); opacity=e.get("opacity",255); sampling=e.get("sampling","nearest"); blend=e.get("blend_mode","over"); fx=e.get("flip_x",False); fy=e.get("flip_y",False)
        if isinstance(rot,bool) or not isinstance(rot,int) or rot not in (0,90,180,270): raise TransferError("rotation must be 0/90/180/270")
        if not isinstance(fx,bool) or not isinstance(fy,bool): raise TransferError("flip_x/flip_y must be booleans")
        if sampling not in ("nearest","bilinear"): raise TransferError("sampling must be nearest or bilinear")
        if isinstance(opacity,bool) or not isinstance(opacity,int) or not 0<=opacity<=255: raise TransferError("opacity must be 0..255")
        if blend not in ("over","replace"): raise TransferError("blend_mode must be over or replace")
        maps.append({"selector":dict(s),"source_rect":dict(r),"rotation":rot,"flip_x":fx,"flip_y":fy,"sampling":sampling,"opacity":opacity,"blend_mode":blend})
    return {"project_directory":project,"geometry_path":geo,"geometry_identifier":gid,"reference_image_path":ref,"base_texture_path":base,"output_path":out,"background_color":bg,"mappings":maps,"allow_uv_overlap":overlap}


def _exclusive_write(path: Path, payload: bytes):
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"): flags|=os.O_NOFOLLOW
    fd=os.open(path,flags,0o600)
    try:
        with os.fdopen(fd,"wb") as stream: stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    except Exception:
        try: path.unlink(missing_ok=True)
        except OSError: pass
        raise


def transfer(raw: dict[str,Any], *, workspace: Path | None = None):
    a=validate_request(raw); workspace=workspace or Path(os.environ.get("MINECRAFT_BEDROCK_WORKSPACE",Path.cwd()))
    project,rp=_resolve_project(a["project_directory"],workspace)
    geo_file=_resolve_file(project,a["geometry_path"],"geometry_path")
    if geo_file.stat().st_size>MAX_JSON_BYTES: raise TransferError("geometry JSON exceeds 2 MiB")
    try:
        root=json.loads(geo_file.read_text(encoding="utf-8-sig"),object_pairs_hook=_unique_pairs,parse_constant=lambda x: (_ for _ in ()).throw(TransferError(f"non-finite JSON constant {x}")))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise TransferError(f"invalid geometry JSON: {exc}") from exc
    geos=root.get("minecraft:geometry") if isinstance(root,dict) else None
    if not isinstance(geos,list) or not geos: raise TransferError("minecraft:geometry must be a non-empty array")
    chosen=[]
    for g in geos:
        desc=g.get("description") if isinstance(g,dict) else None; gid=desc.get("identifier") if isinstance(desc,dict) else None
        if a["geometry_identifier"] is None or gid==a["geometry_identifier"]: chosen.append(g)
    if len(chosen)!=1: raise TransferError("geometry_identifier is required when geometry selection is missing or ambiguous")
    geometry=chosen[0]; desc=geometry.get("description")
    if not isinstance(desc,dict): raise TransferError("selected geometry has no description")
    gid=desc.get("identifier") if isinstance(desc.get("identifier"),str) else "<unnamed>"
    w,h=desc.get("texture_width"),desc.get("texture_height")
    if isinstance(w,bool) or not isinstance(w,int) or isinstance(h,bool) or not isinstance(h,int) or not (1<=w<=MAX_DIMENSION and 1<=h<=MAX_DIMENSION) or w*h>MAX_PIXELS: raise TransferError("geometry texture canvas must use safe positive integer dimensions")
    regions,cubes,findings=extract_face_regions(geometry)
    if not regions: raise TransferError("geometry contains no supported cube-face UV regions")
    oob=[r for r in regions if r["bounds"][0]<0 or r["bounds"][1]<0 or r["bounds"][2]>w or r["bounds"][3]>h]
    if oob: raise TransferError(f"{len(oob)} UV face regions exceed declared {w}x{h} canvas")
    overlaps=[]; comparisons=0; complete=True
    for i,left in enumerate(regions):
        for right in regions[i+1:]:
            comparisons+=1
            if comparisons>250_000: complete=False; break
            if _intersects(left["bounds"],right["bounds"]):
                overlaps.append({"a":{k:left[k] for k in ("bone","cube_index","face")},"b":{k:right[k] for k in ("bone","cube_index","face")}})
                if len(overlaps)>=2001: complete=False; break
        if not complete: break
    if (overlaps or not complete) and not a["allow_uv_overlap"]: raise TransferError("UV overlap found or overlap analysis hit its budget; review and explicitly allow only intentional sharing")
    ref_file=_resolve_file(project,a["reference_image_path"],"reference_image_path")
    if ref_file.stat().st_size>MAX_PNG_BYTES: raise TransferError("reference PNG exceeds 16 MiB")
    reference_payload = ref_file.read_bytes()
    rw, rh, source = decode_png_rgba(reference_payload)
    for i,m in enumerate(a["mappings"]):
        r=m["source_rect"]
        if r["x"]+r["width"]>rw or r["y"]+r["height"]>rh: raise TransferError(f"mappings[{i}] source_rect exceeds {rw}x{rh} image")
    if a["base_texture_path"]:
        base_file=_resolve_file(project,a["base_texture_path"],"base_texture_path")
        if base_file.stat().st_size>MAX_PNG_BYTES: raise TransferError("base PNG exceeds 16 MiB")
        base_payload = base_file.read_bytes()
        bw, bh, canvas = decode_png_rgba(base_payload)
        if (bw,bh)!=(w,h): raise TransferError(f"base texture is {bw}x{bh}; geometry requires {w}x{h}")
        canvas=bytearray(canvas)
    elif a["background_color"]: canvas=bytearray(bytes(a["background_color"])*(w*h))
    else: canvas=bytearray(w*h*4)
    _new_destination(project,a["output_path"])
    plan=[]; seen={}; dupes=0; writes=0
    for mi,m in enumerate(a["mappings"]):
        selected=[r for r in regions if all(r[k]==v for k,v in m["selector"].items())]
        if not selected: raise TransferError(f"mappings[{mi}] selector matched no geometry UV region")
        for region in selected:
            key=(region["bone"],region["cube_index"],region["face"]); seen[key]=seen.get(key,0)+1
            if seen[key]>1: dupes+=1
            x0,y0,x1,y1=region["bounds"]; px0=max(0,math.ceil(x0-.5)); py0=max(0,math.ceil(y0-.5)); px1=min(w,math.ceil(x1-.5)); py1=min(h,math.ceil(y1-.5))
            writes+=max(0,px1-px0)*max(0,py1-py0)
            if writes>MAX_TEXEL_WRITES: raise TransferError("transfer exceeds 16,777,216 texel-write budget")
            plan.append((mi,m,region,(px0,py0,px1,py1)))
    if dupes and not a["allow_uv_overlap"]: raise TransferError("same UV face selected more than once; explicit ordered layering approval required")
    results=[]; changed=0
    for mi,m,region,(x0,y0,x1,y1) in plan:
        rect=m["source_rect"]; local=0; tw,th=x1-x0,y1-y0
        for dy in range(th):
            for dx in range(tw):
                u,v=_transform((dx+.5)/tw,(dy+.5)/th,m)
                px=_bilinear(source,rw,rect,u,v) if m["sampling"]=="bilinear" else _nearest(source,rw,rect,u,v)
                px=(px[0],px[1],px[2],(px[3]*m["opacity"]+127)//255); off=((y0+dy)*w+x0+dx)*4; before=canvas[off:off+4]
                _blend(canvas,off,px,m["blend_mode"])
                if before!=canvas[off:off+4]: local+=1
        changed+=local
        results.append({"mapping_index":mi,"selector":m["selector"],"uv_bounds":list(region["bounds"]),"source_rect":rect,"sampling":m["sampling"],"rotation":m["rotation"],"flip_x":m["flip_x"],"flip_y":m["flip_y"],"opacity":m["opacity"],"blend_mode":m["blend_mode"],"changed_texels":local})
    output=encode_rgba_png(w,h,canvas); decode_png_rgba(output)
    destination=project/a["output_path"]
    _exclusive_write(destination,output)
    ref_hash = hashlib.sha256(reference_payload).hexdigest()
    digest = hashlib.sha256(output).hexdigest()
    return {"status":"PASS","geometry":{"identifier":gid,"path":a["geometry_path"],"texture_size":[w,h],"bone_count":len(geometry.get("bones",[])),"cube_count":cubes,"uv_face_regions":len(regions)},
            "reference":{"path":a["reference_image_path"],"size":[rw,rh],"sha256":ref_hash},
            "output":{"path":a["output_path"],"size":[w,h],"bytes":len(output),"sha256":digest},
            "transfer":{"mapping_count":len(a["mappings"]),"target_region_count":len(plan),"estimated_texel_writes":writes,"changed_texels":changed,"uv_overlap_pairs":len(overlaps),"overlap_analysis_complete":complete,"duplicate_region_selections":dupes,"mapping_results":results,"warnings":findings},
            "runtime":"NOT RUN: static UV/PNG checks do not prove Bedrock face orientation, mipmaps, seam behavior, or in-game rendering."}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("request",help="JSON request file"); ap.add_argument("--workspace",help="workspace directory (default: MINECRAFT_BEDROCK_WORKSPACE or cwd)"); ap.add_argument("--report",help="optional report JSON path"); args=ap.parse_args(argv)
    try:
        p=Path(args.request).resolve(strict=True)
        if p.stat().st_size>MAX_JSON_BYTES: raise TransferError("request JSON exceeds 2 MiB")
        data=json.loads(p.read_text(encoding="utf-8-sig"),object_pairs_hook=_unique_pairs,parse_constant=lambda x: (_ for _ in ()).throw(TransferError(f"non-finite JSON constant {x}")))
        result=transfer(data,workspace=Path(args.workspace) if args.workspace else None); rendered=json.dumps(result,ensure_ascii=False,indent=2)
        if args.report: Path(args.report).write_text(rendered+"\n",encoding="utf-8")
        print(rendered); return 0
    except FileExistsError as exc: print(json.dumps({"status":"FAIL","code":"OUTPUT_EXISTS","error":str(exc)})); return 2
    except (OSError,TransferError,json.JSONDecodeError) as exc: print(json.dumps({"status":"FAIL","error":f"{type(exc).__name__}: {exc}"},ensure_ascii=False)); return 2

if __name__ == "__main__": raise SystemExit(main())
