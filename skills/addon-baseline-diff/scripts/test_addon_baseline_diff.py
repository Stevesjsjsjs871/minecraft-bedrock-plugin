from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from addon_baseline_diff import DiffError, compare_archives

BP_UUID = "11111111-1111-4111-8111-111111111111"
BP_MODULE_UUID = "33333333-3333-4333-8333-333333333333"
RP_UUID = "22222222-2222-4222-8222-222222222222"
RP_MODULE_UUID = "44444444-4444-4444-8444-444444444444"


def manifest(role: str, version=(1, 2, 3), *, api_version="2.4.0", title="pack.name", header_uuid=None, module_uuid=None):
    if role == "BP":
        header_uuid = header_uuid or BP_UUID
        module_uuid = module_uuid or BP_MODULE_UUID
        return {
            "format_version": 2,
            "header": {"name": title, "uuid": header_uuid, "version": list(version), "min_engine_version": [1, 26, 50]},
            "modules": [
                {"type": "data", "uuid": module_uuid, "version": list(version)},
                {"type": "script", "uuid": "55555555-5555-4555-8555-555555555555", "version": list(version), "language": "javascript"},
            ],
            "dependencies": [
                {"uuid": RP_UUID, "version": list(version)},
                {"module_name": "@minecraft/server", "version": api_version},
            ],
        }
    return {
        "format_version": 2,
        "header": {"name": title, "uuid": header_uuid or RP_UUID, "version": list(version), "min_engine_version": [1, 26, 50]},
        "modules": [{"type": "resources", "uuid": module_uuid or RP_MODULE_UUID, "version": list(version)}],
    }


def build_archive(path: Path, *, version=(1, 2, 3), bp_root="CinematicBP", rp_root="CinematicRP",
                  bp_script=b"import { world } from '@minecraft/server';\n", extra=None, removed=False,
                  bp_version_override=None, dependency_version=None, duplicate_json=False, bad_js=False,
                  localized_titles=False, title_suffix=None, api_version="2.4.0", bp_header_uuid=None,
                  bp_module_version_override=None):
    version_text = ".".join(map(str, version))
    title = "pack.name" if localized_titles else f"Cinematic Interactions v{title_suffix or version_text}"
    bp = manifest("BP", bp_version_override or version, title=title, api_version=api_version, header_uuid=bp_header_uuid)
    if bp_module_version_override is not None:
        bp["modules"][0]["version"] = list(bp_module_version_override)
    if dependency_version is not None:
        bp["dependencies"][0]["version"] = list(dependency_version)
    rp = manifest("RP", version, title=("pack.name" if localized_titles else f"Cinematic Interactions RP v{title_suffix or version_text}"))
    members = {
        f"{bp_root}/manifest.json": json.dumps(bp, indent=2).encode(),
        f"{bp_root}/scripts/session.js": (b"function start() {\n  return true;\n" if bad_js else bp_script),
        f"{bp_root}/texts/en_US.lang": f"pack.name=Cinematic Interactions v{title_suffix or version_text}\n".encode() if localized_titles else b"",
        f"{rp_root}/manifest.json": json.dumps(rp, indent=2).encode(),
        f"{rp_root}/entity/player.entity.json": b'{"minecraft:client_entity":{"description":{"identifier":"minecraft:player"}}}\n',
        f"{rp_root}/textures/entity/player.png": b"PNG-stub-A",
    }
    if localized_titles:
        members[f"{rp_root}/texts/en_US.lang"] = f"pack.name=Cinematic Interactions RP v{title_suffix or version_text}\n".encode()
    if duplicate_json:
        members[f"{rp_root}/broken.json"] = b'{"a":1,"a":2}'
    if extra:
        members.update(extra)
    if removed:
        members.pop(f"{rp_root}/textures/entity/player.png", None)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


class AddonBaselineDiffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.base = self.root / "baseline.mcaddon"
        self.candidate = self.root / "candidate.mcaddon"
        build_archive(self.base)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def rewrite_members(path: Path, updates: dict[str, bytes]):
        with zipfile.ZipFile(path, "r") as source:
            members = {name: source.read(name) for name in source.namelist() if not name.endswith("/")}
        members.update(updates)
        rebuilt = path.with_suffix(path.suffix + ".rebuilt")
        with zipfile.ZipFile(rebuilt, "w", compression=zipfile.ZIP_DEFLATED) as destination:
            for name, payload in members.items():
                destination.writestr(name, payload)
        rebuilt.replace(path)

    def rewrite_manifest(self, path: Path, root: str, mutate):
        member = f"{root}/manifest.json"
        with zipfile.ZipFile(path, "r") as archive:
            document = json.loads(archive.read(member).decode("utf-8"))
        mutate(document)
        self.rewrite_members(path, {member: json.dumps(document, indent=2).encode("utf-8")})

    def test_clean_candidate_reports_added_and_modified_without_removals(self):
        build_archive(self.candidate, version=(1, 2, 4), bp_script=b"import { world } from '@minecraft/server';\nexport function start() { return world.getDimension('overworld'); }\n",
                      extra={"CinematicBP/scripts/new_feature.js": b"export const enabled = true;\n"})
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["file_delta"]["summary"]["added"], 1)
        self.assertEqual(report["file_delta"]["summary"]["modified"], 3)  # BP/RP manifests + session script
        self.assertEqual(report["file_delta"]["summary"]["removed"], 0)
        self.assertEqual(report["checks"]["javascript_syntax"], "PASS")
        self.assertEqual(report["checks"]["runtime"], "NOT RUN")

    def test_pack_root_folder_rename_is_not_a_mass_file_removal(self):
        build_archive(self.candidate, bp_root="CinematicBP_New", rp_root="CinematicRP_New")
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["file_delta"]["summary"]["added"], 0)
        self.assertEqual(report["file_delta"]["summary"]["removed"], 0)
        self.assertEqual(report["file_delta"]["summary"]["modified"], 0)

    def test_file_removals_require_manual_review(self):
        build_archive(self.candidate, removed=True)
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["status"], "REVIEW")
        self.assertEqual(report["file_delta"]["summary"]["removed"], 1)
        self.assertTrue(any(f["code"] == "FILES_REMOVED" for f in report["findings"]))

    def test_release_candidate_requires_higher_pack_version(self):
        build_archive(self.candidate)
        report = compare_archives(self.base, self.candidate, release_candidate=True)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(f["code"] == "PACK_VERSION_NOT_ADVANCED" for f in report["findings"]))

    def test_release_candidate_checks_localized_visible_titles(self):
        build_archive(self.base, localized_titles=True)
        build_archive(self.candidate, version=(1, 2, 4), localized_titles=True)
        report = compare_archives(self.base, self.candidate, release_candidate=True)
        self.assertFalse(any(f["code"] == "VISIBLE_TITLE_VERSION_MISSING" for f in report["findings"]))

    def test_release_candidate_fails_if_localized_title_is_stale(self):
        build_archive(self.base, localized_titles=True)
        build_archive(self.candidate, version=(1, 2, 4), localized_titles=True, title_suffix="1.2.3")
        report = compare_archives(self.base, self.candidate, release_candidate=True)
        self.assertTrue(any(f["code"] == "VISIBLE_TITLE_VERSION_MISSING" for f in report["findings"]))

    def test_uuid_change_blocks_update_identity(self):
        build_archive(self.candidate, version=(1, 2, 4), bp_header_uuid="99999999-9999-4999-8999-999999999999")
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(f["code"] == "PACK_HEADER_UUID_CHANGED" for f in report["findings"]))

    def test_internal_dependency_version_mismatch_blocks_candidate(self):
        build_archive(self.candidate, version=(1, 2, 4), dependency_version=(1, 2, 3))
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(f["code"] == "INTERNAL_DEPENDENCY_VERSION_MISMATCH" for f in report["findings"]))

    def test_module_version_mismatch_is_reported(self):
        build_archive(self.candidate, version=(1, 2, 4), bp_module_version_override=(1, 2, 3))
        report = compare_archives(self.base, self.candidate)
        self.assertTrue(any(f["code"] == "MODULE_VERSION_MISMATCH" for f in report["findings"]))

    def test_script_api_dependency_change_is_separate_from_pack_version(self):
        build_archive(self.candidate, version=(1, 2, 4), api_version="2.5.0")
        report = compare_archives(self.base, self.candidate)
        self.assertTrue(any(f["code"] == "SCRIPT_API_DEPENDENCIES_CHANGED" for f in report["findings"]))
        self.assertFalse(any(f["code"] == "MODULE_VERSION_MISMATCH" for f in report["findings"]))

    def test_duplicate_json_key_is_a_failure(self):
        build_archive(self.candidate, version=(1, 2, 4), duplicate_json=True)
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["checks"]["json_duplicate_key_failures"], 1)

    def test_jsonc_or_invalid_json_is_review_not_silent_failure(self):
        build_archive(self.candidate, version=(1, 2, 4), extra={"CinematicRP/commented.json": b'{\n // note\n "ok": true\n}'})
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["status"], "REVIEW")
        self.assertTrue(any(f["code"] == "NON_STRICT_JSON_CANDIDATES" for f in report["findings"]))

    def test_invalid_javascript_syntax_is_a_failure_when_node_available(self):
        import shutil
        if not shutil.which("node"):
            self.skipTest("Node.js is not installed")
        build_archive(self.candidate, version=(1, 2, 4), bad_js=True)
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["checks"]["javascript_syntax"], "FAIL")
        self.assertTrue(any(f["code"] == "JAVASCRIPT_SYNTAX_FAILURE" for f in report["findings"]))

    def test_localized_title_key_without_dot_is_supported(self):
        build_archive(self.base, localized_titles=True)
        build_archive(self.candidate, version=(1, 2, 4), localized_titles=True)
        for path in (self.base, self.candidate):
            for root in ("CinematicBP", "CinematicRP"):
                self.rewrite_manifest(path, root, lambda d: d["header"].update({"name": "packname"}))
                lang_member = f"{root}/texts/en_US.lang"
                with zipfile.ZipFile(path, "r") as archive:
                    lang = archive.read(lang_member).decode("utf-8")
                lang = lang.replace("pack.name=", "packname=")
                self.rewrite_members(path, {lang_member: lang.encode("utf-8")})
        report = compare_archives(self.base, self.candidate, release_candidate=True)
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(any(f["code"] == "PACK_TITLE_UNCHANGED" for f in report["findings"]))
        self.assertFalse(any(f["code"] == "VISIBLE_TITLE_VERSION_MISSING" for f in report["findings"]))

    def test_localized_title_key_without_translation_fails_release_gate(self):
        build_archive(self.base, localized_titles=True)
        build_archive(self.candidate, version=(1, 2, 4), localized_titles=True)
        for path in (self.base, self.candidate):
            for root in ("CinematicBP", "CinematicRP"):
                self.rewrite_manifest(path, root, lambda d: d["header"].update({"name": "packname"}))
                lang_member = f"{root}/texts/en_US.lang"
                with zipfile.ZipFile(path, "r") as archive:
                    lang = archive.read(lang_member).decode("utf-8").replace("pack.name=", "other.key=")
                self.rewrite_members(path, {lang_member: lang.encode("utf-8")})
        report = compare_archives(self.base, self.candidate, release_candidate=True)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(f["code"] == "VISIBLE_TITLE_VERSION_MISSING" for f in report["findings"]))

    def test_every_matching_locale_must_show_candidate_version(self):
        build_archive(self.base, localized_titles=True)
        build_archive(self.candidate, version=(1, 2, 4), localized_titles=True)
        stale = b"pack.name=Cinematic Interactions RP v1.2.3\n"
        self.rewrite_members(self.candidate, {"CinematicRP/texts/ru_RU.lang": stale})
        report = compare_archives(self.base, self.candidate, release_candidate=True)
        self.assertTrue(any(f["code"] == "VISIBLE_TITLE_VERSION_MISSING" and f.get("role") == "RP" for f in report["findings"]))

    def test_manifest_format_version_change_requires_review(self):
        build_archive(self.candidate, version=(1, 2, 4))
        for root in ("CinematicBP", "CinematicRP"):
            self.rewrite_manifest(self.candidate, root, lambda d: d.update({"format_version": 3}))
        report = compare_archives(self.base, self.candidate)
        self.assertTrue(any(f["code"] == "MANIFEST_FORMAT_VERSION_CHANGED" for f in report["findings"]))
        self.assertEqual(report["checks"]["manifest_and_dependency_findings"], "REVIEW")

    def test_repeated_module_types_are_not_collapsed_when_comparing_uuids(self):
        build_archive(self.base)
        build_archive(self.candidate, version=(1, 2, 4))
        extra_module_uuid = "66666666-6666-4666-8666-666666666666"
        for path, new_uuid in ((self.base, extra_module_uuid), (self.candidate, "77777777-7777-4777-8777-777777777777")):
            self.rewrite_manifest(path, "CinematicBP", lambda d, new_uuid=new_uuid: d["modules"].append({
                "type": "data", "uuid": new_uuid, "version": d["header"]["version"]
            }))
        report = compare_archives(self.base, self.candidate)
        findings = [f for f in report["findings"] if f["code"] == "MODULE_UUID_CHANGED"]
        self.assertTrue(any(f.get("module_index") == 2 for f in findings))

    def test_module_uuid_cannot_collide_with_a_later_pack_header_uuid(self):
        build_archive(self.candidate, version=(1, 2, 4))
        self.rewrite_manifest(
            self.candidate,
            "CinematicBP",
            lambda d: d["modules"][0].update({"uuid": RP_UUID}),
        )
        with self.assertRaises(DiffError):
            compare_archives(self.base, self.candidate)

    def test_added_pack_in_release_candidate_must_have_versioned_visible_title(self):
        # A one-pack baseline is expanded to a paired candidate. The newly
        # added RP must still satisfy the visible-title/module gate.
        bp_old = manifest("BP", (1, 2, 3), title="Cinematic BP v1.2.3")
        with zipfile.ZipFile(self.base, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("CinematicBP/manifest.json", json.dumps(bp_old).encode())
            archive.writestr("CinematicBP/scripts/session.js", b"export function start(){return true;}\n")
        bp_new = manifest("BP", (1, 2, 4), title="Cinematic BP v1.2.4")
        rp_new = manifest("RP", (1, 0, 0), title="Cinematic RP")
        bp_new["dependencies"][0]["version"] = [1, 0, 0]
        with zipfile.ZipFile(self.candidate, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("CinematicBP/manifest.json", json.dumps(bp_new).encode())
            archive.writestr("CinematicBP/scripts/session.js", b"export function start(){return true;}\n")
            archive.writestr("CinematicRP/manifest.json", json.dumps(rp_new).encode())
        report = compare_archives(self.base, self.candidate, release_candidate=True)
        self.assertTrue(any(f["code"] == "VISIBLE_TITLE_VERSION_MISSING" and f.get("role") == "RP" for f in report["findings"]))

    def test_multiple_manifests_with_same_pack_role_are_marked_ambiguous(self):
        build_archive(self.candidate, version=(1, 2, 4))
        extra_bp = manifest(
            "BP", (1, 0, 0),
            title="Alternate BP v1.0.0",
            header_uuid="88888888-8888-4888-8888-888888888888",
            module_uuid="99999999-9999-4999-8999-999999999999",
        )
        extra_bp["modules"][1]["uuid"] = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        extra_bp["dependencies"][0]["version"] = [1, 2, 4]
        with zipfile.ZipFile(self.candidate, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("AlternateBP/manifest.json", json.dumps(extra_bp).encode())
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["status"], "REVIEW")
        self.assertTrue(any(f["code"] == "PACK_ROLE_AMBIGUOUS" and f.get("role") == "BP" for f in report["findings"]))

    def test_oversized_json_is_reported_as_not_checked_for_review(self):
        import os
        build_archive(self.candidate, version=(1, 2, 4), extra={"CinematicRP/large.json": os.urandom(4 * 1024 * 1024 + 1)})
        report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["status"], "REVIEW")
        self.assertEqual(report["checks"]["json_not_checked"], 1)
        self.assertTrue(any(f["code"] == "JSON_FILES_NOT_CHECKED" for f in report["findings"]))

    def test_javascript_syntax_is_reviewed_when_node_is_unavailable(self):
        from unittest.mock import patch
        build_archive(self.candidate, version=(1, 2, 4))
        with patch("addon_baseline_diff.shutil.which", return_value=None):
            report = compare_archives(self.base, self.candidate)
        self.assertEqual(report["status"], "REVIEW")
        self.assertEqual(report["checks"]["javascript_syntax"], "PARTIAL")
        self.assertTrue(any(f["code"] == "JAVASCRIPT_SYNTAX_NOT_RUN" for f in report["findings"]))

    def test_path_traversal_is_rejected(self):
        with zipfile.ZipFile(self.candidate, "w") as archive:
            archive.writestr("../escape.txt", b"x")
        with self.assertRaises(DiffError):
            compare_archives(self.base, self.candidate)

    def test_duplicate_archive_member_is_rejected(self):
        with zipfile.ZipFile(self.candidate, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("manifest.json", b"{}")
        with self.assertRaises(DiffError):
            compare_archives(self.base, self.candidate)

    def test_symlink_archive_member_is_rejected(self):
        import stat as stat_module
        with zipfile.ZipFile(self.candidate, "w") as archive:
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = (stat_module.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"target")
        with self.assertRaises(DiffError):
            compare_archives(self.base, self.candidate)

    def test_input_symlink_is_rejected(self):
        link = self.root / "baseline-link.mcaddon"
        link.symlink_to(self.base)
        with self.assertRaises(DiffError):
            compare_archives(link, self.candidate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
