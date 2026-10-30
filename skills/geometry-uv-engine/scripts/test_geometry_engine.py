from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from geometry_engine import GeometryError, analyze_geometry, analyze_file

def doc(cubes, *, identifier="geometry.test", width=64, height=64):
    return {"format_version":"1.12.0","minecraft:geometry":[{"description":{"identifier":identifier,"texture_width":width,"texture_height":height},"bones":[{"name":"root","cubes":cubes}]}]}
class GeometryEngineTests(unittest.TestCase):
    def test_classic_box_layout(self):
        r=analyze_geometry(doc([{"origin":[0,0,0],"size":[4,6,2],"uv":[1,2]}]))
        box=r["regions"][0]; self.assertEqual((box["width"],box["height"]),(12,8)); self.assertEqual(r["summary"]["status"],"PASS")
    def test_per_face_default_extents(self):
        uv={f:{"uv":[0,0]} for f in ("north","south","east","west","up","down")}
        r=analyze_geometry(doc([{"origin":[0,0,0],"size":[4,6,2],"uv":uv}]))
        dims={x["selector"]["face"]:(x["width"],x["height"]) for x in r["regions"]}
        self.assertEqual(dims["north"],(4,6)); self.assertEqual(dims["east"],(2,6)); self.assertEqual(dims["up"],(4,2))
    def test_out_of_bounds(self):
        r=analyze_geometry(doc([{"origin":[0,0,0],"size":[4,6,2],"uv":[60,60]}]))
        self.assertEqual(r["summary"]["status"],"FAIL"); self.assertEqual(r["summary"]["out_of_bounds"],1)
    def test_overlap_is_warning(self):
        cubes=[{"origin":[0,0,0],"size":[4,6,2],"uv":[0,0]},{"origin":[8,0,0],"size":[4,6,2],"uv":[1,1]}]
        r=analyze_geometry(doc(cubes)); self.assertGreater(r["summary"]["overlaps"],0); self.assertEqual(r["summary"]["status"],"WARN")
    def test_rotation_swaps_bounds(self):
        uv={"north":{"uv":[0,0],"uv_size":[4,6],"uv_rotation":90}}
        r=analyze_geometry(doc([{"origin":[0,0,0],"size":[4,6,2],"uv":uv}]))
        self.assertEqual((r["regions"][0]["width"],r["regions"][0]["height"]),(6,4))
    def test_geometry_selection_required(self):
        d=doc([]); d["minecraft:geometry"].append(d["minecraft:geometry"][0].copy())
        with self.assertRaises(GeometryError): analyze_geometry(d)
    def test_geometry_identifier_selects(self):
        d=doc([]); d["minecraft:geometry"].append({"description":{"identifier":"geometry.other"},"bones":[]})
        r=analyze_geometry(d,geometry_identifier="geometry.other"); self.assertEqual(r["geometry_identifier"],"geometry.other")
    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"bad.geo.json"; p.write_text('{"minecraft:geometry":[],"minecraft:geometry":[]}')
            with self.assertRaises(GeometryError): analyze_file(p)
    def test_nonfinite_geometry_number_rejected(self):
        with self.assertRaises(GeometryError): analyze_geometry(doc([{"origin":[0,0,0],"size":[float('nan'),1,1],"uv":[0,0]}]))
    def test_bad_cube_size_rejected(self):
        with self.assertRaises(GeometryError): analyze_geometry(doc([{"origin":[0,0,0],"size":[0,1,1],"uv":[0,0]}]))
if __name__=="__main__": unittest.main(verbosity=2)
