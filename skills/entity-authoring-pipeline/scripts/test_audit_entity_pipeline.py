from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from audit_entity_pipeline import audit


class EntityPipelineAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bp = self.root / "BP"
        self.rp = self.root / "RP"
        for folder in (self.bp / "entities", self.rp / "entity", self.rp / "models/entity", self.rp / "animations", self.rp / "animation_controllers", self.rp / "render_controllers", self.rp / "textures/entity"):
            folder.mkdir(parents=True, exist_ok=True)
        self.write(self.bp / "entities/robot.json", {"minecraft:entity": {"description": {"identifier": "demo:robot"}}})
        self.write(self.rp / "entity/robot.entity.json", {"minecraft:client_entity": {"description": {
            "identifier": "demo:robot", "geometry": {"default": "geometry.robot"},
            "animations": {"idle": "animation.robot.idle", "moving": "controller.animation.robot.move"},
            "render_controllers": ["controller.render.robot"], "textures": {"default": "textures/entity/robot"}
        }}})
        self.write(self.rp / "models/entity/robot.geo.json", {"minecraft:geometry": [{"description": {"identifier": "geometry.robot"}, "bones": [{"name": "root"}]}]})
        self.write(self.rp / "animations/robot.animation.json", {"animations": {"animation.robot.idle": {"bones": {"root": {"rotation": 0}}}}})
        self.write(self.rp / "animation_controllers/robot.animation_controllers.json", {"animation_controllers": {"controller.animation.robot.move": {"states": {"default": {"animations": ["moving"]}}}}})
        self.write(self.rp / "render_controllers/robot.render_controllers.json", {"render_controllers": {"controller.render.robot": {}}})
        (self.rp / "textures/entity/robot.png").write_bytes(b"placeholder-for-path-existence-only")

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def write(path: Path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_complete_literal_graph_passes(self):
        report = audit(self.bp, self.rp, "demo:robot")
        self.assertEqual(report["status"], "PASS", report["findings"])
        self.assertEqual(report["summary"]["fail"], 0)

    def test_missing_geometry_is_failure(self):
        path = self.rp / "entity/robot.entity.json"
        data = json.loads(path.read_text())
        data["minecraft:client_entity"]["description"]["geometry"]["default"] = "geometry.missing"
        self.write(path, data)
        report = audit(self.bp, self.rp, "demo:robot")
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(x["code"] == "GEOMETRY_UNRESOLVED" for x in report["findings"]))

    def test_duplicate_json_key_is_failure(self):
        path = self.rp / "entity/robot.entity.json"
        path.write_text('{"minecraft:client_entity":{},"minecraft:client_entity":{}}', encoding="utf-8")
        report = audit(self.bp, self.rp, "demo:robot")
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(x["code"] == "JSON_INVALID" for x in report["findings"]))

    def test_missing_render_controller_is_failure(self):
        path = self.rp / "entity/robot.entity.json"
        data = json.loads(path.read_text())
        data["minecraft:client_entity"]["description"]["render_controllers"] = ["controller.render.unknown"]
        self.write(path, data)
        report = audit(self.bp, self.rp, "demo:robot")
        self.assertTrue(any(x["code"] == "RENDER_CONTROLLER_UNRESOLVED" for x in report["findings"]))

    def test_missing_texture_is_warning_not_schema_proof(self):
        path = self.rp / "entity/robot.entity.json"
        data = json.loads(path.read_text())
        data["minecraft:client_entity"]["description"]["textures"]["default"] = "textures/entity/absent"
        self.write(path, data)
        report = audit(self.bp, self.rp, "demo:robot")
        self.assertEqual(report["status"], "WARN")
        self.assertTrue(any(x["code"] == "TEXTURE_PATH_UNRESOLVED" for x in report["findings"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
