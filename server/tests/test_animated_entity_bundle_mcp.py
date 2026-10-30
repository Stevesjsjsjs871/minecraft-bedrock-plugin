from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))
import animated_entity_bundle_mcp as bundle


def make_scaffold(root: Path) -> Path:
    project = root / "forest-addon"
    bp = project / "behavior_packs" / "forest-addon_BP"
    rp = project / "resource_packs" / "forest-addon_RP"
    for path in (
        bp / "entities", rp / "entity", rp / "models" / "entity",
        rp / "render_controllers", rp / "animations", rp / "animation_controllers",
    ):
        path.mkdir(parents=True, exist_ok=True)
    return project


def base_args() -> dict:
    return {
        "project_directory": "forest-addon",
        "entity_name": "Forest Guardian",
        "entity_slug": "forest_guardian",
        "target_game_version": "1.26.50",
        "geometry": {
            "texture_width": 64,
            "texture_height": 64,
            "bones": [
                {"name": "body", "pivot": [0, 12, 0], "cubes": []},
                {"name": "head", "parent": "body", "pivot": [0, 24, 0], "cubes": []},
                {"name": "left_leg", "parent": "body", "pivot": [2, 6, 0], "cubes": []},
            ],
        },
        "animations": [
            {
                "animation_slug": "idle",
                "animation_length": 2.0,
                "loop": True,
                "bones": [{"name": "head", "rotation": [
                    {"time": 0.0, "value": [0, 0, 0]},
                    {"time": 1.0, "value": [2, 0, 0]},
                    {"time": 2.0, "value": [0, 0, 0]},
                ]}],
            },
            {
                "animation_slug": "walk",
                "animation_length": 1.0,
                "loop": True,
                "bones": [{"name": "left_leg", "rotation": [
                    {"time": 0.0, "value": [25, 0, 0]},
                    {"time": 0.5, "value": [-25, 0, 0]},
                    {"time": 1.0, "value": [25, 0, 0]},
                ]}],
            },
        ],
        "controller": {
            "controller_slug": "locomotion",
            "initial_state": "idle",
            "states": [
                {"name": "idle", "animations": ["idle"], "transitions": {"walking": "query.modified_move_speed > 0"}},
                {"name": "walking", "animations": ["walk"], "transitions": {"idle": "query.modified_move_speed == 0"}},
            ],
        },
    }


