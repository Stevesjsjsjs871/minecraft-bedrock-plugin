#!/usr/bin/env python3
"""Bounded, deterministic Bedrock geometry-aware texture painter.

Local utility only: it is not a ChatGPT-host Tool and does not start a server.
It writes a new PNG, never overwrites an existing file, and preserves the
source texture outside selected UV regions when a base PNG is supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PROJECT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")
FACES = ("north", "south", "east", "west", "up", "down")
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PNG_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 16_777_216
MAX_OPERATIONS = 128
MAX_REGIONS = 512
MAX_TEXEL_WRITES = 16_777_216
MAX_OVERLAP_COMPARISONS = 250_000
MAX_REPORTED_OVERLAPS = 2_000


class PaintError(ValueError):
    """Invalid project, geometry, PNG, painting request or safety-limit breach."""


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PaintError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str):
    raise PaintError(f"non-finite JSON constant is not allowed: {value}")


def _safe_relative(value: Any, label: str, minimum_parts: int = 1) -> str:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise PaintError(f"{label} must be a relative POSIX path")
    parts = value.split("/")
    if len(parts) < minimum_parts or any(p in ("", ".", "..") for p in parts):
        raise PaintError(f"{label} contains an empty, dot, traversal or incomplete path segment")
    return value


def _parse_color(value: Any, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, str) or not COLOR_RE.fullmatch(value):
        raise PaintError(f"{label} must be #RRGGBB or #RRGGBBAA")
    raw = value[1:]
    if len(raw) == 6:
        raw += "FF"
    return tuple(bytes.fromhex(raw))  # type: ignore[return-value]


def validate_request(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PaintError("request must be a JSON object")
    allowed = {"project_directory", "geometry_path", "output_path", "geometry_identifier", "source_texture_path", "background_color", "operations", "allow_uv_overlap"}
    extra = set(raw) - allowed
    if extra:
        raise PaintError(f"unexpected request fields: {', '.join(sorted(extra))}")
    required = {"project_directory", "geometry_path", "output_path", "operations"}
    missing = required - set(raw)
    if missing:
        raise PaintError(f"missing required request fields: {', '.join(sorted(missing))}")

    project = raw["project_directory"]
    if not isinstance(project, str) or not PROJECT_RE.fullmatch(project) or "--" in project:
        raise PaintError("project_directory must be one lowercase kebab-case directory name")
    geometry_path = _safe_relative(raw["geometry_path"], "geometry_path", 5)
    if geometry_path.split("/")[:4] != ["resource_packs", f"{project}_RP", "models", "entity"] or not geometry_path.endswith(".json"):
        raise PaintError(f"geometry_path must be a .json file under resource_packs/{project}_RP/models/entity/")
    output_path = _safe_relative(raw["output_path"], "output_path", 5)
    if output_path.split("/")[:4] != ["resource_packs", f"{project}_RP", "textures", "entity"] or not output_path.endswith(".png"):
        raise PaintError(f"output_path must be a PNG inside resource_packs/{project}_RP/textures/entity/")
    source = raw.get("source_texture_path")
    if source is not None:
        source = _safe_relative(source, "source_texture_path", 5)
        if source.split("/")[:4] != ["resource_packs", f"{project}_RP", "textures", "entity"] or not source.endswith(".png"):
            raise PaintError(f"source_texture_path must be a PNG inside resource_packs/{project}_RP/textures/entity/")
        if source == output_path:
            raise PaintError("source_texture_path and output_path must be different files")
    geometry_id = raw.get("geometry_identifier")
    if geometry_id is not None and (not isinstance(geometry_id, str) or not geometry_id or len(geometry_id) > 128):
        raise PaintError("geometry_identifier must be a non-empty string up to 128 characters")
    background_raw = raw.get("background_color")
    background = _parse_color(background_raw, "background_color") if background_raw is not None else None
    if source and background is not None:
        raise PaintError("background_color cannot be combined with source_texture_path")
    overlap = raw.get("allow_uv_overlap", False)
    if not isinstance(overlap, bool):
        raise PaintError("allow_uv_overlap must be a boolean")
    entries = raw["operations"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_OPERATIONS:
        raise PaintError(f"operations must contain 1 to {MAX_OPERATIONS} entries")

    operations = []
    for index, entry in enumerate(entries):
        label = f"operations[{index}]"
        if not isinstance(entry, dict):
            raise PaintError(f"{label} must be an object")
        op_allowed = {"selector", "mode", "color", "secondary_color", "opacity", "blend_mode", "border_width", "cell_size", "axis", "seed"}
        extra = set(entry) - op_allowed
        if extra:
            raise PaintError(f"{label} has unexpected fields: {', '.join(sorted(extra))}")
        selector = entry.get("selector")
        if not isinstance(selector, dict) or not selector or set(selector) - {"bone", "cube_index", "face"}:
            raise PaintError(f"{label}.selector must select at least one of bone, cube_index or face")
        if "bone" in selector and (not isinstance(selector["bone"], str) or not selector["bone"] or len(selector["bone"]) > 64):
            raise PaintError(f"{label}.selector.bone must be a non-empty bone name")
        if "cube_index" in selector and (isinstance(selector["cube_index"], bool) or not isinstance(selector["cube_index"], int) or not 0 <= selector["cube_index"] <= 255):
            raise PaintError(f"{label}.selector.cube_index must be an integer from 0 to 255")
        if "face" in selector and selector["face"] not in FACES:
            raise PaintError(f"{label}.selector.face must be one of {FACES}")
        mode = entry.get("mode")
        if not isinstance(mode, str) or mode not in {"fill", "border", "checker", "stripes", "gradient", "noise"}:
            raise PaintError(f"{label}.mode is unsupported")
        color = _parse_color(entry.get("color"), f"{label}.color")
        secondary_raw = entry.get("secondary_color")
        secondary = _parse_color(secondary_raw, f"{label}.secondary_color") if secondary_raw is not None else None
        if mode in {"checker", "stripes", "gradient", "noise"} and secondary is None:
            raise PaintError(f"{label}.secondary_color is required for {mode}")
        opacity = entry.get("opacity", 255)
        if isinstance(opacity, bool) or not isinstance(opacity, int) or not 0 <= opacity <= 255:
            raise PaintError(f"{label}.opacity must be an integer from 0 to 255")
        blend = entry.get("blend_mode", "over")
        if not isinstance(blend, str) or blend not in {"over", "replace"}:
            raise PaintError(f"{label}.blend_mode must be over or replace")
        border_width, cell_size, seed = entry.get("border_width", 1), entry.get("cell_size", 2), entry.get("seed", 1)
        for key, value, lo, hi in (("border_width", border_width, 1, 32), ("cell_size", cell_size, 1, 128)):
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise PaintError(f"{label}.{key} must be an integer from {lo} to {hi}")
        if isinstance(seed, bool) or not isinstance(seed, int) or not -(2**31) <= seed <= 2**31 - 1:
            raise PaintError(f"{label}.seed must be a signed 32-bit integer")
        axis = entry.get("axis", "x")
        if not isinstance(axis, str) or axis not in {"x", "y"}:
            raise PaintError(f"{label}.axis must be x or y")
        operations.append({"selector": dict(selector), "mode": mode, "color": color, "secondary_color": secondary,
                           "opacity": opacity, "blend_mode": blend, "border_width": border_width,
                           "cell_size": cell_size, "seed": seed, "axis": axis})
    return {"project_directory": project, "geometry_path": geometry_path, "output_path": output_path,
            "geometry_identifier": geometry_id, "source_texture_path": source, "background_color": background,
            "operations": operations, "allow_uv_overlap": overlap}


def _workspace_root(workspace: Path | None) -> Path:
    base = workspace or Path(os.environ.get("MINECRAFT_BEDROCK_WORKSPACE", Path.cwd()))
    try:
        root = base.expanduser().resolve(strict=True)
    except OSError as exc:
        raise PaintError(f"configured workspace does not exist: {base}") from exc
    if not root.is_dir():
        raise PaintError("configured workspace must be a directory")
    return root


def _resolve_project(project_name: str, workspace: Path) -> tuple[Path, Path]:
    candidate = workspace / project_name
    if candidate.is_symlink():
        raise PaintError("project directory must not be a symlink")
    try:
        project = candidate.resolve(strict=True)
    except OSError as exc:
        raise PaintError(f"project directory is unavailable: {project_name}") from exc
    if project.parent != workspace or not project.is_dir():
        raise PaintError("project must be one existing directory directly under the configured workspace")
    container = project / "resource_packs"
    rp = container / f"{project_name}_RP"
    for item in (container, rp):
        if item.is_symlink():
            raise PaintError(f"unsafe symlink in Resource Pack path: {item.name}")
    try:
        croot, rp_root = container.resolve(strict=True), rp.resolve(strict=True)
        croot.relative_to(project); rp_root.relative_to(croot)
    except (OSError, ValueError) as exc:
        raise PaintError("expected Resource Pack directories are missing or outside the project") from exc
    if not croot.is_dir() or not rp_root.is_dir():
        raise PaintError("expected Resource Pack directories must be directories")
    manifest = rp_root / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise PaintError("Resource Pack manifest.json is missing or unsafe")
    return project, rp_root


def _resolve_file(root: Path, relative: str, label: str) -> Path:
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise PaintError(f"{label} contains a symlink")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise PaintError(f"{label} is missing or resolves outside the Resource Pack") from exc
    if not resolved.is_file():
        raise PaintError(f"{label} is not a regular file")
    return resolved


def _new_destination(root: Path, relative: str) -> Path:
    parts = relative.split("/")
    current = root
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise PaintError("output path contains a symlink")
        if not current.exists() or not current.is_dir():
            raise PaintError("output parent directories must already exist")
    try:
        current.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise PaintError("output parent resolves outside the Resource Pack") from exc
    dest = current / parts[-1]
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing output: {dest}")
    return dest


def _read_bounded(path: Path, limit: int, label: str) -> bytes:
    # O_NOFOLLOW prevents a symlink swap between the explicit lstat and open on POSIX.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise PaintError(f"{label} must be a regular file")
            if info.st_size > limit:
                raise PaintError(f"{label} exceeds the {limit}-byte limit")
            data = stream.read(limit + 1)
            if len(data) > limit or len(data) != info.st_size:
                raise PaintError(f"{label} changed while being read or exceeds the size limit")
            return data
    except OSError as exc:
        raise PaintError(f"{label} could not be read safely: {exc}") from exc



def _decode_png_rgba(data: bytes) -> tuple[int, int, bytearray]:
    if not isinstance(data, bytes) or not 45 <= len(data) <= MAX_PNG_BYTES or not data.startswith(PNG_SIGNATURE):
        raise PaintError("PNG signature or file-size validation failed")
    pos = 8; ihdr = None; idat = bytearray(); palette = b""; transparency = b""; idat_started = False; idat_ended = False; ended = False
    chunks = 0
    while pos < len(data):
        chunks += 1
        if chunks > 4096: raise PaintError("PNG exceeds the 4096-chunk limit")
        if pos + 12 > len(data): raise PaintError("truncated PNG chunk header")
        size = struct.unpack(">I", data[pos:pos+4])[0]; kind = data[pos+4:pos+8]; end = pos + size + 12
        if end > len(data): raise PaintError(f"truncated PNG {kind!r} chunk")
        if any(not (65 <= c <= 90 or 97 <= c <= 122) for c in kind) or kind[2] & 0x20:
            raise PaintError("invalid PNG chunk type")
        payload = data[pos+8:pos+8+size]; crc = struct.unpack(">I", data[pos+8+size:end])[0]
        if zlib.crc32(kind+payload) & 0xffffffff != crc: raise PaintError(f"PNG CRC mismatch in {kind!r}")
        if ihdr is None:
            if kind != b"IHDR" or size != 13: raise PaintError("IHDR must be the first 13-byte chunk")
            ihdr = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IHDR": raise PaintError("duplicate PNG IHDR")
        if kind == b"PLTE":
            if idat_started or palette or size == 0 or size > 768 or size % 3: raise PaintError("invalid or misplaced PLTE")
            palette = payload
        elif kind == b"tRNS":
            if idat_started or transparency: raise PaintError("invalid or misplaced tRNS")
            transparency = payload
        elif kind == b"IDAT":
            if idat_ended: raise PaintError("PNG IDAT chunks must be consecutive")
            idat_started = True; idat.extend(payload)
        elif idat_started and kind != b"IEND": idat_ended = True
        if kind == b"IEND":
            if size or end != len(data): raise PaintError("IEND must be empty and final")
            ended = True; break
        if kind[0] & 0x20 == 0 and kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
            raise PaintError(f"unknown critical PNG chunk {kind!r}")
        pos = end
    if not ended or ihdr is None or not idat: raise PaintError("PNG is missing IHDR, IDAT or IEND")
    width, height, depth, color, comp, filt, interlace = ihdr
    if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION) or width * height > MAX_PIXELS:
        raise PaintError("PNG dimensions exceed safety limits")
    if depth != 8 or color not in (0, 2, 3, 4, 6) or comp or filt or interlace:
        raise PaintError("only 8-bit non-interlaced PNG color types 0/2/3/4/6 are supported")
    if color == 3 and (not palette or len(palette) % 3 or len(palette) > 768): raise PaintError("indexed PNG requires valid PLTE")
    channels = {0:1,2:3,3:1,4:2,6:4}[color]; row_bytes = width * channels; expected = height * (row_bytes + 1)
    try:
        decoder = zlib.decompressobj(); raw = decoder.decompress(bytes(idat), expected + 1)
        if len(raw) > expected or decoder.unconsumed_tail: raise PaintError("PNG expands beyond declared scanline size")
        raw += decoder.flush(expected + 1 - len(raw))
    except zlib.error as exc: raise PaintError(f"invalid PNG IDAT stream: {exc}") from exc
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise PaintError("PNG scanline stream length mismatch")
    decoded = bytearray(row_bytes * height); cursor = 0
    for y in range(height):
        filter_type = raw[cursor]; cursor += 1
        row = bytearray(raw[cursor:cursor+row_bytes]); cursor += row_bytes
        prev = (y-1)*row_bytes
        for x in range(row_bytes):
            left = row[x-channels] if x >= channels else 0
            up = decoded[prev+x] if y else 0
            upper_left = decoded[prev+x-channels] if y and x >= channels else 0
            if filter_type == 1: row[x] = (row[x] + left) & 255
            elif filter_type == 2: row[x] = (row[x] + up) & 255
            elif filter_type == 3: row[x] = (row[x] + (left+up)//2) & 255
            elif filter_type == 4:
                estimate = left + up - upper_left
                pa,pb,pc = abs(estimate-left),abs(estimate-up),abs(estimate-upper_left)
                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else upper_left
                row[x] = (row[x] + predictor) & 255
            elif filter_type != 0: raise PaintError(f"unsupported PNG filter {filter_type}")
        decoded[y*row_bytes:(y+1)*row_bytes] = row
    rgba = bytearray(width * height * 4)
    for index in range(width * height):
        offset = index * channels
        if color == 6: pixel = decoded[offset:offset+4]
        elif color == 2:
            r,g,b = decoded[offset:offset+3]
            alpha = 0 if len(transparency) >= 6 and (r,g,b) == tuple(int.from_bytes(transparency[k:k+2],"big") for k in (0,2,4)) else 255
            pixel = (r,g,b,alpha)
        elif color == 0:
            gray = decoded[offset]; alpha = 0 if len(transparency) >= 2 and gray == int.from_bytes(transparency[:2],"big") else 255
            pixel = (gray,gray,gray,alpha)
        elif color == 4:
            gray,alpha = decoded[offset:offset+2]; pixel = (gray,gray,gray,alpha)
        else:
            palette_index = decoded[offset]
            if palette_index * 3 + 2 >= len(palette): raise PaintError("PNG palette index exceeds PLTE")
            r,g,b = palette[palette_index*3:palette_index*3+3]
            pixel = (r,g,b,transparency[palette_index] if palette_index < len(transparency) else 255)
        rgba[index*4:index*4+4] = bytes(pixel)
    return width,height,rgba


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)


def _encode_png(width: int, height: int, pixels: bytearray) -> bytes:
    if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION or width*height > MAX_PIXELS or len(pixels) != width*height*4:
        raise PaintError("invalid output PNG dimensions or RGBA buffer")
    stride = width * 4
    raw = b"".join(b"\x00" + bytes(pixels[y*stride:(y+1)*stride]) for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
        raise PaintError(f"{label} must be a finite number")
    return float(value)


def _pair(value: Any, label: str) -> tuple[float,float]:
    if not isinstance(value, list) or len(value) != 2:
        raise PaintError(f"{label} must be a two-number array")
    return _finite_number(value[0],label),_finite_number(value[1],label)


def _size3(value: Any, label: str) -> tuple[float,float,float]:
    if not isinstance(value,list) or len(value)!=3:
        raise PaintError(f"{label} must be a three-number array")
    result=tuple(_finite_number(v,label) for v in value)
    if any(v<=0 for v in result): raise PaintError(f"{label} dimensions must be positive")
    return result


def _extract_regions(geometry: dict[str,Any]):
    bones=geometry.get("bones")
    if not isinstance(bones,list): raise PaintError("selected geometry must contain a bones array")
    regions=[]; findings=[]; cube_count=0
    axes={"north":(0,1),"south":(0,1),"east":(2,1),"west":(2,1),"up":(0,2),"down":(0,2)}
    for bone_index,bone in enumerate(bones):
        if not isinstance(bone,dict) or not isinstance(bone.get("name"),str) or not bone["name"]:
            findings.append({"code":"INVALID_BONE","bone_index":bone_index}); continue
        name=bone["name"]; cubes=bone.get("cubes",[])
        if not isinstance(cubes,list): findings.append({"code":"INVALID_CUBES","bone":name}); continue
        for cube_index,cube in enumerate(cubes):
            cube_count+=1
            if not isinstance(cube,dict): findings.append({"code":"INVALID_CUBE","bone":name,"cube_index":cube_index}); continue
            size=_size3(cube.get("size"),f"{name}.cubes[{cube_index}].size"); uv=cube.get("uv")
            if isinstance(uv,list):
                u,v=_pair(uv,f"{name}.cubes[{cube_index}].uv"); x,y,z=size
                faces={"up":(u+z,v,x,z),"down":(u+z+x,v,x,z),"west":(u,v+z,z,y),"north":(u+z,v+z,x,y),"east":(u+z+x,v+z,z,y),"south":(u+2*z+x,v+z,x,y)}
                for face,(rx,ry,rw,rh) in faces.items(): regions.append({"bone":name,"bone_index":bone_index,"cube_index":cube_index,"face":face,"bounds":(rx,ry,rx+rw,ry+rh),"mapping":"classic_box_uv"})
            elif isinstance(uv,dict):
                for face,entry in uv.items():
                    if face not in FACES: findings.append({"code":"UNKNOWN_UV_FACE","bone":name,"cube_index":cube_index,"face":face}); continue
                    if not isinstance(entry,dict): raise PaintError(f"{name}.cubes[{cube_index}].uv.{face} must be an object")
                    u,v=_pair(entry.get("uv"),f"{name}.cubes[{cube_index}].uv.{face}.uv")
                    uv_size=entry.get("uv_size")
                    if uv_size is None: w,h=(size[axes[face][0]],size[axes[face][1]])
                    else: w,h=_pair(uv_size,f"{name}.cubes[{cube_index}].uv.{face}.uv_size")
                    rotation=entry.get("uv_rotation",0)
                    if isinstance(rotation,bool) or not isinstance(rotation,int) or rotation not in (0,90,180,270): raise PaintError("uv_rotation must be 0, 90, 180 or 270")
                    if rotation in (90,270): w,h=h,w
                    left,top,right,bottom=min(u,u+w),min(v,v+h),max(u,u+w),max(v,v+h)
                    if right <= left or bottom <= top: raise PaintError(f"{name}.cubes[{cube_index}].uv.{face} has zero-area UV size")
                    if w<0 or h<0: findings.append({"code":"UV_AXIS_FLIP","bone":name,"cube_index":cube_index,"face":face})
                    regions.append({"bone":name,"bone_index":bone_index,"cube_index":cube_index,"face":face,"bounds":(left,top,right,bottom),"mapping":"per_face_uv","uv_rotation":rotation})
            else: findings.append({"code":"MISSING_CUBE_UV","bone":name,"cube_index":cube_index})
            for unsupported in ("poly_mesh","texture_meshes"):
                if unsupported in cube: findings.append({"code":"UNSUPPORTED_MESH_UV","bone":name,"cube_index":cube_index,"resource":unsupported})
    if len(regions)>MAX_REGIONS: raise PaintError(f"geometry exceeds {MAX_REGIONS} UV regions")
    return regions,cube_count,findings


def _overlaps(regions):
    ordered=sorted(enumerate(regions),key=lambda item:(item[1]["bounds"][0],item[1]["bounds"][1]))
    active=[]; found=[]; comparisons=0; complete=True; total=0
    for index,region in ordered:
        left,top,right,bottom=region["bounds"]
        active=[(old_i,old) for old_i,old in active if old["bounds"][2]>left]
        for old_i,old in active:
            comparisons+=1
            if comparisons>MAX_OVERLAP_COMPARISONS: complete=False; break
            ol,ot,orr,ob=old["bounds"]; ix=min(right,orr)-max(left,ol); iy=min(bottom,ob)-max(top,ot)
            if ix>0 and iy>0:
                total+=1
                if len(found)<MAX_REPORTED_OVERLAPS:
                    found.append({"a":{"bone":old["bone"],"cube_index":old["cube_index"],"face":old["face"]},"b":{"bone":region["bone"],"cube_index":region["cube_index"],"face":region["face"]},"intersection":[max(left,ol),max(top,ot),min(right,orr),min(bottom,ob)]})
        if not complete: break
        active.append((index,region))
    return found,total,complete


def _matches(region,selector):
    return all(region[k]==v for k,v in selector.items())


def _pixel_bounds(region,width,height):
    left,top,right,bottom=region["bounds"]
    return max(0,math.ceil(left-.5)),max(0,math.ceil(top-.5)),min(width,math.ceil(right-.5)),min(height,math.ceil(bottom-.5))


def _blend(dst: bytearray, offset: int, src: tuple[int,int,int,int], mode: str):
    sr,sg,sb,sa=src
    if mode=="replace": dst[offset:offset+4]=bytes(src); return
    if sa<=0:return
    dr,dg,db,da=dst[offset:offset+4]; out_a=sa+(da*(255-sa)+127)//255
    if out_a<=0:dst[offset:offset+4]=b"\x00\x00\x00\x00";return
    for channel,sc,dc in ((0,sr,dr),(1,sg,dg),(2,sb,db)):
        premul=sc*sa+(dc*da*(255-sa)+127)//255
        dst[offset+channel]=max(0,min(255,(premul+out_a//2)//out_a))
    dst[offset+3]=out_a


def _mix(a,b,amount):
    amount=max(0.0,min(1.0,amount))
    return tuple(round(x*(1.0-amount)+y*amount) for x,y in zip(a,b))


def _operation_color(op,local_x,local_y,region_w,region_h):
    mode=op["mode"]; primary=op["color"]; secondary=op["secondary_color"]; use_primary=True
    if mode=="border":
        bw=op["border_width"]
        if local_x>=bw and local_y>=bw and local_x<region_w-bw and local_y<region_h-bw:
            if secondary is None:return None
            primary=secondary
    elif mode=="checker": use_primary=((local_x//op["cell_size"]+local_y//op["cell_size"])%2)==0
    elif mode=="stripes":
        coord=local_x if op["axis"]=="x" else local_y
        use_primary=(coord//op["cell_size"])%2==0
    elif mode=="gradient":
        extent=max(1,(region_w if op["axis"]=="x" else region_h)-1)
        pos=local_x if op["axis"]=="x" else local_y
        return _mix(primary,secondary,pos/extent)
    elif mode=="noise":
        n=(local_x*0x45D9F3B+local_y*0x119DE1F3+(op["seed"]&0xFFFFFFFF))&0xFFFFFFFF
        n=((n^(n>>16))*0x45D9F3B)&0xFFFFFFFF; n=(n^(n>>16))&0xFFFFFFFF
        use_primary=(n&1)==0
    if not use_primary:primary=secondary
    return primary


def _write_new(path: Path,payload: bytes):
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags,0o600)
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
    except Exception:
        try:path.unlink(missing_ok=True)
        except OSError:pass
        raise


def paint(raw: dict[str,Any], *, workspace: Path | None = None):
    args=validate_request(raw); workspace_root=_workspace_root(workspace)
    project,rp=_resolve_project(args["project_directory"],workspace_root)
    geo_file=_resolve_file(project,args["geometry_path"],"geometry_path")
    geo_bytes=_read_bounded(geo_file,MAX_JSON_BYTES,"geometry JSON")
    try:document=json.loads(geo_bytes.decode("utf-8-sig"),object_pairs_hook=_unique_pairs,parse_constant=_reject_constant)
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise PaintError(f"invalid geometry JSON: {exc}") from exc
    if not isinstance(document,dict) or not isinstance(document.get("minecraft:geometry"),list) or not document["minecraft:geometry"]:
        raise PaintError("minecraft:geometry must be a non-empty array")
    candidates=[]
    for geometry in document["minecraft:geometry"]:
        desc=geometry.get("description") if isinstance(geometry,dict) else None
        if args["geometry_identifier"] is None or (isinstance(desc,dict) and desc.get("identifier")==args["geometry_identifier"]):candidates.append(geometry)
    if len(candidates)!=1:raise PaintError("geometry_identifier is required when geometry selection is missing or ambiguous")
    geometry=candidates[0];desc=geometry.get("description")
    if not isinstance(desc,dict) or not isinstance(desc.get("identifier"),str) or not desc["identifier"]:raise PaintError("selected geometry has no valid description.identifier")
    width,height=desc.get("texture_width",64),desc.get("texture_height",32)
    if isinstance(width,bool) or not isinstance(width,int) or isinstance(height,bool) or not isinstance(height,int) or not (1<=width<=MAX_DIMENSION and 1<=height<=MAX_DIMENSION) or width*height>MAX_PIXELS:
        raise PaintError("geometry texture canvas must use safe positive integer dimensions")
    regions,cube_count,findings=_extract_regions(geometry)
    if not regions:raise PaintError("geometry contains no supported cube UV regions")
    out_of_bounds=[r for r in regions if r["bounds"][0]<0 or r["bounds"][1]<0 or r["bounds"][2]>width or r["bounds"][3]>height]
    if out_of_bounds:raise PaintError(f"{len(out_of_bounds)} UV regions exceed declared {width}x{height} canvas")
    overlaps,overlap_count,complete=_overlaps(regions)
    if (overlap_count or not complete) and not args["allow_uv_overlap"]:
        raise PaintError("UV overlap found or overlap analysis hit its budget; review and explicitly allow only intentional sharing")
    if args["source_texture_path"]:
        source_file=_resolve_file(project,args["source_texture_path"],"source_texture_path")
        source_bytes=_read_bounded(source_file,MAX_PNG_BYTES,"source PNG")
        sw,sh,canvas=_decode_png_rgba(source_bytes)
        if (sw,sh)!=(width,height):raise PaintError(f"source texture is {sw}x{sh}; geometry requires {width}x{height}")
    elif args["background_color"] is not None:
        canvas=bytearray(bytes(args["background_color"])*(width*height))
        source_bytes=None
    else:
        canvas=bytearray(width*height*4);source_bytes=None
    destination=_new_destination(project,args["output_path"])
    plan=[];writes=0
    for op_index,op in enumerate(args["operations"]):
        selected=[r for r in regions if _matches(r,op["selector"])]
        if not selected:raise PaintError(f"operations[{op_index}] selector matched no UV region")
        for region in selected:
            x0,y0,x1,y1=_pixel_bounds(region,width,height)
            writes+=(x1-x0)*(y1-y0)
            if writes>MAX_TEXEL_WRITES:raise PaintError(f"painting exceeds {MAX_TEXEL_WRITES} texel-write budget")
            plan.append((op_index,op,region,(x0,y0,x1,y1)))
    changed=0;results=[]
    for op_index,op,region,(x0,y0,x1,y1) in plan:
        rw,rh=x1-x0,y1-y0;local_changed=0
        for y in range(y0,y1):
            for x in range(x0,x1):
                color=_operation_color(op,x-x0,y-y0,rw,rh)
                if color is None:continue
                rgba=(color[0],color[1],color[2],(color[3]*op["opacity"]+127)//255)
                offset=(y*width+x)*4;before=bytes(canvas[offset:offset+4]);_blend(canvas,offset,rgba,op["blend_mode"])
                if before!=canvas[offset:offset+4]:local_changed+=1
        changed+=local_changed
        results.append({"operation_index":op_index,"selector":op["selector"],"mode":op["mode"],"target":{"bone":region["bone"],"bone_index":region["bone_index"],"cube_index":region["cube_index"],"face":region["face"],"bounds":list(region["bounds"])},"changed_texels":local_changed})
    output=_encode_png(width,height,canvas);_decode_png_rgba(output)
    _write_new(destination,output)
    digest=hashlib.sha256(output).hexdigest()
    return {"status":"PASS","geometry":{"identifier":desc.get("identifier"),"path":args["geometry_path"],"texture_size":[width,height],"bone_count":len(geometry.get("bones",[])),"cube_count":cube_count,"uv_region_count":len(regions)},"source_texture":{"path":args["source_texture_path"],"sha256":hashlib.sha256(source_bytes).hexdigest() if source_bytes is not None else None},"output":{"path":args["output_path"],"width":width,"height":height,"bytes":len(output),"sha256":digest},"painting":{"operation_count":len(args["operations"]),"target_region_count":len(plan),"estimated_texel_writes":writes,"changed_texels":changed,"uv_overlap_pairs":overlap_count,"overlap_analysis_complete":complete,"overlaps":overlaps[:100],"operations":results,"findings":findings[:100]},"runtime":"NOT RUN: static UV/PNG validation does not prove Bedrock face orientation, mipmaps, seams or in-game rendering."}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("request",help="JSON request file");parser.add_argument("--workspace",help="workspace directory (default: MINECRAFT_BEDROCK_WORKSPACE or cwd)");parser.add_argument("--report",help="optional report JSON path")
    args=parser.parse_args(argv)
    try:
        request_path=Path(args.request)
        if request_path.is_symlink():raise PaintError("request JSON path must not be a symlink")
        raw_bytes=_read_bounded(request_path,MAX_JSON_BYTES,"request JSON")
        request=json.loads(raw_bytes.decode("utf-8-sig"),object_pairs_hook=_unique_pairs,parse_constant=_reject_constant)
        result=paint(request,workspace=Path(args.workspace) if args.workspace else None)
        rendered=json.dumps(result,ensure_ascii=False,indent=2)
        if args.report:
            report=Path(args.report)
            if report.exists() or report.is_symlink():raise FileExistsError(f"refusing to overwrite report: {report}")
            report.parent.mkdir(parents=False,exist_ok=True)
            _write_new(report, (rendered+"\n").encode("utf-8"))
        print(rendered);return 0
    except FileExistsError as exc:
        print(json.dumps({"status":"FAIL","code":"OUTPUT_EXISTS","error":str(exc)},ensure_ascii=False));return 2
    except (OSError,PaintError,json.JSONDecodeError) as exc:
        print(json.dumps({"status":"FAIL","error":f"{type(exc).__name__}: {exc}"},ensure_ascii=False));return 2

if __name__=="__main__":raise SystemExit(main())
