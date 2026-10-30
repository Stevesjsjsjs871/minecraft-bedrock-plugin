"""Contract and orchestration tests for the one-call UV retarget pipeline."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve()
SERVER = HERE.parents[1]
if str(SERVER) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(SERVER))

import uv_texture_retarget_mcp as target


def valid_args() -> dict:
    return {
        "project_directory": "demo-addon",
        "geometry_path": "resource_packs/demo-addon_RP/models/entity/demo.geo.json",
        "geometry_identifier": "geometry.demo",
        "reference_image_path": "resource_packs/demo-addon_RP/textures/references/character.png",
        "output_path": "resource_packs/demo-addon_RP/textures/entity/demo.png",
        "review_confirmed": True,
        "source_assignments": [{
            "selector": {"bone": "body", "cube_index": 0, "face": "north"},
            "source_rect": {"x": 0, "y": 0, "width": 8, "height": 8},
            "semantic_label": "torso_front",
            "approved": True,
        }],
    }


class RetargetContractTests(unittest.TestCase):
    def test_tool_has_one_explicit_write_operation(self):
        tool = target.TOOLS[0]
        self.assertEqual(tool["name"], "retarget_texture_to_entity")
        self.assertFalse(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["annotations"]["destructiveHint"])
        self.assertIn("review_confirmed", tool["inputSchema"]["required"])

    def test_accepts_valid_explicit_reviewed_assignment(self):
        self.assertEqual(target._validate_args(valid_args())["project_directory"], "demo-addon")

    def test_refuses_missing_human_confirmation(self):
        args = valid_args()
        args["review_confirmed"] = False
        with self.assertRaisesRegex(ValueError, "review_confirmed"):
            target._validate_args(args)

    def test_refuses_unapproved_assignment(self):
        args = valid_args()
        args["source_assignments"][0]["approved"] = False
        with self.assertRaisesRegex(ValueError, "not explicitly approved"):
            target._validate_args(args)

    def test_refuses_traversal_path(self):
        args = valid_args()
        args["reference_image_path"] = "resource_packs/demo-addon_RP/textures/../../outside.png"
        with self.assertRaisesRegex(ValueError, "parent-traversal"):
            target._validate_args(args)

    def test_refuses_geometry_from_another_project(self):
        args = valid_args()
        args["geometry_path"] = "resource_packs/other_RP/models/entity/demo.geo.json"
        with self.assertRaisesRegex(ValueError, "geometry_path"):
            target._validate_args(args)

    def test_refuses_non_array_assignments(self):
        args = valid_args()
        args["source_assignments"] = None
        with self.assertRaisesRegex(ValueError, "source_assignments must be an array"):
            target._validate_args(args)

    def test_refuses_wrong_output_folder(self):
        args = valid_args()
        args["output_path"] = "resource_packs/demo-addon_RP/textures/blocks/demo.png"
        with self.assertRaisesRegex(ValueError, "output_path"):
            target._validate_args(args)

    def test_jsonrpc_lists_tool(self):
        response = target.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(response["result"]["tools"][0]["name"], "retarget_texture_to_entity")

    def test_jsonrpc_unknown_tool_is_rejected(self):
        response = target.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "missing"}})
        self.assertEqual(response["error"]["code"], -32602)

    @patch.object(target, "_project_file")
    @patch.object(target, "_stable_file_hash", side_effect=[("geo-hash", 100), ("ref-hash", 200), ("geo-hash", 100), ("ref-hash", 200), ("geo-hash", 100), ("ref-hash", 200)])
    @patch.object(target.analyzer, "analyze_visual_reference", return_value={"status": "success", "reference": {"sha256": "ref-hash"}, "regions": [{"region_id": "r1"}], "geometric_candidates": []})
    @patch.object(target.mapping_assistant, "build_uv_mapping_plan")
    @patch.object(target.transfer, "map_reference_texture_to_uv")
    @patch.object(target.transfer, "_load_png", return_value=(16, 16, bytearray(16 * 16 * 4), b"pngbytes"))
    def test_orchestrates_plan_transfer_and_output_verification(self, load_png, transfer_call, planner, analyzer_call, hash_call, project_file):
        import hashlib
        output_hash = hashlib.sha256(b"pngbytes").hexdigest()
        planner.return_value = {
            "status": "success", "plan_status": "partial", "can_execute_transfer": True,
            "transfer_request": {"project_directory": "demo-addon"},
            "reference": {"sha256": "ref-hash"},
            "geometry": {"texture_size": [16, 16]},
            "coverage": {"complete": False, "mapped_regions": 1, "unmapped_regions": 5},
            "overlap": {"pair_count": 0}, "warnings": [],
        }
        transfer_call.return_value = {
            "status": "success", "texture": {"sha256": output_hash, "size": [16, 16]},
            "transfer": {"changed_texels": 64},
        }
        class DummyPath:
            def is_file(self): return True
            def read_bytes(self): return b"pngbytes"
            def unlink(self): pass
        project_file.return_value = DummyPath()
        result = target.retarget_texture_to_entity(valid_args())
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["verification"]["output_sha256_verified"])
        self.assertEqual(result["approval"]["semantic_labels"], ["torso_front"])
        self.assertEqual(analyzer_call.call_count, 1)
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(transfer_call.call_count, 1)
        self.assertNotIn("semantic_label", planner.call_args.args[0]["source_assignments"][0])

    @patch.object(target, "_project_file")
    @patch.object(target, "_stable_file_hash", side_effect=[("geo-hash", 100), ("ref-hash", 200)])
    @patch.object(target.analyzer, "analyze_visual_reference", return_value={"status": "success", "reference": {"sha256": "wrong-hash"}, "regions": []})
    def test_aborts_before_planning_when_reference_hash_differs(self, analyzer_call, hash_call, project_file):
        result = target.retarget_texture_to_entity(valid_args())
        self.assertEqual(result["error"]["code"], "REFERENCE_CHANGED")

    @patch.object(target, "_project_file")
    @patch.object(target, "_stable_file_hash", side_effect=[("geo-hash", 100), ("ref-hash", 200)])
    @patch.object(target.analyzer, "analyze_visual_reference", return_value={"status": "success", "reference": {"sha256": "ref-hash"}, "regions": []})
    @patch.object(target.mapping_assistant, "build_uv_mapping_plan", return_value={"status": "success", "plan_status": "needs_review", "can_execute_transfer": False, "coverage": {}, "overlap": {}, "warnings": []})
    @patch.object(target.transfer, "map_reference_texture_to_uv")
    def test_does_not_write_when_plan_is_not_ready(self, transfer_call, planner, analyzer_call, hash_call, project_file):
        result = target.retarget_texture_to_entity(valid_args())
        self.assertEqual(result["error"]["code"], "UV_PLAN_NOT_READY")
        transfer_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
