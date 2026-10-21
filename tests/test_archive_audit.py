import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit_bedrock_archive.py"
spec = importlib.util.spec_from_file_location("audit_bedrock_archive", SCRIPT)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


class JsonDiagnosticTests(unittest.TestCase):
    def test_strict_json(self):
        mode, data, error = auditor.parse_json_candidates(b'{"a": 1}')
        self.assertEqual(mode, "strict_json")
        self.assertEqual(data, {"a": 1})
        self.assertIsNone(error)

    def test_utf8_bom(self):
        mode, data, _ = auditor.parse_json_candidates(b'\xef\xbb\xbf{"a": 1}')
        self.assertEqual(mode, "strict_json")
        self.assertEqual(data, {"a": 1})

    def test_comment_markers_inside_strings_are_preserved(self):
        source = '{"url":"https://example.invalid/a/*b*/", "text":"comma,] // not a comment"}'
        cleaned = auditor.strip_json_comments(source)
        self.assertEqual(json.loads(cleaned), {"url": "https://example.invalid/a/*b*/", "text": "comma,] // not a comment"})

    def test_line_and_block_comments_diagnostic(self):
        source = b'{\n // comment\n "a": 1 /* block */\n}'
        mode, data, _ = auditor.parse_json_candidates(source)
        self.assertEqual(mode, "json_with_comments")
        self.assertEqual(data, {"a": 1})

    def test_trailing_comma_is_a_separate_recovery_mode(self):
        source = b'{"a": [1, 2,],}'
        mode, data, _ = auditor.parse_json_candidates(source)
        self.assertEqual(mode, "json_comments_trailing_commas")
        self.assertEqual(data, {"a": [1, 2]})

    def test_invalid_json_remains_invalid(self):
        mode, data, error = auditor.parse_json_candidates(b'{"a": }')
        self.assertEqual(mode, "invalid_or_nonstandard")
        self.assertIsNone(data)
        self.assertTrue(error)


if __name__ == "__main__":
    unittest.main()
