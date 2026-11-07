from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from addon_versioning import AddonVersionError, Version, plan_update, read_request


class AddonVersioningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        self.project = self.workspace / "cinematic-interactions"
        self.bp = self.project / "behavior_packs" / "cinematic_bp"
        self.rp = self.project / "resource_packs" / "cinematic_rp"
        self.bp.mkdir(parents=True)
        self.rp.mkdir(parents=True)
        self.bp_uuid = "11111111-1111-4111-8111-111111111111"
        self.rp_uuid = "22222222-2222-4222-8222-222222222222"
        self.bp_manifest = self.bp / "manifest.json"
        self.rp_manifest = self.rp / "manifest.json"
        self.write_manifest(self.bp_manifest, {
            "format_version": 2,
            "header": {"name": "Cinematic Interactions v1.2.3", "description": "BP", "uuid": self.bp_uuid, "version": [1, 2, 3], "min_engine_version": [1, 21, 0]},
            "modules": [{"type": "data", "uuid": "33333333-3333-4333-8333-333333333333", "version": [1, 2, 3]}, {"type": "script", "uuid": "44444444-4444-4444-8444-444444444444", "version": [1, 2, 3]}],
            "dependencies": [{"uuid": self.rp_uuid, "version": [1, 2, 3]}, {"module_name": "@minecraft/server", "version": "2.0.0"}],
        })
        self.write_manifest(self.rp_manifest, {
            "format_version": 2,
            "header": {"name": "Cinematic Interactions RP v1.2.3", "description": "RP", "uuid": self.rp_uuid, "version": [1, 2, 3], "min_engine_version": [1, 21, 0]},
            "modules": [{"type": "resources", "uuid": "55555555-5555-4555-8555-555555555555", "version": [1, 2, 3]}],
        })
        self.request = {
            "project_directory": "cinematic-interactions",
            "change_type": "fix",
            "manifest_paths": [
                "behavior_packs/cinematic_bp/manifest.json",
                "resource_packs/cinematic_rp/manifest.json",
            ],
        }

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def write_manifest(path: Path, content: dict):
        path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")

    def read_manifest(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def apply(self, change_type="fix"):
        self.request["change_type"] = change_type
        return plan_update(self.request, self.workspace, apply=True)

    def test_fix_updates_visible_names_and_all_pack_version_fields(self):
        result = self.apply("fix")
        bp = self.read_manifest(self.bp_manifest)
        rp = self.read_manifest(self.rp_manifest)
        self.assertEqual(bp["header"]["version"], [1, 2, 4])
        self.assertEqual(rp["header"]["version"], [1, 2, 4])
        self.assertEqual(bp["header"]["name"], "Cinematic Interactions v1.2.4")
        self.assertEqual(rp["header"]["name"], "Cinematic Interactions RP v1.2.4")
        self.assertEqual([m["version"] for m in bp["modules"]], [[1, 2, 4], [1, 2, 4]])
        self.assertEqual(bp["dependencies"][0]["version"], [1, 2, 4])
        self.assertEqual(bp["dependencies"][1]["version"], "2.0.0")
        self.assertEqual(bp["header"]["uuid"], self.bp_uuid)
        self.assertEqual(rp["header"]["uuid"], self.rp_uuid)
        self.assertEqual(bp["format_version"], 2)
        self.assertEqual(bp["header"]["min_engine_version"], [1, 21, 0])
        self.assertTrue(result["applied"])
        self.assertFalse(result["format_version_changed"])
        self.assertFalse(result["min_engine_version_changed"])
        self.assertFalse(result["script_api_dependencies_changed"])
        self.assertTrue(result["verification"]["passed"])
        self.assertTrue(result["verification"]["verified_after_write"])

    def test_medium_and_major_follow_addon_policy(self):
        self.assertEqual(Version(1, 2, 3).bump("medium"), Version(1, 3, 0))
        self.assertEqual(Version(1, 2, 3).bump("major"), Version(2, 0, 0))
        self.apply("medium")
        self.assertEqual(self.read_manifest(self.bp_manifest)["header"]["version"], [1, 3, 0])

    def test_string_semver_is_preserved_as_string(self):
        bp = self.read_manifest(self.bp_manifest)
        rp = self.read_manifest(self.rp_manifest)
        bp["header"]["version"] = "1.2.3"
        bp["modules"][0]["version"] = "1.2.3"
        rp["header"]["version"] = "1.2.3"
        rp["modules"][0]["version"] = "1.2.3"
        self.write_manifest(self.bp_manifest, bp)
        self.write_manifest(self.rp_manifest, rp)
        self.apply()
        self.assertEqual(self.read_manifest(self.bp_manifest)["header"]["version"], "1.2.4")
        self.assertEqual(self.read_manifest(self.rp_manifest)["modules"][0]["version"], "1.2.4")

    def test_localized_title_updates_all_matching_lang_files(self):
        self.bp.joinpath("texts").mkdir()
        self.rp.joinpath("texts").mkdir()
        bp = self.read_manifest(self.bp_manifest)
        rp = self.read_manifest(self.rp_manifest)
        bp["header"]["name"] = "pack.name"
        rp["header"]["name"] = "pack.name"
        self.write_manifest(self.bp_manifest, bp)
        self.write_manifest(self.rp_manifest, rp)
        (self.bp / "texts" / "en_US.lang").write_text("pack.name=Cinematic Interactions v1.2.3\n", encoding="utf-8")
        (self.bp / "texts" / "ru_RU.lang").write_text("pack.name=Кинематографические взаимодействия\n", encoding="utf-8")
        (self.rp / "texts" / "en_US.lang").write_text("pack.name=Cinematic Interactions RP\n", encoding="utf-8")
        self.apply()
        self.assertIn("Cinematic Interactions v1.2.4", (self.bp / "texts" / "en_US.lang").read_text(encoding="utf-8"))
        self.assertIn("Кинематографические взаимодействия v1.2.4", (self.bp / "texts" / "ru_RU.lang").read_text(encoding="utf-8"))
        self.assertIn("Cinematic Interactions RP v1.2.4", (self.rp / "texts" / "en_US.lang").read_text(encoding="utf-8"))
        bp_after = self.read_manifest(self.bp_manifest)
        self.assertEqual(bp_after["header"]["name"], "pack.name")

    def test_localized_key_without_dot_is_detected_from_lang_content(self):
        self.bp.joinpath("texts").mkdir()
        bp = self.read_manifest(self.bp_manifest)
        bp["header"]["name"] = "cinematicPackName"
        self.write_manifest(self.bp_manifest, bp)
        (self.bp / "texts" / "en_US.lang").write_text(
            "cinematicPackName=Cinematic Interactions\n", encoding="utf-8"
        )
        request = dict(self.request)
        request["manifest_paths"] = [self.request["manifest_paths"][0]]
        result = plan_update(request, self.workspace)
        self.assertEqual(result["changes"][0]["new_header_name"], "cinematicPackName")
        self.assertIn("Cinematic Interactions v1.2.4",
                      result["localized_titles"][0]["new_value"])

    def test_localized_display_override_is_per_language_and_keeps_manifest_key(self):
        self.bp.joinpath("texts").mkdir()
        bp = self.read_manifest(self.bp_manifest)
        bp["header"]["name"] = "pack.name"
        self.write_manifest(self.bp_manifest, bp)
        (self.bp / "texts" / "en_US.lang").write_text(
            "pack.name=Cinematic Interactions old title\n", encoding="utf-8"
        )
        (self.bp / "texts" / "ru_RU.lang").write_text(
            "pack.name=Кинематографические взаимодействия старое название\n", encoding="utf-8"
        )
        request = dict(self.request)
        request["manifest_paths"] = [self.request["manifest_paths"][0]]
        request["localized_display_names"] = {
            self.request["manifest_paths"][0]: {
                "en_US.lang": "Cinematic Interactions",
                "ru_RU.lang": "Кинематографические взаимодействия",
            }
        }
        result = plan_update(request, self.workspace, apply=True)
        self.assertEqual(self.read_manifest(self.bp_manifest)["header"]["name"], "pack.name")
        self.assertIn("pack.name=Cinematic Interactions v1.2.4",
                      (self.bp / "texts" / "en_US.lang").read_text(encoding="utf-8"))
        self.assertIn("pack.name=Кинематографические взаимодействия v1.2.4",
                      (self.bp / "texts" / "ru_RU.lang").read_text(encoding="utf-8"))
        self.assertTrue(result["verification"]["passed"])

    def test_display_names_cannot_replace_a_localization_key(self):
        self.bp.joinpath("texts").mkdir()
        bp = self.read_manifest(self.bp_manifest)
        bp["header"]["name"] = "pack.name"
        self.write_manifest(self.bp_manifest, bp)
        (self.bp / "texts" / "en_US.lang").write_text(
            "pack.name=Cinematic Interactions\n", encoding="utf-8"
        )
        request = dict(self.request)
        request["manifest_paths"] = [self.request["manifest_paths"][0]]
        request["display_names"] = {self.request["manifest_paths"][0]: "Cinematic Interactions"}
        with self.assertRaisesRegex(AddonVersionError, "keep it unchanged"):
            plan_update(request, self.workspace)

    def test_auto_discovery_finds_a_single_bp_rp_pair(self):
        request = dict(self.request)
        request.pop("manifest_paths")
        result = plan_update(request, self.workspace)
        self.assertEqual(result["manifest_selection"], "auto-discovered")
        self.assertEqual({row["manifest"] for row in result["changes"]}, {
            "behavior_packs/cinematic_bp/manifest.json",
            "resource_packs/cinematic_rp/manifest.json",
        })
        self.assertTrue(result["verification"]["passed"])

    def test_auto_discovery_fails_closed_on_multiple_pack_variants(self):
        duplicate = self.bp.parent / "cinematic_bp_preview"
        duplicate.mkdir()
        alt = self.read_manifest(self.bp_manifest)
        alt["header"]["uuid"] = "66666666-6666-4666-8666-666666666666"
        self.write_manifest(duplicate / "manifest.json", alt)
        request = dict(self.request)
        request.pop("manifest_paths")
        with self.assertRaisesRegex(AddonVersionError, "found 3 pack manifests"):
            plan_update(request, self.workspace)

    def test_cinematic_interactions_style_reference_fixture(self):
        fixtures = Path(__file__).resolve().parents[1] / "references" / "fixtures"
        request_file = fixtures / "cinematic-interactions-style" / "version-request.example.json"
        fixture_workspace = fixtures
        request = read_request(request_file)
        result = plan_update(request, fixture_workspace)
        self.assertEqual(result["manifest_selection"], "auto-discovered")
        self.assertTrue(result["verification"]["passed"])
        self.assertEqual({row["new_version"] for row in result["changes"]}, {"1.2.4"})
        visible = {
            (row["manifest"], row["locale_file"]): row["visible_title"]
            for row in result["verification"]["localized_title_checks"]
        }
        self.assertEqual(
            visible[("behavior_packs/cinematic_bp/manifest.json", "en_US.lang")],
            "Cinematic Interactions v1.2.4",
        )

    def test_existing_suffix_in_parentheses_is_replaced_not_duplicated(self):
        bp = self.read_manifest(self.bp_manifest)
        bp["header"]["name"] = "Cinematic Interactions (v1.2.3)"
        self.write_manifest(self.bp_manifest, bp)
        request = dict(self.request)
        request["manifest_paths"] = [self.request["manifest_paths"][0]]
        result = plan_update(request, self.workspace)
        self.assertEqual(result["changes"][0]["new_header_name"], "Cinematic Interactions v1.2.4")

    def test_dry_run_does_not_write_any_files(self):
        before = self.bp_manifest.read_bytes()
        result = plan_update(self.request, self.workspace, apply=False)
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(self.bp_manifest.read_bytes(), before)

    def test_mismatched_bp_rp_versions_are_blocked(self):
        rp = self.read_manifest(self.rp_manifest)
        rp["header"]["version"] = [1, 2, 2]
        self.write_manifest(self.rp_manifest, rp)
        with self.assertRaisesRegex(AddonVersionError, "do not share one current version"):
            plan_update(self.request, self.workspace, apply=True)

    def test_duplicate_manifest_path_is_blocked(self):
        self.request["manifest_paths"].append(self.request["manifest_paths"][0])
        with self.assertRaisesRegex(AddonVersionError, "duplicates"):
            plan_update(self.request, self.workspace)

    def test_path_traversal_is_blocked(self):
        self.request["manifest_paths"][0] = "../outside/manifest.json"
        with self.assertRaises(AddonVersionError):
            plan_update(self.request, self.workspace)

    def test_missing_localization_key_is_blocked_without_mutation(self):
        bp = self.read_manifest(self.bp_manifest)
        bp["header"]["name"] = "pack.missing"
        self.write_manifest(self.bp_manifest, bp)
        self.bp.joinpath("texts").mkdir()
        (self.bp / "texts" / "en_US.lang").write_text("pack.other=Some Name\n", encoding="utf-8")
        before = self.rp_manifest.read_bytes()
        with self.assertRaisesRegex(AddonVersionError, "cannot guarantee the visible pack title"):
            plan_update(self.request, self.workspace, apply=True)
        self.assertEqual(self.rp_manifest.read_bytes(), before)

    def test_invalid_manifest_version_is_blocked(self):
        bp = self.read_manifest(self.bp_manifest)
        bp["header"]["version"] = [1, -1, 0]
        self.write_manifest(self.bp_manifest, bp)
        with self.assertRaises(AddonVersionError):
            plan_update(self.request, self.workspace)

    def test_independent_tracks_are_explicit_opt_in(self):
        rp = self.read_manifest(self.rp_manifest)
        rp["header"]["version"] = [2, 0, 0]
        self.write_manifest(self.rp_manifest, rp)
        with self.assertRaises(AddonVersionError):
            plan_update(self.request, self.workspace)
        self.request["allow_independent_versions"] = True
        result = plan_update(self.request, self.workspace)
        self.assertEqual([row["new_version"] for row in result["changes"]], ["1.2.4", "2.0.1"])

    def test_localization_utf8_bom_and_windows_newline_preserved(self):
        bp = self.read_manifest(self.bp_manifest)
        bp["header"]["name"] = "pack.name"
        self.write_manifest(self.bp_manifest, bp)
        self.bp.joinpath("texts").mkdir()
        payload = b"\xef\xbb\xbfpack.name=Name\r\nother.key=Keep\r\n"
        (self.bp / "texts" / "en_US.lang").write_bytes(payload)
        bp2 = self.request["manifest_paths"][0]
        self.request["manifest_paths"] = [bp2]
        plan_update(self.request, self.workspace, apply=True)
        changed = (self.bp / "texts" / "en_US.lang").read_bytes()
        self.assertTrue(changed.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"\r\n", changed)
        self.assertIn(b"pack.name=Name v1.2.4", changed)

    def test_empty_modules_array_is_blocked(self):
        bp = self.read_manifest(self.bp_manifest)
        bp["modules"] = []
        self.write_manifest(self.bp_manifest, bp)
        with self.assertRaisesRegex(AddonVersionError, "modules must be a non-empty array"):
            plan_update(self.request, self.workspace)

    def test_file_permissions_are_preserved_on_apply(self):
        import os
        import stat
        if os.name == "nt":
            self.skipTest("POSIX permission bits are not fully supported on Windows")
        os.chmod(self.bp_manifest, 0o640)
        self.apply()
        self.assertEqual(stat.S_IMODE(self.bp_manifest.stat().st_mode), 0o640)


if __name__ == "__main__":
    unittest.main(verbosity=2)
