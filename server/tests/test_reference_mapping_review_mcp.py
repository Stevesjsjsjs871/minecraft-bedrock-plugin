from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import types
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

# The current release supplies the full PNG validator. This overlay-only test
# harness injects a bounded structural shim before importing the texture stack.
validation = sys.modules.get("png_validation") or types.ModuleType("png_validation")
if not hasattr(validation, "PngValidationError"):
    class PngValidationError(ValueError):
        pass
    validation.PngValidationError = PngValidationError
if not hasattr(validation, "validate_png_bytes"):
    def validate_png_bytes(payload, *, max_bytes=16 * 1024 * 1024, max_dimension=4096, max_pixels=16_777_216):
        if not isinstance(payload, bytes) or len(payload) < 45 or len(payload) > max_bytes or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise validation.PngValidationError("invalid PNG signature or size")
        offset = 8
        chunks = []
        while offset + 12 <= len(payload):
            length = struct.unpack(">I", payload[offset:offset + 4])[0]
            kind = payload[offset + 4:offset + 8]
            end = offset + length + 12
            if end > len(payload):
                raise validation.PngValidationError("truncated PNG")
            data = payload[offset + 8:offset + 8 + length]
            crc = struct.unpack(">I", payload[offset + 8 + length:end])[0]
            if zlib.crc32(kind + data) & 0xffffffff != crc:
                raise validation.PngValidationError("PNG CRC mismatch")
            chunks.append((kind, data))
            offset = end
            if kind == b"IEND":
                break
        if offset != len(payload) or not chunks or chunks[0][0] != b"IHDR" or chunks[-1][0] != b"IEND":
            raise validation.PngValidationError("invalid PNG chunk order")
        width, height, depth, ctype, comp, filt, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
        if not (1 <= width <= max_dimension and 1 <= height <= max_dimension and width * height <= max_pixels):
            raise validation.PngValidationError("PNG dimensions exceed limits")
        if depth != 8 or ctype not in {0, 2, 3, 4, 6} or comp != 0 or filt != 0 or interlace != 0:
            raise validation.PngValidationError("unsupported PNG format in test shim")
        if not any(kind == b"IDAT" for kind, _ in chunks):
            raise validation.PngValidationError("PNG IDAT missing")
        return width, height
    validation.validate_png_bytes = validate_png_bytes
sys.modules["png_validation"] = validation

HERE = Path(__file__).resolve()
SERVER = HERE.parents[1]
sys.path.insert(0, str(SERVER))

import texture_painting_mcp as painter
import visual_reference_analyzer_mcp as analyzer
import reference_mapping_review_mcp as review
import geometry_uv_template_mcp as uv


class ReferenceMappingReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        self.envpatch = patch.dict(os.environ, {"MINECRAFT_BEDROCK_WORKSPACE": str(self.workspace)})
        self.envpatch.start()
        self.addCleanup(self.envpatch.stop)
        self.project = self.workspace / "forest-addon"
        self.rp = self.project / "resource_packs" / "forest-addon_RP"
        self.geo_dir = self.rp / "models" / "entity"
        self.ref_dir = self.rp / "textures" / "references"
        self.tex_dir = self.rp / "textures" / "entity"
        self.geo_dir.mkdir(parents=True)
        self.ref_dir.mkdir(parents=True)
        self.tex_dir.mkdir(parents=True)
        (self.rp / "manifest.json").write_text(json.dumps({"header": {}, "modules": []}), encoding="utf-8")
        self.geometry_path = "resource_packs/forest-addon_RP/models/entity/guardian.geo.json"
        self.reference_path = "resource_packs/forest-addon_RP/textures/references/sheet.png"
        self.output_path = "resource_packs/forest-addon_RP/textures/entity/guardian_reviewed.png"
        self.geometry = {
            "format_version": "1.12.0",
            "minecraft:geometry": [{
                "description": {"identifier": "geometry.guardian", "texture_width": 16, "texture_height": 16},
                "bones": [{"name": "body", "pivot": [0, 0, 0], "cubes": [
                    {"origin": [-2, 0, -2], "size": [4, 4, 4], "uv": [0, 0]}
                ]}],
            }],
        }
        (self.project / self.geometry_path).write_text(json.dumps(self.geometry), encoding="utf-8")
        self.write_reference()
        self.analysis = analyzer.analyze_visual_reference({
            "project_directory": "forest-addon", "reference_image_path": self.reference_path,
            "segmentation_mode": "color_components", "color_bucket_size": 16, "min_region_area": 2,
            "geometry_path": self.geometry_path, "geometry_identifier": "geometry.guardian",
        })
        self.source_a = self.analysis["regions"][0]["region_id"]
        self.source_b = self.analysis["regions"][1]["region_id"]

    def write_reference(self, changed=False):
        rgba = bytearray(8 * 8 * 4)
        for y in range(1, 3):
            for x in range(1, 3):
                i = (y * 8 + x) * 4
                rgba[i:i + 4] = bytes((240, 20, 20, 255))
        for y in range(5, 7):
            for x in range(5, 7):
                i = (y * 8 + x) * 4
                rgba[i:i + 4] = bytes((20, 40, 240, 255))
        if changed:
            rgba[(0 * 8 + 0) * 4:(0 * 8 + 0) * 4 + 4] = bytes((1, 2, 3, 255))
        (self.project / self.reference_path).write_bytes(painter._encode_png(8, 8, rgba))

    def decision(self, source_id=None, *, target=None, choice="approve", **extra):
        entry = {
            "source_region_id": source_id or self.source_a,
            "target": target or {"bone": "body", "cube_index": 0, "face": "north"},
            "decision": choice,
            "semantic_label": "front body",
        }
        entry.update(extra)
        return entry

    def args(self, decisions=None, **extra):
        value = {
            "project_directory": "forest-addon",
            "geometry_path": self.geometry_path,
            "geometry_identifier": "geometry.guardian",
            "output_path": self.output_path,
            "analysis_result": self.analysis,
            "review_decisions": decisions or [self.decision()],
        }
        value.update(extra)
        return value

    def run_review(self, args=None):
        response = review.handle_message({
            "jsonrpc": "2.0", "id": 91, "method": "tools/call",
            "params": {"name": "review_reference_mapping", "arguments": args or self.args()},
        })
        return response["result"]["structuredContent"]

    def test_approved_decision_returns_transfer_request_and_manifest_hash(self):
        result = self.run_review()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["summary"]["approved"], 1)
        self.assertIsNotNone(result["transfer_request"])
        self.assertEqual(result["transfer_request"]["mappings"][0]["selector"],
                         {"bone": "body", "cube_index": 0, "face": "north"})
        self.assertEqual(len(result["review_manifest_sha256"]), 64)

    def test_semantic_label_is_preserved(self):
        result = self.run_review()
        self.assertEqual(result["decisions"][0]["semantic_label"], "front body")

    def test_review_hash_binds_transfer_transform_options(self):
        first = self.run_review()
        rotated = self.run_review(self.args(decisions=[self.decision(rotation=90)]))
        self.assertNotEqual(first["review_manifest_sha256"], rotated["review_manifest_sha256"])
        self.assertEqual(rotated["decisions"][0]["rotation"], 90)

    def test_review_hash_binds_exact_geometry_file_bytes(self):
        first = self.run_review()
        geometry = json.loads((self.project / self.geometry_path).read_text())
        geometry["minecraft:geometry"][0]["bones"][0]["cubes"][0]["origin"][0] = -3
        (self.project / self.geometry_path).write_text(json.dumps(geometry), encoding="utf-8")
        second = self.run_review()
        self.assertNotEqual(first["geometry"]["sha256"], second["geometry"]["sha256"])
        self.assertNotEqual(first["review_manifest_sha256"], second["review_manifest_sha256"])

    def test_reference_hash_change_rejected(self):
        self.write_reference(changed=True)
        result = self.run_review()
        self.assertEqual(result["error"]["code"], "REFERENCE_HASH_MISMATCH")

    def test_reference_path_outside_project_rejected(self):
        analysis = json.loads(json.dumps(self.analysis))
        analysis["reference"]["path"] = "../outside.png"
        result = self.run_review(self.args(analysis_result=analysis))
        self.assertEqual(result["error"]["code"], "INVALID_OR_UNSAFE_INPUT")

    def test_reference_dimension_mismatch_rejected(self):
        analysis = json.loads(json.dumps(self.analysis))
        analysis["reference"]["width"] = 999
        result = self.run_review(self.args(analysis_result=analysis))
        self.assertEqual(result["error"]["code"], "REFERENCE_DIMENSION_MISMATCH")

    def test_failed_analysis_result_rejected(self):
        result = self.run_review(self.args(analysis_result={"status": "error"}))
        self.assertEqual(result["status"], "error")

    def test_unknown_source_region_rejected(self):
        result = self.run_review(self.args(decisions=[self.decision("region_missing")]))
        self.assertEqual(result["error"]["code"], "REVIEW_DECISIONS_INVALID")

    def test_unmatched_target_face_rejected(self):
        result = self.run_review(self.args(decisions=[self.decision(target={"bone": "missing", "cube_index": 0, "face": "north"})]))
        self.assertEqual(result["error"]["code"], "REVIEW_DECISIONS_INVALID")

    def test_rejected_decision_does_not_enter_transfer_request(self):
        result = self.run_review(self.args(decisions=[self.decision(choice="reject")]))
        self.assertEqual(result["review_status"], "review_only")
        self.assertEqual(result["summary"]["rejected"], 1)
        self.assertIsNone(result["transfer_request"])

    def test_pending_decision_blocks_transfer_request(self):
        result = self.run_review(self.args(decisions=[self.decision(choice="needs_review")]))
        self.assertEqual(result["review_status"], "needs_review")
        self.assertIsNone(result["transfer_request"])

    def test_pending_decision_hides_otherwise_ready_transfer_request(self):
        decisions = [self.decision(), self.decision(self.source_b,
            target={"bone": "body", "cube_index": 0, "face": "south"}, choice="needs_review")]
        result = self.run_review(self.args(decisions=decisions))
        self.assertIsNone(result["transfer_request"])
        self.assertTrue(result["summary"]["plan_ready"])

    def test_duplicate_target_assignments_rejected_by_default(self):
        decisions = [self.decision(), self.decision(self.source_b)]
        result = self.run_review(self.args(decisions=decisions))
        self.assertEqual(result["error"]["code"], "DUPLICATE_REVIEW_TARGET")

    def test_layered_assignment_requires_overlap_opt_in(self):
        result = self.run_review(self.args(
            decisions=[self.decision(), self.decision(self.source_b)],
            allow_layered_assignments=True,
        ))
        self.assertEqual(result["status"], "error")
        self.assertIn("requires allow_uv_overlap", result["error"]["message"])

    def test_layered_assignment_allowed_when_explicit(self):
        result = self.run_review(self.args(
            decisions=[self.decision(), self.decision(self.source_b)],
            allow_layered_assignments=True, allow_uv_overlap=True,
        ))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["duplicate_targets"], 1)
        self.assertEqual(len(result["transfer_request"]["mappings"]), 2)

    def test_require_full_coverage_blocks_partial_plan(self):
        result = self.run_review(self.args(require_full_coverage=True))
        self.assertEqual(result["review_status"], "needs_review")
        self.assertIsNone(result["transfer_request"])
        self.assertEqual(result["mapping_plan"]["plan_status"], "needs_review")

    def test_partial_coverage_can_be_approved_when_not_required(self):
        result = self.run_review()
        self.assertEqual(result["mapping_plan"]["plan_status"], "partial")
        self.assertIsNotNone(result["transfer_request"])

    def test_geometry_identifier_must_be_unique(self):
        geometry = json.loads((self.project / self.geometry_path).read_text())
        geometry["minecraft:geometry"].append(geometry["minecraft:geometry"][0])
        (self.project / self.geometry_path).write_text(json.dumps(geometry))
        result = self.run_review()
        self.assertEqual(result["error"]["code"], "GEOMETRY_READ_FAILED")

    def test_duplicate_bone_selector_is_not_unique(self):
        geometry = json.loads((self.project / self.geometry_path).read_text())
        geometry["minecraft:geometry"][0]["bones"].append(geometry["minecraft:geometry"][0]["bones"][0])
        (self.project / self.geometry_path).write_text(json.dumps(geometry))
        result = self.run_review()
        self.assertEqual(result["error"]["code"], "REVIEW_DECISIONS_INVALID")

    def test_source_rect_tampering_rejected(self):
        analysis = json.loads(json.dumps(self.analysis))
        analysis["regions"][0]["source_rect"] = {"x": 7, "y": 7, "width": 4, "height": 4}
        result = self.run_review(self.args(analysis_result=analysis))
        self.assertEqual(result["error"]["code"], "INVALID_ANALYSIS_REGION")

    def test_duplicate_region_ids_rejected(self):
        analysis = json.loads(json.dumps(self.analysis))
        analysis["regions"][1]["region_id"] = analysis["regions"][0]["region_id"]
        result = self.run_review(self.args(analysis_result=analysis))
        self.assertEqual(result["error"]["code"], "INVALID_ANALYSIS_REGION")

    def test_bad_decision_type_is_validation_error_not_internal_error(self):
        result = self.run_review(self.args(decisions=[self.decision(choice=[])]))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "INVALID_OR_UNSAFE_INPUT")

    def test_invalid_sampling_rejected(self):
        result = self.run_review(self.args(decisions=[self.decision(sampling="magic")]))
        self.assertEqual(result["status"], "error")

    def test_invalid_path_traversal_rejected(self):
        result = self.run_review(self.args(geometry_path="resource_packs/forest-addon_RP/models/entity/../bad.geo.json"))
        self.assertEqual(result["status"], "error")

    def test_background_color_and_base_texture_mutually_exclusive(self):
        base = "resource_packs/forest-addon_RP/textures/entity/base.png"
        (self.project / base).write_bytes(painter._encode_png(16, 16, bytearray(bytes((0, 0, 0, 255)) * 256)))
        result = self.run_review(self.args(base_texture_path=base, background_color="#000000"))
        self.assertEqual(result["status"], "error")

    def test_mcp_initialize_and_tools_list(self):
        init = review.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        listing = review.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(init["result"]["serverInfo"]["name"], "minecraft-bedrock-reference-mapping-review")
        self.assertEqual(listing["result"]["tools"][0]["name"], "review_reference_mapping")

    def test_mcp_tools_call_returns_structured_content(self):
        response = review.handle_message({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "review_reference_mapping", "arguments": self.args()},
        })
        self.assertEqual(response["result"]["structuredContent"]["review_status"], "approved")


if __name__ == "__main__":
    unittest.main()
