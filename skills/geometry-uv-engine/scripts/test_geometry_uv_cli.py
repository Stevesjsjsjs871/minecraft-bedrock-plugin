from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import geometry_uv_cli as cli


def geometry_payload(uv=(0, 0), *, width=16, height=16, extra_geometry=False):
    description = {"identifier": "geometry.cli_test"}
    if width is not None:
        description["texture_width"] = width
    if height is not None:
        description["texture_height"] = height
    geometry = {
        "description": description,
        "bones": [
            {
                "name": "root",
                "cubes": [
                    {
                        "origin": [0, 0, 0],
                        "size": [2, 2, 2],
                        "uv": list(uv),
                    }
                ],
            }
        ],
    }
    entries = [geometry]
    if extra_geometry:
        second = json.loads(json.dumps(geometry))
        second["description"]["identifier"] = "geometry.second"
        entries.append(second)
    return {"format_version": "1.21.0", "minecraft:geometry": entries}


class GeometryUvCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.project = self.workspace / "cli-addon"
        self.rp = self.project / "resource_packs" / "cli-addon_RP"
        self.geometry_dir = self.rp / "models" / "entity"
        self.texture_dir = self.rp / "textures"
        self.geometry_dir.mkdir(parents=True)
        self.texture_dir.mkdir(parents=True)
        (self.rp / "manifest.json").write_text("{}", encoding="utf-8")
        self.geometry_file = self.geometry_dir / "test.geo.json"
        self.write_geometry(geometry_payload())

    def tearDown(self):
        self.temp.cleanup()

    def write_geometry(self, payload):
        self.geometry_file.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def invoke(self, *args):
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(["--workspace", str(self.workspace), *args])
        return code, json.loads(output.getvalue())

    def geometry_path(self):
        return "resource_packs/cli-addon_RP/models/entity/test.geo.json"

    def test_audit_reports_classic_box_faces(self):
        code, result = self.invoke(
            "audit", "--project", "cli-addon", "--geometry-path", self.geometry_path()
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["faces_checked"], 6)
        self.assertEqual(result["runtime_status"], "NOT RUN")
        self.assertEqual(result["execution"]["mode"], "local-cli-adapter")

    def test_audit_out_of_bounds_returns_failure_exit(self):
        self.write_geometry(geometry_payload((20, 20)))
        code, result = self.invoke(
            "audit", "--project", "cli-addon", "--geometry-path", self.geometry_path()
        )
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "issues_found")
        self.assertGreater(result["summary"]["errors"], 0)

    def test_audit_missing_canvas_is_partial(self):
        self.write_geometry(geometry_payload(width=None, height=None))
        code, result = self.invoke(
            "audit", "--project", "cli-addon", "--geometry-path", self.geometry_path()
        )
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["summary"]["analysis_complete"])

    def test_template_creates_valid_png_and_preserves_geometry(self):
        original = self.geometry_file.read_bytes()
        output_path = "resource_packs/cli-addon_RP/textures/uv_templates/guide.png"
        code, result = self.invoke(
            "template",
            "--project", "cli-addon",
            "--geometry-path", self.geometry_path(),
            "--output-path", output_path,
            "--pixel-scale", "2",
        )
        output = self.project / output_path
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "success")
        self.assertTrue(output.is_file())
        self.assertTrue(result["template"]["png_validation"]["valid"])
        self.assertTrue(result["template"]["sha256_verified"])
        self.assertEqual(result["template"]["width"], 32)
        self.assertEqual(result["template"]["height"], 32)
        self.assertEqual(self.geometry_file.read_bytes(), original)
        self.assertEqual(result["runtime_status"], "NOT RUN")

    def test_template_refuses_to_overwrite_existing_png(self):
        output_path = "resource_packs/cli-addon_RP/textures/uv_templates/guide.png"
        first_code, _ = self.invoke(
            "template", "--project", "cli-addon",
            "--geometry-path", self.geometry_path(),
            "--output-path", output_path,
        )
        output = self.project / output_path
        before = output.read_bytes()
        second_code, second = self.invoke(
            "template", "--project", "cli-addon",
            "--geometry-path", self.geometry_path(),
            "--output-path", output_path,
        )
        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 2)
        self.assertEqual(second["status"], "error")
        self.assertIn("refusing to overwrite", second["error"]["message"])
        self.assertEqual(output.read_bytes(), before)

    def test_template_requires_identifier_for_multiple_geometries(self):
        self.write_geometry(geometry_payload(extra_geometry=True))
        code, result = self.invoke(
            "template", "--project", "cli-addon",
            "--geometry-path", self.geometry_path(),
            "--output-path", "resource_packs/cli-addon_RP/textures/uv_templates/multi.png",
        )
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "error")
        self.assertIn("multiple geometries", result["error"]["message"])

    def test_path_traversal_is_rejected(self):
        code, result = self.invoke(
            "audit", "--project", "cli-addon",
            "--geometry-path",
            "resource_packs/cli-addon_RP/models/entity/../../outside.geo.json",
        )
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "error")
        self.assertIn("parent-traversal", result["error"]["message"])

    def test_missing_workspace_is_rejected(self):
        missing = self.workspace / "does-not-exist"
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(["--workspace", str(missing), "audit", "--project", "cli-addon"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "error")

    def test_workspace_environment_is_restored(self):
        old = os.environ.get(cli.WORKSPACE_ENV)
        with patch.dict(os.environ, {cli.WORKSPACE_ENV: "previous-workspace"}):
            self.invoke("audit", "--project", "cli-addon", "--geometry-path", self.geometry_path())
            self.assertEqual(os.environ[cli.WORKSPACE_ENV], "previous-workspace")
        if old is None:
            self.assertNotIn(cli.WORKSPACE_ENV, os.environ)
        else:
            self.assertEqual(os.environ[cli.WORKSPACE_ENV], old)

    def test_missing_backend_fails_closed(self):
        with tempfile.TemporaryDirectory() as empty_root:
            with patch.object(cli, "ROOT", Path(empty_root)):
                with self.assertRaisesRegex(RuntimeError, "backend is incomplete"):
                    cli._load_backend(Path(empty_root))

    def test_template_out_of_bounds_is_generated_but_quality_fails(self):
        self.write_geometry(geometry_payload((20, 20)))
        output_path = "resource_packs/cli-addon_RP/textures/uv_templates/out-of-bounds.png"
        code, result = self.invoke(
            "template", "--project", "cli-addon",
            "--geometry-path", self.geometry_path(),
            "--output-path", output_path,
        )
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["quality_status"], "FAIL")
        self.assertTrue((self.project / output_path).is_file())

    def test_overlapping_uv_regions_are_reported_as_warning(self):
        payload = geometry_payload()
        cube = json.loads(json.dumps(payload["minecraft:geometry"][0]["bones"][0]["cubes"][0]))
        payload["minecraft:geometry"][0]["bones"][0]["cubes"].append(cube)
        self.write_geometry(payload)
        output_path = "resource_packs/cli-addon_RP/textures/uv_templates/overlap.png"
        code, result = self.invoke(
            "template", "--project", "cli-addon",
            "--geometry-path", self.geometry_path(),
            "--output-path", output_path,
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["quality_status"], "WARN")
        self.assertGreater(result["uv_analysis"]["detected_overlap_pairs"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
