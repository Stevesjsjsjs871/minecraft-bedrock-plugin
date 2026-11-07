from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import project_state as ps


class ProjectStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        (self.root / "behavior_packs").mkdir()
        (self.root / "behavior_packs" / "manifest.json").write_text('{"format_version":2}', encoding="utf-8")
        (self.root / "README.md").write_text("initial\n", encoding="utf-8")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "ignored.bin").write_bytes(b"ignored")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
        self.init()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def init(self, *, allow_partial: bool = False) -> dict:
        args = SimpleNamespace(
            project_root=str(self.root), max_file_bytes=1024 * 1024, max_files=1000, exclude=[],
            allow_partial=allow_partial, project_name="Fixture Add-on", target_game_version="1.26.50",
            source_of_truth="synthetic test fixture", pack_root=["behavior_packs/example"],
            constraint=["preserve identifiers"], preserve=["existing mechanics"],
        )
        return ps.init_project(args)

    def load(self) -> dict:
        return ps.load_state(self.root)

    def record(self, category: str = "task", title: str = "Fix issue", status: str = "PLANNED", expected: int | None = None) -> dict:
        current = self.load()
        args = SimpleNamespace(
            project_root=str(self.root), expected_revision=current["revision"] if expected is None else expected,
            category=category, title=title, status=status, details="test details", evidence=["fixture evidence"], source="unit test",
        )
        return ps.record_item(args)

    def test_init_creates_state_and_initial_complete_snapshot(self) -> None:
        state = self.load()
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["project"]["name"], "Fixture Add-on")
        self.assertEqual(state["project"]["target_game_version"], "1.26.50")
        snapshot = ps._read_snapshot(ps._state_paths(self.root)[2], state["latest_snapshot"])
        self.assertIn("behavior_packs/manifest.json", snapshot["inventory"])
        self.assertIn("README.md", snapshot["inventory"])
        self.assertNotIn(".git/ignored.bin", snapshot["inventory"])
        self.assertNotIn("node_modules/ignored.js", snapshot["inventory"])

    def test_init_refuses_existing_state(self) -> None:
        with self.assertRaisesRegex(ps.StateError, "already exists"):
            self.init()

    def test_inspect_reports_clean_then_file_drift(self) -> None:
        clean = ps.inspect_project(self.root, max_file_bytes=1024 * 1024, max_files=1000, excludes=[])
        self.assertEqual(clean["status"], "CLEAN")
        (self.root / "README.md").write_text("changed\n", encoding="utf-8")
        (self.root / "new.json").write_text("{}", encoding="utf-8")
        drift = ps.inspect_project(self.root, max_file_bytes=1024 * 1024, max_files=1000, excludes=[])
        self.assertEqual(drift["status"], "DRIFT")
        self.assertEqual(drift["delta"]["modified"]["paths"], ["README.md"])
        self.assertEqual(drift["delta"]["added"]["paths"], ["new.json"])

    def test_capture_records_add_modify_delete_and_is_revisioned(self) -> None:
        (self.root / "README.md").write_text("updated\n", encoding="utf-8")
        (self.root / "new.json").write_text("{}", encoding="utf-8")
        (self.root / "behavior_packs" / "manifest.json").unlink()
        current = self.load()
        args = SimpleNamespace(project_root=str(self.root), expected_revision=current["revision"], max_file_bytes=1024 * 1024,
                               max_files=1000, exclude=[], allow_partial=False, message="fixture capture")
        result = ps.capture_project(args)
        self.assertEqual(result["status"], "CAPTURED")
        self.assertEqual(result["revision"], 2)
        self.assertEqual(result["delta"]["added"]["paths"], ["new.json"])
        self.assertEqual(result["delta"]["modified"]["paths"], ["README.md"])
        self.assertEqual(result["delta"]["deleted"]["paths"], ["behavior_packs/manifest.json"])
        self.assertFalse((self.root / "behavior_packs" / "manifest.json").exists())

    def test_capture_rejects_stale_revision(self) -> None:
        current = self.load()
        self.record()
        args = SimpleNamespace(project_root=str(self.root), expected_revision=current["revision"], max_file_bytes=1024 * 1024,
                               max_files=1000, exclude=[], allow_partial=False, message=None)
        with self.assertRaisesRegex(ps.StateError, "stale project state"):
            ps.capture_project(args)

    def test_partial_scan_does_not_infer_deletions(self) -> None:
        (self.root / "README.md").unlink()
        (self.root / "large.bin").write_bytes(b"x" * 2048)
        current = self.load()
        args = SimpleNamespace(project_root=str(self.root), expected_revision=current["revision"], max_file_bytes=1024,
                               max_files=1000, exclude=[], allow_partial=False, message=None)
        with self.assertRaisesRegex(ps.StateError, "capture is incomplete"):
            ps.capture_project(args)
        self.assertEqual(self.load()["revision"], 1)
        args.allow_partial = True
        result = ps.capture_project(args)
        self.assertEqual(result["status"], "CAPTURED_PARTIAL")
        self.assertEqual(result["delta"]["deleted"]["paths"], [])
        self.assertEqual(self.load()["last_complete_snapshot"]["id"], self.load()["history"][0]["payload"]["snapshot_id"])

    def test_record_and_update_preserve_per_record_history(self) -> None:
        result = self.record("task", "Implement entity", "PLANNED")
        record_id = result["record"]["id"]
        current = self.load()
        args = SimpleNamespace(project_root=str(self.root), expected_revision=current["revision"], record_id=record_id,
                               status="IN_PROGRESS", details="implementation started", evidence=["source file changed"])
        update = ps.update_item(args)
        self.assertEqual(update["record"]["status"], "IN_PROGRESS")
        self.assertEqual(len(update["record"]["updates"]), 1)
        self.assertEqual(update["record"]["updates"][0]["previous"]["status"], "PLANNED")
        self.assertEqual(ps.verify_project(self.root)["status"], "PASS")

    def test_invalid_category_status_pair_is_rejected(self) -> None:
        current = self.load()
        args = SimpleNamespace(project_root=str(self.root), expected_revision=current["revision"], category="task",
                               title="Bad status", status="APPROVED", details="", evidence=[], source="")
        with self.assertRaisesRegex(ps.StateError, "invalid status"):
            ps.record_item(args)
        self.assertEqual(self.load()["revision"], 1)

    def test_update_requires_a_change(self) -> None:
        item = self.record()["record"]
        current = self.load()
        args = SimpleNamespace(project_root=str(self.root), expected_revision=current["revision"], record_id=item["id"],
                               status=None, details=None, evidence=None)
        with self.assertRaisesRegex(ps.StateError, "requires at least one"):
            ps.update_item(args)

    def test_restore_metadata_only_does_not_change_project_files(self) -> None:
        self.record("task", "first", "PLANNED")
        self.record("note", "second", "RECORDED")
        before = (self.root / "README.md").read_bytes()
        current = self.load()
        args = SimpleNamespace(project_root=str(self.root), expected_revision=current["revision"], revision=1, confirm_metadata_only=True)
        result = ps.restore_revision(args)
        restored = self.load()
        self.assertEqual(result["status"], "METADATA_RESTORED")
        self.assertEqual(restored["revision"], 4)
        self.assertEqual(restored["records"]["task"], [])
        self.assertFalse(result["project_files_changed"])
        self.assertEqual((self.root / "README.md").read_bytes(), before)
        self.assertEqual(restored["history"][-1]["payload"]["project_files_changed"], False)

    def test_restore_requires_explicit_metadata_only_confirmation(self) -> None:
        self.record()
        current = self.load()
        args = SimpleNamespace(project_root=str(self.root), expected_revision=current["revision"], revision=1, confirm_metadata_only=False)
        with self.assertRaisesRegex(ps.StateError, "metadata only"):
            ps.restore_revision(args)

    def test_state_checksum_detects_tampering(self) -> None:
        state_path = ps._state_paths(self.root)[1]
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["project"]["name"] = "tampered"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ps.StateError, "checksum mismatch"):
            ps.load_state(self.root)

    def test_event_chain_detects_history_tampering(self) -> None:
        state_path = ps._state_paths(self.root)[1]
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["history"][0]["summary"] = "tampered"
        ps._seal_state(state)
        state_path.write_text(ps.pretty_json(state), encoding="utf-8")
        with self.assertRaisesRegex(ps.StateError, "event hash mismatch"):
            ps.load_state(self.root)

    def test_snapshot_checksum_detects_tampering(self) -> None:
        state = self.load()
        snapshot_path = ps._state_paths(self.root)[2] / f"{state['latest_snapshot']['id']}.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["inventory"]["README.md"]["size_bytes"] += 1
        snapshot_path.write_text(ps.pretty_json(snapshot), encoding="utf-8")
        with self.assertRaisesRegex(ps.StateError, "snapshot checksum mismatch"):
            ps.load_state(self.root)

    def test_recover_rebuilds_new_state_generation_from_valid_backup(self) -> None:
        self.record("decision", "Preserve IDs", "APPROVED")
        state_path = ps._state_paths(self.root)[1]
        corrupted = state_path.read_text(encoding="utf-8")
        state = json.loads(corrupted)
        state["project"]["name"] = "corrupt edit"
        state_path.write_text(ps.pretty_json(state), encoding="utf-8")
        args = SimpleNamespace(
            project_root=str(self.root), confirm_recovery=True, max_file_bytes=1024 * 1024,
            max_files=1000, exclude=[], allow_partial=False,
        )
        before_files = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file() and ".mbe" not in p.parts)
        result = ps.recover_project(args)
        recovered = self.load()
        after_files = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file() and ".mbe" not in p.parts)
        self.assertEqual(result["status"], "RECOVERED")
        self.assertNotEqual(result["new_project_id"], result["previous_project_id"])
        self.assertEqual(result["restored_records"], 0)  # newest valid backup predates the failed mutation
        self.assertEqual(recovered["revision"], 1)
        self.assertEqual(recovered["history"][0]["kind"], "state.recovered_from_backup")
        self.assertEqual(before_files, after_files)
        self.assertTrue(list(ps._state_paths(self.root)[3].glob("corrupt-state-*.corrupt")))
        self.assertEqual(ps.verify_project(self.root)["status"], "PASS")

    def test_recovery_requires_explicit_confirmation(self) -> None:
        self.record()
        state_path = ps._state_paths(self.root)[1]
        state_path.write_text("broken", encoding="utf-8")
        args = SimpleNamespace(project_root=str(self.root), confirm_recovery=False, max_file_bytes=1024 * 1024,
                               max_files=1000, exclude=[], allow_partial=False)
        with self.assertRaisesRegex(ps.StateError, "--confirm-recovery"):
            ps.recover_project(args)
        self.assertEqual(state_path.read_text(encoding="utf-8"), "broken")

    def test_recovery_refuses_when_current_state_is_valid(self) -> None:
        self.record()
        args = SimpleNamespace(project_root=str(self.root), confirm_recovery=True, max_file_bytes=1024 * 1024,
                               max_files=1000, exclude=[], allow_partial=False)
        with self.assertRaisesRegex(ps.StateError, "current project state is valid"):
            ps.recover_project(args)

    def test_verify_checks_backups(self) -> None:
        self.record()
        report = ps.verify_project(self.root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["backups_checked"], 1)
        self.assertEqual(report["history_events"], 2)

    def test_lock_prevents_concurrent_mutation(self) -> None:
        lock_path = ps._state_paths(self.root)[4]
        with ps.StateLock(lock_path):
            with self.assertRaisesRegex(ps.StateError, "locked"):
                with ps.StateLock(lock_path):
                    pass

    def test_sha256_file_rejects_symlink_and_preserves_target(self) -> None:
        target = self.root / "README.md"
        link = self.root / "hash-link.md"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is not supported")
        with self.assertRaisesRegex(ps.StateError, "non-regular file"):
            ps.sha256_file(link)
        self.assertEqual(target.read_text(encoding="utf-8"), "initial\n")

    def test_sha256_file_rejects_replaced_path_identity(self) -> None:
        target = self.root / "README.md"
        expected = target.lstat()
        replacement = self.root / "replacement.md"
        replacement.write_text("replacement\n", encoding="utf-8")
        target.unlink()
        replacement.rename(target)
        with self.assertRaisesRegex(ps.StateError, "identity changed"):
            ps.sha256_file(target, expected_stat=expected)

    def test_symlink_files_are_skipped_and_make_scan_partial(self) -> None:
        target = self.root / "README.md"
        link = self.root / "alias.md"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is not supported")
        scan = ps._scan_project(self.root, max_file_bytes=1024 * 1024, max_files=1000, excludes=[])
        self.assertFalse(scan["complete"])
        self.assertTrue(any(x["code"] == "SYMLINK_SKIPPED" and x["path"] == "alias.md" for x in scan["issues"]))
        self.assertNotIn("alias.md", scan["inventory"])

    def test_work_order_link_writes_only_to_explicit_output(self) -> None:
        source = self.root / "work-order.json"
        output = self.root / "work-order.linked.json"
        source.write_text(json.dumps({"schema_version": "1.0.0", "status": "PLANNED"}), encoding="utf-8")
        args = SimpleNamespace(project_root=str(self.root), work_order=str(source), output=str(output), overwrite=False, replace_link=False)
        result = ps.link_work_order(args)
        linked = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "LINKED")
        self.assertEqual(linked["project_state"]["project_id"], self.load()["project"]["id"])
        self.assertEqual(linked["project_state"]["revision"], 1)
        self.assertNotIn("project_state", json.loads(source.read_text(encoding="utf-8")))

    def test_work_order_existing_link_requires_explicit_replacement(self) -> None:
        source = self.root / "linked.json"
        source.write_text(json.dumps({"project_state": {"revision": 0}}), encoding="utf-8")
        args = SimpleNamespace(project_root=str(self.root), work_order=str(source), output=str(self.root / "linked2.json"), overwrite=False, replace_link=False)
        with self.assertRaisesRegex(ps.StateError, "already has project_state"):
            ps.link_work_order(args)

    def test_work_order_duplicate_json_keys_are_rejected(self) -> None:
        source = self.root / "duplicate.json"
        source.write_text('{"status":"PLANNED","status":"COMPLETE"}', encoding="utf-8")
        args = SimpleNamespace(project_root=str(self.root), work_order=str(source), output=str(self.root / "out.json"), overwrite=False, replace_link=False)
        with self.assertRaisesRegex(ps.StateError, "duplicate JSON key"):
            ps.link_work_order(args)

    def test_state_directory_symlink_is_rejected(self) -> None:
        state_dir, _, _, _, _ = ps._state_paths(self.root)
        shutil_root = Path(self.tmp.name) / "outside"
        shutil_root.mkdir()
        shutil.rmtree(state_dir)
        try:
            state_dir.symlink_to(shutil_root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlink creation is not supported")
        with self.assertRaisesRegex(ps.StateError, "must not be a symlink"):
            ps.load_state(self.root)

    def test_duplicate_json_keys_rejected_by_state_reader(self) -> None:
        path = self.root / "broken.json"
        path.write_text('{"a":1,"a":2}', encoding="utf-8")
        with self.assertRaisesRegex(ps.StateError, "duplicate JSON key"):
            ps.read_json(path)

    def test_partial_initialization_requires_opt_in(self) -> None:
        state_dir, _, _, _, _ = ps._state_paths(self.root)
        # Create an invalid entry after removing the initialized state.
        shutil.rmtree(state_dir)
        (self.root / "alias.md").symlink_to(self.root / "README.md")
        with self.assertRaisesRegex(ps.StateError, "initial scan is incomplete"):
            self.init(allow_partial=False)
        result = self.init(allow_partial=True)
        self.assertEqual(result["status"], "INITIALIZED_PARTIAL")
        self.assertIsNone(self.load()["last_complete_snapshot"])

    def test_record_requires_expected_revision(self) -> None:
        args = SimpleNamespace(project_root=str(self.root), expected_revision=None, category="note", title="x", status="RECORDED", details="", evidence=[], source="")
        with self.assertRaisesRegex(ps.StateError, "require --expected-revision"):
            ps.record_item(args)

    def test_restore_requires_existing_earlier_revision_backup(self) -> None:
        current = self.load()
        args = SimpleNamespace(project_root=str(self.root), expected_revision=current["revision"], revision=1, confirm_metadata_only=True)
        with self.assertRaisesRegex(ps.StateError, "must be an earlier"):
            ps.restore_revision(args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
