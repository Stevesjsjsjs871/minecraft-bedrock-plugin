from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT / "server"
for directory in (ROOT, SERVER_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

EXPECTED_PROMPTS = [
    "Create a new Minecraft Bedrock add-on from scratch or implement a feature in my clean project. Search version-matched samples, make real project file changes only within the selected project, validate the generated BP/RP resources, and report what was and was not verified.",
    "Audit this Bedrock add-on or candidate release. Check archive integrity, BP/RP manifests and dependency links, JSON/JavaScript, resource references, identifiers, and regressions against a baseline. Provide evidence and severity; do not delete resources.",
    "Research this Minecraft Bedrock feature for the exact target version. Prioritize official documentation and matching Mojang samples, verify API and format compatibility, compare viable implementations, cite sources, then implement if I asked for implementation.",
]

EXPECTED_SERVERS = {
    "minecraft-bedrock-engineer": "mcp_server.py",
    "minecraft-bedrock-texture-generator": "texture_generator_mcp.py",
    "minecraft-bedrock-texture-link-auditor": "texture_link_audit_mcp.py",
    "minecraft-bedrock-entity-authoring": "entity_authoring_mcp.py",
    "minecraft-bedrock-animation-controller-authoring": "animation_controller_mcp.py",
}


def _load_server(module_name: str, filename: str):
    path = SERVER_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load MCP server module: {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class MCPRegistryContractTests(unittest.TestCase):
    def test_both_configs_register_the_five_expected_stdio_servers(self):
        normalized_configs = []
        for relative in ("mcp.json", ".mcp.json"):
            config = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            servers = config.get("mcpServers")
            self.assertIsInstance(servers, dict)
            self.assertEqual(set(servers), set(EXPECTED_SERVERS))
            normalized = {}
            for name, filename in EXPECTED_SERVERS.items():
                server = servers[name]
                self.assertEqual(server.get("type"), "stdio")
                self.assertEqual(server.get("command"), "python3")
                self.assertEqual(server.get("args"), [f"${{PLUGIN_ROOT}}/server/{filename}"])
                self.assertTrue((SERVER_DIR / filename).is_file())
                normalized[name] = {key: server.get(key) for key in ("type", "command", "args")}
            normalized_configs.append(normalized)
        self.assertEqual(normalized_configs[0], normalized_configs[1])

    def test_tool_names_are_unique_and_creator_tools_bridge_is_preserved(self):
        modules = [
            _load_server("mbe_core_registry", "mcp_server.py"),
            _load_server("mbe_texture_generator_registry", "texture_generator_mcp.py"),
            _load_server("mbe_texture_audit_registry", "texture_link_audit_mcp.py"),
            _load_server("mbe_entity_authoring_registry", "entity_authoring_mcp.py"),
            _load_server("mbe_animation_controller_registry", "animation_controller_mcp.py"),
        ]
        names = [tool["name"] for module in modules for tool in module.TOOLS]
        self.assertEqual(len(names), len(set(names)), "MCP tool names must be unique across all registered servers")
        required = {
            "create_addon_entity",
            "create_addon_entity_with_geometry",
            "creator_tools_status",
            "creator_tools_catalog",
            "validate_with_mct",
            "create_entity_with_mct",
            "create_animation_controller",
            "validate_animation_controller",
            "generate_texture",
            "register_texture_atlas",
            "audit_texture_links",
        }
        self.assertTrue(required.issubset(set(names)), f"missing required MCP tools: {sorted(required - set(names))}")

    def test_original_three_default_prompts_and_version_markers_are_unchanged(self):
        root_manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        compatibility = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        root_prompts = root_manifest["extensions"]["com.openai"]["interface"]["defaultPrompt"]
        compatibility_prompts = compatibility["interface"]["defaultPrompt"]
        self.assertEqual(root_prompts, EXPECTED_PROMPTS)
        self.assertEqual(compatibility_prompts, EXPECTED_PROMPTS)
        self.assertEqual(root_manifest["version"], compatibility["version"])
        self.assertEqual(root_manifest["version"], (ROOT / "VERSION").read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
