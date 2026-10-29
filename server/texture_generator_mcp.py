#!/usr/bin/env python3
"""Dedicated local MCP server for safe, procedural Minecraft Bedrock PNG textures.

This intentionally runs beside the main Minecraft Bedrock Engineer MCP server:
it adds one focused texture tool without replacing or monkey-patching the main
server, and makes no network requests or subprocess calls.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
try:
    SERVER_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

GENERATOR_PATH = ROOT / "skills" / "visual-resource-pipeline" / "scripts" / "generate_texture.py"
TEXTURE_STYLES = [
    "pixel_noise", "checker", "stripes", "solid", "vertical_gradient",
    "horizontal_gradient", "brick", "stone_noise", "ore_veins", "wood_grain",
]
MAX_DIMENSION = 1024
MAX_PIXELS = 1_048_576
PROJECT_NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def _tool() -> dict[str, Any]:
    return {
        "name": "generate_texture",
        "description": (
            "Generate a deterministic procedural RGBA PNG directly inside an existing Minecraft Bedrock "
            "Resource Pack. The output path must be relative to the selected project and inside "
            "resource_packs/<project>_RP/textures/. Supports ten bounded pixel-art styles, explicit colors, "
            "seed and alpha. Refuses traversal, symlinks, missing folders and existing destinations; it never "
            "overwrites files. This is procedural generation, not AI synthesis or UV-aware painting. "
            "Static output only; Minecraft runtime remains NOT RUN."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {
                    "type": "string", "minLength": 1, "maxLength": 63,
                    "description": "One existing project directory directly inside the configured workspace, e.g. ruby-addon.",
                },
                "output_path": {
                    "type": "string", "minLength": 1, "maxLength": 512,
                    "description": "Canonical project-relative POSIX path inside resource_packs/<project>_RP/textures/, e.g. resource_packs/ruby-addon_RP/textures/blocks/ruby_ore.png.",
                },
                "width": {"type": "integer", "minimum": 1, "maximum": MAX_DIMENSION, "default": 16},
                "height": {"type": "integer", "minimum": 1, "maximum": MAX_DIMENSION, "default": 16},
                "style": {"type": "string", "enum": TEXTURE_STYLES, "default": "pixel_noise"},
                "base_color": {"type": "string", "minLength": 6, "maxLength": 7, "default": "#777777", "description": "Six-digit RGB hex, with optional leading #."},
                "accent_color": {"type": "string", "minLength": 6, "maxLength": 7, "default": "#A0A0A0", "description": "Six-digit RGB hex, with optional leading #."},
                "seed": {"type": "integer", "minimum": -2147483648, "maximum": 2147483647, "default": 1},
                "alpha": {"type": "integer", "minimum": 0, "maximum": 255, "default": 255},
            },
            "required": ["project_directory", "output_path"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    }


TOOLS = [_tool()]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def _validate_arguments(name: str, raw_args: Any) -> dict[str, Any]:
    if name not in TOOL_BY_NAME:
        raise ValueError(f"unknown tool {name!r}")
    if not isinstance(raw_args, dict):
        raise ValueError("arguments must be a JSON object")
    schema = TOOL_BY_NAME[name]["inputSchema"]
    props = schema["properties"]
    extras = set(raw_args) - set(props)
    missing = set(schema["required"]) - set(raw_args)
    if extras:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extras))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")

    normalized: dict[str, Any] = {}
    for key, value in raw_args.items():
        definition = props[key]
        kind = definition["type"]
        if kind == "string":
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            if len(value) < definition.get("minLength", 0) or len(value) > definition.get("maxLength", 1_000_000):
                raise ValueError(f"{key} has an invalid string length")
            if "enum" in definition and value not in definition["enum"]:
                raise ValueError(f"{key} must be one of {definition['enum']}")
        elif kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{key} must be an integer")
            if value < definition.get("minimum", -10**18) or value > definition.get("maximum", 10**18):
                raise ValueError(f"{key} must be between {definition.get('minimum')} and {definition.get('maximum')}")
        normalized[key] = value

    for key, definition in props.items():
        if key not in normalized and "default" in definition:
            normalized[key] = definition["default"]

    project_name = normalized["project_directory"]
    if not PROJECT_NAME_RE.fullmatch(project_name) or "--" in project_name:
        raise ValueError("project_directory must be one lowercase kebab-case directory name, not a path")

    output_path = normalized["output_path"]
    if (
        "\\" in output_path or "\x00" in output_path or output_path.startswith("/")
        or re.match(r"^[A-Za-z]:", output_path)
    ):
        raise ValueError("output_path must be a safe relative POSIX path")
    parts = output_path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("output_path must not contain empty, dot or parent-traversal path segments")
    expected_rp = f"{project_name}_RP"
    if len(parts) < 4 or parts[0] != "resource_packs" or parts[1] != expected_rp or parts[2] != "textures":
        raise ValueError(f"output_path must be inside resource_packs/{expected_rp}/textures/")
    if not output_path.endswith(".png"):
        raise ValueError("output_path must end with lowercase .png")

    if normalized["width"] * normalized["height"] > MAX_PIXELS:
        raise ValueError(f"image cannot exceed {MAX_PIXELS} pixels")
    for color_key in ("base_color", "accent_color"):
        if not re.fullmatch(r"#?[0-9A-Fa-f]{6}", normalized[color_key]):
            raise ValueError(f"{color_key} must be six-digit RGB hex, optionally prefixed with #")
    return normalized


def _workspace_root() -> Path:
    raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    base = Path(raw).expanduser() if raw else Path.cwd()
    try:
        return base.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"Configured workspace does not exist: {base}") from exc


def _resolve_destination(project_name: str, output_path: str) -> tuple[Path, Path]:
    workspace = _workspace_root()
    project_candidate = workspace / project_name
    if project_candidate.is_symlink():
        raise ValueError("project_directory must not be a symlink")
    try:
        project = project_candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"project_directory is unavailable: {project_name}") from exc
    if project.parent != workspace or not project.is_dir():
        raise ValueError("project_directory must be an existing real directory directly under the configured workspace")

    parts = output_path.split("/")
    rp_root = project / "resource_packs" / f"{project_name}_RP"
    for ancestor in (project / "resource_packs", rp_root):
        if ancestor.is_symlink():
            raise ValueError("Resource Pack path contains a symlink; refusing to write")
    try:
        resolved_rp = rp_root.resolve(strict=True)
        resolved_rp.relative_to(project)
    except (OSError, ValueError) as exc:
        raise ValueError("expected Resource Pack does not exist or resolves outside the project") from exc
    if not resolved_rp.is_dir():
        raise ValueError("expected Resource Pack path must be a directory")

    destination = project.joinpath(*parts)
    current = project
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("output_path contains a symlinked parent; refusing to write")
        if not current.is_dir():
            raise ValueError("output_path parent directories must already exist; no folders are created automatically")
    try:
        destination.parent.resolve(strict=True).relative_to(resolved_rp)
    except (OSError, ValueError) as exc:
        raise ValueError("output_path resolves outside the expected Resource Pack") from exc
    if destination.is_symlink() or destination.exists():
        raise FileExistsError(f"refusing to overwrite existing destination: {output_path}")
    return project, destination


def _load_generator():
    if not GENERATOR_PATH.is_file() or GENERATOR_PATH.is_symlink():
        raise RuntimeError("bundled procedural texture generator is missing or unsafe")
    spec = importlib.util.spec_from_file_location("mbe_procedural_texture_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load bundled procedural texture generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate_texture(raw_args: Any) -> dict[str, Any]:
    """Validate the project destination, then create a real PNG without overwrite."""
    args = _validate_arguments("generate_texture", raw_args)
    project, destination = _resolve_destination(args["project_directory"], args["output_path"])
    generator = _load_generator()
    result = generator.write_texture(
        destination,
        width=args["width"],
        height=args["height"],
        style=args["style"],
        base_color=args["base_color"],
        accent_color=args["accent_color"],
        seed=args["seed"],
        alpha=args["alpha"],
        force=False,
    )
    png_bytes = destination.read_bytes()
    result.update({
        "path": args["output_path"],
        "project_directory": args["project_directory"],
        "sha256": hashlib.sha256(png_bytes).hexdigest(),
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
        "generator_kind": "PROCEDURAL",
        "note": "Created a valid PNG using local deterministic algorithms. This is not AI image synthesis, UV-aware entity texture painting, or proof of in-game rendering.",
    })
    return result


def _tool_result(request_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
            "structuredContent": payload,
            "isError": payload.get("status") == "error",
        },
    }


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid JSON-RPC request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {})
    if not isinstance(method, str) or not isinstance(params, dict):
        return _jsonrpc_error(request_id, -32600, "Invalid method or params")
    if "id" not in message:
        # Notifications, including notifications/initialized, receive no reply.
        return None
    if method == "initialize":
        requested = params.get("protocolVersion", "2024-11-05")
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": requested,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-texture-generator", "version": SERVER_VERSION},
            "instructions": "Use generate_texture to create procedural PNGs only inside an existing project's RP textures folder. Outputs are never overwritten; runtime is NOT RUN.",
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str):
            return _jsonrpc_error(request_id, -32602, "tools/call requires a string name")
        if name not in TOOL_BY_NAME:
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = generate_texture(arguments)
        except FileExistsError as exc:
            payload = _error("OUTPUT_EXISTS", str(exc))
        except ValueError as exc:
            payload = _error("INVALID_ARGUMENT", str(exc))
        except OSError as exc:
            payload = _error("FILE_WRITE_FAILED", f"could not write texture safely: {exc}")
        except RuntimeError as exc:
            payload = _error("GENERATOR_UNAVAILABLE", str(exc))
        except Exception as exc:  # Structured failure; do not expose a traceback.
            payload = _error("INTERNAL_ERROR", f"unexpected {type(exc).__name__}: {exc}")
        return _tool_result(request_id, payload)
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    # One JSON-RPC request per line; stdout is protocol-only.
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_message(request)
        except json.JSONDecodeError:
            response = _jsonrpc_error(None, -32700, "Parse error")
        except Exception as exc:
            response = _jsonrpc_error(None, -32603, f"Internal error: {type(exc).__name__}")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
