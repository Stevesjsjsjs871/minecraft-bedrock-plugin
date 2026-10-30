#!/usr/bin/env python3
"""Render a transparent, labeled UV guide from supported Bedrock cube geometry."""
from __future__ import annotations
import argparse, json, math, struct, zlib, hashlib
from pathlib import Path
from geometry_engine import GeometryError, analyze_file, FACES, _pairs_no_duplicates

class TemplateError(ValueError):
    pass

# Classic box UV face net in Bedrock texture-space order relative to the box origin.
def _classic_faces(size):
    x,y,z=size
    return {
        "west":(0,z,z,y), "north":(z,z,x,y), "east":(z+x,z,z,y),
        "south":(2*z+x,z,x,y), "up":(z,0,x,z), "down":(z+x,0,x,z)
    }

def extract_regions(data, geometry_identifier=None):
    # Use the validated analyzer for selection, geometry schema, numeric and UV checks,
    # then expand each classic net into its six labeled face rectangles.
    result = analyze_file_data(data, geometry_identifier)
    geo = data["minecraft:geometry"][result["geometry_index"]]
    regions=[]; cursor=0
    for bone in geo.get("bones",[]):
        name=bone["name"]
        for ci,cube in enumerate(bone.get("cubes",[])):
            size=tuple(float(v) for v in cube["size"])
            uv=cube["uv"]
            if isinstance(uv,list):
                u,v=map(float,uv)
                for face,(du,dv,w,h) in _classic_faces(size).items():
                    regions.append({"bone":name,"cube_index":ci,"face":face,"u":u+du,"v":v+dv,"width":w,"height":h,"out_of_bounds":u+du<0 or v+dv<0 or u+du+w>result['texture_canvas']['width'] or v+dv+h>result['texture_canvas']['height']})
            elif isinstance(uv,dict):
                dims={"north":(size[0],size[1]),"south":(size[0],size[1]),"east":(size[2],size[1]),"west":(size[2],size[1]),"up":(size[0],size[2]),"down":(size[0],size[2])}
                for face,fd in uv.items():
                    if face not in FACES: continue
                    u,v=map(float,fd["uv"]); fw,fh=map(float,fd.get("uv_size",dims[face])); rot=fd.get("uv_rotation",0)
                    if rot in (90,270): fw,fh=abs(fh),abs(fw)
                    else: fw,fh=abs(fw),abs(fh)
                    regions.append({"bone":name,"cube_index":ci,"face":face,"u":u,"v":v,"width":fw,"height":fh,"out_of_bounds":u<0 or v<0 or u+fw>result['texture_canvas']['width'] or v+fh>result['texture_canvas']['height']})
    return result,regions

def analyze_file_data(data, geometry_identifier=None):
    # Reuse the shared analysis implementation, serializing only the selected in-memory object
    # through analyze_geometry to avoid divergent validation rules.
    from geometry_engine import analyze_geometry
    return analyze_geometry(data, geometry_identifier=geometry_identifier)

def _chunk(kind,payload):
    return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)

def encode_png(width,height,pixels):
    raw=b''.join(b'\x00'+bytes(pixels[y*width*4:(y+1)*width*4]) for y in range(height))
    ihdr=struct.pack('>IIBBBBB',width,height,8,6,0,0,0)
    return b'\x89PNG\r\n\x1a\n'+_chunk(b'IHDR',ihdr)+_chunk(b'IDAT',zlib.compress(raw,9))+_chunk(b'IEND',b'')

