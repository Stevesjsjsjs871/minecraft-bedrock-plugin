from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import struct
import zlib
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve()
SERVER = HERE.parents[1]
sys.path.insert(0, str(SERVER))
validation = types.ModuleType("png_validation")
class PngValidationError(ValueError):
    pass
def validate_png_bytes(payload, *, max_bytes=16 * 1024 * 1024, max_dimension=4096, max_pixels=16_777_216):
    if not isinstance(payload, bytes) or len(payload) < 45 or len(payload) > max_bytes or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PngValidationError('invalid PNG signature or size')
    offset = 8
    chunks = []
    while offset + 12 <= len(payload):
        length = struct.unpack('>I', payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        end = offset + length + 12
        if end > len(payload):
            raise PngValidationError('truncated PNG chunk')
        data = payload[offset + 8:offset + 8 + length]
        crc = struct.unpack('>I', payload[offset + 8 + length:end])[0]
        if zlib.crc32(kind + data) & 0xffffffff != crc:
            raise PngValidationError('PNG CRC mismatch')
        chunks.append((kind, data))
        offset = end
        if kind == b'IEND':
            break
    if offset != len(payload) or not chunks or chunks[0][0] != b'IHDR' or chunks[-1][0] != b'IEND':
        raise PngValidationError('invalid PNG chunk order or trailing data')
    width, height, depth, ctype, comp, filt, interlace = struct.unpack('>IIBBBBB', chunks[0][1])
    if not (1 <= width <= max_dimension and 1 <= height <= max_dimension and width * height <= max_pixels):
        raise PngValidationError('PNG dimensions exceed test limits')
    if depth != 8 or ctype not in {0, 2, 3, 4, 6} or comp != 0 or filt != 0 or interlace != 0:
        raise PngValidationError('PNG format is outside test-shim scope')
    if not any(kind == b'IDAT' for kind, _ in chunks):
        raise PngValidationError('PNG IDAT missing')
    return width, height
validation.PngValidationError = PngValidationError
validation.validate_png_bytes = validate_png_bytes
with patch.dict(sys.modules, {"png_validation": validation}):
    import texture_painting_mcp as painter
    import uv_mapping_assistant_mcp as assistant


class UvMappingAssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        os.environ['MINECRAFT_BEDROCK_WORKSPACE'] = str(self.workspace)
        self.project = self.workspace / 'forest-addon'
        self.rp = self.project / 'resource_packs' / 'forest-addon_RP'
        self.geo_dir = self.rp / 'models' / 'entity'
        self.ref_dir = self.rp / 'textures' / 'references'
        self.tex_dir = self.rp / 'textures' / 'entity'
        self.geo_dir.mkdir(parents=True)
        self.ref_dir.mkdir(parents=True)
        self.tex_dir.mkdir(parents=True)
        (self.rp / 'manifest.json').write_text('{"header":{},"modules":[]}', encoding='utf-8')
        self.geometry_rel = 'resource_packs/forest-addon_RP/models/entity/guardian.geo.json'
        self.reference_rel = 'resource_packs/forest-addon_RP/textures/references/sheet.png'
        self.output_rel = 'resource_packs/forest-addon_RP/textures/entity/guardian_out.png'
        (self.project / self.geometry_rel).write_text(json.dumps(self._classic_geometry()), encoding='utf-8')
        png = painter._encode_png(64, 64, bytearray(bytes((40, 80, 120, 255)) * (64 * 64)))
        (self.project / self.reference_rel).write_bytes(png)
        self.base_rel = 'resource_packs/forest-addon_RP/textures/entity/base.png'
        (self.project / self.base_rel).write_bytes(png)

    @staticmethod
    def _classic_geometry():
        return {
            'format_version': '1.12.0',
            'minecraft:geometry': [{
                'description': {'identifier': 'geometry.guardian', 'texture_width': 64, 'texture_height': 64},
                'bones': [
                    {'name': 'body', 'pivot': [0, 12, 0], 'cubes': [
                        {'origin': [-8, 0, -4], 'size': [16, 24, 8], 'uv': [0, 0]},
                    ]},
                    {'name': 'head', 'parent': 'body', 'pivot': [0, 26, 0], 'cubes': [
                        {'origin': [-6, 24, -6], 'size': [12, 12, 12], 'uv': [0, 40]},
                    ]},
                ],
            }],
        }

    def _args(self, **overrides):
        args = {
            'project_directory': 'forest-addon',
            'geometry_path': self.geometry_rel,
            'geometry_identifier': 'geometry.guardian',
            'reference_image_path': self.reference_rel,
            'output_path': self.output_rel,
            'source_assignments': [{
                'selector': {'bone': 'body', 'cube_index': 0, 'face': 'north'},
                'source_rect': {'x': 0, 'y': 0, 'width': 16, 'height': 24},
            }],
        }
        args.update(overrides)
        return args

    def _run(self, args):
        response = assistant.handle_message({
            'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
            'params': {'name': 'build_uv_mapping_plan', 'arguments': args},
        })
        return response['result']['structuredContent']

    def test_exact_selector_returns_partial_plan(self):
        result = self._run(self._args())
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['plan_status'], 'partial')
        self.assertTrue(result['can_execute_transfer'])
        self.assertEqual(result['coverage']['mapped_regions'], 1)
        self.assertEqual(result['coverage']['unmapped_regions'], 11)
        self.assertEqual(result['transfer_request']['mappings'][0]['selector'], {'bone': 'body', 'cube_index': 0, 'face': 'north'})

    def test_bone_selector_expands_to_all_six_faces(self):
        args = self._args(source_assignments=[{
            'selector': {'bone': 'body'}, 'source_rect': {'x': 0, 'y': 0, 'width': 16, 'height': 24}
        }])
        result = self._run(args)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['coverage']['mapped_regions'], 6)
        self.assertEqual(len(result['transfer_request']['mappings']), 6)
        self.assertEqual({m['selector']['face'] for m in result['transfer_request']['mappings']},
                         {'north', 'south', 'east', 'west', 'up', 'down'})

    def test_cube_selector_expands_one_cube(self):
        result = self._run(self._args(source_assignments=[{
            'selector': {'bone': 'head', 'cube_index': 0}, 'source_rect': {'x': 16, 'y': 0, 'width': 12, 'height': 12}
        }]))
        self.assertEqual(result['coverage']['mapped_regions'], 6)

    def test_face_selector_across_bone_expands_multiple_cubes(self):
        result = self._run(self._args(source_assignments=[{
            'selector': {'face': 'north'}, 'source_rect': {'x': 0, 'y': 0, 'width': 16, 'height': 24}
        }]))
        self.assertEqual(result['coverage']['mapped_regions'], 2)

    def test_complete_coverage_becomes_ready(self):
        assignments = []
        for region in assistant.uv._extract_regions(self._classic_geometry()['minecraft:geometry'][0], 'geometry.guardian')[0]:
            assignments.append({'selector': {'bone': region['bone'], 'cube_index': region['cube_index'], 'face': region['face']},
                                 'source_rect': {'x': 0, 'y': 0, 'width': 8, 'height': 8}})
        result = self._run(self._args(source_assignments=assignments, require_full_coverage=True))
        self.assertEqual(result['plan_status'], 'ready')
        self.assertTrue(result['coverage']['complete'])
        self.assertTrue(result['can_execute_transfer'])

    def test_missing_coverage_with_required_full_coverage_needs_review(self):
        result = self._run(self._args(require_full_coverage=True))
        self.assertEqual(result['plan_status'], 'needs_review')
        self.assertFalse(result['can_execute_transfer'])
        self.assertIsNone(result['transfer_request'])
        self.assertIsNotNone(result['draft_transfer_request'])

    def test_missing_coverage_can_be_intentionally_partial(self):
        result = self._run(self._args())
        self.assertEqual(result['plan_status'], 'partial')
        self.assertTrue(result['can_execute_transfer'])
        self.assertTrue(any(w['code'] == 'INCOMPLETE_UV_COVERAGE' for w in result['warnings']))

    def test_out_of_bounds_source_rect_rejected(self):
        result = self._run(self._args(source_assignments=[{
            'selector': {'face': 'north'}, 'source_rect': {'x': 60, 'y': 0, 'width': 8, 'height': 8}
        }]))
        self.assertEqual(result['error']['code'], 'SOURCE_RECT_OUT_OF_BOUNDS')

    def test_unmatched_selector_rejected(self):
        result = self._run(self._args(source_assignments=[{
            'selector': {'bone': 'missing'}, 'source_rect': {'x': 0, 'y': 0, 'width': 8, 'height': 8}
        }]))
        self.assertEqual(result['error']['code'], 'SELECTOR_MATCHED_NO_UV')

    def test_duplicate_assignments_rejected_by_default(self):
        assignments = [
            {'selector': {'bone': 'body'}, 'source_rect': {'x': 0, 'y': 0, 'width': 8, 'height': 8}},
            {'selector': {'bone': 'body', 'cube_index': 0, 'face': 'north'}, 'source_rect': {'x': 8, 'y': 0, 'width': 8, 'height': 8}},
        ]
        result = self._run(self._args(source_assignments=assignments))
        self.assertEqual(result['error']['code'], 'DUPLICATE_TARGET_ASSIGNMENT')

    def test_layered_assignment_needs_shared_overlap_switch(self):
        assignments = [
            {'selector': {'bone': 'body', 'cube_index': 0, 'face': 'north'}, 'source_rect': {'x': 0, 'y': 0, 'width': 8, 'height': 8}},
            {'selector': {'bone': 'body', 'cube_index': 0, 'face': 'north'}, 'source_rect': {'x': 8, 'y': 0, 'width': 8, 'height': 8}},
        ]
        result = self._run(self._args(source_assignments=assignments, allow_layered_assignments=True))
        self.assertEqual(result['error']['code'], 'UV_OVERLAP_ACCEPTANCE_REQUIRED')

    def test_layered_assignment_can_be_explicitly_accepted(self):
        assignments = [
            {'selector': {'bone': 'body', 'cube_index': 0, 'face': 'north'}, 'source_rect': {'x': 0, 'y': 0, 'width': 8, 'height': 8}},
            {'selector': {'bone': 'body', 'cube_index': 0, 'face': 'north'}, 'source_rect': {'x': 8, 'y': 0, 'width': 8, 'height': 8}},
        ]
        result = self._run(self._args(source_assignments=assignments, allow_layered_assignments=True, allow_uv_overlap=True))
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['transfer_request']['mappings']), 2)
        self.assertTrue(result['transfer_request']['allow_uv_overlap'])

    def test_geometry_overlaps_block_transfer_without_explicit_acceptance(self):
        geometry = self._classic_geometry()
        geometry['minecraft:geometry'][0]['bones'][1]['cubes'][0]['uv'] = [0, 0]
        (self.project / self.geometry_rel).write_text(json.dumps(geometry), encoding='utf-8')
        result = self._run(self._args())
        self.assertEqual(result['plan_status'], 'needs_review')
        self.assertFalse(result['can_execute_transfer'])
        self.assertIsNone(result['transfer_request'])
        self.assertGreater(result['overlap']['pair_count'], 0)

    def test_geometry_overlaps_can_be_accepted(self):
        geometry = self._classic_geometry()
        geometry['minecraft:geometry'][0]['bones'][1]['cubes'][0]['uv'] = [0, 0]
        (self.project / self.geometry_rel).write_text(json.dumps(geometry), encoding='utf-8')
        result = self._run(self._args(allow_uv_overlap=True))
        self.assertTrue(result['can_execute_transfer'])
        self.assertTrue(result['overlap']['accepted'])

    def test_base_texture_dimensions_validated(self):
        result = self._run(self._args(base_texture_path=self.base_rel))
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['base_texture']['size'], [64, 64])

    def test_base_texture_dimension_mismatch_rejected(self):
        png = painter._encode_png(16, 16, bytearray(bytes((0, 0, 0, 255)) * (16 * 16)))
        (self.project / self.base_rel).write_bytes(png)
        result = self._run(self._args(base_texture_path=self.base_rel))
        self.assertEqual(result['error']['code'], 'BASE_TEXTURE_DIMENSION_MISMATCH')

    def test_output_path_collision_rejected(self):
        (self.project / self.output_rel).write_bytes(b'already exists')
        result = self._run(self._args())
        self.assertEqual(result['status'], 'error')
        self.assertIn('already exists', result['error']['message'])

    def test_missing_output_parent_rejected(self):
        result = self._run(self._args(output_path='resource_packs/forest-addon_RP/textures/entity/newfolder/file.png'))
        self.assertEqual(result['status'], 'error')
        self.assertIn('output parent directory does not exist', result['error']['message'])

    def test_ambiguous_duplicate_geometry_identifier_rejected(self):
        geometry = self._classic_geometry()
        geometry['minecraft:geometry'].append(geometry['minecraft:geometry'][0])
        (self.project / self.geometry_rel).write_text(json.dumps(geometry), encoding='utf-8')
        result = self._run(self._args())
        self.assertEqual(result['status'], 'error')
        self.assertIn('exactly one geometry', result['error']['message'])

    def test_wrong_geometry_identifier_rejected(self):
        result = self._run(self._args(geometry_identifier='geometry.wrong'))
        self.assertEqual(result['status'], 'error')
        self.assertIn('exactly one geometry', result['error']['message'])

    def test_path_traversal_rejected(self):
        result = self._run(self._args(geometry_path='../outside.json'))
        self.assertEqual(result['status'], 'error')

    def test_symlinked_source_rejected(self):
        alias = self.rp / 'textures' / 'references' / 'alias.png'
        alias.symlink_to(self.project / self.reference_rel)
        result = self._run(self._args(reference_image_path='resource_packs/forest-addon_RP/textures/references/alias.png'))
        self.assertEqual(result['status'], 'error')
        self.assertIn('symlink', result['error']['message'])

    def test_duplicate_json_keys_rejected(self):
        (self.project / self.geometry_rel).write_text('{"minecraft:geometry":[],"minecraft:geometry":[]}', encoding='utf-8')
        result = self._run(self._args())
        self.assertEqual(result['status'], 'error')
        self.assertIn('invalid', result['error']['message'])

    def test_invalid_source_assignment_type_rejected(self):
        result = self._run(self._args(source_assignments=[{'selector': {'face': []}, 'source_rect': {'x': 0, 'y': 0, 'width': 1, 'height': 1}}]))
        self.assertEqual(result['status'], 'error')

    def test_invalid_sampling_rejected(self):
        result = self._run(self._args(source_assignments=[{
            'selector': {'face': 'north'}, 'source_rect': {'x': 0, 'y': 0, 'width': 8, 'height': 8}, 'sampling': 'lanczos'
        }]))
        self.assertEqual(result['status'], 'error')

    def test_transfer_request_matches_downstream_schema(self):
        result = self._run(self._args())
        validated = assistant.transfer._validate_args(result['transfer_request'])
        self.assertEqual(validated['project_directory'], 'forest-addon')
        self.assertEqual(validated['mappings'][0]['selector']['face'], 'north')

    def test_per_face_uv_face_regions_are_expanded(self):
        geometry = {
            'minecraft:geometry': [{
                'description': {'identifier': 'geometry.guardian', 'texture_width': 64, 'texture_height': 64},
                'bones': [{'name': 'head', 'cubes': [{
                    'origin': [-2, 0, -2], 'size': [4, 6, 4],
                    'uv': {
                        'north': {'uv': [0, 0], 'uv_size': [4, 6], 'uv_rotation': 90},
                        'south': {'uv': [4, 0], 'uv_size': [-4, 6]},
                    },
                }]}],
            }]
        }
        (self.project / self.geometry_rel).write_text(json.dumps(geometry), encoding='utf-8')
        result = self._run(self._args(source_assignments=[{
            'selector': {'bone': 'head'}, 'source_rect': {'x': 0, 'y': 0, 'width': 4, 'height': 6}
        }]))
        self.assertEqual(result['coverage']['mapped_regions'], 2)
        north = next(r for r in result['inventory'] if r['selector']['face'] == 'north')
        self.assertEqual(north['uv_rotation'], 90)
        self.assertEqual(north['uv_size'], [6.0, 4.0])

    def test_json_schema_is_valid(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('jsonschema is unavailable')
        jsonschema.Draft202012Validator.check_schema(assistant.TOOLS[0]['inputSchema'])

    def test_mcp_initialize_and_tool_list(self):
        init = assistant.handle_message({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05'}})
        self.assertEqual(init['result']['serverInfo']['name'], 'minecraft-bedrock-uv-mapping-assistant')
        listing = assistant.handle_message({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})
        self.assertEqual(listing['result']['tools'][0]['name'], 'build_uv_mapping_plan')


if __name__ == '__main__':
    unittest.main()
