from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("build_plugin_archive.py")
PROMPTS = ["create", "audit", "research"]


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def write(repo: Path, path: str, data: str | bytes) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "ci@example.invalid")
    git(repo, "config", "user.name", "CI")
    write(repo, "VERSION", "1.2.3\n")
    root_manifest = {"name": "minecraft-bedrock-engineer", "version": "1.2.3",
                     "extensions": {"com.openai": {"interface": {"defaultPrompt": PROMPTS}}}}
    compat_manifest = {"name": "minecraft-bedrock-engineer", "version": "1.2.3",
                       "interface": {"defaultPrompt": PROMPTS}}
    write(repo, "plugin.json", json.dumps(root_manifest))
    write(repo, ".codex-plugin/plugin.json", json.dumps(compat_manifest))
    server = {"minecraft-bedrock-engineer": {"type": "stdio", "command": "python3",
              "args": ["$" + "{PLUGIN_ROOT}/server/mcp_server.py"]}}
    codex_server = {"minecraft-bedrock-engineer": {**server["minecraft-bedrock-engineer"], "env": {}}}
    write(repo, ".mcp.json", json.dumps({"mcpServers": codex_server}))
    write(repo, "mcp.json", json.dumps({"mcpServers": server}))
    for path, body in {"CHANGELOG.md": "# Plugin package changelog\n\n## 1.2.3 — Fixture release\n",
                       "README.md": "# Minecraft Bedrock Engineer — 1.2.3\n",
                       "archive_safety.py": "# safety\n", "server/mcp_server.py": "print('ok')\n",
                       "skills/example/SKILL.md": "# Skill\n"}.items():
        write(repo, path, body)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "fixture")
    return repo


class BuildPluginArchiveTests(unittest.TestCase):
    def run_builder(self, repo: Path, output: Path, expected: int = 0):
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(repo), "--output", str(output)],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_provenance_and_file_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root); output = root / "out.tar.gz"
            result = self.run_builder(repo, output); report = json.loads(result.stdout)
            self.assertEqual(report["git_commit"], git(repo, "rev-parse", "HEAD"))
            with tarfile.open(output, "r:gz") as tar:
                self.assertIn("BUILD_PROVENANCE.json", tar.getnames())
                prov = json.load(tar.extractfile("BUILD_PROVENANCE.json"))
                self.assertEqual(prov["version"], "1.2.3")
                self.assertTrue(prov["provenance_file_excluded_from_payload_hash"])
                for item in prov["files"]:
                    data = tar.extractfile(item["path"]).read()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
                    self.assertEqual(len(data), item["size_bytes"])
            self.assertEqual(output.with_name(output.name + ".sha256").read_text().split()[0],
                             hashlib.sha256(output.read_bytes()).hexdigest())

    def test_reproducible_for_same_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            a, b = root / "a.tar.gz", root / "b.tar.gz"
            self.run_builder(repo, a); self.run_builder(repo, b)
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_untracked_bytecode_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            write(repo, "server/__pycache__/noise.pyc", b"untracked")
            output = root / "out.tar.gz"; self.run_builder(repo, output)
            with tarfile.open(output, "r:gz") as tar:
                self.assertFalse(any("__pycache__" in x or x.endswith(".pyc") for x in tar.getnames()))

    def test_tracked_bytecode_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            write(repo, "server/__pycache__/noise.pyc", b"tracked")
            git(repo, "add", "."); git(repo, "commit", "-qm", "bad bytecode")
            self.run_builder(repo, root / "out.tar.gz", 1)

    def test_tracked_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            (repo / "server/external.py").symlink_to("../../outside.py")
            git(repo, "add", "server/external.py"); git(repo, "commit", "-qm", "bad symlink")
            self.run_builder(repo, root / "out.tar.gz", 1)

    def test_manifest_version_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            manifest = json.loads((repo / "plugin.json").read_text()); manifest["version"] = "9.9.9"
            write(repo, "plugin.json", json.dumps(manifest))
            git(repo, "add", "plugin.json"); git(repo, "commit", "-qm", "bad version")
            self.run_builder(repo, root / "out.tar.gz", 1)

    def test_missing_mcp_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            git(repo, "rm", "-q", "server/mcp_server.py"); git(repo, "commit", "-qm", "missing server")
            self.run_builder(repo, root / "out.tar.gz", 1)

    def test_uncommitted_worktree_edits_do_not_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            write(repo, "README.md", "uncommitted\n"); output = root / "out.tar.gz"
            self.run_builder(repo, output)
            with tarfile.open(output, "r:gz") as tar:
                self.assertEqual(tar.extractfile("README.md").read(), b"# Minecraft Bedrock Engineer — 1.2.3\n")

    def test_mcp_config_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            write(repo, "mcp.json", json.dumps({"mcpServers": {"other": {"type": "stdio", "command": "python3",
                  "args": ["$" + "{PLUGIN_ROOT}/server/mcp_server.py"]}}}))
            git(repo, "add", "mcp.json"); git(repo, "commit", "-qm", "mcp mismatch")
            self.run_builder(repo, root / "out.tar.gz", 1)

    def test_readme_version_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            write(repo, "README.md", "# Minecraft Bedrock Engineer — 9.9.9\n")
            git(repo, "add", "README.md"); git(repo, "commit", "-qm", "bad README version")
            self.run_builder(repo, root / "out.tar.gz", 1)

    def test_changelog_version_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            write(repo, "CHANGELOG.md", "# Plugin package changelog\n\n## 9.9.9 — Wrong release\n")
            git(repo, "add", "CHANGELOG.md"); git(repo, "commit", "-qm", "bad changelog version")
            self.run_builder(repo, root / "out.tar.gz", 1)

    def test_mcp_env_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            config = json.loads((repo / "mcp.json").read_text())
            config["mcpServers"]["minecraft-bedrock-engineer"]["env"] = {"MODE": "different"}
            write(repo, "mcp.json", json.dumps(config))
            git(repo, "add", "mcp.json"); git(repo, "commit", "-qm", "MCP env mismatch")
            self.run_builder(repo, root / "out.tar.gz", 1)

    def test_mcp_extra_field_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            config = json.loads((repo / "mcp.json").read_text())
            config["mcpServers"]["minecraft-bedrock-engineer"]["cwd"] = "$" + "{PLUGIN_ROOT}"
            write(repo, "mcp.json", json.dumps(config))
            git(repo, "add", "mcp.json"); git(repo, "commit", "-qm", "MCP cwd mismatch")
            self.run_builder(repo, root / "out.tar.gz", 1)

    def test_output_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            target = root / "target.tar.gz"; target.write_bytes(b"safe")
            output = root / "link.tar.gz"; output.symlink_to(target)
            self.run_builder(repo, output, 1)
            self.assertEqual(target.read_bytes(), b"safe")

    def test_tracked_provenance_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = make_repo(root)
            write(repo, "BUILD_PROVENANCE.json", "{}\n")
            git(repo, "add", "BUILD_PROVENANCE.json"); git(repo, "commit", "-qm", "self reference")
            self.run_builder(repo, root / "out.tar.gz", 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
