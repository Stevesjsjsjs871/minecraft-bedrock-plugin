#!/usr/bin/env python3
"""Dependency-free static parser and UV bounds/overlap analyzer for Bedrock .geo.json."""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path

FACES = ("north", "south", "east", "west", "up", "down")
class GeometryError(ValueError):
    pass

def _pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise GeometryError(f"duplicate JSON key: {key!r}")
        out[key] = value
    return out

def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise GeometryError(f"{label} must be a finite number")
    return float(value)

def _vec3(value, label, *, positive=False):
    if not isinstance(value, list) or len(value) != 3:
        raise GeometryError(f"{label} must be a three-number array")
    result = tuple(_finite_number(v, f"{label}[{i}]") for i, v in enumerate(value))
    if positive and any(v <= 0 for v in result):
        raise GeometryError(f"{label} dimensions must be positive")
    return result

def _uv_pair(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise GeometryError(f"{label} must be a two-number array")
    return tuple(_finite_number(v, f"{label}[{i}]") for i, v in enumerate(value))

def _rect(selector, u, v, width, height, canvas):
    if width < 0 or height < 0 or not all(math.isfinite(x) for x in (u,v,width,height)):
        raise GeometryError(f"invalid UV rectangle for {selector}")
    tw, th = canvas
    return {"selector": selector, "u": u, "v": v, "width": width, "height": height,
            "u2": u + width, "v2": v + height,
            "out_of_bounds": u < 0 or v < 0 or u + width > tw or v + height > th}

def _intersects(a, b):
    return min(a["u2"], b["u2"]) > max(a["u"], b["u"]) and min(a["v2"], b["v2"]) > max(a["v"], b["v"])

def analyze_geometry(data, *, geometry_identifier=None):
    if not isinstance(data, dict):
        raise GeometryError("geometry document root must be an object")
    if data.get("format_version") is not None and not isinstance(data["format_version"], str):
        raise GeometryError("format_version must be a string")
    geos = data.get("minecraft:geometry")
    if not isinstance(geos, list) or not geos:
        raise GeometryError("minecraft:geometry must be a non-empty array")
    selected = []
    for i, geo in enumerate(geos):
        if not isinstance(geo, dict):
            raise GeometryError(f"minecraft:geometry[{i}] must be an object")
        desc = geo.get("description")
        if not isinstance(desc, dict) or not isinstance(desc.get("identifier"), str) or not desc["identifier"]:
            raise GeometryError(f"minecraft:geometry[{i}].description.identifier is required")
        if geometry_identifier is None or desc["identifier"] == geometry_identifier:
            selected.append((i, geo, desc))
    if geometry_identifier is not None and not selected:
        raise GeometryError(f"geometry identifier not found: {geometry_identifier}")
    if geometry_identifier is None and len(selected) > 1:
        raise GeometryError("multiple geometries found; pass --geometry-identifier to select one")
    index, geo, desc = selected[0]
    tw = desc.get("texture_width", 64); th = desc.get("texture_height", 32)
    tw = _finite_number(tw, "texture_width"); th = _finite_number(th, "texture_height")
    if tw <= 0 or th <= 0 or not tw.is_integer() or not th.is_integer():
        raise GeometryError("texture_width and texture_height must be positive integers")
    canvas = (int(tw), int(th))
    bones = geo.get("bones", [])
    if not isinstance(bones, list):
        raise GeometryError("bones must be an array")
    regions, findings, bone_names = [], [], set()
    cube_count = 0
    for bi, bone in enumerate(bones):
        if not isinstance(bone, dict):
            raise GeometryError(f"bones[{bi}] must be an object")
        name = bone.get("name")
        if not isinstance(name, str) or not name:
            raise GeometryError(f"bones[{bi}].name is required")
        if name in bone_names:
            findings.append({"severity":"WARN","code":"DUPLICATE_BONE_NAME","message":f"duplicate bone name {name!r}","bone":name})
        bone_names.add(name)
        cubes = bone.get("cubes", [])
        if not isinstance(cubes, list):
            raise GeometryError(f"bone {name!r} cubes must be an array")
        for ci, cube in enumerate(cubes):
            cube_count += 1
            if not isinstance(cube, dict):
                raise GeometryError(f"bone {name!r} cube {ci} must be an object")
            size = _vec3(cube.get("size"), f"{name}.cubes[{ci}].size", positive=True)
            origin = _vec3(cube.get("origin"), f"{name}.cubes[{ci}].origin")
            inflate = _finite_number(cube.get("inflate", 0), f"{name}.cubes[{ci}].inflate")
            selector = {"bone": name, "cube_index": ci}
            uv = cube.get("uv")
            if isinstance(uv, list):
                u, v = _uv_pair(uv, f"{name}.cubes[{ci}].uv")
                w = 2 * (size[0] + size[2]); h = size[1] + size[2]
                regions.append(_rect({**selector,"face":"box"}, u, v, w, h, canvas))
            elif isinstance(uv, dict):
                for face, face_data in uv.items():
                    if face not in FACES:
                        findings.append({"severity":"WARN","code":"UNKNOWN_UV_FACE","message":f"unsupported face key {face!r}",**selector})
                        continue
                    if not isinstance(face_data, dict):
                        raise GeometryError(f"{name}.cubes[{ci}].uv.{face} must be an object")
                    u, v = _uv_pair(face_data.get("uv"), f"{name}.cubes[{ci}].uv.{face}.uv")
                    default_size = {"north":(size[0],size[1]),"south":(size[0],size[1]),"east":(size[2],size[1]),"west":(size[2],size[1]),"up":(size[0],size[2]),"down":(size[0],size[2])}[face]
                    uv_size = face_data.get("uv_size")
                    fw, fh = default_size if uv_size is None else _uv_pair(uv_size, f"{name}.cubes[{ci}].uv.{face}.uv_size")
                    rotation = face_data.get("uv_rotation", 0)
                    if isinstance(rotation, bool) or rotation not in (0,90,180,270):
                        raise GeometryError(f"{name}.cubes[{ci}].uv.{face}.uv_rotation must be 0, 90, 180 or 270")
                    if rotation in (90,270): fw, fh = abs(fh), abs(fw)
                    else: fw, fh = abs(fw), abs(fh)
                    regions.append(_rect({**selector,"face":face},u,v,fw,fh,canvas))
            else:
                raise GeometryError(f"{name}.cubes[{ci}].uv must be an array or per-face object")
            if "poly_mesh" in cube or "texture_meshes" in cube:
                findings.append({"severity":"WARN","code":"UNSUPPORTED_MESH_UV","message":"mesh UV form is outside cube-UV analysis coverage",**selector})
    for r in regions:
        if r["out_of_bounds"]:
            findings.append({"severity":"FAIL","code":"UV_OUT_OF_BOUNDS","message":"UV rectangle exceeds the declared texture canvas","region":r})
    overlaps=[]
    for i, a in enumerate(regions):
        for b in regions[i+1:]:
            if _intersects(a,b):
                overlaps.append({"a":a["selector"],"b":b["selector"],"intersection":{"u":max(a["u"],b["u"]),"v":max(a["v"],b["v"]),"u2":min(a["u2"],b["u2"]),"v2":min(a["v2"],b["v2"])}})
    for overlap in overlaps:
        findings.append({"severity":"WARN","code":"UV_OVERLAP","message":"UV rectangles share a positive-area region; intentional mirroring/reuse is possible","overlap":overlap})
    return {"geometry_identifier":desc["identifier"],"geometry_index":index,"format_version":data.get("format_version"),"texture_canvas":{"width":canvas[0],"height":canvas[1]},"bone_count":len(bones),"cube_count":cube_count,"regions":regions,"overlaps":overlaps,"findings":findings,"summary":{"regions":len(regions),"overlaps":len(overlaps),"out_of_bounds":sum(1 for x in regions if x["out_of_bounds"]),"status":"FAIL" if any(f["severity"]=="FAIL" for f in findings) else ("WARN" if findings else "PASS")}}

def analyze_file(path, *, geometry_identifier=None):
    raw = Path(path).read_text(encoding="utf-8-sig")
    try: data=json.loads(raw,object_pairs_hook=_pairs_no_duplicates,parse_constant=lambda v: (_ for _ in ()).throw(GeometryError(f"non-finite JSON constant {v}")))
    except json.JSONDecodeError as e: raise GeometryError(f"invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}") from e
    return analyze_geometry(data,geometry_identifier=geometry_identifier)

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("geometry"); ap.add_argument("--geometry-identifier"); ap.add_argument("--report"); args=ap.parse_args(argv)
    try: result=analyze_file(args.geometry,geometry_identifier=args.geometry_identifier)
    except Exception as e:
        print(json.dumps({"status":"FAIL","error":str(e)},indent=2,ensure_ascii=False)); return 2
    rendered=json.dumps(result,indent=2,ensure_ascii=False)
    if args.report: Path(args.report).write_text(rendered+"\n",encoding="utf-8")
    print(rendered)
    return 1 if result["summary"]["status"]=="FAIL" else 0
if __name__=="__main__": raise SystemExit(main())
