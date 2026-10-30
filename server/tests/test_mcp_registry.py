from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

ORIGINAL_PROMPTS = [
    "Create a new Minecraft Bedrock add-on from scratch or implement a feature in my clean project. Search version-matched samples, make real project file changes only within the selected project, validate the generated BP/RP resources, and report what was and was not verified.",
    "Audit this Bedrock add-on or candidate release. Check archive integrity, BP/RP manifests and dependency links, JSON/JavaScript, resource references, identifiers, and regressions against a baseline. Provide evidence and severity; do not delete resources.",
    "Research this Minecraft Bedrock feature for the exact target version. Prioritize official documentation and matching Mojang samples, verify API and format compatibility, compare viable implementations, cite sources, then implement if I asked for implementation.",
]


def load_module(index: int, path: Path):
    name = f"mbe_registry_{index}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load MCP server: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class MCPRegistryContractTests(unittest.TestCase):
    def test_both_configs_resolve_every_registered_stdio_server(self):
        configs = []
        for relative in ("mcp.json", ".mcp.json"):
            config = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            servers = config.get("mcpServers")
            self.assertIsInstance(servers, dict)
            self.assertTrue(servers)
            normalized = {}
            for name, server in servers.items():
                self.assertEqual(server.get("type"), "stdio", name)
                self.assertEqual(server.get("command"), "python3", name)
                args = server.get("args")
                self.assertIsInstance(args, list, name)
                roots = [arg.split("$" + "{PLUGIN_ROOT}/", 1)[1] for arg in args
                         if isinstance(arg, str) and "$" + "{PLUGIN_ROOT}/" in arg]
                self.assertEqual(len(roots), 1, name)
                relative_script = roots[0].replace("\\", "/")
                self.assertFalse(relative_script.startswith("/"), name)
                self.assertNotIn("..", Path(relative_script).parts, name)
                script = ROOT / relative_script
                self.assertTrue(script.is_file(), f"{relative}: {name} points to missing {relative_script}")
                normalized[name] = (server.get("type"), server.get("command"), args)
            configs.append(normalized)
        self.assertEqual(configs[0], configs[1])

    def test_registered_tool_names_are_unique_and_required_tools_exist(self):
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        modules = []
        for index, (name, server) in enumerate(config["mcpServers"].items()):
            relative = next(arg.split("$" + "{PLUGIN_ROOT}/", 1)[1]
                            for arg in server["args"] if "$" + "{PLUGIN_ROOT}/" in arg)
            module = load_module(index, ROOT / relative)
            self.assertIsInstance(getattr(module, "TOOLS", None), list, name)
            modules.append(module)
        names = [tool["name"] for module in modules for tool in module.TOOLS]
        self.assertEqual(len(names), len(set(names)), "MCP tool names must be unique across configured servers")
        required = {
            "creator_tools_status", "creator_tools_catalog", "validate_with_mct",
            "create_entity_with_mct", "create_addon_entity_with_geometry",
            "create_animation_controller", "validate_animation_controller",
            "generate_texture", "register_texture_atlas", "audit_texture_links",
        }
        self.assertTrue(required.issubset(set(names)), f"missing required tools: {sorted(required - set(names))}")

    def test_original_three_prompts_remain_unchanged_and_versions_match(self):
        root = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        compat = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        prompts = root["extensions"]["com.openai"]["interface"]["defaultPrompt"]
        self.assertEqual(prompts, compat["interface"]["defaultPrompt"])
        self.assertGreaterEqual(len(prompts), 3)
        self.assertEqual(prompts[:3], ORIGINAL_PROMPTS)
        self.assertEqual(len(prompts), len(set(prompts)))
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(root["version"], compat["version"])
        self.assertEqual(root["version"], version)


if __name__ == "__main__":
    unittest.main(verbosity=2)
