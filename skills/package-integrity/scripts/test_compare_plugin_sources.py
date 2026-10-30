from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import compare_plugin_sources as auditor

PROMPTS = [
    "Create a Minecraft Bedrock add-on safely.",
    "Audit an add-on and report exact evidence.",
    "Research the exact target version using official sources.",
]


def make_package(root: Path, version: str = "1.5.11", prompts: list[str] | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".codex-plugin").mkdir()
    values = list(PROMPTS if prompts is None else prompts)
    root_manifest = {
        "name": auditor.EXPECTED_NAME,
        "version": version,
        "extensions": {"com.openai": {"interface": {"defaultPrompt": values}}},
    }
    compatibility_manifest = {
        "name": auditor.EXPECTED_NAME,
        "version": version,
        "skills": "./skills",
        "interface": {"defaultPrompt": values},
    }
    (root / "plugin.json").write_text(json.dumps(root_manifest), encoding="utf-8")
    (root / ".codex-plugin/plugin.json").write_text(json.dumps(compatibility_manifest), encoding="utf-8")
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    (root / "README.md").write_text(
        f"# Minecraft Bedrock Engineer — {version}\n\nSkills-only package.\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## {version} — Test fixture\n",
        encoding="utf-8",
    )
    (root / "skills/example/SKILL.md").parent.mkdir(parents=True)
    (root / "skills/example/SKILL.md").write_text("# Example\n", encoding="utf-8")
    (root / "payload.txt").write_text("same payload\n", encoding="utf-8")


def set_prompts(root: Path, prompts: list[str], *, compatibility_only: bool = False) -> None:
    root_path = root / ".codex-plugin/plugin.json"
    root_manifest_path = root / "plugin.json"
    if not compatibility_only:
        manifest = json.loads(root_manifest_path.read_text(encoding="utf-8"))
        manifest["extensions"]["com.openai"]["interface"]["defaultPrompt"] = prompts
        root_manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    compatibility = json.loads(root_path.read_text(encoding="utf-8"))
    compatibility["interface"]["defaultPrompt"] = prompts
    root_path.write_text(json.dumps(compatibility), encoding="utf-8")


def set_version(root: Path, version: str) -> None:
    root_manifest_path = root / "plugin.json"
    compatibility_path = root / ".codex-plugin/plugin.json"
    root_manifest = json.loads(root_manifest_path.read_text(encoding="utf-8"))
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    root_manifest["version"] = version
    compatibility["version"] = version
    root_manifest_path.write_text(json.dumps(root_manifest), encoding="utf-8")
    compatibility_path.write_text(json.dumps(compatibility), encoding="utf-8")
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    (root / "README.md").write_text(
        f"# Minecraft Bedrock Engineer — {version}\n\nSkills-only package.\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## {version} — Test fixture\n",
        encoding="utf-8",
    )


class PluginSourceParityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.reference = base / "reference"
        self.candidate = base / "candidate"
        make_package(self.reference)
        make_package(self.candidate)

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_trees_and_metadata_pass(self):
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "PASS", result)
        self.assertTrue(result["metadata"]["parity"]["original_first_three_prompts_match"])
        self.assertEqual(result["summary"]["identical_files"], 6)

    def test_changed_file_is_reported_with_both_hashes(self):
        (self.candidate / "payload.txt").write_text("changed\n", encoding="utf-8")
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "DIFFERENT")
        self.assertEqual(result["summary"]["changed_files"], 1)
        self.assertEqual(result["files"]["changed"][0]["path"], "payload.txt")
        self.assertNotEqual(
            result["files"]["changed"][0]["reference"]["sha256"],
            result["files"]["changed"][0]["candidate"]["sha256"],
        )

    def test_missing_and_extra_files_are_reported(self):
        (self.candidate / "payload.txt").unlink()
        (self.candidate / "new.txt").write_text("new\n", encoding="utf-8")
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "DIFFERENT")
        self.assertEqual(result["files"]["only_in_reference"], ["payload.txt"])
        self.assertEqual(result["files"]["only_in_candidate"], ["new.txt"])

    def test_cross_package_version_mismatch_is_different(self):
        set_version(self.candidate, "1.5.12")
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "DIFFERENT")
        self.assertFalse(result["metadata"]["parity"]["versions_match"])

    def test_all_prompt_mismatch_is_different(self):
        changed = list(PROMPTS)
        changed[2] = "Different third prompt."
        set_prompts(self.candidate, changed)
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "DIFFERENT")
        self.assertFalse(result["metadata"]["parity"]["all_default_prompts_match"])
        self.assertFalse(result["metadata"]["parity"]["original_first_three_prompts_match"])

    def test_prompt_arrays_inside_candidate_manifests_must_match(self):
        changed = list(PROMPTS)
        changed[1] = "Different compatibility prompt."
        set_prompts(self.candidate, changed, compatibility_only=True)
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("defaultPrompt arrays differ" in item for item in result["metadata_errors"]))

    def test_duplicate_json_keys_fail_closed(self):
        (self.candidate / "plugin.json").write_text(
            '{"name":"minecraft-bedrock-engineer","name":"other","version":"1.5.11"}',
            encoding="utf-8",
        )
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["metadata_errors"])

    def test_malformed_nested_manifest_shape_fails_closed(self):
        (self.candidate / "plugin.json").write_text(
            json.dumps({
                "name": auditor.EXPECTED_NAME,
                "version": "1.5.11",
                "extensions": [],
            }),
            encoding="utf-8",
        )
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["metadata_errors"])

    def test_bytecode_and_cache_directories_are_rejected(self):
        cache = self.candidate / "skills/example/__pycache__"
        cache.mkdir()
        (cache / "bad.cpython-312.pyc").write_bytes(b"bytecode")
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("__pycache__" in item or ".pyc" in item for item in result["safety_errors"]))

    def test_symlink_is_rejected(self):
        target = self.candidate / "payload.txt"
        link = self.candidate / "linked.txt"
        try:
            link.symlink_to(target.name)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable on this platform")
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("symlink" in item for item in result["safety_errors"]))

    def test_casefold_path_collision_is_rejected(self):
        (self.candidate / "A.txt").write_text("A\n", encoding="utf-8")
        (self.candidate / "a.txt").write_text("a\n", encoding="utf-8")
        result = auditor.compare_roots(self.reference, self.candidate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("portable path collision" in item for item in result["safety_errors"]))

    def test_symlinked_package_root_is_rejected(self):
        link = Path(self.tmp.name) / "candidate-link"
        try:
            link.symlink_to(self.candidate, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable on this platform")
        result = auditor.compare_roots(self.reference, link)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("candidate: scan failed" in item for item in result["safety_errors"]))

    def test_json_report_refuses_overwrite_and_package_mutation(self):
        report = auditor.compare_roots(self.reference, self.candidate)
        output = Path(self.tmp.name) / "parity.json"
        auditor.write_json_report(output, report, (self.reference, self.candidate))
        self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["status"] == "PASS")
        with self.assertRaises(FileExistsError):
            auditor.write_json_report(output, report, (self.reference, self.candidate))
        with self.assertRaises(ValueError):
            auditor.write_json_report(self.reference / "report.json", report, (self.reference, self.candidate))


if __name__ == "__main__":
    unittest.main(verbosity=2)
