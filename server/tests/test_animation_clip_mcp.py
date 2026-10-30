from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import animation_clip_mcp as server


def scaffold(root: Path) -> Path:
    project = root / "forest-addon"
    bp = project / "behavior_packs" / "forest-addon_BP"
    rp = project / "resource_packs" / "forest-addon_RP"
    for path in (bp / "entities", rp / "entity", rp / "models" / "entity", rp / "animations", rp / "animation_controllers"):
        path.mkdir(parents=True, exist_ok=True)
    rp_uuid = "7abc9d49-9538-4f3d-b4f8-e5b699d00a73"
    bp_manifest = {
        "format_version": 2,
        "header": {"name": "Forest BP", "uuid": "4615fc03-ff88-4494-b6a3-b73b8ae1665a", "version": [1, 0, 0], "min_engine_version": [1, 26, 50]},
        "modules": [{"type": "data", "uuid": "f5ef27a7-97d6-4c2e-bcd3-f0de66c6a1f9", "version": [1, 0, 0]}],
        "dependencies": [{"uuid": rp_uuid, "version": [1, 0, 0]}],
    }
    rp_manifest = {
        "format_version": 2,
        "header": {"name": "Forest RP", "uuid": rp_uuid, "version": [1, 0, 0], "min_engine_version": [1, 26, 50]},
        "modules": [{"type": "resources", "uuid": "01b3e74f-4c70-4997-bc13-2b2931acb9bb", "version": [1, 0, 0]}],
    }
    (bp / "manifest.json").write_text(json.dumps(bp_manifest), encoding="utf-8")
    (rp / "manifest.json").write_text(json.dumps(rp_manifest), encoding="utf-8")
    client = {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": "forest:guardian",
                "geometry": {"default": "geometry.forest_guardian"},
                "animations": {"controller": "controller.animation.forest.guardian"},
                "scripts": {"animate": ["controller"]},
            }
        },
    }
    (rp / "entity" / "forest_guardian.entity.json").write_text(json.dumps(client), encoding="utf-8")
    geometry = {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": "geometry.forest_guardian", "texture_width": 64, "texture_height": 64},
            "bones": [{"name": "body"}, {"name": "head"}, {"name": "left_leg"}],
        }],
    }
    (rp / "models" / "entity" / "forest_guardian.geo.json").write_text(json.dumps(geometry), encoding="utf-8")
    return project


def valid_args() -> dict:
    return {
        "project_directory": "forest-addon",
        "target_game_version": "1.26.50",
        "animation_slug": "guardian_idle",
        "client_entity_file": "entity/forest_guardian.entity.json",
        "animation_length": 1.0,
        "loop": True,
        "bones": [
            {"name": "body", "rotation": [
                {"time": 0.0, "value": [0, 0, 0]},
                {"time": 0.5, "value": [0, "Math.sin(query.anim_time * 2.0) * 2.0", 0]},
                {"time": 1.0, "value": [0, 0, 0]},
            ]},
            {"name": "head", "position": [
                {"time": 0.0, "value": [0, 0, 0]},
                {"time": 0.5, "pre": [0, 0, 0], "post": [0, 0.5, 0]},
                {"time": 1.0, "value": [0, 0, 0]},
            ]},
        ],
    }


