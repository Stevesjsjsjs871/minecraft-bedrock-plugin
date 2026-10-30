from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SERVER_PATH = Path(__file__).resolve().parents[1] / "animation_controller_mcp.py"
spec = importlib.util.spec_from_file_location("mbe_animation_controller_mcp", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(server)


def scaffold(workspace: Path, name: str = "forest-addon") -> Path:
    project = workspace / name
    bp = project / "behavior_packs" / f"{name}_BP"
    rp = project / "resource_packs" / f"{name}_RP"
    for folder in (bp / "entities", rp / "entity", rp / "animation_controllers"):
        folder.mkdir(parents=True, exist_ok=True)
    rp_uuid = "33333333-3333-4333-8333-333333333333"
    (bp / "manifest.json").write_text(json.dumps({"format_version": 2, "header": {"uuid": "11111111-1111-4111-8111-111111111111"}, "modules": [{"type": "data"}], "dependencies": [{"uuid": rp_uuid, "version": [1, 0, 0]}]}), encoding="utf-8")
    (rp / "manifest.json").write_text(json.dumps({"format_version": 2, "header": {"uuid": rp_uuid}, "modules": [{"type": "resources"}]}), encoding="utf-8")
    client = {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": {
            "identifier": "forest_addon:forest_guardian",
            "animations": {"idle": "animation.forest_guardian.idle", "walk": "animation.forest_guardian.walk"},
            "scripts": {"animate": ["idle"]},
        }},
    }
    (rp / "entity/forest_guardian.entity.json").write_text(json.dumps(client, indent=2), encoding="utf-8")
    return project


def valid_args() -> dict:
    return {
        "project_directory": "forest-addon",
        "target_game_version": "1.26.50",
        "controller_slug": "forest_guardian",
        "client_entity_file": "entity/forest_guardian.entity.json",
        "initial_state": "idle",
        "states": [
            {"name": "idle", "animations": ["idle"], "transitions": {"walking": "query.modified_move_speed > 0.01"}, "blend_transition": 0.2},
            {"name": "walking", "animations": ["walk"], "transitions": {"idle": "query.modified_move_speed <= 0.01"}},
        ],
    }


class ContractTests(unittest.TestCase):
    def test_tool_registry_contains_creator_and_read_only_validator(self):
        self.assertEqual(set(server.TOOL_BY_NAME), {"create_animation_controller", "validate_animation_controller"})
        creator = server.TOOL_BY_NAME["create_animation_controller"]
        validator = server.TOOL_BY_NAME["validate_animation_controller"]
        self.assertFalse(creator["inputSchema"]["additionalProperties"])
        self.assertFalse(creator["annotations"]["readOnlyHint"])
        self.assertTrue(validator["annotations"]["readOnlyHint"])
        self.assertFalse(creator["annotations"]["destructiveHint"])
        animation_items = creator["inputSchema"]["properties"]["states"]["items"]["properties"]["animations"]["items"]
        self.assertEqual({item["type"] for item in animation_items["anyOf"]}, {"string", "object"})

    def test_initialize_and_tools_list_protocol(self):
        init = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(init["result"]["serverInfo"]["version"], "1.1.1")
        listing = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(len(listing["result"]["tools"]), 2)

    def test_rejects_extra_arguments_and_invalid_project_directory(self):
        bad = dict(valid_args(), unwanted=True)
        result = server.call_tool("create_animation_controller", bad)
        self.assertEqual(result["status"], "error")
        self.assertIn("unexpected argument", result["error"]["message"])
        bad = dict(valid_args(), project_directory="../outside")
        result = server.call_tool("create_animation_controller", bad)
        self.assertEqual(result["status"], "error")