def fake_modules(*, fail_clip: str | None = None, audit_status: str = "valid", mutate_during_audit: str | None = None):
    entity = types.ModuleType("entity_authoring_mcp")
    clip = types.ModuleType("animation_clip_mcp")
    controller = types.ModuleType("animation_controller_mcp")
    audit = types.ModuleType("animation_pipeline_audit_mcp")

    def validation(*args, **kwargs):
        return args[-1] if args else kwargs

    entity._validate_arguments = validation

    def entity_call(name, args):
        project = Path(os.environ["MINECRAFT_BEDROCK_WORKSPACE"]) / args["project_directory"]
        slug = args["entity_slug"]
        rp = project / "resource_packs" / f"{args['project_directory']}_RP"
        bp = project / "behavior_packs" / f"{args['project_directory']}_BP"
        paths = {
            bp / "entities" / f"{slug}.json": {"minecraft:entity": {"description": {"identifier": "forest:forest_guardian"}}},
            rp / "entity" / f"{slug}.entity.json": {"minecraft:client_entity": {"description": {"identifier": "forest:forest_guardian", "geometry": {"default": "geometry.forest.forest_guardian"}, "animations": {}, "scripts": {"animate": []}}}},
            rp / "models" / "entity" / f"{slug}.geo.json": {"minecraft:geometry": [{"description": {"identifier": "geometry.forest.forest_guardian"}, "bones": [{"name": "body"}, {"name": "head"}, {"name": "left_leg"}]}]},
            rp / "render_controllers" / f"{slug}.render_controllers.json": {"render_controllers": {}},
        }
        for path, data in paths.items():
            path.write_text(json.dumps(data), encoding="utf-8")
        return {"status": "created", "entity_identifier": "forest:forest_guardian", "geometry_identifier": "geometry.forest.forest_guardian", "geometry_summary": {"bones": 3, "cubes": 0}, "texture_file_expected": "textures/entity/forest/forest_guardian.png", "files_created": [p.relative_to(project).as_posix() for p in paths]}
    entity.call_tool = entity_call

    clip._validate_arguments = lambda name, args: args

    def clip_call(name, args):
        project = Path(os.environ["MINECRAFT_BEDROCK_WORKSPACE"]) / args["project_directory"]
        rp = project / "resource_packs" / f"{args['project_directory']}_RP"
        if name == "validate_animation_clip":
            return {"status": "valid", "runtime_status": "NOT RUN"}
        slug = args["animation_slug"]
        if slug == fail_clip:
            return {"status": "error", "error": {"message": "synthetic clip failure"}}
        alias = args.get("animation_alias", slug)
        client_path = rp / args["client_entity_file"]
        client_data = json.loads(client_path.read_text(encoding="utf-8"))
        description = client_data["minecraft:client_entity"]["description"]
        description.setdefault("animations", {})[alias] = f"animation.forest.{slug}"
        client_path.write_text(json.dumps(client_data), encoding="utf-8")
        animation_path = rp / "animations" / f"{slug}.animation.json"
        animation_path.write_text(json.dumps({"animations": {f"animation.forest.{slug}": {"loop": args.get("loop", False)}}}), encoding="utf-8")
        return {"status": "created", "animation_alias": alias, "files_created": [animation_path.relative_to(project).as_posix()], "files_updated": [client_path.relative_to(project).as_posix()]}
    clip.call_tool = clip_call

    controller._validate_arguments = lambda name, args: args
    controller._validate_states = lambda states, initial, aliases: _fake_validate_states(states, initial, aliases)

    def controller_call(name, args):
        if name == "validate_animation_controller":
            return {"status": "valid"}
        project = Path(os.environ["MINECRAFT_BEDROCK_WORKSPACE"]) / args["project_directory"]
        rp = project / "resource_packs" / f"{args['project_directory']}_RP"
        client_path = rp / args["client_entity_file"]
        client = json.loads(client_path.read_text(encoding="utf-8"))
        description = client["minecraft:client_entity"]["description"]
        alias = args["animation_alias"]
        identifier = f"controller.animation.forest.{args['controller_slug']}"
        description.setdefault("animations", {})[alias] = identifier
        description.setdefault("scripts", {}).setdefault("animate", []).append(alias)
        client_path.write_text(json.dumps(client), encoding="utf-8")
        path = rp / "animation_controllers" / f"{args['controller_slug']}.animation_controllers.json"
        path.write_text(json.dumps({"animation_controllers": {identifier: {"initial_state": args["initial_state"], "states": {}}}}), encoding="utf-8")
        return {"status": "created", "controller_identifier": identifier, "animation_alias": alias, "files_created": [path.relative_to(project).as_posix()]}
    controller.call_tool = controller_call

    def audit_call(name, args):
        if mutate_during_audit:
            project = Path(os.environ["MINECRAFT_BEDROCK_WORKSPACE"]) / args["project_directory"]
            path = project / mutate_during_audit
            if path.is_file():
                path.write_text(path.read_text(encoding="utf-8") + "\nexternal-change", encoding="utf-8")
        return {"status": audit_status, "analysis_complete": audit_status == "valid", "inventory": {}, "severity_counts": {}, "findings": []}
    audit.call_tool = audit_call
    return entity, clip, controller, audit


def _fake_validate_states(states, initial, aliases):
    names = {state.get("name") for state in states if isinstance(state, dict)}
    if initial not in names:
        raise ValueError("initial state missing")
    for state in states:
        for alias in state.get("animations", []):
            if alias not in aliases:
                raise ValueError(f"unknown animation alias: {alias}")
        for target in state.get("transitions", {}):
            if target not in names:
                raise ValueError(f"unknown transition target: {target}")
    return {}, len(names), 0, []


