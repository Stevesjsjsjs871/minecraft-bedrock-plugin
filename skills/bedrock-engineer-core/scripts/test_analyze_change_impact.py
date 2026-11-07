from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("analyze_change_impact.py")
spec = importlib.util.spec_from_file_location("analyze_change_impact", SCRIPT)
impact = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(impact)


class ChangeImpactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bp = self.root / "behavior_packs" / "demo_bp"
        self.rp = self.root / "resource_packs" / "demo_rp"
        self._write(self.bp / "manifest.json", {
            "header": {"uuid": "11111111-1111-4111-8111-111111111111"},
            "modules": [{"uuid": "22222222-2222-4222-8222-222222222222"}],
            "dependencies": [{"uuid": "33333333-3333-4333-8333-333333333333"}],
        })
        self._write(self.rp / "manifest.json", {
            "header": {"uuid": "33333333-3333-4333-8333-333333333333"},
            "modules": [{"uuid": "44444444-4444-4444-8444-444444444444"}],
        })
        self._write(self.bp / "entities" / "guardian.json", {
            "minecraft:entity": {"description": {"identifier": "demo:guardian"}, "components": {}}
        })
        self._write(self.bp / "items" / "sword.json", {
            "minecraft:item": {"description": {"identifier": "demo:sword"}, "components": {}}
        })
        self._write(self.bp / "items" / "ore.json", {
            "minecraft:item": {"description": {"identifier": "demo:ore"}, "components": {}}
        })
        self._write(self.bp / "recipes" / "sword.json", {
            "minecraft:recipe_shaped": {
                "description": {"identifier": "demo:recipe_sword"},
                "key": {"O": {"item": "demo:ore"}},
                "result": {"item": "demo:sword"},
            }
        })
        self._write(self.rp / "entity" / "guardian.entity.json", {
            "minecraft:client_entity": {"description": {
                "identifier": "demo:guardian",
                "materials": {"default": "entity_alphatest"},
                "textures": {"default": "textures/entity/guardian"},
                "geometry": {"default": "geometry.guardian"},
                "animations": {"idle": "animation.guardian.idle"},
                "scripts": {"animate": ["idle"]},
                "animation_controllers": ["controller.animation.guardian"],
                "render_controllers": ["controller.render.guardian"],
            }}
        })
        self._write(self.rp / "models" / "entity" / "guardian.geo.json", {
            "minecraft:geometry": [{"description": {"identifier": "geometry.guardian"}, "bones": [{"name": "root"}]}]
        })
        self._write(self.rp / "animations" / "guardian.animation.json", {
            "animations": {"animation.guardian.idle": {"loop": True, "bones": {"root": {"rotation": [0, 0, 0]}}}}
        })
        self._write(self.rp / "animation_controllers" / "guardian.controller.json", {
            "animation_controllers": {"controller.animation.guardian": {"states": {"default": {"animations": ["animation.guardian.idle"]}}}}
        })
        self._write(self.rp / "render_controllers" / "guardian.render_controllers.json", {
            "render_controllers": {"controller.render.guardian": {"geometry": "Geometry.default", "textures": ["Texture.default"]}}
        })
        (self.rp / "textures" / "entity").mkdir(parents=True, exist_ok=True)
        (self.rp / "textures" / "entity" / "guardian.png").write_bytes(b"not-a-real-png-but-a-file-node")
        self._write(self.rp / "ui" / "hud_screen.json", {"$ui_defs": ["ui/widgets.json"]})
        self._write(self.rp / "ui" / "widgets.json", {"namespace": "demo", "controls": {}})
        (self.bp / "scripts").mkdir(parents=True, exist_ok=True)
        (self.bp / "scripts" / "main.js").write_text("import { helper } from './helper.js';\n", encoding="utf-8")
        (self.bp / "scripts" / "helper.js").write_text("export const helper = true;\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write(self, path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def _analyze(self, *changed: str, **kwargs):
        return impact.analyze_project(self.root, list(changed), **kwargs)

    def test_impact_walk_from_bp_entity_finds_client_entity(self):
        report = self._analyze("behavior_packs/demo_bp/entities/guardian.json")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("resource_packs/demo_rp/entity/guardian.entity.json", paths)

    def test_texture_change_impacts_client_entity(self):
        report = self._analyze("resource_packs/demo_rp/textures/entity/guardian.png")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("resource_packs/demo_rp/entity/guardian.entity.json", paths)

    def test_deleted_texture_path_still_impacts_referencing_client_entity(self):
        texture = self.rp / "textures" / "entity" / "guardian.png"
        texture.unlink()
        report = self._analyze("resource_packs/demo_rp/textures/entity/guardian.png")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("resource_packs/demo_rp/entity/guardian.entity.json", paths)
        self.assertIn("CHANGED_DEPENDENCY_MISSING", {f["code"] for f in report["findings"]})

    def test_geometry_change_impacts_client_entity(self):
        report = self._analyze("resource_packs/demo_rp/models/entity/guardian.geo.json")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("resource_packs/demo_rp/entity/guardian.entity.json", paths)

    def test_animation_change_impacts_client_entity(self):
        report = self._analyze("resource_packs/demo_rp/animations/guardian.animation.json")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("resource_packs/demo_rp/entity/guardian.entity.json", paths)

    def test_controller_change_impacts_client_entity(self):
        report = self._analyze("resource_packs/demo_rp/animation_controllers/guardian.controller.json")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("resource_packs/demo_rp/entity/guardian.entity.json", paths)

    def test_render_controller_change_impacts_client_entity(self):
        report = self._analyze("resource_packs/demo_rp/render_controllers/guardian.render_controllers.json")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("resource_packs/demo_rp/entity/guardian.entity.json", paths)

    def test_recipe_references_item_outputs_and_ingredients(self):
        report = self._analyze("behavior_packs/demo_bp/items/ore.json")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("behavior_packs/demo_bp/recipes/sword.json", paths)

    def test_entity_reference_resolves_to_bp_entity_not_client_binding_pair(self):
        self._write(self.bp / "recipes" / "guardian_spawn.json", {
            "minecraft:recipe_shapeless": {"description": {"identifier": "demo:guardian_recipe"}, "entity": "demo:guardian"}
        })
        report = self._analyze("behavior_packs/demo_bp/entities/guardian.json")
        related = [edge for edge in report["edges"] if edge["from"] == "behavior_packs/demo_bp/recipes/guardian_spawn.json"]
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["to"], "behavior_packs/demo_bp/entities/guardian.json")

    def test_manifest_dependency_connects_behavior_and_resource_packs(self):
        report = self._analyze("resource_packs/demo_rp/manifest.json")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("behavior_packs/demo_bp/manifest.json", paths)

    def test_ui_import_is_resolved_and_propagates_impact(self):
        report = self._analyze("resource_packs/demo_rp/ui/widgets.json")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("resource_packs/demo_rp/ui/hud_screen.json", paths)

    def test_deleted_ui_import_target_impacts_importing_screen(self):
        target = self.rp / "ui" / "widgets.json"
        target.unlink()
        report = self._analyze("resource_packs/demo_rp/ui/widgets.json")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("resource_packs/demo_rp/ui/hud_screen.json", paths)
        self.assertIn("CHANGED_DEPENDENCY_MISSING", {f["code"] for f in report["findings"]})

    def test_relative_script_import_is_resolved(self):
        report = self._analyze("behavior_packs/demo_bp/scripts/helper.js")
        paths = {row["path"] for row in report["impact"]}
        self.assertIn("behavior_packs/demo_bp/scripts/main.js", paths)

    def test_changed_path_is_always_direct_impact(self):
        report = self._analyze("removed/old.json")
        self.assertEqual(report["impact"][0]["impact"], "DIRECT")
        self.assertEqual(report["summary"]["changed_paths_present"], 0)
        self.assertIn("CHANGED_PATH_NOT_IN_WORKSPACE", {f["code"] for f in report["findings"]})

    def test_unsafe_changed_paths_are_rejected(self):
        for path in ("../outside.json", "/absolute.json", "C:/outside.json", "a//b.json", "a/./b.json"):
            with self.subTest(path=path), self.assertRaises(impact.ImpactError):
                self._analyze(path)

    def test_duplicate_changed_paths_are_deduplicated(self):
        report = self._analyze("behavior_packs/demo_bp/items/ore.json", "behavior_packs/demo_bp/items/ore.json")
        self.assertEqual(report["changed_paths"], ["behavior_packs/demo_bp/items/ore.json"])

    def test_duplicate_json_keys_are_reported_and_mark_scan_partial(self):
        path = self.bp / "items" / "broken.json"
        path.write_text('{"a":1,"a":2}', encoding="utf-8")
        report = self._analyze("behavior_packs/demo_bp/items/broken.json")
        self.assertIn("JSON_PARSE_ERROR", {f["code"] for f in report["findings"]})
        self.assertEqual(report["summary"]["status"], "PARTIAL")

    def test_max_file_size_skip_is_reported_and_marks_scan_partial(self):
        report = self._analyze("behavior_packs/demo_bp/items/ore.json", max_file_bytes=8)
        self.assertEqual(report["summary"]["status"], "PARTIAL")
        self.assertGreater(report["coverage"]["parse_skipped_size"], 0)

    def test_cli_writes_report_to_explicit_output(self):
        output = self.root / "impact-report.json"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = impact.main([
                "--project-root", str(self.root),
                "--changed-path", "behavior_packs/demo_bp/items/ore.json",
                "--output", str(output),
            ])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["summary"]["status"], "PASS")
        self.assertTrue(stdout.getvalue().strip().startswith("{"))

    def test_cli_does_not_overwrite_existing_report_without_flag(self):
        output = self.root / "impact-report.json"
        output.write_text("keep", encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = impact.main([
                "--project-root", str(self.root),
                "--changed-path", "behavior_packs/demo_bp/items/ore.json",
                "--output", str(output),
            ])
        self.assertEqual(code, 2)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep")
        self.assertIn("--overwrite", stderr.getvalue())

    def test_ambiguous_identifier_does_not_guess_owner(self):
        self._write(self.bp / "items" / "ore_copy.json", {
            "minecraft:item": {"description": {"identifier": "demo:ore"}, "components": {}}
        })
        report = self._analyze("behavior_packs/demo_bp/items/ore.json")
        findings = [f for f in report["findings"] if f["code"] == "AMBIGUOUS_IDENTIFIER"]
        self.assertTrue(findings)
        self.assertEqual(len(findings[0]["owners"]), 2)

    def test_duplicate_identifier_is_reported(self):
        self._write(self.bp / "items" / "ore_copy.json", {
            "minecraft:item": {"description": {"identifier": "demo:ore"}, "components": {}}
        })
        report = self._analyze("behavior_packs/demo_bp/items/ore.json")
        self.assertIn("DUPLICATE_IDENTIFIER", {f["code"] for f in report["findings"]})

    def test_missing_explicit_namespaced_reference_is_reported(self):
        self._write(self.bp / "recipes" / "broken.json", {
            "minecraft:recipe_shaped": {"key": {"X": {"item": "demo:missing"}}}
        })
        report = self._analyze("behavior_packs/demo_bp/recipes/broken.json")
        self.assertIn("UNRESOLVED_IDENTIFIER", {f["code"] for f in report["findings"]})

    def test_minecraft_vanilla_ids_are_not_reported_as_unresolved(self):
        self._write(self.bp / "recipes" / "vanilla.json", {
            "minecraft:recipe_shaped": {"key": {"X": {"item": "minecraft:stick"}}}
        })
        report = self._analyze("behavior_packs/demo_bp/recipes/vanilla.json")
        unresolved = [f for f in report["findings"] if f.get("reference") == "minecraft:stick"]
        self.assertFalse(unresolved)

    def test_path_resolver_rejects_parent_traversal(self):
        candidates = {"resource_packs/demo_rp/textures/entity/guardian.png": {}}
        resolved = impact._resolve_asset_path(
            self.root,
            self.rp / "entity" / "guardian.entity.json",
            "../../../../resource_packs/demo_rp/textures/entity/guardian.png",
            candidates=candidates,
            pack_root=Path("resource_packs/demo_rp"),
        )
        self.assertIsNone(resolved)

    def test_symlink_is_not_followed(self):
        outside = self.root.parent / (self.root.name + "_outside.json")
        outside.write_text("{}", encoding="utf-8")
        link = self.root / "outside-link.json"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        report = self._analyze("behavior_packs/demo_bp/items/ore.json")
        self.assertNotIn("outside-link.json", {row["path"] for row in report["impact"]})
        outside.unlink(missing_ok=True)

    def test_total_budget_truncation_marks_partial(self):
        report = self._analyze("behavior_packs/demo_bp/items/ore.json", max_total_bytes=10)
        self.assertEqual(report["summary"]["status"], "PARTIAL")
        self.assertTrue(report["coverage"]["files_exceeding_total_byte_budget"])

    def test_file_count_budget_marks_partial(self):
        report = self._analyze("behavior_packs/demo_bp/items/ore.json", max_files=2)
        self.assertTrue(report["coverage"]["truncated"])
        self.assertEqual(report["summary"]["status"], "PARTIAL")

    def test_deterministic_output_for_same_tree(self):
        first = self._analyze("behavior_packs/demo_bp/items/ore.json")
        second = self._analyze("behavior_packs/demo_bp/items/ore.json")
        # Timestamps are intentionally not included in report content.
        self.assertEqual(first, second)

    def test_report_is_json_serializable(self):
        report = self._analyze("behavior_packs/demo_bp/items/ore.json")
        json.dumps(report, ensure_ascii=False, allow_nan=False)

    def test_atomic_output_refuses_overwrite_by_default(self):
        out = self.root / "impact.json"
        out.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(impact.ImpactError, "--overwrite"):
            impact._atomic_write(out, "replace")
        self.assertEqual(out.read_text(encoding="utf-8"), "keep")

    def test_atomic_output_overwrite_is_opt_in(self):
        out = self.root / "impact.json"
        out.write_text("old", encoding="utf-8")
        impact._atomic_write(out, "new", overwrite=True)
        self.assertEqual(out.read_text(encoding="utf-8"), "new")


if __name__ == "__main__":
    unittest.main(verbosity=2)
