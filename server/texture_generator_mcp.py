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
from contextlib import contextmanager
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
            "seed and alpha. Validates the generated PNG before returning success. Refuses traversal, symlinks, "
            "missing folders and existing destinations; it never overwrites files. This is procedural generation, "
            "not AI synthesis or UV-aware painting. "
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
            "Preserves unrelated JSON entries, refuses duplicate identifiers that point elsewhere, validates the "
            "PNG's legal IHDR fields, chunk order/CRCs, IDAT decompression and scanline filters, and serializes "
            "registrations with a non-overwriting lock. Existing lock files are never removed automatically. "
            "It does not create or modify BP/RP item/block definitions; those must reference the chosen texture "
            "identifier. Static checks only; Minecraft runtime remains NOT RUN."
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
    actual_width, actual_height = _read_valid_png(destination)
    if (actual_width, actual_height) != (args["width"], args["height"]):
        raise RuntimeError("bundled generator output dimensions do not match the requested dimensions")
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



class DuplicateAtlasKeyError(ValueError):
    """Raised when an existing atlas contains duplicate JSON object keys."""


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateAtlasKeyError(f"duplicate JSON key {key!r}")
        result[key] = value
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
    """Validate PNG chunk structure, CRCs, image metadata and decompressed scanlines."""
    try:
        size = path.stat().st_size
        if size < 45 or size > MAX_PNG_BYTES:
            raise AtlasToolError("INVALID_PNG", f"texture PNG must be between 45 bytes and {MAX_PNG_BYTES} bytes")
        payload = path.read_bytes()
    except AtlasToolError:
        raise
    except OSError as exc:
        raise AtlasToolError("TEXTURE_UNAVAILABLE", f"texture file is unavailable: {exc}") from exc
    if len(payload) < 45 or len(payload) > MAX_PNG_BYTES or len(payload) != size:
        raise AtlasToolError("INVALID_PNG", "texture PNG size changed while it was being read or is outside the safety limits")
    if not payload.startswith(PNG_SIGNATURE):
        raise AtlasToolError("INVALID_PNG", "texture file does not have a PNG signature")

    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    legal_depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = 0
    seen_ihdr = seen_plte = seen_trns = seen_idat = seen_iend = False
    idat_finished = False
    palette_entries: int | None = None
    idat_parts: list[bytes] = []
    chunk_count = 0
    max_chunks = 4096

    while offset < len(payload):
        chunk_count += 1
        if chunk_count > max_chunks:
            raise AtlasToolError("INVALID_PNG", f"PNG exceeds the {max_chunks}-chunk structural limit")
        if len(payload) - offset < 12:
            raise AtlasToolError("INVALID_PNG", "PNG contains a truncated chunk header")
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(payload):
            raise AtlasToolError("INVALID_PNG", "PNG contains a truncated chunk body")
        if any(not (65 <= byte <= 90 or 97 <= byte <= 122) for byte in kind):
            raise AtlasToolError("INVALID_PNG", "PNG chunk type contains non-letter bytes")
        if kind[2] & 0x20:
            raise AtlasToolError("INVALID_PNG", "PNG chunk uses a lowercase reserved third type character")

        data = payload[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + length:end])[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != expected_crc:
            raise AtlasToolError("INVALID_PNG", f"PNG {kind.decode('ascii', 'replace')} chunk checksum failed")

        if not seen_ihdr:
            if kind != b"IHDR" or length != 13:
                raise AtlasToolError("INVALID_PNG", "PNG must begin with a 13-byte IHDR chunk")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", data)
            if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
                raise AtlasToolError("INVALID_PNG", "PNG dimensions are outside the supported texture limits")
            if color_type not in legal_depths or bit_depth not in legal_depths[color_type]:
                raise AtlasToolError("INVALID_PNG", "PNG IHDR uses an illegal bit-depth/color-type combination")
            if compression != 0 or filter_method != 0 or interlace not in {0, 1}:
                raise AtlasToolError("INVALID_PNG", "PNG IHDR uses an unsupported compression, filter or interlace method")
            seen_ihdr = True
        elif kind == b"IHDR":
            raise AtlasToolError("INVALID_PNG", "PNG contains a duplicate IHDR chunk")

        if kind == b"PLTE":
            if seen_plte or seen_trns or seen_idat or length < 3 or length > 768 or length % 3:
                raise AtlasToolError("INVALID_PNG", "PNG PLTE chunk is duplicated, misplaced or has an invalid palette length")
            if color_type in {0, 4}:
                raise AtlasToolError("INVALID_PNG", "PNG grayscale color types must not contain a PLTE chunk")
            palette_entries = length // 3
            if color_type == 3 and palette_entries > (1 << bit_depth):
                raise AtlasToolError("INVALID_PNG", "PNG indexed palette contains more entries than its bit depth allows")
            seen_plte = True
        elif kind == b"tRNS":
            if seen_trns or seen_idat or color_type in {4, 6}:
                raise AtlasToolError("INVALID_PNG", "PNG tRNS chunk is duplicated, misplaced or invalid for its color type")
            if color_type == 0 and length != 2:
                raise AtlasToolError("INVALID_PNG", "grayscale PNG tRNS must contain exactly two bytes")
            if color_type == 2 and length != 6:
                raise AtlasToolError("INVALID_PNG", "truecolor PNG tRNS must contain exactly six bytes")
            if color_type == 3 and (not seen_plte or palette_entries is None or length < 1 or length > palette_entries):
                raise AtlasToolError("INVALID_PNG", "indexed PNG tRNS must follow PLTE and not exceed its palette")
            seen_trns = True
        elif kind == b"IDAT":
            if idat_finished:
                raise AtlasToolError("INVALID_PNG", "PNG IDAT chunks must be consecutive")
            if color_type == 3 and not seen_plte:
                raise AtlasToolError("INVALID_PNG", "indexed PNG must contain PLTE before IDAT")
            seen_idat = True
            idat_parts.append(data)
        else:
            if seen_idat:
                idat_finished = True
            if kind == b"IEND":
                if length != 0 or not seen_idat or end != len(payload):
                    raise AtlasToolError("INVALID_PNG", "PNG IEND must be empty, follow IDAT and terminate the file")
                seen_iend = True
                offset = end
                break
            # PLTE, IDAT and IEND are the only critical chunks besides IHDR.
            if kind[0] & 0x20 == 0 and kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
                raise AtlasToolError("INVALID_PNG", f"PNG contains an unknown critical chunk {kind.decode('ascii')}")

        offset = end

    if not (seen_ihdr and seen_idat and seen_iend):
        raise AtlasToolError("INVALID_PNG", "PNG must contain IHDR, IDAT and IEND chunks")

    # Validate the compressed image stream, not just its chunk CRCs. This rejects
    # structurally plausible PNGs whose IDAT bytes are corrupt or inflate to an
    # impossible scanline layout. Adam7 pass sizes are computed per PNG spec.
    bits_per_pixel = channels_by_type[color_type] * bit_depth
    if interlace == 0:
        passes = ((0, 0, 1, 1),)
    else:
        passes = (
            (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8),
            (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
        )
    pass_rows: list[tuple[int, int]] = []
    expected_size = 0
    for x_start, y_start, x_step, y_step in passes:
        pass_width = (width - x_start + x_step - 1) // x_step if width > x_start else 0
        pass_height = (height - y_start + y_step - 1) // y_step if height > y_start else 0
        if pass_width and pass_height:
            row_bytes = (pass_width * bits_per_pixel + 7) // 8
            pass_rows.append((row_bytes, pass_height))
            expected_size += (row_bytes + 1) * pass_height
    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(b"".join(idat_parts), expected_size + 1)
        if len(decoded) > expected_size or decompressor.unconsumed_tail:
            raise AtlasToolError("INVALID_PNG", "PNG IDAT expands beyond the scanline size declared by IHDR")
        decoded += decompressor.flush()
    except zlib.error as exc:
        raise AtlasToolError("INVALID_PNG", f"PNG IDAT compression stream is invalid: {exc}") from exc
    if len(decoded) != expected_size or not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail:
        raise AtlasToolError("INVALID_PNG", "PNG IDAT data does not decode to the exact scanline size declared by IHDR")

    cursor = 0
    for row_bytes, rows in pass_rows:
        stride = row_bytes + 1
        for _ in range(rows):
            if decoded[cursor] > 4:
                raise AtlasToolError("INVALID_PNG", "PNG scanline uses an unknown filter method")
            cursor += stride
    if cursor != len(decoded):
        raise AtlasToolError("INVALID_PNG", "PNG scanline layout is inconsistent with IHDR")
    return width, height

@contextmanager
def _atlas_update_lock(path: Path):
    """Serialize this tool's read/modify/write cycles for one atlas file.

    A lock file is created with O_EXCL so only one process using this tool can
    register against the atlas at a time. Existing locks are never deleted as
    "stale" automatically: doing so could break a live writer's protection.
    """
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise AtlasToolError("UNSAFE_ATLAS_PATH", "atlas parent directory is missing or symlinked")
    lock_path = parent / f".{path.name}.mbe.lock"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(lock_path, flags, 0o600)
    except FileExistsError as exc:
        raise AtlasToolError("ATLAS_BUSY", f"atlas registration is already locked ({lock_path.name}); retry after the active operation finishes, or inspect/remove the lock only when no texture tool is running") from exc
    identity = os.fstat(fd)
    try:
        stream = os.fdopen(fd, "w", encoding="utf-8")
        fd = -1
        with stream:
            stream.write(f"pid={os.getpid()}\n")
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            current = lock_path.lstat()
            if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                lock_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # Do not mask the original atlas operation failure during cleanup.
            pass


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


def _register_texture_atlas_locked(
    args: dict[str, str],
    project_name: str,
    texture_ref: str,
    width: int,
    height: int,
    atlas_path: Path,
    atlas_relpath: str,
    expected_atlas_name: str,
) -> dict[str, Any]:
    """Read and update one atlas while its per-file registration lock is held."""
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
            if len(original_bytes) > MAX_ATLAS_BYTES:
                raise AtlasToolError("INVALID_ATLAS", f"existing atlas exceeds the {MAX_ATLAS_BYTES}-byte safety limit")
            original_sha = hashlib.sha256(original_bytes).hexdigest()
            atlas_data = json.loads(original_bytes.decode("utf-8"), object_pairs_hook=_unique_json_object)
        except DuplicateAtlasKeyError as exc:
            raise AtlasToolError("INVALID_ATLAS", f"existing atlas contains duplicate JSON keys: {exc}") from exc
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


def register_texture_atlas(raw_args: Any) -> dict[str, Any]:
    """Safely add a fully validated PNG to a Bedrock terrain or item texture atlas."""
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
    with _atlas_update_lock(atlas_path):
        return _register_texture_atlas_locked(
            args, project_name, texture_ref, width, height,
            atlas_path, atlas_relpath, expected_atlas_name,
        )

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
