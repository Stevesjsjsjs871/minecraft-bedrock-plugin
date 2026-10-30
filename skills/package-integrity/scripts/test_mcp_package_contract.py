from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mcp_package_contract import (
    CORE_CREATOR_TOOLS, LOCAL_MCP_SERVERS, MCP_SCHEMA,
    REMOTE_ENDPOINT, REMOTE_HEALTH, REMOTE_WORKER_TOOLS,
    validate_mcp_package,
)


def strict_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_package(root: Path):
    (root / "server").mkdir(parents=True)
    (root / "cloudflare/src").mkdir(parents=True)
    entries = {}
    for name, filename in LOCAL_MCP_SERVERS.items():
        source = '_tool("dummy_tool", "description", {}, [])\n'
        if name == "minecraft-bedrock-engineer":
            source = "".join(f'_tool("{tool}", "description", {{}}, [])\n' for tool in CORE_CREATOR_TOOLS)
        (root / "server" / filename).write_text(source, encoding="utf-8")
        entries[name] = {
            "type": "stdio",
            "command": "python3",
            "args": [f"${{PLUGIN_ROOT}}/server/{filename}"],
            "env": {"MINECRAFT_BEDROCK_WORKSPACE": "${PLUGIN_DATA}"},
            "cwd": "${PLUGIN_DATA}",
        }
    (root / "mcp.json").write_text(json.dumps({"$schema": MCP_SCHEMA, "mcpServers": entries}), encoding="utf-8")
    (root / ".mcp.json").write_text(json.dumps({"mcpServers": entries}), encoding="utf-8")
    (root / "cloudflare/src/index.ts").write_text(
        "const tools = [" + ",".join('{ name: "' + n + '" }' for n in REMOTE_WORKER_TOOLS) + "] as const;",
        encoding="utf-8",
    )
    (root / "cloudflare/capabilities.json").write_text(json.dumps({
        "endpoint": REMOTE_ENDPOINT,
        "health_url": REMOTE_HEALTH,
        "remote": {"tool_count": 4, "tool_names": list(REMOTE_WORKER_TOOLS)},
        "local": {"server_count": len(LOCAL_MCP_SERVERS)},
    }), encoding="utf-8")
    (root / "cloudflare/README.md").write_text(REMOTE_ENDPOINT + "\n" + REMOTE_HEALTH, encoding="utf-8")


class McpPackageContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_package(self.root)
        self.root_manifest = {}
        self.compat_manifest = {"mcpServers": "./.mcp.json"}

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return validate_mcp_package(self.root, self.root_manifest, self.compat_manifest, strict_json)

    def test_valid_local_and_remote_contract_passes(self):
        ok, message, tools = self.check()
        self.assertTrue(ok, message)
        self.assertTrue(set(CORE_CREATOR_TOOLS).issubset(tools))
        self.assertTrue(set(REMOTE_WORKER_TOOLS).issubset(tools))

    def test_workspace_must_be_plugin_data_scoped(self):
        path = self.root / "mcp.json"
        data = strict_json(path)
        first = next(iter(data["mcpServers"]))
        data["mcpServers"][first]["cwd"] = "../"
        path.write_text(json.dumps(data), encoding="utf-8")
        ok, message, _ = self.check()
        self.assertFalse(ok)
        self.assertIn("cwd", message)

    def test_compatibility_registry_must_match_portable_registry(self):
        path = self.root / ".mcp.json"
        data = strict_json(path)
        data["mcpServers"].pop(next(iter(data["mcpServers"])))
        path.write_text(json.dumps(data), encoding="utf-8")
        ok, message, _ = self.check()
        self.assertFalse(ok)
        self.assertIn("exactly", message)

    def test_core_creator_tools_bridge_is_required(self):
        path = self.root / "server/mcp_server.py"
        path.write_text('_tool("create_addon_project", "description", {}, [])\n', encoding="utf-8")
        ok, message, _ = self.check()
        self.assertFalse(ok)
        self.assertIn("Creator Tools bridge", message)

    def test_remote_worker_tool_catalog_is_exact(self):
        path = self.root / "cloudflare/src/index.ts"
        path.write_text('const tools = [{ name: "bedrock_generate_manifest" }] as const;', encoding="utf-8")
        ok, message, _ = self.check()
        self.assertFalse(ok)
        self.assertIn("four-tool", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
