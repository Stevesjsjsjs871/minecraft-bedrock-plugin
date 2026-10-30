"""Static contract tests for the Free Worker and full local STDIO profiles."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = json.loads((ROOT / "cloudflare" / "capabilities.json").read_text(encoding="utf-8"))
WORKER = (ROOT / "cloudflare" / "src" / "index.ts").read_text(encoding="utf-8")
README = (ROOT / "cloudflare" / "README.md").read_text(encoding="utf-8")


def _array_block(pattern: str, source: str, label: str) -> str:
    match = re.search(pattern, source, re.DOTALL)
    if not match:
        raise AssertionError(f"Could not locate {label} declaration")
    return match.group(1)


class CapabilityProfileContractTests(unittest.TestCase):
    def test_remote_tool_catalog_matches_machine_readable_contract(self):
        block = _array_block(r"const tools\s*=\s*\[(.*?)\]\s*as const;", WORKER, "tools")
        names = re.findall(r'\{\s*name:\s*"([^"]+)"', block)
        self.assertEqual(names, PROFILE["remote"]["tool_names"])
        self.assertEqual(len(names), PROFILE["remote"]["tool_count"])
        self.assertEqual(len(names), 4)
        for name in names:
            self.assertIn(chr(96) + name + chr(96), README)

    def test_remote_profile_declares_non_filesystem_scope(self):
        remote = PROFILE["remote"]
        self.assertEqual(remote["transport"], "streamable-http")
        self.assertFalse(remote["executes_local_python_mcp"])
        self.assertFalse(remote["writes_project_files"])
        self.assertFalse(remote["invokes_creator_tools_cli"])
        self.assertGreaterEqual(len(remote["limitations"]), 4)
        self.assertIn("does not execute the existing Python", README)

    def test_worker_module_catalog_matches_local_profile(self):
        block = _array_block(r"const modules\s*=\s*\[(.*?)\];", WORKER, "modules")
        names = re.findall(r'"([a-z0-9_]+)"', block)
        self.assertEqual(names, PROFILE["local"]["module_names"])
        self.assertEqual(len(names), PROFILE["local"]["server_count"])
        self.assertEqual(len(names), 16)

    def test_both_local_configs_register_every_module_safely(self):
        local = PROFILE["local"]
        normalized_configs = []
        prefix = "$" + "{PLUGIN_ROOT}/"
        for config_name in local["config_files"]:
            config = json.loads((ROOT / config_name).read_text(encoding="utf-8"))
            servers = config.get("mcpServers")
            self.assertIsInstance(servers, dict)
            self.assertEqual(len(servers), local["server_count"])
            modules = []
            normalized = {}
            for name, entry in servers.items():
                self.assertEqual(entry.get("type"), "stdio", name)
                self.assertEqual(entry.get("command"), "python3", name)
                args = entry.get("args")
                self.assertIsInstance(args, list)
                self.assertEqual(len(args), 1)
                script = args[0]
                self.assertTrue(script.startswith(prefix), (name, script))
                relative = script[len(prefix):]
                path = Path(relative)
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertTrue((ROOT / path).is_file(), (name, script))
                modules.append(path.stem)
                normalized[name] = {
                    "type": entry.get("type"),
                    "command": entry.get("command"),
                    "args": args,
                    "env": entry.get("env", {}),
                }
            self.assertEqual(modules, local["module_names"])
            normalized_configs.append(normalized)
        self.assertEqual(normalized_configs[0], normalized_configs[1])


if __name__ == "__main__":
    unittest.main()
