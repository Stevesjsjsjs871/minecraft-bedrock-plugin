from __future__ import annotations
import json, tempfile, unittest, struct, zlib
from pathlib import Path
from uv_template_engine import extract_regions, render_template, TemplateError
from geometry_engine import analyze_geometry

def geometry(uv, *, width=64, height=64):
    return {"format_version":"1.12.0","minecraft:geometry":[{"description":{"identifier":"geometry.test","texture_width":width,"texture_height":height},"bones":[{"name":"root","cubes":[{"origin":[0,0,0],"size":[4,6,2],"uv":uv}]}]}]}
class UVTemplateTests(unittest.TestCase):
    def test_classic_uv_expands_six_faces(self):
        report, regions=extract_regions(geometry([0,0]))
        self.assertEqual(len(regions),6)
        self.assertEqual({r['face'] for r in regions},{'north','south','east','west','up','down'})
    def test_classic_net_face_rectangles(self):
        _, rs=extract_regions(geometry([0,0])); by={r['face']:r for r in rs}
        self.assertEqual((by['north']['u'],by['north']['v'],by['north']['width'],by['north']['height']),(2,2,4,6))
        self.assertEqual((by['up']['u'],by['up']['v'],by['up']['width'],by['up']['height']),(2,0,4,2))
    def test_per_face_regions_preserved(self):
        uv={'north':{'uv':[3,4],'uv_size':[-5,6]},'up':{'uv':[1,2],'uv_size':[4,2],'uv_rotation':90}}
        _,rs=extract_regions(geometry(uv)); by={r['face']:r for r in rs}
        self.assertEqual((by['north']['u'],by['north']['v'],by['north']['width'],by['north']['height']),(3,4,5,6))
        self.assertEqual((by['up']['width'],by['up']['height']),(2,4))
    def test_template_png_signature_and_dimensions(self):
        rep,rs=extract_regions(geometry([0,0])); png,meta=render_template(rep,rs,pixel_scale=2,margin=1)
        self.assertEqual(png[:8],b'\x89PNG\r\n\x1a\n')
        w,h=struct.unpack('>II',png[16:24]); self.assertEqual((w,h),(130,130))
    def test_max_pixels_enforced(self):
        rep,rs=extract_regions(geometry([0,0]))
        with self.assertRaises(TemplateError): render_template(rep,rs,max_pixels=10)
    def test_invalid_scale_rejected(self):
        rep,rs=extract_regions(geometry([0,0]))
        with self.assertRaises(TemplateError): render_template(rep,rs,pixel_scale=0)
    def test_per_face_overlap_drawable(self):
        uv={'north':{'uv':[0,0],'uv_size':[4,6]},'south':{'uv':[0,0],'uv_size':[4,6]}}
        rep,rs=extract_regions(geometry(uv)); png,meta=render_template(rep,rs,pixel_scale=1)
        self.assertTrue(png.startswith(b'\x89PNG')); self.assertEqual(meta['regions'],2)
    def test_oversized_unsafe_dimensions_fail(self):
        rep,rs=extract_regions(geometry([0,0],width=4096,height=4096))
        with self.assertRaises(TemplateError): render_template(rep,rs,pixel_scale=8,max_pixels=1_000_000)
if __name__=='__main__': unittest.main(verbosity=2)