class AnimatedEntityBundleTests(unittest.TestCase):
    def _run(self, root: Path, args: dict, fakes) -> dict:
        with patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(root)}), patch.dict(sys.modules, {
            "entity_authoring_mcp": fakes[0], "animation_clip_mcp": fakes[1],
            "animation_controller_mcp": fakes[2], "animation_pipeline_audit_mcp": fakes[3],
        }):
            return bundle.call_tool("create_animated_entity_bundle", args)

    def test_creates_entity_clips_controller_and_validates(self):
        with tempfile.TemporaryDirectory() as td:
            make_scaffold(Path(td))
            result = self._run(Path(td), base_args(), fake_modules())
            self.assertEqual(result["status"], "created", result)
            self.assertEqual(result["animation_count"], 2)
            self.assertEqual(result["runtime_status"], "NOT RUN")
            project = Path(td) / "forest-addon"
            self.assertTrue((project / "behavior_packs/forest-addon_BP/entities/forest_guardian.json").is_file())
            self.assertTrue((project / "resource_packs/forest-addon_RP/animations/idle.animation.json").is_file())
            self.assertTrue((project / "resource_packs/forest-addon_RP/animations/walk.animation.json").is_file())
            self.assertTrue((project / "resource_packs/forest-addon_RP/animation_controllers/locomotion.animation_controllers.json").is_file())

    def test_rolls_back_all_created_files_when_later_clip_fails(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_scaffold(Path(td))
            result = self._run(Path(td), base_args(), fake_modules(fail_clip="walk"))
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["rollback"]["conflicts"], [])
            self.assertFalse((project / "behavior_packs/forest-addon_BP/entities/forest_guardian.json").exists())
            self.assertFalse((project / "resource_packs/forest-addon_RP/animations/idle.animation.json").exists())

    def test_rolls_back_when_end_to_end_audit_is_not_clean(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_scaffold(Path(td))
            result = self._run(Path(td), base_args(), fake_modules(audit_status="issues_found"))
            self.assertEqual(result["status"], "error")
            self.assertFalse((project / "resource_packs/forest-addon_RP/entity/forest_guardian.entity.json").exists())

    def test_rollback_preserves_file_changed_concurrently(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_scaffold(Path(td))
            changed = "resource_packs/forest-addon_RP/animations/walk.animation.json"
            result = self._run(Path(td), base_args(), fake_modules(audit_status="issues_found", mutate_during_audit=changed))
            self.assertEqual(result["status"], "error")
            self.assertIn(changed, result["rollback"]["conflicts"])
            self.assertTrue((project / changed).is_file())
            self.assertFalse((project / "behavior_packs/forest-addon_BP/entities/forest_guardian.json").exists())

    def test_rejects_animation_bone_missing_from_geometry_before_writes(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_scaffold(Path(td))
            args = base_args()
            args["animations"][0]["bones"][0]["name"] = "tail"
            result = self._run(Path(td), args, fake_modules())
            self.assertEqual(result["status"], "error")
            self.assertIn("absent from", result["error"]["message"])
            self.assertFalse((project / "behavior_packs/forest-addon_BP/entities/forest_guardian.json").exists())

    def test_rejects_animation_alias_collision_before_writes(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_scaffold(Path(td))
            args = base_args()
            args["animations"][1]["animation_alias"] = "idle"
            result = self._run(Path(td), args, fake_modules())
            self.assertEqual(result["status"], "error")
            self.assertIn("duplicate animation_alias", result["error"]["message"])
            self.assertFalse((project / "behavior_packs/forest-addon_BP/entities/forest_guardian.json").exists())

    def test_rejects_controller_state_reference_to_unknown_alias(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_scaffold(Path(td))
            args = base_args()
            args["controller"]["states"][0]["animations"] = ["walk_typo"]
            result = self._run(Path(td), args, fake_modules())
            self.assertEqual(result["status"], "error")
            self.assertIn("unknown animation alias", result["error"]["message"])
            self.assertFalse((project / "behavior_packs/forest-addon_BP/entities/forest_guardian.json").exists())

    def test_refuses_existing_entity_output_without_overwriting(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_scaffold(Path(td))
            target = project / "behavior_packs/forest-addon_BP/entities/forest_guardian.json"
            target.write_text('{"untouched":true}', encoding="utf-8")
            result = self._run(Path(td), base_args(), fake_modules())
            self.assertEqual(result["status"], "error")
            self.assertEqual(json.loads(target.read_text()), {"untouched": True})

    def test_marks_unused_animation_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            make_scaffold(Path(td))
            args = base_args()
            args["controller"]["states"][1]["animations"] = []
            result = self._run(Path(td), args, fake_modules())
            self.assertEqual(result["status"], "created", result)
            self.assertEqual(result["unused_animation_aliases"], ["walk"])

    def test_tool_schema_and_mcp_handshake(self):
        schema = bundle.TOOLS[0]["inputSchema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], ["project_directory", "entity_name", "entity_slug", "target_game_version", "geometry", "animations", "controller"])
        init = bundle.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "minecraft-bedrock-animated-entity-authoring")
        tools = bundle.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(tools["result"]["tools"][0]["name"], "create_animated_entity_bundle")


if __name__ == "__main__":
    unittest.main()