class ControllerCreationTests(unittest.TestCase):
    def test_creates_controller_and_updates_client_entity_atomically(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", valid_args())
            self.assertEqual(result["status"], "created")
            self.assertEqual(result["controller_identifier"], "controller.animation.forest_addon.forest_guardian")
            self.assertEqual(result["state_count"], 2)
            self.assertEqual(result["transition_count"], 2)
            self.assertEqual(result["runtime_status"], "NOT RUN")
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            client_path = project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json"
            controller = json.loads(controller_path.read_text(encoding="utf-8"))
            client = json.loads(client_path.read_text(encoding="utf-8"))
            definition = controller["animation_controllers"][result["controller_identifier"]]
            self.assertEqual(definition["initial_state"], "idle")
            self.assertEqual(definition["states"]["idle"]["transitions"], [{"walking": "query.modified_move_speed > 0.01"}])
            description = client["minecraft:client_entity"]["description"]
            self.assertEqual(description["animations"]["forest_guardian"], result["controller_identifier"])
            self.assertIn("forest_guardian", description["scripts"]["animate"])

    def test_ordered_transition_array_input_preserves_bedrock_priority(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["states"][0]["transitions"] = [
                {"walking": "query.modified_move_speed > 0.01"},
                {"idle": "query.is_sprinting"},
            ]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
            self.assertEqual(result["status"], "created")
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            controller = json.loads(controller_path.read_text(encoding="utf-8"))
            transitions = controller["animation_controllers"][result["controller_identifier"]]["states"]["idle"]["transitions"]
            self.assertEqual(transitions, [
                {"walking": "query.modified_move_speed > 0.01"},
                {"idle": "query.is_sprinting"},
            ])

    def test_blended_animation_alias_object_is_preserved_and_counted(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["states"][0]["animations"] = ["idle", {"walk": "query.modified_move_speed"}]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
                checked = server.call_tool("validate_animation_controller", {
                    "project_directory": "forest-addon",
                    "controller_file": "animation_controllers/forest_guardian.animation_controllers.json",
                    "client_entity_file": "entity/forest_guardian.entity.json",
                    "animation_alias": "forest_guardian",
                })
            self.assertEqual(result["status"], "created")
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            controller = json.loads(controller_path.read_text(encoding="utf-8"))
            definition = controller["animation_controllers"][result["controller_identifier"]]
            self.assertEqual(definition["states"]["idle"]["animations"], ["idle", {"walk": "query.modified_move_speed"}])
            self.assertEqual(result["molang_expressions"], 3)
            self.assertEqual(checked["status"], "valid")
            self.assertEqual(checked["molang_expressions_inspected"], 3)
            self.assertEqual(checked["referenced_animation_aliases"], ["idle", "walk"])

    def test_rejects_blended_animation_with_multiple_aliases_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["states"][0]["animations"] = [{"idle": "1.0", "walk": "1.0"}]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("exactly one animation alias", result["error"]["message"])
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            self.assertFalse(controller_path.exists())

    def test_rejects_missing_alias_in_blended_animation_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["states"][0]["animations"] = [{"missing": "1.0"}]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("not defined", result["error"]["message"])
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            self.assertFalse(controller_path.exists())

    def test_rejects_invalid_blend_expression_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["states"][0]["animations"] = [{"walk": "query.foo\nquery.bar"}]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("Molang string", result["error"]["message"])
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            self.assertFalse(controller_path.exists())

    def test_rejects_transition_array_entries_with_multiple_targets_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["states"][0]["transitions"] = [
                {"walking": "query.modified_move_speed > 0.01", "idle": "query.is_sprinting"}
            ]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("exactly one target", result["error"]["message"])
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            self.assertFalse(controller_path.exists())

    def test_optional_animate_condition_is_bound_as_expression(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = dict(valid_args(), animate_condition="query.is_alive")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
            self.assertEqual(result["status"], "created")
            client = json.loads((project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json").read_text(encoding="utf-8"))
            self.assertIn({"forest_guardian": "query.is_alive"}, client["minecraft:client_entity"]["description"]["scripts"]["animate"])

    def test_missing_animation_alias_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["states"][0]["animations"] = ["missing"]
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("not defined", result["error"]["message"])
            self.assertFalse((project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json").exists())

    def test_unknown_transition_target_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            args = valid_args()
            args["states"][0]["transitions"] = {"flight": "query.is_moving"}
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("unknown", result["error"]["message"])
            self.assertFalse((project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json").exists())

    def test_duplicate_states_and_missing_initial_state_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            scaffold(Path(td))
            args = valid_args()
            args["states"].append({"name": "idle"})
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                duplicate = server.call_tool("create_animation_controller", args)
                missing = server.call_tool("create_animation_controller", dict(valid_args(), initial_state="absent"))
            self.assertEqual(duplicate["status"], "error")
            self.assertIn("duplicate", duplicate["error"]["message"])
            self.assertEqual(missing["status"], "error")

    def test_molang_must_be_printable_and_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            scaffold(Path(td))
            args = valid_args()
            args["states"][0]["transitions"] = {"walking": "query.foo\nquery.bar"}
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", args)
            self.assertEqual(result["status"], "error")
            self.assertIn("Molang string", result["error"]["message"])

    def test_refuses_existing_output_and_preserves_it(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            existing = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            existing.write_text('{"untouched":true}\n', encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("refusing to overwrite", result["error"]["message"])
            self.assertEqual(existing.read_text(encoding="utf-8"), '{"untouched":true}\n')

    def test_removes_new_controller_if_client_entity_replacement_fails(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            client_path = project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json"
            original = client_path.read_bytes()
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}), patch.object(server, "_atomic_update_existing", side_effect=OSError("simulated replace failure")):
                result = server.call_tool("create_animation_controller", valid_args())
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            self.assertEqual(result["status"], "error")
            self.assertFalse(controller_path.exists())
            self.assertEqual(client_path.read_bytes(), original)

    def test_refuses_alias_conflict_and_duplicate_script_entry(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            client = project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json"
            data = json.loads(client.read_text(encoding="utf-8"))
            data["minecraft:client_entity"]["description"]["animations"]["forest_guardian"] = "controller.animation.someone_else"
            client.write_text(json.dumps(data), encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("different resource", result["error"]["message"])

    def test_refuses_invalid_manifest_linkage(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            bp_manifest = project / "behavior_packs/forest-addon_BP/manifest.json"
            data = json.loads(bp_manifest.read_text(encoding="utf-8"))
            data["dependencies"] = []
            bp_manifest.write_text(json.dumps(data), encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("linked Behavior Pack", result["error"]["message"])

    def test_rejects_symlinked_client_entity(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            entity = project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json"
            entity.unlink()
            entity.symlink_to(project / "resource_packs/forest-addon_RP/manifest.json")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_animation_controller", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("symlink", result["error"]["message"])


class ControllerValidationTests(unittest.TestCase):
    def test_read_only_validator_passes_created_controller(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                created = server.call_tool("create_animation_controller", valid_args())
                checked = server.call_tool("validate_animation_controller", {
                    "project_directory": "forest-addon",
                    "controller_file": "animation_controllers/forest_guardian.animation_controllers.json",
                    "client_entity_file": "entity/forest_guardian.entity.json",
                    "animation_alias": "forest_guardian",
                })
            self.assertEqual(created["status"], "created")
            self.assertEqual(checked["status"], "valid")
            self.assertEqual(checked["state_count"], 2)

    def test_validator_detects_transition_to_missing_state(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                server.call_tool("create_animation_controller", valid_args())
                controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
                data = json.loads(controller_path.read_text(encoding="utf-8"))
                controller = next(iter(data["animation_controllers"].values()))
                controller["states"]["idle"]["transitions"] = [{"missing": "1.0"}]
                controller_path.write_text(json.dumps(data), encoding="utf-8")
                checked = server.call_tool("validate_animation_controller", {
                    "project_directory": "forest-addon",
                    "controller_file": "animation_controllers/forest_guardian.animation_controllers.json",
                    "client_entity_file": "entity/forest_guardian.entity.json",
                    "animation_alias": "forest_guardian",
                })
            self.assertEqual(checked["status"], "error")
            self.assertIn("missing state", checked["error"]["message"])

    def test_validator_rejects_missing_blend_animation_alias(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                created = server.call_tool("create_animation_controller", valid_args())
            self.assertEqual(created["status"], "created")
            controller_path = project / "resource_packs/forest-addon_RP/animation_controllers/forest_guardian.animation_controllers.json"
            data = json.loads(controller_path.read_text(encoding="utf-8"))
            definition = data["animation_controllers"][created["controller_identifier"]]
            definition["states"]["idle"]["animations"] = [{"missing": "query.modified_move_speed"}]
            controller_path.write_text(json.dumps(data), encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                checked = server.call_tool("validate_animation_controller", {
                    "project_directory": "forest-addon",
                    "controller_file": "animation_controllers/forest_guardian.animation_controllers.json",
                    "client_entity_file": "entity/forest_guardian.entity.json",
                    "animation_alias": "forest_guardian",
                })
            self.assertEqual(checked["status"], "error")
            self.assertIn("missing client-entity animation alias", checked["error"]["message"])

    def test_symlinked_project_and_path_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            scaffold(Path(td))
            (Path(td) / "linked-addon").symlink_to(outside, target_is_directory=True)
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                linked = server.call_tool("create_animation_controller", dict(valid_args(), project_directory="linked-addon"))
                traversal = server.call_tool("validate_animation_controller", {
                    "project_directory": "forest-addon",
                    "controller_file": "animation_controllers/../../manifest.json",
                    "client_entity_file": "entity/forest_guardian.entity.json",
                    "animation_alias": "forest_guardian",
                })
            self.assertEqual(linked["status"], "error")
            self.assertEqual(traversal["status"], "error")


if __name__ == "__main__":
    unittest.main()
