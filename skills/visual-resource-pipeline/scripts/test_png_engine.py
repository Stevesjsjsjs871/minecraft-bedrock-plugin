import struct, unittest, zlib
from png_engine import inspect_png, PNGValidationError

def chunk(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
def make_png(width=2,height=2,color=6,depth=8,filter_type=0,interlace=0,with_palette=True):
    channels={0:1,2:3,3:1,4:2,6:4}[color]; row=(width*channels*depth+7)//8
    raw=b''.join(bytes([filter_type])+bytes(row) for _ in range(height))
    ihdr=struct.pack('>IIBBBBB',width,height,depth,color,0,0,interlace)
    parts=[b'\x89PNG\r\n\x1a\n',chunk(b'IHDR',ihdr)]
    if color==3 and with_palette: parts.append(chunk(b'PLTE',b'\x00\x00\x00'))
    parts.extend([chunk(b'IDAT',zlib.compress(raw)),chunk(b'IEND',b'')])
    return b''.join(parts)
class TestPNGEngine(unittest.TestCase):
    def test_rgba(self): self.assertTrue(inspect_png(make_png())['valid'])
    def test_rgb(self): self.assertEqual(inspect_png(make_png(color=2))['color_type'],2)
    def test_indexed_requires_palette(self):
        with self.assertRaises(PNGValidationError): inspect_png(make_png(color=3,with_palette=False))
    def test_bad_signature(self):
        with self.assertRaises(PNGValidationError): inspect_png(b'not png')
    def test_bad_crc(self):
        b=bytearray(make_png()); b[29]^=1
        with self.assertRaises(PNGValidationError): inspect_png(b)
    def test_trailing_bytes(self):
        with self.assertRaises(PNGValidationError): inspect_png(make_png()+b'x')
    def test_zero_dimension(self):
        with self.assertRaises(PNGValidationError): inspect_png(make_png(width=0))
    def test_bad_filter(self):
        with self.assertRaises(PNGValidationError): inspect_png(make_png(filter_type=5))
    def test_max_bytes(self):
        with self.assertRaises(PNGValidationError): inspect_png(make_png(),max_bytes=10)
    def test_adam7_lengths(self):
        with self.assertRaises(PNGValidationError): inspect_png(make_png(interlace=1))
if __name__=='__main__': unittest.main()
