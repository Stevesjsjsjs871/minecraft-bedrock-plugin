from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_skill_tests


class SkillTestRunnerSafetyTests(unittest.TestCase):
    def make_root(self, base: Path) -> Path:
        root = base / "pkg"
        (root / "skills" / "example" / "scripts").mkdir(parents=True)
        return root

    def test_discovers_only_skill_test_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            test = root / "skills" / "example" / "scripts" / "test_ok.py"
            test.write_text("import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n", encoding="utf-8")
            (root / "server").mkdir()
            (root / "server" / "test_legacy.py").write_text("raise RuntimeError()", encoding="utf-8")
            _, found = run_skill_tests._discover_tests(root)
            self.assertEqual([test.resolve()], found)

    def test_rejects_symlinked_test_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            outside = Path(temp) / "outside.py"
            outside.write_text("raise RuntimeError()", encoding="utf-8")
            link = root / "skills" / "example" / "scripts" / "test_escape.py"
            link.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "symlinked test"):
                run_skill_tests._discover_tests(root)

    def test_rejects_symlinked_skills_root(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "pkg"
            root.mkdir()
            external = base / "external"
            external.mkdir()
            (external / "test_escape.py").write_text("pass", encoding="utf-8")
            (root / "skills").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(FileNotFoundError, "real Skills directory"):
                run_skill_tests._discover_tests(root)

    def test_timeout_must_be_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            for value in (0, -1, 901, float("inf"), True):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    run_skill_tests.run(root, timeout=value)

    @patch("run_skill_tests.subprocess.run")
    def test_runs_each_test_in_its_own_directory(self, mocked_run):
        class Proc:
            returncode = 0
            stdout = ""
            stderr = "Ran 2 tests in 0.01s\n"
        mocked_run.return_value = Proc()
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            test = root / "skills" / "example" / "scripts" / "test_ok.py"
            test.write_text("pass\n", encoding="utf-8")
            result = run_skill_tests.run(root)
        self.assertEqual(1, result["summary"]["passed_files"])
        args, kwargs = mocked_run.call_args
        self.assertEqual([run_skill_tests.sys.executable, "test_ok.py", "-v"], args[0])
        self.assertEqual(test.parent, kwargs["cwd"])


if __name__ == "__main__":
    unittest.main()