class AnimationClipCreateTests(unittest.TestCase):
    def test_create_clip_registers_alias_and_keeps_scripts_animate_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", valid_args())
            self.assertEqual(result["status"], "created", result)
            rp = project / "resource_packs" / "forest-addon_RP"
            clip = json.loads((rp / "animations" / "guardian_idle.animation.json").read_text(encoding="utf-8"))
            client = json.loads((rp / "entity" / "forest_guardian.entity.json").read_text(encoding="utf-8"))
            self.assertEqual(clip["format_version"], "1.8.0")
            self.assertIn("animation.forest_addon.guardian_idle", clip["animations"])
            desc = client["minecraft:client_entity"]["description"]
            self.assertEqual(desc["animations"]["guardian_idle"], "animation.forest_addon.guardian_idle")
            self.assertEqual(desc["scripts"]["animate"], ["controller"])
            self.assertEqual(result["runtime_status"], "NOT RUN")
            self.assertEqual(result["geometry"]["status"], "RESOLVED")
            self.assertEqual(result["geometry"]["unknown_bone_names"], [])

    def test_validate_created_clip(self):
        with tempfile.TemporaryDirectory() as td:
            scaffold(Path(td))
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                created = server.call_tool("create_animation_clip", valid_args())
                checked = server.call_tool("validate_animation_clip", {
                    "project_directory": "forest-addon",
                    "animation_file": "animations/guardian_idle.animation.json",
                    "client_entity_file": "entity/forest_guardian.entity.json",
                    "animation_alias": "guardian_idle",
                })
            self.assertEqual(created["status"], "created")
            self.assertEqual(checked["status"], "valid", checked)
            self.assertEqual(checked["bone_count"], 2)
            self.assertEqual(checked["keyframe_count"], 6)

    def test_unknown_geometry_bones_are_reported_not_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            scaffold(Path(td))
            args = valid_args()
            args["bones"].append({"name": "tail", "rotation": [{"time": 0, "value": [0, 0, 0]}]})
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", args)
            self.assertEqual(result["status"], "created", result)
            self.assertEqual(result["geometry"]["unknown_bone_names"], ["tail"])

    def test_existing_alias_conflict_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["animation_alias"] = "controller"
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("already mapped", result["error"]["message"])
            self.assertFalse((project / "resource_packs/forest-addon_RP/animations/guardian_idle.animation.json").exists())

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            target = project / "resource_packs/forest-addon_RP/animations/guardian_idle.animation.json"
            original = '{"untouched":true}\n'
            target.write_text(original, encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("refusing to overwrite", result["error"]["message"])
            self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_unsorted_frames_and_unknown_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            scaffold(Path(td))
            args = valid_args()
            args["bones"][0]["rotation"] = [{"time": 0.5, "value": [0, 0, 0]}, {"time": 0.25, "value": [0, 0, 0]}]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                unsorted = server.call_tool("create_animation_clip", args)
                extra = server.call_tool("create_animation_clip", dict(valid_args(), surprise=True))
            self.assertEqual(unsorted["status"], "error")
            self.assertIn("strictly increasing", unsorted["error"]["message"])
            self.assertEqual(extra["status"], "error")
            self.assertIn("unexpected argument", extra["error"]["message"])

    def test_missing_value_or_incomplete_pre_post_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            scaffold(Path(td))
            args = valid_args()
            args["bones"][0]["rotation"] = [{"time": 0, "pre": [0, 0, 0]}]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("both pre and post", result["error"]["message"])

    def test_nonfinite_and_out_of_range_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            scaffold(Path(td))
            args = valid_args()
            args["bones"][0]["rotation"][0]["value"] = [float("nan"), 0, 0]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("finite number", result["error"]["message"])

    def test_path_traversal_and_bad_manifest_link_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["client_entity_file"] = "entity/../../outside.entity.json"
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                traversal = server.call_tool("create_animation_clip", args)
                manifest_path = project / "behavior_packs/forest-addon_BP/manifest.json"
                bp = json.loads(manifest_path.read_text(encoding="utf-8"))
                bp["dependencies"] = []
                manifest_path.write_text(json.dumps(bp), encoding="utf-8")
                broken = server.call_tool("create_animation_clip", valid_args())
            self.assertEqual(traversal["status"], "error")
            self.assertEqual(broken["status"], "error")
            self.assertIn("linked Behavior Pack", broken["error"]["message"])

    def test_symlinked_client_entity_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            rp = project / "resource_packs/forest-addon_RP"
            client = rp / "entity/forest_guardian.entity.json"
            client.unlink()
            try:
                client.symlink_to(rp / "manifest.json")
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable on this platform")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("symlink", result["error"]["message"])

    def test_rollback_removes_clip_when_client_update_fails(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            rp = project / "resource_packs/forest-addon_RP"
            client = rp / "entity/forest_guardian.entity.json"
            original = client.read_bytes()
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}), patch.object(server, "_atomic_update_existing", side_effect=OSError("simulated replace failure")):
                result = server.call_tool("create_animation_clip", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertFalse((rp / "animations/guardian_idle.animation.json").exists())
            self.assertEqual(client.read_bytes(), original)


    def test_keyframe_after_animation_end_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            scaffold(Path(td))
            args = valid_args()
            args["bones"][0]["rotation"][-1]["time"] = 1.1
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("at most 1.0", result["error"]["message"])

    def test_duplicate_animation_identifier_in_another_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            rp = project / "resource_packs/forest-addon_RP"
            (rp / "animations" / "existing.animation.json").write_text(json.dumps({
                "format_version": "1.8.0",
                "animations": {"animation.forest_addon.guardian_idle": {"loop": True, "bones": {}}},
            }), encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("identifier already exists", result["error"]["message"])

    def test_explicit_geometry_alias_and_file_are_checked(self):
        with tempfile.TemporaryDirectory() as td:
            scaffold(Path(td))
            args = valid_args()
            args["geometry_alias"] = "default"
            args["geometry_file"] = "models/entity/forest_guardian.geo.json"
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", args)
            self.assertEqual(result["status"], "created", result)
            self.assertEqual(result["geometry"]["status"], "RESOLVED")

    def test_wrong_geometry_identifier_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            geometry_path = project / "resource_packs/forest-addon_RP/models/entity/forest_guardian.geo.json"
            geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
            geometry["minecraft:geometry"][0]["description"]["identifier"] = "geometry.other_model"
            geometry_path.write_text(json.dumps(geometry), encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_clip", valid_args())
            self.assertEqual(result["status"], "created")
            self.assertEqual(result["geometry"]["status"], "NOT FOUND")
            self.assertTrue(result["warnings"])

    def test_validator_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                server.call_tool("create_animation_clip", valid_args())
                client = project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json"
                clip = project / "resource_packs/forest-addon_RP/animations/guardian_idle.animation.json"
                before = (client.read_bytes(), clip.read_bytes())
                checked = server.call_tool("validate_animation_clip", {
                    "project_directory": "forest-addon",
                    "animation_file": "animations/guardian_idle.animation.json",
                    "client_entity_file": "entity/forest_guardian.entity.json",
                    "animation_alias": "guardian_idle",
                })
                after = (client.read_bytes(), clip.read_bytes())
            self.assertEqual(checked["status"], "valid")
            self.assertEqual(before, after)

    def test_mcp_initialize_announces_expected_server_and_instructions(self):
        response = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(response["result"]["serverInfo"]["name"], "minecraft-bedrock-animation-clip-authoring")
        self.assertIn("Animation controllers", response["result"]["instructions"])

    def test_mcp_tool_registry_exposes_two_tools(self):
        response = server.handle_message({"jsonrpc": "2.0", "id": 7, "method": "tools/list"})
        names = {item["name"] for item in response["result"]["tools"]}
        self.assertEqual(names, {"create_animation_clip", "validate_animation_clip"})


if __name__ == "__main__":
    unittest.main()
