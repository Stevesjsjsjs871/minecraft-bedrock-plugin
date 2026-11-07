import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
SCRIPTS=ROOT/'skills'/'automated-validation'/'scripts'
if str(SCRIPTS) not in sys.path: sys.path.insert(0,str(SCRIPTS))
import bedrock_audit

class JSONCParsingTests(unittest.TestCase):
    def test_strict_json_is_preserved(self):
        findings=[]
        parsed,modes=bedrock_audit.parse_json({'a.json':b'{"text":"ok"}'},findings)
        self.assertEqual(parsed['a.json']['text'],'ok')
        self.assertEqual(modes,{'strict':1,'jsonc':0,'invalid':0})
        self.assertFalse(findings)

    def test_line_and_block_comments_and_trailing_commas_are_accepted(self):
        raw=b'''{\n // region comment\n "name": "bedrock://textures/*", /* inline */\n "values": [1,2,],\n}\n'''
        findings=[]
        parsed,modes=bedrock_audit.parse_json({'a.json':raw},findings)
        self.assertEqual(parsed['a.json'],{'name':'bedrock://textures/*','values':[1,2]})
        self.assertEqual(modes['jsonc'],1)
        self.assertEqual(findings[0]['title'],'JSONC comments or trailing commas accepted')

    def test_comment_markers_inside_strings_are_not_removed(self):
        raw=b'{"url":"https://example.invalid/a//b","comment":"/* literal */"}'
        findings=[]
        parsed,modes=bedrock_audit.parse_json({'a.json':raw},findings)
        self.assertEqual(parsed['a.json']['url'],'https://example.invalid/a//b')
        self.assertEqual(parsed['a.json']['comment'],'/* literal */')
        self.assertEqual(modes['strict'],1)

    def test_duplicate_keys_are_rejected(self):
        findings=[]
        parsed,modes=bedrock_audit.parse_json({'a.json':b'{"x":1,"x":2}'},findings)
        self.assertNotIn('a.json',parsed)
        self.assertEqual(modes['invalid'],1)
        self.assertEqual(findings[0]['title'],'Duplicate JSON object key')

    def test_unterminated_block_comment_is_rejected(self):
        findings=[]
        parsed,modes=bedrock_audit.parse_json({'a.json':b'{"x":1 /* unfinished'},findings)
        self.assertNotIn('a.json',parsed)
        self.assertEqual(modes['invalid'],1)

    def test_malformed_syntax_is_not_silently_repaired(self):
        findings=[]
        parsed,modes=bedrock_audit.parse_json({'a.json':b'{"x":,,}'},findings)
        self.assertNotIn('a.json',parsed)
        self.assertEqual(modes['invalid'],1)

if __name__=='__main__': unittest.main()
