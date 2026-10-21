import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'audit_bedrock_references.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('audit_bedrock_references', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ReferenceAuditTests(unittest.TestCase):
    def test_nested_strings_are_walked(self):
        self.assertEqual(list(module.strings({'a': [{'b': 'textures/foo.png'}]})), [('$ /a/0/b'.replace('$ ', '$'), 'textures/foo.png')])
    def test_normalizes_relative_prefix_and_backslashes(self):
        self.assertEqual(module.normalize_candidate('.\\\\textures\\\\foo.png'), 'textures/foo.png')
    def test_recognizes_explicit_path_but_not_namespace_identifier(self):
        self.assertIsNotNone(module.PATH_RE.search('textures/blocks/stone.png'))
        self.assertIsNone(module.PATH_RE.search('minecraft:stone'))

if __name__ == '__main__':
    unittest.main()
