from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import animation_pipeline_audit_mcp as server


def make_project(root: Path) -> Path:
    project = root / "forest-addon"
    bp = project / "behavior_packs" / "forest-addon_BP"
    rp = project / "resource_packs" / "forest-addon_RP"
    for path in (bp / "entities", rp / "entity", rp / "models" / "entity", rp / "animations", rp / "animation_controllers"):
        path.mkdir(parents=True, exist_ok=True)
    rp_uuid = "7abc9d49-9538-4f3d-b4f8-e5b699d00a73"
    (bp / "manifest.json").write_text(json.dumps({
        "format_version": 2,
        "header": {"name": "Forest BP", "uuid": "4615fc03-ff88-4494-b6a3-b73b8ae1665a", "version": [1, 0, 0]},
        "modules": [{"type": "data", "uuid": "f5ef27a7-97d6-4c2e-bcd3-f0de66c6a1f9", "version": [1, 0, 0]}],
        "dependencies": [{"uuid": rp_uuid, "version": [1, 0, 0]}],
    }), encoding="utf-8")
    (rp / "manifest.json").write_text(json.dumps({
        "format_version": 2,
        "header": {"name": "Forest RP", "uuid": rp_uuid, "version": [1, 0, 0]},
        "modules": [{"type": "resources", "uuid": "01b3e74f-4c70-4997-bc13-2b2931acb9bb", "version": [1, 0, 0]}],
    }), encoding="utf-8")

    client = {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": {
            "identifier": "forest:guardian",
            "geometry": {"default": "geometry.forest.guardian"},
            "animations": {
                "walk": "animation.forest.guardian_walk",
                "locomotion": "controller.animation.forest.guardian_locomotion",
            },
            "scripts": {"animate": ["locomotion"]},
        }},
    }
    (rp / "entity" / "forest_guardian.entity.json").write_text(json.dumps(client), encoding="utf-8")
    geometry = {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": "geometry.forest.guardian", "texture_width": 64, "texture_height": 64},
            "bones": [{"name": "body"}, {"name": "head"}, {"name": "left_leg"}],
        }],
    }
    (rp / "models" / "entity" / "forest_guardian.geo.json").write_text(json.dumps(geometry), encoding="utf-8")
    animation = {
        "format_version": "1.8.0",
        "animations": {"animation.forest.guardian_walk": {
            "loop": True,
            "animation_length": 1.0,
            "bones": {
                "left_leg": {"rotation": {"0.0": [0, 0, 0], "0.5": [30, 0, 0], "1.0": [0, 0, 0]}},
                "body": {"position": {"0.0": [0, 0, 0], "1.0": [0, 0, 0]}},
            },
        }},
    }
    (rp / "animations" / "guardian_walk.animation.json").write_text(json.dumps(animation), encoding="utf-8")
    controller = {
        "format_version": "1.10.0",
        "animation_controllers": {"controller.animation.forest.guardian_locomotion": {
            "initial_state": "moving",
            "states": {
                "moving": {"animations": ["walk"], "transitions": [{"idle": "query.modified_move_speed == 0"}]},
                "idle": {"animations": [], "transitions": [{"moving": "query.modified_move_speed > 0"}]},
            },
        }},
    }
    (rp / "animation_controllers" / "guardian.animation_controllers.json").write_text(json.dumps(controller), encoding="utf-8")
    return project


def run_audit(project_root: Path) -> dict:
    with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(project_root)}):
        return server.call_tool("audit_entity_animation_pipeline", {
            "project_directory": "forest-addon",
            "client_entity_file": "entity/forest_guardian.entity.json",
        })


