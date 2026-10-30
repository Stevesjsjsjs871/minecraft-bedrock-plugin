from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_skills_package as checker
from package_provenance import make_provenance, scan_package, validate_provenance


class SkillsPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".codex-plugin").mkdir()
        sample = self.root / "skills/bedrock-development/references/mojang-samples-1.26.50.4"
        sample.mkdir(parents=True)
        for name in ("bedrock-engineer-core", "skills-first-execution", "skills-only-maintenance", "geometry-uv-engine", "visual-resource-pipeline"):
            directory = self.root / "skills" / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test skill {name}.\n---\n", encoding="utf-8")
        geometry = self.root / "skills/geometry-uv-engine/scripts"
        visual = self.root / "skills/visual-resource-pipeline/scripts"
        geometry.mkdir(parents=True)
        visual.mkdir(parents=True)
        (geometry / "geometry_engine.py").write_text("def analyze_geometry(): pass\n# duplicate JSON key UV_OUT_OF_BOUNDS UV_OVERLAP --geometry-identifier\n", encoding="utf-8")
        (geometry / "test_geometry_engine.py").write_text("# tests\n", encoding="utf-8")
        (geometry / "uv_template_engine.py").write_text("def extract_regions(): pass\ndef render_template(): pass\ndef encode_png(): pass\nmax_pixels xb\n", encoding="utf-8")
        (geometry / "test_uv_template_engine.py").write_text("# tests\n", encoding="utf-8")
        (visual / "png_engine.py").write_text("# png engine\n", encoding="utf-8")
        (visual / "test_png_engine.py").write_text("# tests\n", encoding="utf-8")
        prompts = list(checker.ORIGINAL_DEFAULT_PROMPTS) + ["A fourth test prompt."]
        interface = {"defaultPrompt": prompts}
        root_manifest = {"name": checker.EXPECTED_NAME, "version": "1.5.11", "skills": "./skills", "extensions": {"com.openai": {"interface": interface}}}
        compat_manifest = {"name": checker.EXPECTED_NAME, "version": "1.5.11", "skills": "./skills", "interface": interface}
        (self.root / "plugin.json").write_text(json.dumps(root_manifest), encoding="utf-8")
        (self.root / ".codex-plugin/plugin.json").write_text(json.dumps(compat_manifest), encoding="utf-8")
        (self.root / "VERSION").write_text("1.5.11\n", encoding="utf-8")
        (self.root / "README.md").write_text("# Minecraft Bedrock Engineer — 1.5.11\n\nSkills-and-instructions-only plugin. It does not use MCP.\n", encoding="utf-8")
        (self.root / "CHANGELOG.md").write_text("# Changelog\n\n## 1.5.11 — Test fixture\n", encoding="utf-8")
        audit_benchmark = self.root / "skills/audit-benchmark"
        audit_benchmark.mkdir(parents=True)
        (audit_benchmark / "SKILL.md").write_text("---\nname: audit-benchmark\ndescription: Benchmark tests.\n---\n", encoding="utf-8")
        (audit_benchmark / "requirements.txt").write_text("jsonschema==4.26.0\n", encoding="utf-8")
        package_scripts = self.root / "skills/package-integrity/scripts"
        package_scripts.mkdir(parents=True)
        (package_scripts / "package_provenance.py").write_text("# provenance helper\n", encoding="utf-8")
        (package_scripts / "check_skills_package.py").write_text("# checker\n", encoding="utf-8")
        (package_scripts / "test_check_skills_package.py").write_text("# tests\n", encoding="utf-8")
        (package_scripts / "build_skills_package.py").write_text("# builder\n", encoding="utf-8")
        (package_scripts / "test_build_skills_package.py").write_text("# tests\n", encoding="utf-8")
        (package_scripts / "compare_plugin_sources.py").write_text("# parity auditor\n", encoding="utf-8")
        (package_scripts / "test_compare_plugin_sources.py").write_text("# parity tests\n", encoding="utf-8")
        index_metadata = {
            "source_archive": "bedrock-samples-v1.26.50.4-full.zip",
            "target_version": "1.26.50.4",
            "zip_sha256": "a" * 64,
            "entry_count": 2,
            "indexed_count": 2,
            "declared_uncompressed_bytes": 123,
            "category_counts": {"geometry": 1, "item": 1},
        }
        (sample / "INDEX_METADATA.json").write_text(json.dumps(index_metadata), encoding="utf-8")
        index_payload = {
            "schema_version": 1,
            "dataset_id": "mojang-bedrock-samples",
            "target_version": "1.26.50.4",
            "source": "https://github.com/Mojang/bedrock-samples",
            "archive_file_name": index_metadata["source_archive"],
            "archive_sha256": index_metadata["zip_sha256"],
            "archive_stats": {"entry_count": 2, "indexed_count": 2, "declared_uncompressed_bytes": 123},
            "entries": [
                {"path": "resource_pack/models/entity/pig.geo.json", "category": "geometry"},
                {"path": "behavior_pack/items/apple.json", "category": "item"},
            ],
        }
        with gzip.open(sample / "mojang-samples-index.json.gz", "wb") as stream:
            stream.write(json.dumps(index_payload).encode("utf-8"))
        restore_scripts = self.root / "skills/bedrock-development/scripts"
        restore_scripts.mkdir(parents=True, exist_ok=True)
        (restore_scripts / "restore_mojang_index.py").write_text("# restore helper\n", encoding="utf-8")
        (restore_scripts / "test_restore_mojang_index.py").write_text("# restore tests\n", encoding="utf-8")
        records, violations = scan_package(self.root)
        self.assertEqual(violations, [])
        provenance = make_provenance(self.root, records, "a" * 40, 0, "refs/heads/test")
        (self.root / checker.PROVENANCE_NAME).write_text(json.dumps(provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def by_id(self, result, check_id):
        return next(item for item in result["checks"] if item["id"] == check_id)

    def test_valid_package_passes(self):
        result = checker.check(self.root)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(self.by_id(result, "original-default-prompts")["status"], "PASS")
        self.assertEqual(self.by_id(result, "provenance-integrity")["status"], "PASS")

    def test_version_mismatch_fails(self):
        (self.root / "VERSION").write_text("1.5.9", encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "version-parity")["status"], "FAIL")

    def test_non_string_version_type_fails_cleanly(self):
        path = self.root / "plugin.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = {"unexpected": "object"}
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "version-parity")["status"], "FAIL")

    def test_malformed_extensions_fail_cleanly(self):
        path = self.root / "plugin.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["extensions"] = None
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "default-prompt-parity")["status"], "FAIL")

    def test_prompt_mismatch_fails(self):
        path = self.root / ".codex-plugin/plugin.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["interface"]["defaultPrompt"] = ["different"]
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "default-prompt-parity")["status"], "FAIL")

    def test_original_prompt_change_fails(self):
        path = self.root / "plugin.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["extensions"]["com.openai"]["interface"]["defaultPrompt"][0] = "changed original prompt"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "original-default-prompts")["status"], "FAIL")

    def test_mcp_config_rejected(self):
        (self.root / ".mcp.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "skills-only-boundary")["status"], "FAIL")

    def test_obsolete_cloudflare_rejected(self):
        (self.root / "cloudflare").mkdir()
        self.assertEqual(self.by_id(checker.check(self.root), "obsolete-deployment")["status"], "FAIL")

    def test_stale_tool_invocation_rejected(self):
        path = self.root / "skills/skills-only-maintenance/SKILL.md"
        path.write_text("---\nname: skills-only-maintenance\ndescription: Useful description.\n---\ncall `create_addon_project` now\n", encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "skill-tool-boundary")["status"], "FAIL")

    def test_duplicate_skill_name_rejected(self):
        path = self.root / "skills/skills-only-maintenance/SKILL.md"
        path.write_text("---\nname: bedrock-engineer-core\ndescription: duplicate\n---\n", encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "skill-inventory")["status"], "FAIL")

    def test_missing_frontmatter_rejected(self):
        (self.root / "skills/skills-only-maintenance/SKILL.md").write_text("# missing", encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "skill-inventory")["status"], "FAIL")

    def test_bad_gzip_rejected(self):
        path = self.root / "skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz"
        path.write_bytes(b"not gzip")
        self.assertEqual(self.by_id(checker.check(self.root), "mojang-index-integrity")["status"], "FAIL")

    def test_wrong_readme_version_fails(self):
        (self.root / "README.md").write_text("# Minecraft Bedrock Engineer — 1.5.1\nSkills-and-instructions-only. It does not use MCP.", encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "readme-version")["status"], "FAIL")

    def test_wrong_changelog_version_fails(self):
        (self.root / "CHANGELOG.md").write_text("# Changelog\n\n## 1.5.10 — old\n", encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "changelog-version")["status"], "FAIL")

    def test_missing_png_tests_fails(self):
        (self.root / "skills/visual-resource-pipeline/scripts/test_png_engine.py").unlink()
        self.assertEqual(self.by_id(checker.check(self.root), "required-files")["status"], "FAIL")

    def test_missing_uv_template_tests_fails(self):
        (self.root / "skills/geometry-uv-engine/scripts/test_uv_template_engine.py").unlink()
        self.assertEqual(self.by_id(checker.check(self.root), "required-files")["status"], "FAIL")

    def test_missing_provenance_fails(self):
        (self.root / checker.PROVENANCE_NAME).unlink()
        result = checker.check(self.root)
        self.assertEqual(self.by_id(result, "provenance-integrity")["status"], "FAIL")
        self.assertIn("missing", self.by_id(result, "provenance-integrity")["message"])

    def test_tampered_payload_fails_provenance(self):
        (self.root / "README.md").write_text("tampered", encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "provenance-integrity")["status"], "FAIL")

    def test_bytecode_file_rejected(self):
        cache = self.root / "skills/example/__pycache__"
        cache.mkdir(parents=True)
        (cache / "bad.cpython-313.pyc").write_bytes(b"bytecode")
        self.assertEqual(self.by_id(checker.check(self.root), "package-hygiene")["status"], "FAIL")

    def test_bytecode_suffix_rejected_outside_cache_dir(self):
        (self.root / "stray.pyo").write_bytes(b"bytecode")
        self.assertEqual(self.by_id(checker.check(self.root), "package-hygiene")["status"], "FAIL")

    def test_symlink_rejected(self):
        target = self.root / "README.md"
        link = self.root / "linked-readme"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable on this runner")
        self.assertEqual(self.by_id(checker.check(self.root), "package-hygiene")["status"], "FAIL")

    def test_duplicate_json_keys_rejected(self):
        (self.root / "plugin.json").write_text('{"name":"one","name":"two"}', encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "manifest-parse")["status"], "FAIL")

    def test_missing_benchmark_dependency_fails(self):
        (self.root / "skills/audit-benchmark/requirements.txt").unlink()
        self.assertEqual(self.by_id(checker.check(self.root), "required-files")["status"], "FAIL")

    def test_unpinned_benchmark_dependency_fails(self):
        (self.root / "skills/audit-benchmark/requirements.txt").write_text("jsonschema>=4.0\n", encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "benchmark-schema-dependency")["status"], "FAIL")

    def test_provenance_duplicate_path_rejected(self):
        path = self.root / checker.PROVENANCE_NAME
        data = json.loads(path.read_text(encoding="utf-8"))
        data["files"].append(dict(data["files"][0]))
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "provenance-integrity")["status"], "FAIL")


    def test_mojang_index_archive_hash_mismatch_fails(self):
        path = self.root / "skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz"
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            data = json.load(stream)
        data["archive_sha256"] = "0" * 64
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(data, stream)
        self.assertEqual(self.by_id(checker.check(self.root), "mojang-index-integrity")["status"], "FAIL")

    def test_mojang_index_category_mismatch_fails(self):
        path = self.root / "skills/bedrock-development/references/mojang-samples-1.26.50.4/mojang-samples-index.json.gz"
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            data = json.load(stream)
        data["entries"][0]["category"] = "texture"
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(data, stream)
        self.assertEqual(self.by_id(checker.check(self.root), "mojang-index-integrity")["status"], "FAIL")
    def test_mojang_index_pinned_hash_mismatch_fails(self):
        meta_path = self.root / "skills/bedrock-development/references/mojang-samples-1.26.50.4/INDEX_METADATA.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["index_sha256"] = "0" * 64
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        self.assertEqual(self.by_id(checker.check(self.root), "mojang-index-integrity")["status"], "FAIL")

    def test_package_hygiene_failure_short_circuits_before_manifest_reads(self):
        (self.root / "stray.pyc").write_bytes(b"generated")
        with patch.object(checker, "read_json") as read_json:
            result = checker.check(self.root)
            read_json.assert_not_called()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual([item["id"] for item in result["checks"]], ["package-hygiene"])

    def test_provenance_payload_count_requires_integer(self):
        records, _ = scan_package(self.root)
        provenance = make_provenance(self.root, records, "b" * 40, 0)
        provenance["payload_file_count"] = float(provenance["payload_file_count"])
        ok, _ = validate_provenance(provenance, records)
        self.assertFalse(ok)

    def test_provenance_payload_bytes_requires_integer(self):
        records, _ = scan_package(self.root)
        provenance = make_provenance(self.root, records, "c" * 40, 0)
        provenance["payload_total_bytes"] = float(provenance["payload_total_bytes"])
        ok, _ = validate_provenance(provenance, records)
        self.assertFalse(ok)

    def test_missing_source_parity_auditor_fails_required_files(self):
        path = self.root / "skills/package-integrity/scripts/compare_plugin_sources.py"
        path.unlink()
        result = checker.check(self.root)
        self.assertEqual(self.by_id(result, "required-files")["status"], "FAIL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
