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
import struct
import sys
import tempfile
import zlib
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
MAX_PNG_BYTES = 16 * 1024 * 1024
MAX_ATLAS_BYTES = 8 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
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


def _atlas_tool() -> dict[str, Any]:
    return {
        "name": "register_texture_atlas",
        "description": (
            "Register an existing PNG in an existing Minecraft Bedrock Resource Pack texture atlas. "
            "Use texture_type=blocks for textures/terrain_texture.json or items for textures/item_texture.json. "
            "Preserves unrelated JSON entries, refuses duplicate identifiers that point elsewhere, and never "
            "follows symlinked paths. It does not create or modify BP/RP item/block definitions; those must "
            "reference the chosen texture identifier. Static checks only; Minecraft runtime remains NOT RUN."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {
                    "type": "string", "minLength": 1, "maxLength": 63,
                    "description": "One existing project directory directly inside the configured workspace, e.g. ruby-addon.",
                },
                "texture_type": {
                    "type": "string", "enum": ["blocks", "items"],
                    "description": "Which vanilla texture atlas to update: blocks or items.",
                },
                "texture_identifier": {
                    "type": "string", "minLength": 1, "maxLength": 63,
                    "description": "New lowercase atlas key, e.g. ruby_ore. Existing conflicting keys are never overwritten.",
                },
                "texture_path": {
                    "type": "string", "minLength": 1, "maxLength": 512,
                    "description": "Project-relative POSIX path to an existing PNG under resource_packs/<project>_RP/textures/blocks/ or textures/items/.",
                },
            },
            "required": ["project_directory", "texture_type", "texture_identifier", "texture_path"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


TOOLS = [_tool(), _atlas_tool()]
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



class AtlasToolError(ValueError):
    """An expected atlas-registry failure with a stable MCP error code."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _valid_project_name(value: Any) -> bool:
    return isinstance(value, str) and PROJECT_NAME_RE.fullmatch(value) is not None and "--" not in value


def _validate_atlas_arguments(raw_args: Any) -> dict[str, str]:
    if not isinstance(raw_args, dict):
        raise ValueError("arguments must be a JSON object")
    required = {"project_directory", "texture_type", "texture_identifier", "texture_path"}
    extras = set(raw_args) - required
    missing = required - set(raw_args)
    if extras:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extras))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    for key, max_length in (("project_directory", 63), ("texture_type", 16), ("texture_identifier", 63), ("texture_path", 512)):
        value = raw_args[key]
        if not isinstance(value, str) or not value or len(value) > max_length:
            raise ValueError(f"{key} must be a non-empty string of at most {max_length} characters")
    if not _valid_project_name(raw_args["project_directory"]):
        raise ValueError("project_directory must be one lowercase kebab-case directory name, not a path")
    if raw_args["texture_type"] not in {"blocks", "items"}:
        raise ValueError("texture_type must be either 'blocks' or 'items'")
    identifier = raw_args["texture_identifier"]
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?", identifier) or ".." in identifier:
        raise ValueError("texture_identifier must be a lowercase atlas key using letters, digits, dot, underscore or hyphen")
    path = raw_args["texture_path"]
    if "\\" in path or "\x00" in path or path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise ValueError("texture_path must be a safe relative POSIX path")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("texture_path must not contain empty, dot or parent-traversal path segments")
    expected_type = raw_args["texture_type"]
    expected_rp = f"{raw_args['project_directory']}_RP"
    if len(parts) < 5 or parts[0] != "resource_packs" or parts[1] != expected_rp or parts[2] != "textures" or parts[3] != expected_type:
        raise ValueError(f"texture_path must be inside resource_packs/{expected_rp}/textures/{expected_type}/")
    if not path.endswith(".png"):
        raise ValueError("texture_path must end with lowercase .png")
    return {key: raw_args[key] for key in required}


def _resolve_project_directory(project_name: str) -> tuple[Path, Path]:
    workspace = _workspace_root()
    candidate = workspace / project_name
    if candidate.is_symlink():
        raise ValueError("project_directory must not be a symlink")
    try:
        project = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"project_directory is unavailable: {project_name}") from exc
    if project.parent != workspace or not project.is_dir():
        raise ValueError("project_directory must be an existing real directory directly under the configured workspace")
    return workspace, project


def _read_valid_png(path: Path) -> tuple[int, int]:
    """Validate PNG chunks, compressed image data, scanline sizes and filters."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise AtlasToolError("TEXTURE_UNAVAILABLE", f"texture file is unavailable: {exc}") from exc
    if len(payload) < 45 or len(payload) > MAX_PNG_BYTES:
        raise AtlasToolError("INVALID_PNG", f"texture PNG must be between 45 bytes and {MAX_PNG_BYTES} bytes")
    if not payload.startswith(PNG_SIGNATURE):
        raise AtlasToolError("INVALID_PNG", "texture file does not have a PNG signature")

    allowed_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    channel_counts = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    width = height = bit_depth = color_type = interlace_method = 0
    seen_ihdr = seen_plte = seen_idat = seen_iend = False
    idat_ended = False
    idat_chunks: list[bytes] = []
    offset = len(PNG_SIGNATURE)
    chunk_count = 0

    while offset < len(payload):
        if len(payload) - offset < 12:
            raise AtlasToolError("INVALID_PNG", "PNG contains a truncated chunk header")
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(payload):
            raise AtlasToolError("INVALID_PNG", "PNG contains a truncated chunk body")
        if not all(65 <= byte <= 90 or 97 <= byte <= 122 for byte in kind):
            raise AtlasToolError("INVALID_PNG", "PNG contains an invalid chunk type")
        data = payload[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + length:end])[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != expected_crc:
            raise AtlasToolError("INVALID_PNG", "PNG chunk checksum failed")

        if chunk_count == 0:
            if kind != b"IHDR" or length != 13:
                raise AtlasToolError("INVALID_PNG", "PNG must begin with a 13-byte IHDR chunk")
            width, height = struct.unpack(">II", data[:8])
            bit_depth, color_type, compression_method, filter_method, interlace_method = data[8:13]
            if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
                raise AtlasToolError("INVALID_PNG", "PNG dimensions are outside the supported texture limits")
            if color_type not in allowed_depths or bit_depth not in allowed_depths[color_type]:
                raise AtlasToolError("INVALID_PNG", "PNG uses an invalid color type and bit-depth combination")
            if compression_method != 0 or filter_method != 0 or interlace_method not in {0, 1}:
                raise AtlasToolError("INVALID_PNG", "PNG uses an unsupported compression, filter or interlace method")
            seen_ihdr = True
        elif kind == b"IHDR":
            raise AtlasToolError("INVALID_PNG", "PNG contains a duplicate IHDR chunk")

        if kind == b"PLTE":
            if seen_plte or seen_idat or color_type in {0, 4}:
                raise AtlasToolError("INVALID_PNG", "PNG palette is duplicated, misplaced or forbidden for its color type")
            if length < 3 or length > 768 or length % 3:
                raise AtlasToolError("INVALID_PNG", "PNG palette length must contain between 1 and 256 RGB entries")
            if color_type == 3 and length // 3 > (1 << bit_depth):
                raise AtlasToolError("INVALID_PNG", "PNG palette contains more entries than its bit depth permits")
            seen_plte = True
        elif kind == b"IDAT":
            if idat_ended:
                raise AtlasToolError("INVALID_PNG", "PNG IDAT chunks must be consecutive")
            seen_idat = True
            idat_chunks.append(data)
        elif kind == b"IEND":
            if length != 0 or end != len(payload):
                raise AtlasToolError("INVALID_PNG", "PNG IEND must be empty and terminate the file")
            if not seen_idat:
                raise AtlasToolError("INVALID_PNG", "PNG must contain image data before IEND")
            seen_iend = True
            offset = end
            chunk_count += 1
            break
        else:
            if seen_idat:
                idat_ended = True
            if kind not in {b"IHDR", b"PLTE"} and not (kind[0] & 0x20):
                raise AtlasToolError("INVALID_PNG", f"PNG contains an unknown critical chunk {kind.decode('ascii')}")

        offset = end
        chunk_count += 1
        if chunk_count > 4096:
            raise AtlasToolError("INVALID_PNG", "PNG contains too many chunks")

    if not (seen_ihdr and seen_idat and seen_iend):
        raise AtlasToolError("INVALID_PNG", "PNG must contain IHDR, IDAT and IEND chunks")
    if color_type == 3 and not seen_plte:
        raise AtlasToolError("INVALID_PNG", "indexed-color PNG must contain a PLTE palette")

    channels = channel_counts[color_type]
    if interlace_method == 0:
        passes = [(width, height)]
    else:
        pass_specs = (
            (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8),
            (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
        )
        passes = []
        for x_start, y_start, x_step, y_step in pass_specs:
            pass_width = 0 if width <= x_start else (width - x_start + x_step - 1) // x_step
            pass_height = 0 if height <= y_start else (height - y_start + y_step - 1) // y_step
            if pass_width and pass_height:
                passes.append((pass_width, pass_height))

    row_sizes = [
        (pass_width * channels * bit_depth + 7) // 8
        for pass_width, _pass_height in passes
    ]
    expected_size = sum((row_size + 1) * pass_height for row_size, (_pass_width, pass_height) in zip(row_sizes, passes))
    compressed = b"".join(idat_chunks)
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(compressed, expected_size + 1)
        if len(decoded) > expected_size or decoder.unconsumed_tail:
            raise AtlasToolError("INVALID_PNG", "PNG image data expands beyond the dimensions declared in IHDR")
        decoded += decoder.flush()
    except zlib.error as exc:
        raise AtlasToolError("INVALID_PNG", "PNG IDAT data is not a valid zlib stream") from exc

    if not decoder.eof or decoder.unused_data or len(decoded) != expected_size:
        raise AtlasToolError("INVALID_PNG", "PNG decompressed image data does not match the dimensions declared in IHDR")

    decoded_offset = 0
    for row_size, (_pass_width, pass_height) in zip(row_sizes, passes):
        for _ in range(pass_height):
            if decoded_offset >= len(decoded) or decoded[decoded_offset] > 4:
                raise AtlasToolError("INVALID_PNG", "PNG scanline contains an invalid filter byte")
            decoded_offset += row_size + 1
    if decoded_offset != len(decoded):
        raise AtlasToolError("INVALID_PNG", "PNG scanline data has an inconsistent length")

    return width, height

def _atomic_update_json(path: Path, encoded: bytes, original_sha256: str | None) -> None:
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise AtlasToolError("UNSAFE_ATLAS_PATH", "atlas parent directory is missing or symlinked")
    if path.is_symlink():
        raise AtlasToolError("UNSAFE_ATLAS_PATH", "refusing to update a symlinked atlas file")
    temp_path: Path | None = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=str(parent))
        temp_path = Path(name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if original_sha256 is None:
            # Atomic no-overwrite creation if another process creates the atlas concurrently.
            os.link(temp_path, path)
            temp_path.unlink()
        else:
            if not path.is_file():
                raise AtlasToolError("ATLAS_CHANGED", "atlas file changed while preparing the update")
            current = path.read_bytes()
            if hashlib.sha256(current).hexdigest() != original_sha256:
                raise AtlasToolError("ATLAS_CHANGED", "atlas file changed during registration; retry after inspecting its current contents")
            if path.is_symlink():
                raise AtlasToolError("UNSAFE_ATLAS_PATH", "refusing to update a symlinked atlas file")
            os.replace(temp_path, path)
        temp_path = None
    except FileExistsError as exc:
        raise AtlasToolError("ATLAS_CHANGED", "atlas file appeared during registration; no file was overwritten") from exc
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def register_texture_atlas(raw_args: Any) -> dict[str, Any]:
    """Safely add an existing PNG to a Bedrock terrain or item texture atlas."""
    args = _validate_atlas_arguments(raw_args)
    _, project = _resolve_project_directory(args["project_directory"])
    project_name = args["project_directory"]
    pack_root = project / "resource_packs" / f"{project_name}_RP"
    for ancestor in (project / "resource_packs", pack_root, pack_root / "textures"):
        if ancestor.is_symlink():
            raise AtlasToolError("UNSAFE_TEXTURE_PATH", "Resource Pack texture path contains a symlink; refusing to register")
    try:
        resolved_pack = pack_root.resolve(strict=True)
        resolved_pack.relative_to(project)
        resolved_textures = (pack_root / "textures").resolve(strict=True)
        resolved_textures.relative_to(resolved_pack)
    except (OSError, ValueError) as exc:
        raise AtlasToolError("RESOURCE_PACK_UNAVAILABLE", "expected Resource Pack and textures directory must exist inside the selected project") from exc
    if not resolved_pack.is_dir() or not resolved_textures.is_dir():
        raise AtlasToolError("RESOURCE_PACK_UNAVAILABLE", "expected Resource Pack and textures directory must be directories")

    parts = args["texture_path"].split("/")
    texture = project.joinpath(*parts)
    current = project
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise AtlasToolError("UNSAFE_TEXTURE_PATH", "texture_path contains a symlinked parent; refusing to register")
        if not current.is_dir():
            raise AtlasToolError("TEXTURE_UNAVAILABLE", "texture_path parent directories must already exist")
    if texture.is_symlink() or not texture.is_file():
        raise AtlasToolError("TEXTURE_UNAVAILABLE", "texture_path must be an existing regular PNG file, not a symlink")
    try:
        resolved_texture = texture.resolve(strict=True)
        resolved_texture.relative_to(resolved_pack)
    except (OSError, ValueError) as exc:
        raise AtlasToolError("UNSAFE_TEXTURE_PATH", "texture_path resolves outside the expected Resource Pack") from exc
    width, height = _read_valid_png(resolved_texture)

    texture_ref = "textures/" + "/".join(parts[3:])[:-4]
    atlas_filename = "terrain_texture.json" if args["texture_type"] == "blocks" else "item_texture.json"
    atlas_path = resolved_textures / atlas_filename
    atlas_relpath = f"resource_packs/{project_name}_RP/textures/{atlas_filename}"
    expected_atlas_name = "atlas.terrain" if args["texture_type"] == "blocks" else "atlas.items"
    original_sha: str | None = None
    if atlas_path.is_symlink():
        raise AtlasToolError("UNSAFE_ATLAS_PATH", "refusing to update a symlinked atlas file")
    if atlas_path.exists():
        if not atlas_path.is_file():
            raise AtlasToolError("INVALID_ATLAS", "atlas path exists but is not a regular file")
        try:
            if atlas_path.stat().st_size > MAX_ATLAS_BYTES:
                raise AtlasToolError("INVALID_ATLAS", f"existing atlas exceeds the {MAX_ATLAS_BYTES}-byte safety limit")
            original_bytes = atlas_path.read_bytes()
            original_sha = hashlib.sha256(original_bytes).hexdigest()
            atlas_data = json.loads(original_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AtlasToolError("INVALID_ATLAS", f"existing atlas is not valid UTF-8 JSON: {exc}") from exc
        if not isinstance(atlas_data, dict):
            raise AtlasToolError("INVALID_ATLAS", "existing atlas root must be a JSON object")
        if atlas_data.get("texture_name") != expected_atlas_name:
            raise AtlasToolError("INVALID_ATLAS", f"existing atlas texture_name must be {expected_atlas_name!r}")
        if not isinstance(atlas_data.get("texture_data"), dict):
            raise AtlasToolError("INVALID_ATLAS", "existing atlas must contain an object-valued texture_data map")
        texture_data = atlas_data["texture_data"]
    else:
        atlas_data = {
            "resource_pack_name": project_name,
            "texture_name": expected_atlas_name,
            "texture_data": {},
        }
        if args["texture_type"] == "blocks":
            atlas_data["padding"] = 8
            atlas_data["num_mip_levels"] = 4
        texture_data = atlas_data["texture_data"]

    identifier = args["texture_identifier"]
    if identifier in texture_data:
        existing = texture_data[identifier]
        if isinstance(existing, dict) and existing.get("textures") == texture_ref:
            return {
                "status": "already_registered",
                "atlas_path": atlas_relpath,
                "texture_type": args["texture_type"],
                "texture_identifier": identifier,
                "texture_reference": texture_ref,
                "sha256": hashlib.sha256(atlas_path.read_bytes()).hexdigest() if atlas_path.is_file() else None,
                "mcp_server_version": SERVER_VERSION,
                "runtime_status": "NOT RUN",
            }
        raise AtlasToolError("IDENTIFIER_CONFLICT", f"texture identifier {identifier!r} already points to a different atlas entry; nothing was overwritten")

    texture_data[identifier] = {"textures": texture_ref}
    encoded = (json.dumps(atlas_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _atomic_update_json(atlas_path, encoded, original_sha)
    return {
        "status": "registered",
        "atlas_path": atlas_relpath,
        "texture_type": args["texture_type"],
        "texture_identifier": identifier,
        "texture_reference": texture_ref,
        "width": width,
        "height": height,
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
        "note": "Atlas registration preserves unrelated entries but does not edit BP/RP item or block definitions. Minecraft import/rendering remains NOT RUN.",
    }

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
            "instructions": "Use generate_texture for procedural PNG creation, then register_texture_atlas to add an existing block/item PNG to the matching RP atlas. Both tools operate only in an existing project workspace; Minecraft runtime is NOT RUN.",
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
            if name == "generate_texture":
                payload = generate_texture(arguments)
            elif name == "register_texture_atlas":
                payload = register_texture_atlas(arguments)
            else:  # TOOL_BY_NAME and dispatch must stay in sync.
                return _jsonrpc_error(request_id, -32602, f"Unsupported tool: {name}")
        except AtlasToolError as exc:
            payload = _error(exc.code, str(exc))
        except FileExistsError as exc:
            payload = _error("OUTPUT_EXISTS", str(exc))
        except ValueError as exc:
            payload = _error("INVALID_ARGUMENT", str(exc))
        except OSError as exc:
            payload = _error("FILE_WRITE_FAILED", f"could not write texture resource safely: {exc}")
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
