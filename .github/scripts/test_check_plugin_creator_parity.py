from __future__ import annotations

import io
import json
import stat
import tarfile
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from check_plugin_creator_parity import audit_archive


PROMPTS = ["Create", "Audit", "Research"]


class PluginCreatorParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.archive = self.root / "plugin.zip"
        self._write_repo()
        self._write_zip()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_repo(self) -> None:
        compat = {"name": "minecraft-bedrock-engineer", "version": "1.1.1", "interface": {"defaultPrompt": PROMPTS}}
        root_manifest = {
            "name": "minecraft-bedrock-engineer",
            "version": "1.1.1",
            "extensions": {"com.openai": {"interface": {"defaultPrompt": PROMPTS}}},
        }
        config = {"mcpServers": {"core": {"type": "stdio", "command": "python3", "args": ["${PLUGIN_ROOT}/server/mcp_server.py"]}}}
        files = {
            "plugin.json": json.dumps(root_manifest),
            ".codex-plugin/plugin.json": json.dumps(compat),
            ".mcp.json": json.dumps(config),
            "mcp.json": json.dumps(config),
            "VERSION": "1.1.1\n",
            "CHANGELOG.md": "# Changelog\n",
            "README.md": "# README\n",
            "archive_safety.py": "SAFE = True\n",
            "server/mcp_server.py": "def main(): pass\n",
            "skills/demo/SKILL.md": "# Demo\n",
        }
        for relative, content in files.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def _write_zip(self, extra: dict[str, bytes] | None = None) -> None:
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.repo.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(self.repo).as_posix())
            for name, content in (extra or {}).items():
                archive.writestr(name, content)

    def _write_tar(self, path: Path) -> None:
        with tarfile.open(path, "w:gz") as archive:
            for source in sorted(self.repo.rglob("*")):
                if source.is_file():
                    archive.add(source, arcname=source.relative_to(self.repo).as_posix(), recursive=False)

    def test_exact_zip_package_passes(self) -> None:
        report = audit_archive(self.archive, self.repo)
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["archive_type"], "zip")
        self.assertEqual(report["summary"]["byte_identical_files"], 10)

    def test_exact_tar_gz_package_passes(self) -> None:
        tar_path = self.root / "plugin.tar.gz"
        self._write_tar(tar_path)
        report = audit_archive(tar_path, self.repo)
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["archive_type"], "tar")

    def test_changed_source_is_reported_with_hashes(self) -> None:
        (self.repo / "server/mcp_server.py").write_text("def main(): return 1\n", encoding="utf-8")
        report = audit_archive(self.archive, self.repo)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["mismatched"][0]["path"], "server/mcp_server.py")
        self.assertNotEqual(report["mismatched"][0]["archive_sha256"], report["mismatched"][0]["repository_sha256"])

    def test_missing_and_extra_files_are_reported(self) -> None:
        with zipfile.ZipFile(self.archive, "w") as archive:
            for path in sorted(self.repo.rglob("*")):
                if path.is_file() and path.name != "README.md":
                    archive.write(path, path.relative_to(self.repo).as_posix())
            archive.writestr("unexpected.txt", "extra")
        report = audit_archive(self.archive, self.repo)
        self.assertIn("README.md", report["missing"])
        self.assertIn("unexpected.txt", report["extra"])

    def test_duplicate_archive_entry_fails(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.archive, "a") as archive:
                archive.writestr("README.md", "duplicate")
        report = audit_archive(self.archive, self.repo)
        self.assertTrue(any("duplicate archive entry" in item for item in report["errors"]))

    def test_zip_path_traversal_fails(self) -> None:
        self._write_zip({"../outside.txt": b"no"})
        report = audit_archive(self.archive, self.repo)
        self.assertTrue(any("unsafe archive path" in item for item in report["errors"]))

    def test_zip_symlink_entry_fails(self) -> None:
        with zipfile.ZipFile(self.archive, "a") as archive:
            info = zipfile.ZipInfo("server/evil.py")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "../../outside.py")
        report = audit_archive(self.archive, self.repo)
        self.assertTrue(any("archive entry is a symlink" in item for item in report["errors"]))

    def test_tar_path_traversal_fails(self) -> None:
        path = self.root / "traversal.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            info = tarfile.TarInfo("../outside.txt")
            payload = b"no"
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        report = audit_archive(path, self.repo)
        self.assertTrue(any("unsafe archive path" in item for item in report["errors"]))

    def test_tar_symlink_fails(self) -> None:
        path = self.root / "symlink.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            info = tarfile.TarInfo("server/evil.py")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../outside.py"
            archive.addfile(info)
        report = audit_archive(path, self.repo)
        self.assertTrue(any("not a regular file" in item for item in report["errors"]))

    def test_default_prompt_drift_is_reported(self) -> None:
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.repo.rglob("*")):
                if path.is_file() and path.relative_to(self.repo).as_posix() != "plugin.json":
                    archive.write(path, path.relative_to(self.repo).as_posix())
            changed = json.loads((self.repo / "plugin.json").read_text(encoding="utf-8"))
            changed["extensions"]["com.openai"]["interface"]["defaultPrompt"][0] = "Changed"
            archive.writestr("plugin.json", json.dumps(changed))
        report = audit_archive(self.archive, self.repo)
        self.assertTrue(any("default prompts differ" in item for item in report["errors"]))

    def test_version_mismatch_is_reported(self) -> None:
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.repo.rglob("*")):
                if path.is_file() and path.name != "VERSION":
                    archive.write(path, path.relative_to(self.repo).as_posix())
            archive.writestr("VERSION", "1.1.0\n")
        report = audit_archive(self.archive, self.repo)
        self.assertTrue(any("versions differ" in item for item in report["errors"]))

    def test_missing_mcp_server_script_is_reported(self) -> None:
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.repo.rglob("*")):
                if path.is_file() and path.relative_to(self.repo).as_posix() != "server/mcp_server.py":
                    archive.write(path, path.relative_to(self.repo).as_posix())
        report = audit_archive(self.archive, self.repo)
        self.assertTrue(any("server script is absent" in item for item in report["errors"]))

    def test_windows_drive_path_fails(self) -> None:
        self._write_zip({"C:/outside.txt": b"no"})
        report = audit_archive(self.archive, self.repo)
        self.assertTrue(any("unsafe archive path" in item for item in report["errors"]))

    def test_case_insensitive_collision_fails(self) -> None:
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("readme.md", "case collision")
        report = audit_archive(self.archive, self.repo)
        self.assertTrue(any("case-insensitive archive path collision" in item for item in report["errors"]))

    def test_missing_repository_root_fails_closed(self) -> None:
        report = audit_archive(self.archive, self.root / "missing")
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("unable to inspect repository root" in item for item in report["errors"]))

    def test_invalid_archive_fails_closed(self) -> None:
        self.archive.write_bytes(b"not an archive")
        report = audit_archive(self.archive, self.repo)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