_FONT={
'A':("01110","10001","10001","11111","10001","10001","10001"), 'B':("11110","10001","10001","11110","10001","10001","11110"),
'C':("01111","10000","10000","10000","10000","10000","01111"), 'D':("11110","10001","10001","10001","10001","10001","11110"),
'E':("11111","10000","10000","11110","10000","10000","11111"), 'F':("11111","10000","10000","11110","10000","10000","10000"),
'G':("01111","10000","10000","10111","10001","10001","01111"), 'H':("10001","10001","10001","11111","10001","10001","10001"),
'I':("11111","00100","00100","00100","00100","00100","11111"), 'J':("00111","00010","00010","00010","10010","10010","01100"),
'K':("10001","10010","10100","11000","10100","10010","10001"), 'L':("10000","10000","10000","10000","10000","10000","11111"),
'M':("10001","11011","10101","10101","10001","10001","10001"), 'N':("10001","11001","10101","10011","10001","10001","10001"),
'O':("01110","10001","10001","10001","10001","10001","01110"), 'P':("11110","10001","10001","11110","10000","10000","10000"),
'Q':("01110","10001","10001","10001","10101","10010","01101"), 'R':("11110","10001","10001","11110","10100","10010","10001"),
'S':("01111","10000","10000","01110","00001","00001","11110"), 'T':("11111","00100","00100","00100","00100","00100","00100"),
'U':("10001","10001","10001","10001","10001","10001","01110"), 'V':("10001","10001","10001","10001","10001","01010","00100"),
'W':("10001","10001","10001","10101","10101","10101","01010"), 'X':("10001","10001","01010","00100","01010","10001","10001"),
'Y':("10001","10001","01010","00100","00100","00100","00100"), 'Z':("11111","00001","00010","00100","01000","10000","11111"),
'0':("01110","10001","10011","10101","11001","10001","01110"),'1':("00100","01100","00100","00100","00100","00100","01110"),
'2':("01110","10001","00001","00010","00100","01000","11111"),'3':("11110","00001","00001","01110","00001","00001","11110"),
'4':("00010","00110","01010","10010","11111","00010","00010"),'5':("11111","10000","10000","11110","00001","00001","11110"),
'6':("01110","10000","10000","11110","10001","10001","01110"),'7':("11111","00001","00010","00100","01000","01000","01000"),
'8':("01110","10001","10001","01110","10001","10001","01110"),'9':("01110","10001","10001","01111","00001","00001","01110"),
'-':("00000","00000","00000","11111","00000","00000","00000"),'_':("00000","00000","00000","00000","00000","00000","11111"),
' ': ("00000",)*7
}

def _set(pix,w,h,x,y,color):
    if 0<=x<w and 0<=y<h:
        i=(y*w+x)*4; pix[i:i+4]=bytes(color)

def _line(pix,w,h,x0,y0,x1,y1,color):
    dx=abs(x1-x0); sx=1 if x0<x1 else -1; dy=-abs(y1-y0); sy=1 if y0<y1 else -1; err=dx+dy
    while True:
        _set(pix,w,h,x0,y0,color)
        if x0==x1 and y0==y1: break
        e2=2*err
        if e2>=dy: err+=dy; x0+=sx
        if e2<=dx: err+=dx; y0+=sy

def _text(pix,w,h,x,y,text,color,scale=1):
    cur=x
    for ch in text.upper():
        glyph=_FONT.get(ch,_FONT[' '])
        for gy,row in enumerate(glyph):
            for gx,on in enumerate(row):
                if on=='1':
                    for sy in range(scale):
                        for sx in range(scale): _set(pix,w,h,cur+gx*scale+sx,y+gy*scale+sy,color)
        cur+=6*scale

