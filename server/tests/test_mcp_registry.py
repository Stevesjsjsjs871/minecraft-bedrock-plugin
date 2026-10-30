from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "minecraft-bedrock-engineer": "mcp_server.py",
    "minecraft-bedrock-texture-generator": "texture_generator_mcp.py",
    "minecraft-bedrock-texture-link-auditor": "texture_link_audit_mcp.py",
    "minecraft-bedrock-entity-authoring": "entity_authoring_mcp.py",
    "minecraft-bedrock-animation-controller-authoring": "animation_controller_mcp.py",
    "minecraft-bedrock-animation-clip-authoring": "animation_clip_mcp.py",
    "minecraft-bedrock-animation-pipeline-audit": "animation_pipeline_audit_mcp.py",
    "minecraft-bedrock-animated-entity-authoring": "animated_entity_bundle_mcp.py",
    "minecraft-bedrock-geometry-uv-auditor": "geometry_uv_audit_mcp.py",
    "minecraft-bedrock-geometry-uv-template": "geometry_uv_template_mcp.py",
    "minecraft-bedrock-texture-painter": "texture_painting_mcp.py",
    "minecraft-bedrock-reference-texture-transfer": "reference_texture_transfer_mcp.py",
    "minecraft-bedrock-uv-mapping-assistant": "uv_mapping_assistant_mcp.py",
    "minecraft-bedrock-visual-reference-analyzer": "visual_reference_analyzer_mcp.py",
    "minecraft-bedrock-reference-mapping-review": "reference_mapping_review_mcp.py",
    "minecraft-bedrock-uv-texture-retarget": "uv_texture_retarget_mcp.py",
}


class McpRegistryHandshakeTests(unittest.TestCase):
    def test_portable_and_compat_registries_match_and_are_data_scoped(self):
        portable = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        compatibility = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(portable["$schema"], "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json")
        self.assertEqual(set(portable["mcpServers"]), set(EXPECTED))
        self.assertEqual(portable["mcpServers"], compatibility["mcpServers"])
        for name, filename in EXPECTED.items():
            config = portable["mcpServers"][name]
            self.assertEqual(config["type"], "stdio")
            self.assertEqual(config["command"], "python3")
            self.assertEqual(config["args"], [f"${{PLUGIN_ROOT}}/server/{filename}"])
            self.assertEqual(config["cwd"], "${PLUGIN_DATA}")
            self.assertEqual(config["env"], {"MINECRAFT_BEDROCK_WORKSPACE": "${PLUGIN_DATA}"})
            self.assertTrue((ROOT / "server" / filename).is_file())

    def test_all_sixteen_servers_complete_initialize_and_tools_list(self):
        portable = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}}
        listing = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        payload = json.dumps(init) + "\n" + json.dumps(listing) + "\n"
        with tempfile.TemporaryDirectory() as workspace:
            for name, filename in EXPECTED.items():
                env = os.environ.copy()
                env["MINECRAFT_BEDROCK_WORKSPACE"] = workspace
                process = subprocess.run(
                    [sys.executable, str(ROOT / "server" / filename)],
                    input=payload,
                    text=True,
                    capture_output=True,
                    cwd=workspace,
                    env=env,
                    timeout=20,
                    check=False,
                )
                self.assertEqual(process.returncode, 0, f"{name}: {process.stderr}")
                lines = process.stdout.splitlines()
                self.assertEqual(len(lines), 2, f"{name}: expected two protocol responses, got {lines!r}")
                responses = [json.loads(line) for line in lines]
                self.assertEqual([item.get("id") for item in responses], [1, 2], name)
                self.assertIn("result", responses[0], name)
                version = responses[0]["result"]["serverInfo"].get("version")
                self.assertTrue(isinstance(version, str) and version, name)
                tools = responses[1]["result"]["tools"]
                self.assertIsInstance(tools, list, name)
                self.assertGreater(len(tools), 0, name)
                self.assertEqual(len({item["name"] for item in tools}), len(tools), name)
                if name == "minecraft-bedrock-engineer":
                    tool_names = {item["name"] for item in tools}
                    self.assertTrue({"creator_tools_status", "creator_tools_catalog", "validate_with_mct", "create_entity_with_mct"}.issubset(tool_names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