class AnimationPipelineAuditTests(unittest.TestCase):
    def test_valid_complete_pipeline(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            result = run_audit(Path(td))
            self.assertEqual(result["status"], "valid", result["findings"])
            self.assertTrue(result["analysis_complete"])
            self.assertEqual(result["target_entity_identifier"], "forest:guardian")
            self.assertEqual(result["inventory"]["resolved_animation_aliases"], 1)
            self.assertEqual(result["inventory"]["resolved_controller_aliases"], 1)
            self.assertEqual(result["inventory"]["resolved_geometry_aliases"], 1)
            self.assertEqual(result["runtime_status"], "NOT RUN")
            before = (project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json").read_bytes()
            run_audit(Path(td))
            after = (project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json").read_bytes()
            self.assertEqual(before, after)

    def test_missing_animation_file_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            (project / "resource_packs/forest-addon_RP/animations/guardian_walk.animation.json").unlink()
            result = run_audit(Path(td))
            codes = {x["code"] for x in result["findings"]}
            self.assertEqual(result["status"], "issues_found")
            self.assertIn("ANIMATION_RESOURCE_MISSING", codes)

    def test_controller_reference_to_missing_alias_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/guardian.animation_controllers.json"
            data = json.loads(controller_path.read_text())
            definition = data["animation_controllers"]["controller.animation.forest.guardian_locomotion"]
            definition["states"]["moving"]["animations"] = ["walk_typo"]
            controller_path.write_text(json.dumps(data))
            result = run_audit(Path(td))
            codes = {x["code"] for x in result["findings"]}
            self.assertIn("CONTROLLER_ANIMATION_ALIAS_MISSING", codes)

    def test_script_animate_missing_alias_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            entity_path = project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json"
            data = json.loads(entity_path.read_text())
            data["minecraft:client_entity"]["description"]["scripts"]["animate"] = ["missing_alias"]
            entity_path.write_text(json.dumps(data))
            result = run_audit(Path(td))
            self.assertIn("SCRIPT_ANIMATE_ALIAS_MISSING", {x["code"] for x in result["findings"]})

    def test_external_vanilla_animation_reference_is_not_a_missing_local_file(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            entity_path = project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json"
            data = json.loads(entity_path.read_text())
            data["minecraft:client_entity"]["description"]["animations"]["walk"] = "animation.quadruped.walk"
            entity_path.write_text(json.dumps(data))
            (project / "resource_packs/forest-addon_RP/animations/guardian_walk.animation.json").unlink()
            result = run_audit(Path(td))
            codes = {x["code"] for x in result["findings"]}
            self.assertIn("ANIMATION_EXTERNAL_REFERENCE", codes)
            self.assertNotIn("ANIMATION_RESOURCE_MISSING", codes)
            self.assertEqual(result["status"], "valid")

    def test_external_geometry_dependency_is_reported_as_info(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            entity_path = project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json"
            data = json.loads(entity_path.read_text())
            data["minecraft:client_entity"]["description"]["geometry"]["default"] = "geometry.humanoid.custom"
            entity_path.write_text(json.dumps(data))
            (project / "resource_packs/forest-addon_RP/models/entity/forest_guardian.geo.json").unlink()
            result = run_audit(Path(td))
            codes = {x["code"] for x in result["findings"]}
            self.assertIn("GEOMETRY_EXTERNAL_REFERENCE", codes)
            self.assertNotIn("GEOMETRY_RESOURCE_MISSING", codes)
            self.assertEqual(result["status"], "valid")

    def test_missing_geometry_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            (project / "resource_packs/forest-addon_RP/models/entity/forest_guardian.geo.json").unlink()
            result = run_audit(Path(td))
            self.assertIn("GEOMETRY_RESOURCE_MISSING", {x["code"] for x in result["findings"]})

    def test_unknown_animated_bone_is_a_warning_not_a_false_error(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            clip_path = project / "resource_packs/forest-addon_RP/animations/guardian_walk.animation.json"
            data = json.loads(clip_path.read_text())
            data["animations"]["animation.forest.guardian_walk"]["bones"]["tail"] = {"rotation": {"0.0": [0, 0, 0]}}
            clip_path.write_text(json.dumps(data))
            result = run_audit(Path(td))
            finding = next(x for x in result["findings"] if x["code"] == "ANIMATION_BONE_NOT_IN_GEOMETRY")
            self.assertEqual(finding["severity"], "WARNING")
            self.assertEqual(result["status"], "valid")

    def test_duplicate_animation_identifier_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            animations = project / "resource_packs/forest-addon_RP/animations"
            duplicate = json.loads((animations / "guardian_walk.animation.json").read_text())
            (animations / "duplicate.animation.json").write_text(json.dumps(duplicate))
            result = run_audit(Path(td))
            codes = {x["code"] for x in result["findings"]}
            self.assertIn("DUPLICATE_RESOURCE_IDENTIFIER", codes)
            self.assertIn("ANIMATION_RESOURCE_AMBIGUOUS", codes)

    def test_bad_transition_destination_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            path = project / "resource_packs/forest-addon_RP/animation_controllers/guardian.animation_controllers.json"
            data = json.loads(path.read_text())
            data["animation_controllers"]["controller.animation.forest.guardian_locomotion"]["states"]["moving"]["transitions"] = [{"flying": "1.0"}]
            path.write_text(json.dumps(data))
            result = run_audit(Path(td))
            self.assertIn("CONTROLLER_TRANSITION_TARGET_MISSING", {x["code"] for x in result["findings"]})

    def test_nested_controller_cycle_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            rp = project / "resource_packs/forest-addon_RP"
            entity_path = rp / "entity/forest_guardian.entity.json"
            entity = json.loads(entity_path.read_text())
            description = entity["minecraft:client_entity"]["description"]
            description["animations"]["sub"] = "controller.animation.forest.sub"
            entity_path.write_text(json.dumps(entity))
            controllers = {
                "format_version": "1.10.0",
                "animation_controllers": {
                    "controller.animation.forest.sub": {"initial_state": "default", "states": {"default": {"animations": ["locomotion"]}}}
                },
            }
            (rp / "animation_controllers/sub.animation_controllers.json").write_text(json.dumps(controllers))
            main_path = rp / "animation_controllers/guardian.animation_controllers.json"
            main = json.loads(main_path.read_text())
            main["animation_controllers"]["controller.animation.forest.guardian_locomotion"]["states"]["moving"]["animations"] = ["sub"]
            main_path.write_text(json.dumps(main))
            # The added sub-controller points back to the original controller, producing a cycle.
            result = run_audit(Path(td))
            self.assertIn("CONTROLLER_REFERENCE_CYCLE", {x["code"] for x in result["findings"]})

    def test_unrelated_controller_is_not_validated_against_selected_entity(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            rp = project / "resource_packs/forest-addon_RP"
            unrelated = {
                "format_version": "1.10.0",
                "animation_controllers": {"controller.animation.other.mob": {
                    "initial_state": "default",
                    "states": {"default": {"animations": ["other_entity_alias"]}},
                }},
            }
            (rp / "animation_controllers/other.animation_controllers.json").write_text(json.dumps(unrelated))
            result = run_audit(Path(td))
            codes = {x["code"] for x in result["findings"]}
            self.assertNotIn("CONTROLLER_ANIMATION_ALIAS_MISSING", codes)
            self.assertEqual(result["status"], "valid")

    def test_invalid_keyframe_time_and_pre_post_shape_are_reported(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            clip_path = project / "resource_packs/forest-addon_RP/animations/guardian_walk.animation.json"
            data = json.loads(clip_path.read_text())
            data["animations"]["animation.forest.guardian_walk"]["bones"]["left_leg"]["rotation"] = {
                "2.0": [0, 0, 0],
                "0.5": {"pre": [0, 0, 0]},
            }
            clip_path.write_text(json.dumps(data))
            result = run_audit(Path(td))
            codes = {x["code"] for x in result["findings"]}
            self.assertIn("ANIMATION_KEYFRAME_TIME_INVALID", codes)
            self.assertIn("ANIMATION_PRE_POST_INVALID", codes)

    def test_symlinked_animation_root_is_not_followed(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            project = make_project(Path(td))
            rp = project / "resource_packs/forest-addon_RP"
            animations = rp / "animations"
            animations.rename(rp / "animations_original")
            animations.symlink_to(Path(outside), target_is_directory=True)
            result = run_audit(Path(td))
            self.assertFalse(result["analysis_complete"])
            self.assertIn("SYMLINK_DIRECTORY", {x["code"] for x in result["findings"]})

    def test_total_scan_budget_marks_the_result_partial(self):
        with tempfile.TemporaryDirectory() as td:
            make_project(Path(td))
            with patch.object(server, "_MAX_TOTAL_SCAN_BYTES", 1):
                result = run_audit(Path(td))
            self.assertEqual(result["status"], "partial")
            self.assertFalse(result["analysis_complete"])
            self.assertIn("SCAN_BYTE_LIMIT", {x["code"] for x in result["findings"]})

    def test_keyframe_object_property_order_is_not_treated_as_semantic(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            clip_path = project / "resource_packs/forest-addon_RP/animations/guardian_walk.animation.json"
            data = json.loads(clip_path.read_text())
            data["animations"]["animation.forest.guardian_walk"]["bones"]["left_leg"]["rotation"] = {
                "1.0": [0, 0, 0],
                "0.0": [30, 0, 0],
            }
            clip_path.write_text(json.dumps(data))
            result = run_audit(Path(td))
            codes = {x["code"] for x in result["findings"]}
            self.assertNotIn("ANIMATION_KEYFRAME_ORDER_INVALID", codes)
            self.assertEqual(result["status"], "valid")

    def test_numeric_duplicate_keyframe_times_are_reported(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            clip_path = project / "resource_packs/forest-addon_RP/animations/guardian_walk.animation.json"
            data = json.loads(clip_path.read_text())
            data["animations"]["animation.forest.guardian_walk"]["bones"]["left_leg"]["rotation"] = {
                "0.5": [0, 0, 0],
                "0.50": [30, 0, 0],
            }
            clip_path.write_text(json.dumps(data))
            result = run_audit(Path(td))
            self.assertIn("ANIMATION_KEYFRAME_TIME_DUPLICATE", {x["code"] for x in result["findings"]})

    def test_duplicate_json_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            clip_path = project / "resource_packs/forest-addon_RP/animations/guardian_walk.animation.json"
            clip_path.write_text('{"format_version":"1.8.0","animations":{},"animations":{}}')
            result = run_audit(Path(td))
            codes = {x["code"] for x in result["findings"]}
            self.assertIn("RESOURCE_JSON_INVALID", codes)
            self.assertFalse(result["analysis_complete"])

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            make_project(Path(td))
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("audit_entity_animation_pipeline", {
                    "project_directory": "forest-addon",
                    "client_entity_file": "entity/../../outside.entity.json",
                })
            self.assertEqual(result["status"], "error")

    def test_invalid_linked_manifests_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(Path(td))
            manifest = project / "behavior_packs/forest-addon_BP/manifest.json"
            data = json.loads(manifest.read_text())
            data["dependencies"] = []
            manifest.write_text(json.dumps(data))
            result = run_audit(Path(td))
            self.assertEqual(result["status"], "error")
            self.assertIn("linked", result["error"]["message"])

    def test_mcp_registry_and_initialize(self):
        listing = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(listing["result"]["tools"][0]["name"], "audit_entity_animation_pipeline")
        initialized = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "minecraft-bedrock-animation-pipeline-audit")


if __name__ == "__main__":
    unittest.main()