def render_template(report,regions,*,pixel_scale=4,label_scale=1,margin=2,max_pixels=64_000_000):
    if not isinstance(pixel_scale,int) or isinstance(pixel_scale,bool) or not 1<=pixel_scale<=8: raise TemplateError('pixel_scale must be an integer from 1 to 8')
    if not isinstance(label_scale,int) or isinstance(label_scale,bool) or not 1<=label_scale<=3: raise TemplateError('label_scale must be an integer from 1 to 3')
    if not isinstance(margin,int) or isinstance(margin,bool) or not 0<=margin<=64: raise TemplateError('margin must be an integer from 0 to 64')
    cw=report['texture_canvas']['width']; ch=report['texture_canvas']['height']; w=cw*pixel_scale+margin*2; h=ch*pixel_scale+margin*2
    if w*h>max_pixels: raise TemplateError(f'output canvas exceeds pixel budget ({w}x{h})')
    pixels=bytearray(w*h*4)
    # very subtle grid at each texture pixel when scale permits
    grid=(70,80,92,90); outline=(225,230,238,255); warning=(255,70,185,255); text=(238,243,250,255); panel=(18,22,30,255)
    for x in range(margin,margin+cw*pixel_scale,pixel_scale):
        for y in range(margin,margin+ch*pixel_scale): _set(pixels,w,h,x,y,grid)
    for y in range(margin,margin+ch*pixel_scale,pixel_scale):
        for x in range(margin,margin+cw*pixel_scale): _set(pixels,w,h,x,y,grid)
    # Transparent background; outline each region, use separate hatches for out-of-bounds.
    for idx,r in enumerate(regions):
        x0=margin+round(r['u']*pixel_scale); y0=margin+round(r['v']*pixel_scale)
        x1=margin+round((r['u']+r['width'])*pixel_scale); y1=margin+round((r['v']+r['height'])*pixel_scale)
        col=warning if r['out_of_bounds'] else outline
        _line(pixels,w,h,x0,y0,x1,y0,col); _line(pixels,w,h,x1,y0,x1,y1,col); _line(pixels,w,h,x1,y1,x0,y1,col); _line(pixels,w,h,x0,y1,x0,y0,col)
        if r['out_of_bounds']:
            # Mark the in-canvas portion with a sparse warning hatch; source geometry is untouched.
            xa=max(0,x0); xb=min(w-1,x1); ya=max(0,y0); yb=min(h-1,y1)
            for yy in range(ya,yb+1,max(3,pixel_scale*2)):
                for xx in range(xa,xb+1,max(3,pixel_scale*2)):
                    _set(pixels,w,h,xx,yy,warning)
        label=f"{r['bone'][:12]} {r['cube_index']} {r['face']}"
        _text(pixels,w,h,max(margin,x0+1),max(margin,y0+1),label,text,label_scale)
    return encode_png(w,h,pixels),{'width':w,'height':h,'texture_width':cw,'texture_height':ch,'pixel_scale':pixel_scale,'regions':len(regions),'out_of_bounds':sum(r['out_of_bounds'] for r in regions)}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('geometry'); ap.add_argument('output'); ap.add_argument('--geometry-identifier'); ap.add_argument('--pixel-scale',type=int,default=4); ap.add_argument('--label-scale',type=int,default=1); ap.add_argument('--margin',type=int,default=2); ap.add_argument('--max-pixels',type=int,default=64_000_000); args=ap.parse_args(argv)
    src=Path(args.geometry).resolve(); dst=Path(args.output).resolve()
    if src==dst: ap.error('output must not overwrite geometry input')
    if dst.exists(): ap.error('refusing to overwrite existing output file')
    try:
        raw=src.read_text(encoding='utf-8-sig'); data=json.loads(raw,object_pairs_hook=_pairs_no_duplicates,parse_constant=lambda v: (_ for _ in ()).throw(GeometryError(f'non-finite JSON constant {v}')))
        report,regions=extract_regions(data,args.geometry_identifier); png,meta=render_template(report,regions,pixel_scale=args.pixel_scale,label_scale=args.label_scale,margin=args.margin,max_pixels=args.max_pixels)
        dst.parent.mkdir(parents=True,exist_ok=True)
        # Recheck the destination after making parents; exclusive create prevents races/overwrites.
        with dst.open('xb') as f: f.write(png)
    except Exception as e:
        print(json.dumps({'status':'FAIL','error':str(e)},ensure_ascii=False,indent=2)); return 2
    print(json.dumps({'status':'PASS' if not meta['out_of_bounds'] else 'WARN','output':str(dst),'sha256':hashlib.sha256(png).hexdigest(),**meta},ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
