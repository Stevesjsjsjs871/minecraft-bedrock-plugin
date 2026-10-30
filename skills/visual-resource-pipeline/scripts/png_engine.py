#!/usr/bin/env python3
"""Standalone, dependency-free PNG structural validator for Bedrock assets."""
from __future__ import annotations
import argparse, json, struct, zlib
from pathlib import Path
_SIGNATURE=b'\x89PNG\r\n\x1a\n'
_CHANNELS={0:1,2:3,3:1,4:2,6:4}
class PNGValidationError(ValueError): pass

def inspect_png(data: bytes, *, max_bytes: int=64*1024*1024) -> dict:
    if not isinstance(data,(bytes,bytearray)): raise TypeError('PNG input must be bytes')
    data=bytes(data)
    if len(data)>max_bytes: raise PNGValidationError('file exceeds byte limit')
    if len(data)<33 or data[:8]!=_SIGNATURE: raise PNGValidationError('invalid PNG signature or truncated IHDR')
    pos=8; ihdr=None; idats=[]; idat_started=False; idat_ended=False; iend=False; plte=False; chunks=[]
    while pos<len(data):
        if pos+12>len(data): raise PNGValidationError('truncated chunk header')
        n=struct.unpack('>I',data[pos:pos+4])[0]; kind=data[pos+4:pos+8]; end=pos+12+n
        if end>len(data): raise PNGValidationError(f'truncated {kind!r} chunk')
        payload=data[pos+8:pos+8+n]; crc=struct.unpack('>I',data[pos+8+n:end])[0]
        if zlib.crc32(kind+payload)&0xffffffff != crc: raise PNGValidationError(f'CRC mismatch in {kind!r}')
        chunks.append(kind.decode('ascii','replace'))
        if ihdr is None:
            if kind!=b'IHDR' or n!=13: raise PNGValidationError('IHDR must be the first 13-byte chunk')
            w,h,depth,color,comp,filt,interlace=struct.unpack('>IIBBBBB',payload)
            if not w or not h: raise PNGValidationError('dimensions must be positive')
            if color not in _CHANNELS: raise PNGValidationError('unsupported color type')
            depths={0:{1,2,4,8,16},2:{8,16},3:{1,2,4,8},4:{8,16},6:{8,16}}
            if depth not in depths[color]: raise PNGValidationError('invalid bit depth/color type combination')
            if comp or filt or interlace not in (0,1): raise PNGValidationError('invalid PNG method field')
            ihdr=(w,h,depth,color,interlace)
        elif kind==b'IHDR': raise PNGValidationError('duplicate IHDR')
        if kind==b'PLTE':
            if idat_started or plte or not n or n%3 or n>768: raise PNGValidationError('invalid PLTE chunk')
            plte=True
        if kind==b'IDAT':
            if idat_ended: raise PNGValidationError('IDAT chunks must be consecutive')
            idat_started=True; idats.append(payload)
        elif idat_started and kind!=b'IEND': idat_ended=True
        if kind==b'IEND':
            if n: raise PNGValidationError('IEND must be empty')
            iend=True; pos=end
            if pos!=len(data): raise PNGValidationError('trailing data after IEND')
            break
        pos=end
    if not iend or not idats: raise PNGValidationError('missing IDAT or IEND')
    w,h,depth,color,interlace=ihdr
    if color==3 and not plte: raise PNGValidationError('indexed PNG requires PLTE')
    compressed=b''.join(idats)
    try:
        d=zlib.decompressobj(); raw=d.decompress(compressed,max_bytes+1)
        if len(raw)>max_bytes or d.unconsumed_tail: raise PNGValidationError('decoded PNG exceeds byte limit')
        raw+=d.flush(max_bytes+1-len(raw))
        if len(raw)>max_bytes: raise PNGValidationError('decoded PNG exceeds byte limit')
    except zlib.error as e: raise PNGValidationError(f'invalid IDAT stream: {e}') from e
    if not d.eof or d.unused_data or d.unconsumed_tail: raise PNGValidationError('invalid or trailing compressed IDAT data')
    if interlace==0:
        rb=(w*_CHANNELS[color]*depth+7)//8; expected=h*(rb+1)
        if len(raw)!=expected: raise PNGValidationError(f'scanline length mismatch ({len(raw)} != {expected})')
        if any(raw[y*(rb+1)]>4 for y in range(h)): raise PNGValidationError('unknown scanline filter')
    else:
        passes=[(0,0,8,8),(4,0,8,8),(0,4,4,8),(2,0,4,4),(0,2,2,4),(1,0,2,2),(0,1,1,2)]
        expected=0; shapes=[]
        for sx,sy,dx,dy in passes:
            pw=0 if w<=sx else (w-sx+dx-1)//dx; ph=0 if h<=sy else (h-sy+dy-1)//dy
            if pw and ph:
                rb=(pw*_CHANNELS[color]*depth+7)//8; expected+=ph*(rb+1); shapes.append((ph,rb))
        if len(raw)!=expected: raise PNGValidationError(f'Adam7 scanline length mismatch ({len(raw)} != {expected})')
        cur=0
        for ph,rb in shapes:
            for _ in range(ph):
                if raw[cur]>4: raise PNGValidationError('unknown Adam7 filter')
                cur+=rb+1
    return {'valid':True,'width':w,'height':h,'bit_depth':depth,'color_type':color,'interlaced':bool(interlace),'file_bytes':len(data),'decoded_bytes':len(raw),'chunks':chunks}

def validate_file(path: str|Path, *, max_bytes:int=64*1024*1024)->dict:
    p=Path(path)
    if not p.is_file(): raise FileNotFoundError(p)
    if p.stat().st_size>max_bytes: raise PNGValidationError('file exceeds byte limit')
    return inspect_png(p.read_bytes(),max_bytes=max_bytes)
def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('png'); ap.add_argument('--max-bytes',type=int,default=64*1024*1024); a=ap.parse_args(argv)
    try: result=validate_file(a.png,max_bytes=a.max_bytes)
    except Exception as e: print(json.dumps({'valid':False,'error':str(e)},indent=2)); return 1
    print(json.dumps(result,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
