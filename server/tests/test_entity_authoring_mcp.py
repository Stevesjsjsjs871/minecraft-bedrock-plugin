from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SERVER_PATH = Path(__file__).resolve().parents[1] / "entity_authoring_mcp.py"
spec = importlib.util.spec_from_file_location("mbe_entity_authoring_mcp", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(server)


def scaffold(workspace: Path, name: str = "forest-addon") -> Path:
    project = workspace / name
    bp = project / "behavior_packs" / f"{name}_BP"
    rp = project / "resource_packs" / f"{name}_RP"
    for directory in (
        bp / "entities",
        rp / "entity",
        rp / "models" / "entity",
        rp / "render_controllers",
        rp / "textures" / "entity" / name.replace("-", "_"),
    ):
        directory.mkdir(parents=True, exist_ok=True)
    rp_uuid = "33333333-3333-4333-8333-333333333333"
    (bp / "manifest.json").write_text(json.dumps({
        "format_version": 2,
        "header": {"uuid": "11111111-1111-4111-8111-111111111111"},
        "modules": [{"type": "data"}],
        "dependencies": [{"uuid": rp_uuid, "version": [1, 0, 0]}],
    }), encoding="utf-8")
    (rp / "manifest.json").write_text(json.dumps({
        "format_version": 2,
        "header": {"uuid": rp_uuid},
        "modules": [{"type": "resources"}],
    }), encoding="utf-8")
    return project


def valid_args(project: str = "forest-addon") -> dict:
    return {
        "project_directory": project,
        "entity_name": "Forest Guardian",
        "entity_slug": "forest_guardian",
        "target_game_version": "1.26.50",
        "health": 36,
        "movement_speed": 0.2,
        "geometry": {
            "texture_width": 64,
            "texture_height": 64,
            "visible_bounds_width": 2.5,
            "visible_bounds_height": 3.0,
            "visible_bounds_offset": [0, 1.5, 0],
            "bones": [
                {
                    "name": "root",
                    "pivot": [0, 0, 0],
                    "cubes": [{"origin": [-4, 0, -2], "size": [8, 16, 4], "uv": [0, 0]}],
                },
                {
                    "name": "head",
                    "parent": "root",
                    "pivot": [0, 16, 0],
                    "cubes": [{"origin": [-3, 16, -3], "size": [6, 6, 6], "uv": [24, 0]}],
                },
            ],
        },
    }


class SchemaAndProtocolTests(unittest.TestCase):
    def test_entity_tool_has_closed_schema_and_write_annotations(self):
        tool = server.TOOL_BY_NAME["create_addon_entity_with_geometry"]
        self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertFalse(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["annotations"]["idempotentHint"])
        self.assertFalse(tool["annotations"]["destructiveHint"])

    def test_tools_list_exposes_entity_authoring(self):
        response = server.handle_message({"jsonrpc": "2.0", "id": 8, "method": "tools/list", "params": {}})
        self.assertEqual(response["result"]["tools"][0]["name"], "create_addon_entity_with_geometry")

    def test_initialize_reports_server_version_and_workflow(self):
        response = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(response["result"]["serverInfo"]["version"], "1.1.0")
        self.assertIn("create_addon_entity_with_geometry", response["result"]["instructions"])


class EntityCreationTests(unittest.TestCase):
    def test_creates_bp_entity_client_entity_geometry_and_render_controller(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            project = scaffold(workspace)
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_entity_with_geometry", valid_args())
            self.assertEqual(result["status"], "created")
            self.assertEqual(result["entity_identifier"], "forest_addon:forest_guardian")
            self.assertEqual(result["geometry_identifier"], "geometry.forest_addon.forest_guardian")
            self.assertEqual(len(result["files_created"]), 4)
            self.assertEqual(result["geometry_summary"], {"bones": 2, "cubes": 2, "texture_size": [64, 64]})
            self.assertEqual(result["runtime_status"], "NOT RUN")

            bp = json.loads((project / "behavior_packs/forest-addon_BP/entities/forest_guardian.json").read_text(encoding="utf-8"))
            client = json.loads((project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json").read_text(encoding="utf-8"))
            geometry = json.loads((project / "resource_packs/forest-addon_RP/models/entity/forest_guardian.geo.json").read_text(encoding="utf-8"))
            render = json.loads((project / "resource_packs/forest-addon_RP/render_controllers/forest_guardian.render_controllers.json").read_text(encoding="utf-8"))
            identifier = "forest_addon:forest_guardian"
            self.assertEqual(bp["minecraft:entity"]["description"]["identifier"], identifier)
            self.assertEqual(bp["minecraft:entity"]["components"]["minecraft:health"], {"value": 36, "max": 36})
            description = client["minecraft:client_entity"]["description"]
            self.assertEqual(description["identifier"], identifier)
            self.assertEqual(description["geometry"]["default"], "geometry.forest_addon.forest_guardian")
            self.assertEqual(geometry["minecraft:geometry"][0]["bones"][1]["parent"], "root")
            self.assertIn("controller.render.forest_addon.forest_guardian", render["render_controllers"])
            self.assertIn("NOT CREATED", result["texture_file_status"])

    def test_refuses_file_collision_without_overwriting_anything(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            existing = project / "resource_packs/forest-addon_RP/models/entity/forest_guardian.geo.json"
            existing.write_text('{"do_not_touch":true}\n', encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_entity_with_geometry", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("refusing to overwrite", result["error"]["message"])
            self.assertEqual(existing.read_text(encoding="utf-8"), '{"do_not_touch":true}\n')
            self.assertFalse((project / "behavior_packs/forest-addon_BP/entities/forest_guardian.json").exists())

    def test_refuses_duplicate_identifier_in_differently_named_file(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            existing = project / "behavior_packs/forest-addon_BP/entities/other-file.json"
            existing.write_text(json.dumps({"minecraft:entity": {"description": {"identifier": "forest_addon:forest_guardian"}}}), encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_entity_with_geometry", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("identifier already exists", result["error"]["message"])

    def test_requires_linked_bp_rp_scaffold_manifests(self):
        with tempfile.TemporaryDirectory() as td:
            project = scaffold(Path(td))
            manifest = project / "behavior_packs/forest-addon_BP/manifest.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["dependencies"] = []
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_entity_with_geometry", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("linked Behavior Pack/Resource Pack scaffold", result["error"]["message"])

    def test_rejects_project_symlink(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            real = scaffold(Path(outside))
            link = Path(td) / "forest-addon"
            link.symlink_to(real, target_is_directory=True)
            with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": td}):
                result = server.call_tool("create_addon_entity_with_geometry", valid_args())
            self.assertEqual(result["status"], "error")
            self.assertIn("non-symlink", result["error"]["message"])


class GeometryValidationTests(unittest.TestCase):
    def test_rejects_missing_parent_and_parent_cycles(self):
        args = valid_args()
        args["geometry"]["bones"][1]["parent"] = "missing"
        with self.assertRaisesRegex(ValueError, "missing parent"):
            server._validate_arguments(args)
        args = valid_args()
        args["geometry"]["bones"][0]["parent"] = "head"
        with self.assertRaisesRegex(ValueError, "cycle"):
            server._validate_arguments(args)

    def test_rejects_uv_out_of_bounds(self):
        args = valid_args()
        args["geometry"]["bones"][0]["cubes"][0]["uv"] = [60, 60]
        with self.assertRaisesRegex(ValueError, "exceeds"):
            server._validate_arguments(args)

    def test_rejects_duplicate_bones_and_nonfinite_values(self):
        args = valid_args()
        args["geometry"]["bones"][1]["name"] = "root"
        with self.assertRaisesRegex(ValueError, "duplicate bone"):
            server._validate_arguments(args)
        args = valid_args()
        args["geometry"]["bones"][0]["pivot"] = [0, float("nan"), 0]
        with self.assertRaisesRegex(ValueError, "finite number"):
            server._validate_arguments(args)

    def test_rejects_bool_as_numeric_values(self):
        args = valid_args()
        args["geometry"]["bones"][0]["pivot"] = [0, True, 0]
        with self.assertRaisesRegex(ValueError, "finite number"):
            server._validate_arguments(args)
        args = valid_args()
        args["health"] = True
        with self.assertRaisesRegex(ValueError, "health"):
            server._validate_arguments(args)

    def test_rejects_unsafe_paths_and_extra_arguments(self):
        args = valid_args()
        args["project_directory"] = "../outside"
        with self.assertRaisesRegex(ValueError, "project_directory"):
            server._validate_arguments(args)
        args = valid_args()
        args["surprise"] = True
        with self.assertRaisesRegex(ValueError, "unexpected argument"):
            server._validate_arguments(args)


if __name__ == "__main__":
    unittest.main()
