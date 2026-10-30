from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
REMOTE_ENDPOINT = "https://minecraft-bedrock-plugin.msg2026.workers.dev/mcp"
REMOTE_HEALTH = "https://minecraft-bedrock-plugin.msg2026.workers.dev/health"
REMOTE_WORKER_TOOLS = (
    "bedrock_generate_manifest",
    "bedrock_validate_manifest",
    "bedrock_read_plugin_source",
    "bedrock_plugin_capabilities",
)
CORE_CREATOR_TOOLS = (
    "creator_tools_status",
    "creator_tools_catalog",
    "validate_with_mct",
    "create_entity_with_mct",
)
LOCAL_MCP_SERVERS = {
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


def validate_mcp_package(
    root: Path,
    root_manifest: dict[str, Any],
    compat_manifest: dict[str, Any],
    read_json: Callable[[Path], Any],
) -> tuple[bool, str, set[str]]:
    root = Path(root)
    errors: list[str] = []
    registered_tools: set[str] = set()
    try:
        portable = read_json(root / "mcp.json")
        compatibility = read_json(root / ".mcp.json")
        if not isinstance(portable, dict) or set(portable) != {"$schema", "mcpServers"}:
            errors.append("mcp.json must contain only $schema and mcpServers")
        if isinstance(portable, dict) and portable.get("$schema") != MCP_SCHEMA:
            errors.append("mcp.json schema identifier is not canonical Agent Plugins 1.0.0")
        if not isinstance(compatibility, dict) or set(compatibility) != {"mcpServers"}:
            errors.append(".mcp.json must contain only mcpServers")
        portable_servers = portable.get("mcpServers") if isinstance(portable, dict) else None
        compat_servers = compatibility.get("mcpServers") if isinstance(compatibility, dict) else None
        expected_names = set(LOCAL_MCP_SERVERS)
        if not isinstance(portable_servers, dict) or set(portable_servers) != expected_names:
            errors.append(f"mcp.json must register exactly {len(expected_names)} expected local servers")
        if not isinstance(compat_servers, dict) or set(compat_servers) != expected_names:
            errors.append(f".mcp.json must register exactly {len(expected_names)} expected local servers")
        if isinstance(portable_servers, dict) and isinstance(compat_servers, dict) and portable_servers != compat_servers:
            errors.append("mcp.json and .mcp.json server definitions differ")
        if root_manifest.get("mcpServers") is not None:
            errors.append("portable MCP configuration must live in root mcp.json, not plugin.json")
        if compat_manifest.get("mcpServers") != "./.mcp.json":
            errors.append("compatibility manifest must reference ./.mcp.json")

        if isinstance(portable_servers, dict):
            resolved_root = root.resolve(strict=True)
            for name, filename in LOCAL_MCP_SERVERS.items():
                config = portable_servers.get(name)
                expected = {
                    "type": "stdio",
                    "command": "python3",
                    "args": [f"${{PLUGIN_ROOT}}/server/{filename}"],
                    "env": {"MINECRAFT_BEDROCK_WORKSPACE": "${PLUGIN_DATA}"},
                    "cwd": "${PLUGIN_DATA}",
                }
                if config != expected:
                    errors.append(f"{name} has an invalid STDIO command, args, env or cwd")
                module = root / "server" / filename
                if not module.is_file():
                    errors.append(f"registered module is missing: server/{filename}")
                    continue
                try:
                    module.resolve(strict=True).relative_to(resolved_root)
                except (OSError, ValueError):
                    errors.append(f"registered module escapes package root: server/{filename}")
                    continue
                try:
                    source = module.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    errors.append(f"registered module is not readable UTF-8: server/{filename}")
                    continue
                registered_tools.update(re.findall(r'_tool\(\s*"([^"]+)"', source))
                registered_tools.update(re.findall(r'"name"\s*:\s*"([^"]+)"', source))
                if name == "minecraft-bedrock-engineer":
                    missing_bridge = [tool for tool in CORE_CREATOR_TOOLS if tool not in registered_tools]
                    if missing_bridge:
                        errors.append("core server is missing Creator Tools bridge tools: " + ", ".join(missing_bridge))

        worker_path = root / "cloudflare" / "src" / "index.ts"
        capability_path = root / "cloudflare" / "capabilities.json"
        worker_readme = root / "cloudflare" / "README.md"
        if not worker_path.is_file() or not capability_path.is_file() or not worker_readme.is_file():
            errors.append("Cloudflare Worker source, capability contract or README is missing")
        else:
            worker_source = worker_path.read_text(encoding="utf-8")
            remote_names = re.findall(r'\{\s*name:\s*"([^"]+)"', worker_source)
            if tuple(remote_names) != REMOTE_WORKER_TOOLS:
                errors.append("remote Worker tool list does not match the four-tool contract")
            registered_tools.update(remote_names)
            capabilities = read_json(capability_path)
            remote = capabilities.get("remote", {}) if isinstance(capabilities, dict) else {}
            local = capabilities.get("local", {}) if isinstance(capabilities, dict) else {}
            if remote.get("tool_count") != 4 or set(remote.get("tool_names", [])) != set(REMOTE_WORKER_TOOLS):
                errors.append("cloudflare/capabilities.json remote tool contract is inconsistent")
            if local.get("server_count") != len(LOCAL_MCP_SERVERS):
                errors.append("cloudflare/capabilities.json local server count is inconsistent")
            if capabilities.get("endpoint") != REMOTE_ENDPOINT or capabilities.get("health_url") != REMOTE_HEALTH:
                errors.append("Cloudflare capability contract endpoint/health URL is inconsistent")
            readme_text = worker_readme.read_text(encoding="utf-8")
            if REMOTE_ENDPOINT not in readme_text or REMOTE_HEALTH not in readme_text:
                errors.append("Cloudflare README must document the current remote endpoint and health URL")
    except Exception as exc:
        errors.append(f"MCP package contract could not be read: {type(exc).__name__}: {exc}")

    if errors:
        return False, "; ".join(errors[:12]), registered_tools
    return True, f"{len(LOCAL_MCP_SERVERS)} local STDIO servers, {len(registered_tools)} registered tool names, Creator Tools bridge and four-tool remote Worker contract verified", registered_tools
