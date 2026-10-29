#!/usr/bin/env python3
"""Local stdio MCP server for Minecraft Bedrock Engineer. Creates new projects and item slices; analysis tools remain read-only."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from archive_safety import (  # noqa: E402
    MAX_ARCHIVE_BYTES,
    MAX_ARCHIVE_MEMBERS,
    MAX_MEMBER_BYTES,
    MAX_UNCOMPRESSED_BYTES,
    validate_zip_limits,
)

VERSION_FILE = ROOT / "VERSION"
SERVER_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
MAX_MEMBERS_RETURNED = 2000
SUPPORTED_SUFFIXES = {".mcaddon", ".mcpack", ".mcworld", ".zip"}
AUDITOR = ROOT / "skills" / "automated-validation" / "scripts" / "bedrock_audit.py"

# Keep the priority workflow short and front-loaded for clients that expose it.
WORKFLOW_INSTRUCTIONS = (
    "Project: create_addon_project. Content writers: create_addon_item, create_addon_block, create_addon_recipe, create_addon_entity. "
    "Writes stay in scaffold; refuse collisions; no fake textures. Samples: search_mojang_samples/read_mojang_sample. "
    "inspect_archive; audit_pack/compare_baseline/diff_packs; get_resource_graph/validate_manifest/audit_geometry/audit_animation. "
    "Cite evidence; runtime NOT RUN unless tested. Audit/reference tools are read-only; optional MCT CLI handoff."
)


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
    *,
    read_only: bool = True,
    destructive: bool = False,
    idempotent: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "idempotentHint": idempotent,
            "openWorldHint": False,
        },
    }


_PATH = {"type": "string", "minLength": 1, "maxLength": 4096, "description": "Path to an archive inside the configured workspace; relative paths are recommended."}
_DOMAIN = {"type": "string", "enum": ["all", "geometry", "animations", "controllers", "textures", "ui", "localization"]}
_SAMPLE_CATEGORIES = [
    "all", "item", "block", "entity_behavior", "recipe", "loot_table", "trading", "function",
    "feature_rule", "feature", "client_entity", "geometry", "animation", "animation_controller",
    "render_controller", "particle", "ui", "texture", "sound", "attachable", "localization",
    "material", "block_model", "json", "script", "other",
]
_SAMPLE_PATH = {
    "type": "string", "minLength": 1, "maxLength": 512,
    "description": "Exact relative path in the version-labelled Mojang sample index, such as behavior_pack/items/apple.json.",
}
MOJANG_SAMPLE_INDEX = ROOT / "skills" / "bedrock-development" / "references" / "mojang-samples-1.26.50.4" / "mojang-samples-index.json.gz"
MOJANG_SAMPLE_REFERENCE_ROOT = ROOT / "skills" / "bedrock-development" / "references" / "mojang-samples-1.26.50.4"
MAX_SAMPLE_OUTPUT_CHARS = 12000
MAX_SAMPLE_READ_BYTES = 2 * 1024 * 1024
_BUNDLED_SAMPLE_FILES = {
    "behavior_pack/manifest.json": "behavior_pack/manifest.json",
    "resource_pack/manifest.json": "resource_pack/manifest.json",
    "behavior_pack/items/apple.json": "behavior_pack/items/apple.json",
    "behavior_pack/blocks/black_concrete_slab.block.json": "behavior_pack/blocks/black_concrete_slab.block.json",
    "behavior_pack/recipes/emerald.json": "behavior_pack/recipes/emerald.json",
    "resource_pack/entity/pig.entity.json": "resource_pack/entity/pig.entity.json",
    "resource_pack/animations/pig.animation.json": "resource_pack/animations/pig.animation.json",
    "resource_pack/models/entity/goat.geo.json": "resource_pack/models/entity/goat.geo.json",
    "documentation/Item.html": "documentation/Item.html",
    "documentation/Blocks.html": "documentation/Blocks.html",
    "documentation/Recipes.html": "documentation/Recipes.html",
    "documentation/Animations.html": "documentation/Animations.html",
    "documentation/Schemas.html": "documentation/Schemas.html",
}
TOOLS = [
    _tool(
        "create_addon_project",
        "Create a NEW Minecraft Bedrock starter project inside the configured workspace. Generates linked Behavior Pack and Resource Pack manifests, standard content folders, README and PROJECT_STATE.md. Creates no gameplay content yet; refuses an existing target and never overwrites files.",
        {
            "project_directory": {"type": "string", "minLength": 1, "maxLength": 63, "description": "A single new directory name, not a path; use lowercase letters, digits and hyphens, for example my-first-addon."},
            "display_name": {"type": "string", "minLength": 1, "maxLength": 80, "description": "Human-readable add-on/project name."},
            "description": {"type": "string", "minLength": 1, "maxLength": 200, "description": "Short project description used in both pack manifests."},
            "target_game_version": {"type": "string", "minLength": 5, "maxLength": 20, "description": "Three-part Minecraft Bedrock target version, such as 1.26.50."},
        },
        ["project_directory", "display_name", "description", "target_game_version"],
        read_only=False,
        destructive=False,
        idempotent=False,
    ),
    _tool(
        "create_addon_item",
        "Create a minimal custom item in an EXISTING project scaffold created by create_addon_project. Writes a BP item definition and merges the RP texture atlas/localization when those files are valid and unambiguous. Refuses conflicting item files/keys, malformed shared resources and unsafe paths; never overwrites the item definition. Optional PNG must already be supplied. Static structure only; runtime remains NOT RUN.",
        {
            "project_directory": {"type": "string", "minLength": 1, "maxLength": 63, "description": "One existing child directory of the configured workspace, e.g. my-first-addon."},
            "item_name": {"type": "string", "minLength": 2, "maxLength": 80, "description": "Human-readable item name, e.g. Ruby Shard."},
            "item_slug": {"type": "string", "minLength": 2, "maxLength": 48, "description": "Lowercase snake_case identifier suffix, e.g. ruby_shard."},
            "texture_path": {"type": "string", "minLength": 1, "maxLength": 200, "description": "Optional project-relative PNG with PNG signature already present inside the RP, e.g. resource_packs/my-addon_RP/textures/items/ruby_shard.png. Leave omitted to create definitions without claiming a texture file exists."},
            "target_game_version": {"type": "string", "minLength": 5, "maxLength": 20, "description": "Three-part numeric target version, e.g. 1.26.50."},
        },
        ["project_directory", "item_name", "item_slug", "target_game_version"],
        read_only=False,
        destructive=False,
        idempotent=False,
    ),
    _tool(
        "create_addon_block",
        "Create a starter custom block in an EXISTING project scaffold. Writes a BP block definition and merges one mapping into RP textures/terrain_texture.json, preserving existing valid mappings. Optional texture PNG must already be supplied. Refuses collisions, malformed shared files and unsafe paths; static only, runtime remains NOT RUN.",
        {
            "project_directory": {"type": "string", "minLength": 1, "maxLength": 63, "description": "One existing child directory of the configured workspace."},
            "block_name": {"type": "string", "minLength": 2, "maxLength": 80, "description": "Human-readable block name, e.g. Ruby Ore."},
            "block_slug": {"type": "string", "minLength": 2, "maxLength": 48, "description": "Lowercase snake_case identifier suffix, e.g. ruby_ore."},
            "texture_path": {"type": "string", "minLength": 1, "maxLength": 200, "description": "Optional project-relative PNG already present in RP/textures/blocks/<block_slug>.png."},
            "target_game_version": {"type": "string", "minLength": 5, "maxLength": 20, "description": "Three-part numeric target version, e.g. 1.26.50."},
        },
        ["project_directory", "block_name", "block_slug", "target_game_version"],
        read_only=False,
        destructive=False,
        idempotent=False,
    ),
    _tool(
        "create_addon_entity",
        "Create a minimal custom entity as one coordinated BP/RP slice: BP entity, RP client entity, geometry and render controller. Validates the linked project and all paths before writing; refuses any output collision; never invents a PNG. Static generation only; runtime remains NOT RUN.",
        {
            "project_directory": {"type": "string", "minLength": 1, "maxLength": 63, "description": "One existing child directory of the configured workspace."},
            "entity_name": {"type": "string", "minLength": 2, "maxLength": 80, "description": "Human-readable entity name, e.g. Forest Golem."},
            "entity_slug": {"type": "string", "minLength": 2, "maxLength": 48, "description": "Lowercase snake_case identifier suffix, e.g. forest_golem."},
            "texture_path": {"type": "string", "minLength": 1, "maxLength": 200, "description": "Optional project-relative PNG already inside this project's RP. If omitted, files reference textures/entity/<entity_slug>.png without creating a fake texture."},
            "target_game_version": {"type": "string", "minLength": 5, "maxLength": 20, "description": "Three-part numeric target version matching the BP/RP scaffold, e.g. 1.26.50."},
        },
        ["project_directory", "entity_name", "entity_slug", "target_game_version"],
        read_only=False,
        destructive=False,
        idempotent=False,
    ),
    _tool(
        "create_addon_recipe",
        "Create a shaped or shapeless crafting-table recipe in an EXISTING project scaffold. Validates the BP/RP scaffold, target version and custom identifiers; writes one new recipes/<slug>.json without overwriting existing files. Ingredients/results must be vanilla IDs or definitions already present in this project's BP. Static output only; runtime remains NOT RUN.",
        {
            "project_directory": {"type": "string", "minLength": 1, "maxLength": 63, "description": "One existing child directory of the configured workspace."},
            "recipe_slug": {"type": "string", "minLength": 2, "maxLength": 48, "description": "Lowercase snake_case recipe identifier suffix, e.g. ruby_shard_from_ore."},
            "recipe_type": {"type": "string", "enum": ["shaped", "shapeless"], "description": "shapeless uses ingredients; shaped uses pattern and key_mapping."},
            "result_identifier": {"type": "string", "minLength": 3, "maxLength": 160, "description": "Namespaced result item/block identifier, e.g. test_addon:ruby_shard."},
            "result_count": {"type": "integer", "minimum": 1, "maximum": 64, "description": "Number of output items; defaults to 1."},
            "ingredients": {"type": "array", "minItems": 1, "maxItems": 9, "items": {"type": "string", "minLength": 3, "maxLength": 160}, "description": "For shapeless recipes only, 1–9 namespaced ingredient IDs such as minecraft:iron_ingot or test_addon:ruby_shard."},
            "pattern": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string", "minLength": 1, "maxLength": 3}, "description": "For shaped recipes only, 1–3 equal-width rows, each 1–3 characters. Use A–Z/0–9 symbols and spaces."},
            "key_mapping": {"type": "object", "minProperties": 1, "maxProperties": 9, "additionalProperties": {"type": "string", "minLength": 3, "maxLength": 160}, "description": "For shaped recipes only, maps each used A–Z/0–9 pattern symbol to a namespaced ingredient ID."},
            "target_game_version": {"type": "string", "minLength": 5, "maxLength": 20, "description": "Three-part numeric target version matching the BP/RP scaffold, e.g. 1.26.50."},
        },
        ["project_directory", "recipe_slug", "recipe_type", "result_identifier", "target_game_version"],
        read_only=False,
        destructive=False,
        idempotent=False,
    ),
    _tool("audit_pack", "Run all supported static checks against a Bedrock ZIP-compatible archive. Returns the full structured report; runtime remains NOT RUN.", {"candidate_path": _PATH}, ["candidate_path"]),
    _tool("compare_baseline", "Compare a candidate archive against a baseline and report additions, removals, modifications and audit findings.", {"candidate_path": _PATH, "baseline_path": _PATH}, ["candidate_path", "baseline_path"]),
    _tool("diff_packs", "Summarize changes between two Bedrock pack archives: file additions/removals/modifications, newly introduced findings, severity changes and unresolved resource-graph regressions. Read-only; no patch is applied.", {"candidate_path": _PATH, "baseline_path": _PATH}, ["candidate_path", "baseline_path"]),
    _tool("get_resource_graph", "Return the static resource reference graph. Choose a fixed domain or all; unresolved/dynamic references are not runtime proof.", {"archive_path": _PATH, "domain": _DOMAIN}, ["archive_path"]),
    _tool("validate_manifest", "Return manifest, UUID and dependency checks and related findings from the static report.", {"archive_path": _PATH}, ["archive_path"]),
    _tool("audit_geometry", "Return geometry, bone, cube, vector and UV checks/findings from the static report.", {"archive_path": _PATH}, ["archive_path"]),
    _tool("audit_animation", "Return animation/controller and related identifier checks/findings from the static report.", {"archive_path": _PATH}, ["archive_path"]),
    _tool("inspect_archive", "List archive metadata and unsafe/duplicate path indicators without extracting files or reading file payloads.", {"archive_path": _PATH}, ["archive_path"]),
    _tool(
        "search_mojang_samples",
        "Search the bundled path/hash/identifier index built from the user-provided Mojang bedrock-samples 1.26.50.4 ZIP. Returns version-labelled example paths and identifiers; does not make network calls or extract the source archive.",
        {
            "query": {"type": "string", "minLength": 1, "maxLength": 160, "description": "Search resource paths, categories and indexed identifiers; examples: geometry goat, minecraft:apple, recipe emerald."},
            "category": {"type": "string", "enum": _SAMPLE_CATEGORIES, "description": "Optional resource type filter; defaults to all."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Maximum number of matches to return; defaults to 10."},
        },
        ["query"],
    ),
    _tool(
        "read_mojang_sample",
        "Read a curated bundled Mojang sample/documentation file, or an indexed text file from a user-supplied sample ZIP located inside the configured workspace. Output is capped and read-only; no files are extracted.",
        {
            "sample_path": _SAMPLE_PATH,
            "archive_path": {"type": "string", "minLength": 1, "maxLength": 4096, "description": "Optional path to the original source ZIP inside the configured workspace. If omitted, only curated bundled examples can be read."},
        },
        ["sample_path"],
    ),
]
TOOL_BY_NAME = {item["name"]: item for item in TOOLS}


def _error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    out: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        out["error"]["details"] = details
    return out


def _workspace_root() -> Path:
    raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    base = Path(raw).expanduser() if raw else Path.cwd()
    try:
        return base.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"Configured workspace does not exist: {base}") from exc



def _resolve_archive(raw: Any) -> Path:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 4096:
        raise ValueError("archive path must be a non-empty string no longer than 4096 characters")
    root = _workspace_root()
    value = Path(raw).expanduser()
    path = value if value.is_absolute() else root / value
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"archive path is unavailable: {raw}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("archive path resolves outside the configured workspace") from exc
    if not resolved.is_file():
        raise ValueError("archive path must identify a regular file")
    if resolved.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported archive extension {resolved.suffix!r}; expected one of {sorted(SUPPORTED_SUFFIXES)}")
    validate_zip_limits(resolved)
    return resolved


def _validate_arguments(name: str, args: Any) -> dict[str, Any]:
    if name not in TOOL_BY_NAME:
        raise ValueError(f"unknown tool {name!r}")
    if not isinstance(args, dict):
        raise ValueError("arguments must be a JSON object")
    schema = TOOL_BY_NAME[name]["inputSchema"]
    props = schema["properties"]
    extras = set(args) - set(props)
    missing = set(schema["required"]) - set(args)
    if extras:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extras))}")
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    normalized: dict[str, Any] = {}
    for key, value in args.items():
        definition = props[key]
        value_type = definition.get("type")
        if value_type == "string":
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            if len(value) < definition.get("minLength", 0) or len(value) > definition.get("maxLength", 1_000_000):
                raise ValueError(f"{key} has an invalid string length")
            if "enum" in definition and value not in definition["enum"]:
                raise ValueError(f"{key} must be one of {definition['enum']}")
        elif value_type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{key} must be an integer")
            if value < definition.get("minimum", -10**18) or value > definition.get("maximum", 10**18):
                raise ValueError(f"{key} must be between {definition.get('minimum')} and {definition.get('maximum')}")
        elif value_type == "array":
            if not isinstance(value, list):
                raise ValueError(f"{key} must be an array")
            if len(value) < definition.get("minItems", 0) or len(value) > definition.get("maxItems", 1_000_000):
                raise ValueError(f"{key} has an invalid number of items")
            item_schema = definition.get("items", {})
            if item_schema.get("type") == "string":
                for index, item in enumerate(value):
                    if not isinstance(item, str):
                        raise ValueError(f"{key}[{index}] must be a string")
                    if len(item) < item_schema.get("minLength", 0) or len(item) > item_schema.get("maxLength", 1_000_000):
                        raise ValueError(f"{key}[{index}] has an invalid string length")
        elif value_type == "object":
            if not isinstance(value, dict):
                raise ValueError(f"{key} must be an object")
            if len(value) < definition.get("minProperties", 0) or len(value) > definition.get("maxProperties", 1_000_000):
                raise ValueError(f"{key} has an invalid number of properties")
            additional = definition.get("additionalProperties")
            if isinstance(additional, dict) and additional.get("type") == "string":
                for obj_key, obj_value in value.items():
                    if not isinstance(obj_value, str):
                        raise ValueError(f"{key}.{obj_key} must be a string")
                    if len(obj_value) < additional.get("minLength", 0) or len(obj_value) > additional.get("maxLength", 1_000_000):
                        raise ValueError(f"{key}.{obj_key} has an invalid string length")
        normalized[key] = value
    if name == "get_resource_graph" and "domain" not in normalized:
        normalized["domain"] = "all"
    if name == "search_mojang_samples":
        normalized.setdefault("category", "all")
        normalized.setdefault("limit", 10)
        if not normalized["query"].strip():
            raise ValueError("query must contain a searchable character")
    if name == "read_mojang_sample" and "archive_path" in normalized and not normalized["archive_path"].strip():
        raise ValueError("archive_path must not be blank when supplied")
    if name == "create_addon_project":
        dirname = normalized["project_directory"]
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", dirname) or "--" in dirname:
            raise ValueError("project_directory must be one lowercase kebab-case directory name (letters/digits with single hyphens), not a path")
        for key in ("display_name", "description"):
            if not normalized[key].strip():
                raise ValueError(f"{key} must not be blank")
        if normalized["display_name"] != normalized["display_name"].strip():
            raise ValueError("display_name must not have leading or trailing whitespace")
        if normalized["description"] != normalized["description"].strip():
            raise ValueError("description must not have leading or trailing whitespace")
        version = normalized["target_game_version"]
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", version):
            raise ValueError("target_game_version must be a three-part numeric version, for example 1.26.50")
    if name == "create_addon_item":
        dirname = normalized["project_directory"]
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", dirname) or "--" in dirname:
            raise ValueError("project_directory must be one lowercase kebab-case directory name, not a path")
        if not normalized["item_name"].strip() or normalized["item_name"] != normalized["item_name"].strip():
            raise ValueError("item_name must be nonblank and have no leading/trailing whitespace")
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", normalized["item_slug"]):
            raise ValueError("item_slug must be lowercase snake_case and start with a letter")
        version = normalized["target_game_version"]
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", version):
            raise ValueError("target_game_version must be a three-part numeric version, for example 1.26.50")
        texture = normalized.get("texture_path")
        if texture is not None:
            if not isinstance(texture, str) or not texture.strip() or texture != texture.strip():
                raise ValueError("texture_path must be nonblank with no surrounding whitespace")
            if "\\" in texture or "\x00" in texture or texture.startswith("/") or re.match(r"^[A-Za-z]:", texture):
                raise ValueError("texture_path must be a safe relative POSIX path")
            parts = texture.split("/")
            if any(part in {"", ".", ".."} for part in parts) or not texture.endswith(".png"):
                raise ValueError("texture_path must be a canonical relative path ending in .png")
    if name == "create_addon_block":
        dirname = normalized["project_directory"]
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", dirname) or "--" in dirname:
            raise ValueError("project_directory must be one lowercase kebab-case directory name, not a path")
        if not normalized["block_name"].strip() or normalized["block_name"] != normalized["block_name"].strip():
            raise ValueError("block_name must be nonblank and have no leading/trailing whitespace")
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", normalized["block_slug"]):
            raise ValueError("block_slug must be lowercase snake_case and start with a letter")
        version = normalized["target_game_version"]
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", version):
            raise ValueError("target_game_version must be a three-part numeric version, for example 1.26.50")
        texture = normalized.get("texture_path")
        if texture is not None:
            if not isinstance(texture, str) or not texture.strip() or texture != texture.strip():
                raise ValueError("texture_path must be nonblank with no surrounding whitespace")
            if "\\" in texture or "\x00" in texture or texture.startswith("/") or re.match(r"^[A-Za-z]:", texture):
                raise ValueError("texture_path must be a safe relative POSIX path")
            parts = texture.split("/")
            if any(part in {"", ".", ".."} for part in parts) or not texture.endswith(".png"):
                raise ValueError("texture_path must be a canonical relative path ending in .png")
    if name == "create_addon_entity":
        dirname = normalized["project_directory"]
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", dirname) or "--" in dirname:
            raise ValueError("project_directory must be one lowercase kebab-case directory name, not a path")
        if not normalized["entity_name"].strip() or normalized["entity_name"] != normalized["entity_name"].strip():
            raise ValueError("entity_name must be nonblank and have no leading/trailing whitespace")
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", normalized["entity_slug"]):
            raise ValueError("entity_slug must be lowercase snake_case and start with a letter")
        version = normalized["target_game_version"]
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", version):
            raise ValueError("target_game_version must be a three-part numeric version, for example 1.26.50")
        texture = normalized.get("texture_path")
        if texture is not None:
            if not texture.strip() or texture != texture.strip():
                raise ValueError("texture_path must be nonblank and have no surrounding whitespace")
            if "\\" in texture or "\x00" in texture or texture.startswith("/") or re.match(r"^[A-Za-z]:", texture):
                raise ValueError("texture_path must be a safe relative POSIX path")
            parts = texture.split("/")
            if any(part in {"", ".", ".."} for part in parts) or not texture.lower().endswith(".png"):
                raise ValueError("texture_path must be a canonical relative path ending in .png")
    if name == "create_addon_recipe":
        dirname = normalized["project_directory"]
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", dirname) or "--" in dirname:
            raise ValueError("project_directory must be one lowercase kebab-case directory name, not a path")
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", normalized["recipe_slug"]):
            raise ValueError("recipe_slug must be lowercase snake_case and start with a letter")
        if normalized["recipe_type"] not in {"shaped", "shapeless"}:
            raise ValueError("recipe_type must be shaped or shapeless")
        identifier_pattern = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_.-]+$")
        if not identifier_pattern.fullmatch(normalized["result_identifier"]):
            raise ValueError("result_identifier must be a lowercase namespaced identifier such as namespace:item_name")
        version = normalized["target_game_version"]
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", version):
            raise ValueError("target_game_version must be a three-part numeric version, for example 1.26.50")
        normalized.setdefault("result_count", 1)
        count = normalized["result_count"]
        if isinstance(count, bool) or not isinstance(count, int) or not (1 <= count <= 64):
            raise ValueError("result_count must be an integer from 1 to 64")
        if normalized["recipe_type"] == "shapeless":
            if "ingredients" not in normalized:
                raise ValueError("shapeless recipes require ingredients")
            if "pattern" in normalized or "key_mapping" in normalized:
                raise ValueError("shapeless recipes accept ingredients only, not pattern/key_mapping")
            if not isinstance(normalized["ingredients"], list) or not 1 <= len(normalized["ingredients"]) <= 9:
                raise ValueError("shapeless recipes require 1 to 9 ingredients")
            for ingredient in normalized["ingredients"]:
                if not isinstance(ingredient, str) or not identifier_pattern.fullmatch(ingredient):
                    raise ValueError("each ingredient must be a lowercase namespaced identifier such as minecraft:iron_ingot")
        else:
            if "ingredients" in normalized:
                raise ValueError("shaped recipes accept pattern/key_mapping, not ingredients")
            if "pattern" not in normalized or "key_mapping" not in normalized:
                raise ValueError("shaped recipes require both pattern and key_mapping")
            pattern = normalized["pattern"]
            key_mapping = normalized["key_mapping"]
            if not isinstance(pattern, list) or not 1 <= len(pattern) <= 3:
                raise ValueError("pattern must contain 1 to 3 rows")
            if any(not isinstance(row, str) or not 1 <= len(row) <= 3 for row in pattern):
                raise ValueError("each pattern row must contain 1 to 3 characters")
            if len({len(row) for row in pattern}) != 1:
                raise ValueError("all shaped recipe rows must have equal width")
            if any(any(ord(char) < 32 for char in row) for row in pattern):
                raise ValueError("pattern cannot contain control characters")
            if any(not re.fullmatch(r"[A-Z0-9]", symbol) for symbol in key_mapping):
                raise ValueError("key_mapping symbols must be one uppercase letter or digit")
            used_symbols = {char for row in pattern for char in row if char != " "}
            if not used_symbols:
                raise ValueError("pattern must use at least one ingredient symbol")
            if used_symbols != set(key_mapping):
                raise ValueError("key_mapping keys must exactly match the non-space symbols used in pattern")
            for symbol, ingredient in key_mapping.items():
                if not isinstance(ingredient, str) or not identifier_pattern.fullmatch(ingredient):
                    raise ValueError(f"key_mapping.{symbol} must be a lowercase namespaced identifier")
    return normalized


def _sample_category(path: str) -> str:
    """Classify version-labelled examples shipped with the source tree."""
    for prefix, category in (
        ("resource_pack/models/entity/", "geometry"),
        ("resource_pack/animations/", "animation"),
        ("resource_pack/entity/", "client_entity"),
        ("behavior_pack/items/", "item"),
        ("behavior_pack/blocks/", "block"),
        ("behavior_pack/recipes/", "recipe"),
    ):
        if path.startswith(prefix):
            return category
    return "other"


def _sample_identifiers(value: Any) -> list[str]:
    """Harvest literal identifiers from curated JSON examples."""
    found: set[str] = set()
    def visit(node: Any, depth: int = 0) -> None:
        if depth > 16:
            return
        if isinstance(node, dict):
            for key, child in node.items():
                if key == "identifier" and isinstance(child, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", child):
                    found.add(child)
                elif key in {"geometry", "animation", "animation_controller", "render_controller"}:
                    if isinstance(child, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", child):
                        found.add(child)
                    elif isinstance(child, dict):
                        found.update(v for v in child.values() if isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", v))
                visit(child, depth + 1)
        elif isinstance(node, list):
            for child in node[:5000]:
                visit(child, depth + 1)
    visit(value)
    return sorted(found)[:500]


def _build_curated_mojang_sample_index() -> dict[str, Any]:
    """Build a small, honest fallback when the generated full index is not packaged."""
    metadata_path = MOJANG_SAMPLE_REFERENCE_ROOT / "INDEX_METADATA.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        reference_root = MOJANG_SAMPLE_REFERENCE_ROOT.resolve(strict=True)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"curated Mojang sample references are unavailable or invalid: {exc}") from exc
    if not isinstance(metadata, dict) or not isinstance(metadata.get("target_version"), str):
        raise ValueError("curated Mojang sample metadata has an invalid shape")

    entries: list[dict[str, Any]] = []
    for sample_path, bundled_rel in _BUNDLED_SAMPLE_FILES.items():
        try:
            file_path = (reference_root / bundled_rel).resolve(strict=True)
            file_path.relative_to(reference_root)
            if not file_path.is_file() or file_path.stat().st_size > MAX_SAMPLE_READ_BYTES:
                continue
            raw = file_path.read_bytes()
            content = raw.decode("utf-8")
        except (OSError, RuntimeError, ValueError, UnicodeDecodeError):
            continue
        parsed: Any = None
        json_parsed = False
        if file_path.suffix.lower() == ".json":
            try:
                parsed = json.loads(content)
                json_parsed = isinstance(parsed, (dict, list))
            except json.JSONDecodeError:
                pass
        entries.append({
            "path": sample_path,
            "category": _sample_category(sample_path),
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "identifiers": _sample_identifiers(parsed) if json_parsed else [],
            "json_parsed": json_parsed,
            "search_terms": sorted(set(re.findall(r"[a-z0-9_.:-]{3,}", content.lower())))[:12000],
        })
    if not entries:
        raise ValueError("no readable curated Mojang sample examples are available")
    return {
        "target_version": metadata["target_version"],
        "source": "mojang_bedrock_samples_curated_fallback",
        "archive_sha256": metadata.get("zip_sha256"),
        "archive_stats": {
            "source_archive_entry_count": metadata.get("entry_count"),
            "source_archive_indexed_count": metadata.get("indexed_count"),
            "curated_fallback_entry_count": len(entries),
            "full_index_available": False,
        },
        "index_mode": "curated_fallback",
        "entries": entries,
    }


def _load_mojang_sample_index() -> dict[str, Any]:
    """Load the full offline index, or fall back to packaged curated examples."""
    if not MOJANG_SAMPLE_INDEX.is_file():
        return _build_curated_mojang_sample_index()
    try:
        with gzip.open(MOJANG_SAMPLE_INDEX, "rt", encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, EOFError, json.JSONDecodeError) as exc:
        raise ValueError(f"bundled Mojang sample index is unavailable or invalid: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise ValueError("bundled Mojang sample index has an invalid shape")
    payload.setdefault("index_mode", "full_index")
    return payload


def _search_mojang_samples(args: dict[str, Any]) -> dict[str, Any]:
    payload = _load_mojang_sample_index()
    query = " ".join(args["query"].strip().lower().split())
    tokens = re.findall(r"[a-z0-9_.:-]+", query)
    if not tokens:
        raise ValueError("query must contain at least one letter, digit, identifier or path character")
    category = args["category"]
    limit = args["limit"]
    matches: list[tuple[int, dict[str, Any]]] = []
    for entry in payload["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        if category != "all" and entry.get("category") != category:
            continue
        path_text = entry["path"].lower()
        category_text = str(entry.get("category", "")).lower()
        ids = entry.get("identifiers") if isinstance(entry.get("identifiers"), list) else []
        id_text = " ".join(v.lower() for v in ids if isinstance(v, str))
        search_terms = entry.get("search_terms") if isinstance(entry.get("search_terms"), list) else []
        search_text = " ".join(v.lower() for v in search_terms if isinstance(v, str))
        score = 0
        if query in path_text:
            score += 24
        if query in id_text:
            score += 30
        if search_text and query in search_text:
            score += 8
        matched = 0
        for token in tokens:
            token_match = False
            if token in path_text:
                score += 7
                token_match = True
                if token in path_text.split("/"):
                    score += 2
                filename_stem = Path(path_text).name.split(".")[0]
                stem_parts = re.split(r"[^a-z0-9]+", filename_stem)
                if token == filename_stem:
                    score += 40
                elif token in stem_parts:
                    score += 14
                elif token in filename_stem:
                    score += 3
            if token in id_text:
                score += 10
                token_match = True
            if token in search_text:
                score += 2
                token_match = True
            if token in category_text:
                score += 3
                token_match = True
            if token_match:
                matched += 1
        if matched == 0:
            continue
        if matched == len(tokens):
            score += 6
        sample_path = entry["path"]
        bundled_rel = _BUNDLED_SAMPLE_FILES.get(sample_path)
        matches.append((score, {
            "path": sample_path,
            "category": entry.get("category", "other"),
            "size_bytes": entry.get("size_bytes"),
            "sha256": entry.get("sha256") or None,
            "identifiers": [v for v in ids if isinstance(v, str)][:20],
            "json_parsed": entry.get("json_parsed") is True,
            "bundled_reference": str((MOJANG_SAMPLE_REFERENCE_ROOT / bundled_rel).relative_to(ROOT)) if bundled_rel else None,
        }))
    matches.sort(key=lambda item: (-item[0], item[1]["path"]))
    total = len(matches)
    return {
        "status": "completed",
        "query": args["query"].strip(),
        "category": category,
        "target_version": payload.get("target_version"),
        "source": payload.get("source"),
        "source_archive_sha256": payload.get("archive_sha256"),
        "index_stats": payload.get("archive_stats"),
        "index_mode": payload.get("index_mode", "full_index"),
        "total_matches": total,
        "truncated": total > limit,
        "results": [result for _, result in matches[:limit]],
        "limitations": [
            "This is an index of paths, hashes and selected literal identifiers, not a complete schema validator.",
            "A bundled_reference means a small curated example is packaged. Other sample contents require the user's original ZIP to be available to read_mojang_sample inside the configured workspace.",
            "The sample set is labelled 1.26.50.4; it does not itself prove every format is compatible with every 1.26.50 runtime.",
        ],
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
    }


def _read_mojang_sample(args: dict[str, Any]) -> dict[str, Any]:
    payload = _load_mojang_sample_index()
    sample_path = args["sample_path"]
    if not _safe_indexed_sample_path(sample_path):
        raise ValueError("sample_path must be a canonical relative POSIX path from the bundled Mojang sample index")
    indexed = next((entry for entry in payload["entries"] if isinstance(entry, dict) and entry.get("path") == sample_path), None)
    if indexed is None:
        raise ValueError("sample_path is not present in the bundled sample index")
    suffix = Path(sample_path).suffix.lower()
    if suffix not in {".json", ".html", ".md", ".lang", ".molang", ".txt", ".js", ".ts"}:
        raise ValueError("binary/sample asset content is not exposed by this read tool; use user-provided assets directly under their applicable license")
    source = "bundled_curated_sample"
    if "archive_path" in args:
        archive = _resolve_archive(args["archive_path"])
        try:
            with zipfile.ZipFile(archive) as zf:
                matches = [info for info in zf.infolist() if not info.is_dir() and info.filename == sample_path]
                if not matches:
                    raise ValueError("sample_path is not present in the supplied archive")
                if len(matches) != 1:
                    raise ValueError("sample_path occurs more than once in the supplied archive; refusing ambiguous duplicate entries")
                info = matches[0]
                if info.file_size > MAX_SAMPLE_READ_BYTES:
                    raise ValueError(f"sample file exceeds the {MAX_SAMPLE_READ_BYTES}-byte read limit")
                content_bytes = zf.read(info)
        except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
            raise ValueError(f"unable to read sample file: {exc}") from exc
        source = "user_supplied_archive"
    else:
        bundled = _BUNDLED_SAMPLE_FILES.get(sample_path)
        if not bundled:
            return {
                "status": "not_bundled",
                "sample_path": sample_path,
                "category": indexed.get("category"),
                "sha256": indexed.get("sha256") or None,
                "target_version": payload.get("target_version"),
                "message": "This path is indexed but its content is not bundled. Put the original sample ZIP inside the configured workspace and pass its archive_path to read_mojang_sample.",
                "runtime_status": "NOT RUN",
            }
        file_path = (MOJANG_SAMPLE_REFERENCE_ROOT / bundled).resolve(strict=True)
        try:
            file_path.relative_to(MOJANG_SAMPLE_REFERENCE_ROOT.resolve(strict=True))
        except ValueError as exc:
            raise ValueError("bundled sample reference resolves outside its reference directory") from exc
        if not file_path.is_file() or file_path.stat().st_size > MAX_SAMPLE_READ_BYTES:
            raise ValueError("bundled sample is unavailable or exceeds the read limit")
        content_bytes = file_path.read_bytes()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return {"status": "error", "error": {"code": "SAMPLE_NOT_TEXT", "message": "sample file is not UTF-8 text"}}
    limit = MAX_SAMPLE_OUTPUT_CHARS
    truncated = len(content) > limit
    excerpt = content[:limit]
    digest = __import__("hashlib").sha256(content_bytes).hexdigest()
    indexed_digest = indexed.get("sha256") if isinstance(indexed.get("sha256"), str) else ""
    return {
        "status": "completed",
        "sample_path": sample_path,
        "category": indexed.get("category"),
        "target_version": payload.get("target_version"),
        "source_archive_sha256": payload.get("archive_sha256"),
        "index_mode": payload.get("index_mode", "full_index"),
        "content_sha256": digest,
        "content_hash_matches_index": digest == indexed_digest if indexed_digest else None,
        "source": source,
        "truncated": truncated,
        "content_characters": len(content),
        "content_excerpt": excerpt,
        "notice": "Mojang sample reference. Adapt to a custom namespace and verify target-version compatibility; do not copy vanilla-only internal fields or redistribute vanilla assets automatically.",
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
    }


def _safe_indexed_sample_path(value: str) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return False
    parts = value.split("/")
    return not value.startswith("/") and all(part not in {"", ".", ".."} for part in parts) and not re.match(r"^[A-Za-z]:", value)


def _create_addon_project(args: dict[str, Any]) -> dict[str, Any]:
    """Scaffold a new linked BP/RP project under the configured workspace root."""
    workspace = _workspace_root()
    project_dir = args["project_directory"]
    target = workspace / project_dir
    if target.exists() or target.is_symlink():
        raise ValueError(f"target already exists; refusing to overwrite: {project_dir}")

    version_parts = [int(part) for part in args["target_game_version"].split(".")]
    display_name = args["display_name"]
    description = args["description"]
    namespace = re.sub(r"[^a-z0-9_]", "_", project_dir.lower().replace("-", "_"))
    if not namespace or not namespace[0].isalpha():
        namespace = f"addon_{namespace}"

    bp_folder = f"{project_dir}_BP"
    rp_folder = f"{project_dir}_RP"
    bp_header_uuid, bp_module_uuid, rp_header_uuid, rp_module_uuid = [str(uuid.uuid4()) for _ in range(4)]
    pack_version = [1, 0, 0]
    bp_manifest = {
        "format_version": 2,
        "header": {
            "name": f"{display_name} - Behavior Pack",
            "description": description,
            "uuid": bp_header_uuid,
            "version": pack_version,
            "min_engine_version": version_parts,
        },
        "modules": [{
            "type": "data",
            "description": f"{display_name} behavior data",
            "uuid": bp_module_uuid,
            "version": pack_version,
        }],
        "dependencies": [{"uuid": rp_header_uuid, "version": pack_version}],
    }
    rp_manifest = {
        "format_version": 2,
        "header": {
            "name": f"{display_name} - Resource Pack",
            "description": description,
            "uuid": rp_header_uuid,
            "version": pack_version,
            "min_engine_version": version_parts,
        },
        "modules": [{
            "type": "resources",
            "description": f"{display_name} resources",
            "uuid": rp_module_uuid,
            "version": pack_version,
        }],
    }

    bp_dirs = ["entities", "items", "blocks", "recipes", "loot_tables", "spawn_rules", "functions"]
    rp_dirs = ["entity", "models/entity", "textures/entity", "textures/items", "textures/blocks", "animations", "animation_controllers", "render_controllers", "attachables", "particles", "ui", "texts"]
    created_files: list[str] = []
    created_root = False
    try:
        # mkdir is the reservation: it fails atomically if a path appears after the check above.
        target.mkdir()
        created_root = True
        bp_root = target / "behavior_packs" / bp_folder
        rp_root = target / "resource_packs" / rp_folder
        for folder in bp_dirs:
            (bp_root / folder).mkdir(parents=True, exist_ok=True)
        for folder in rp_dirs:
            (rp_root / folder).mkdir(parents=True, exist_ok=True)

        def write_text(relative: str, content: str) -> None:
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            created_files.append(relative.replace("\\", "/"))

        write_text(f"behavior_packs/{bp_folder}/manifest.json", json.dumps(bp_manifest, ensure_ascii=False, indent=2) + "\n")
        write_text(f"resource_packs/{rp_folder}/manifest.json", json.dumps(rp_manifest, ensure_ascii=False, indent=2) + "\n")
        project_readme = f"""# {display_name}

{description}

## Project scaffold

- Target Minecraft Bedrock version: `{args['target_game_version']}`
- Namespace suggestion for custom identifiers: `{namespace}`
- Behavior Pack: `behavior_packs/{bp_folder}`
- Resource Pack: `resource_packs/{rp_folder}`
- The Behavior Pack has a manifest dependency on the Resource Pack's header UUID, so activating the BP can activate the linked RP.

## Next development steps

1. Define the first playable feature and its acceptance criteria.
2. Add the smallest related BP/RP files; avoid placeholder gameplay resources.
3. Validate JSON, manifest UUID/dependency links and every cross-pack reference.
4. Run the static audit and compare against a baseline after meaningful changes.
5. Import into the target Minecraft build and test in-game; static checks are not runtime proof.

No Script API module, JavaScript, entity, block, item, texture, geometry or animation has been generated yet.
"""
        write_text("README.md", project_readme)
        state = f"""# PROJECT_STATE

- Project: {display_name}
- Directory: `{project_dir}`
- Target Minecraft Bedrock: `{args['target_game_version']}`
- Namespace suggestion: `{namespace}`
- Status: scaffold created; gameplay features not implemented yet
- Behavior Pack root: `behavior_packs/{bp_folder}`
- Resource Pack root: `resource_packs/{rp_folder}`
- BP header UUID: `{bp_header_uuid}`
- RP header UUID: `{rp_header_uuid}`
- BP dependency on RP header UUID: verified in generated manifest
- Pack/module UUID uniqueness: generated with Python UUIDv4; static inspection still recommended
- Runtime test status: NOT RUN

## User-approved scope

{description}

## First milestone

Translate the requested idea into a feature plan with affected BP/RP files, exact-version documentation, acceptance criteria, and a validation strategy before implementing content.

## Change log

- Initial BP/RP project scaffold generated by Minecraft Bedrock Engineer {SERVER_VERSION}.
"""
        write_text("PROJECT_STATE.md", state)
    except FileExistsError as exc:
        if created_root:
            shutil.rmtree(target, ignore_errors=True)
        raise ValueError(f"target already exists; refusing to overwrite: {project_dir}") from exc
    except Exception:
        if created_root:
            shutil.rmtree(target, ignore_errors=True)
        raise

    return {
        "status": "created",
        "project_name": display_name,
        "project_directory": str(target),
        "workspace_root": str(workspace),
        "target_game_version": args["target_game_version"],
        "namespace_suggestion": namespace,
        "behavior_pack": {"path": f"behavior_packs/{bp_folder}", "header_uuid": bp_header_uuid, "module_uuid": bp_module_uuid},
        "resource_pack": {"path": f"resource_packs/{rp_folder}", "header_uuid": rp_header_uuid, "module_uuid": rp_module_uuid},
        "created_files": created_files,
        "created_directories": [f"behavior_packs/{bp_folder}/{name}" for name in bp_dirs] + [f"resource_packs/{rp_folder}/{name}" for name in rp_dirs],
        "features_generated": [],
        "runtime_status": "NOT RUN",
        "mcp_server_version": SERVER_VERSION,
        "note": "This is a clean BP/RP scaffold. No gameplay content, textures, models or Script API code has been generated yet.",
    }


def _run_audit(candidate: Path, baseline: Path | None = None) -> dict[str, Any]:
    if not AUDITOR.is_file():
        raise RuntimeError(f"static analyzer was not found at {AUDITOR}")
    command = [sys.executable, str(AUDITOR), str(candidate)]
    if baseline is not None:
        command.extend(["--baseline", str(baseline)])
    try:
        proc = subprocess.run(
            command,
            cwd=str(_workspace_root()),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("static analysis exceeded the 120-second time limit") from exc
    except OSError as exc:
        raise RuntimeError(f"could not start static analyzer: {exc}") from exc
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"static analyzer did not return JSON (exit {proc.returncode}): {proc.stderr[-1000:]}") from exc
    if not isinstance(report, dict):
        raise RuntimeError("static analyzer returned a JSON value other than an object")
    # Preserve analyzer exit semantics as evidence; exit 1 can mean findings, not tool failure.
    report["execution"] = {
        "status": "completed_with_findings" if proc.returncode else "completed",
        "exit_code": proc.returncode,
        "mcp_server_version": SERVER_VERSION,
    }
    report["runtime_status"] = "NOT RUN"
    return report


def _finding_text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(key, "")) for key in ("title", "path", "evidence", "recommendation", "confidence")).lower()


def _select_report(report: dict[str, Any], kind: str) -> dict[str, Any]:
    checks = report.get("checks", [])
    findings = report.get("findings", [])
    if kind == "manifest":
        match = re.compile(r"manifest|uuid|dependenc", re.I)
        checks = [x for x in checks if match.search(str(x.get("name", "")) + " " + str(x.get("details", "")))]
        findings = [x for x in findings if match.search(_finding_text(x))]
    elif kind == "geometry":
        match = re.compile(r"geometry|bone|cube|uv|texture_width|texture_height", re.I)
        checks = [x for x in checks if match.search(str(x.get("name", "")) + " " + str(x.get("details", "")))]
        findings = [x for x in findings if match.search(_finding_text(x))]
    elif kind == "animation":
        match = re.compile(r"animation|controller", re.I)
        checks = [x for x in checks if match.search(str(x.get("name", "")) + " " + str(x.get("details", "")))]
        findings = [x for x in findings if match.search(_finding_text(x))]
    return {
        "status": "completed_with_findings" if findings else "completed",
        "candidate": report.get("candidate"),
        "checks": checks,
        "findings": findings,
        "coverage": (report.get("reference_graph") or {}).get("scope", {}).get("coverage", {}),
        "runtime_status": "NOT RUN",
        "analyzer_version": report.get("tool_version"),
        "mcp_server_version": SERVER_VERSION,
    }


def _filter_graph(graph: dict[str, Any], domain: str) -> dict[str, Any]:
    """Filter graph data by its explicit domain fields before using heuristics.

    When an edge has a target_domain, that declared domain is authoritative. This
    avoids cross-contamination such as a UI path containing the word "geometry"
    appearing in the geometry filter. Field-name heuristics are a fallback only
    for edges whose analyzer output has no target domain.
    """
    if domain == "all":
        return graph

    target_domains = {
        "geometry": {"geometry"},
        "animations": {"animation", "animations"},
        "controllers": {"animation_controllers", "render_controllers", "controllers", "controller"},
        "textures": {"texture", "textures"},
        "ui": {"ui", "ui_files"},
        "localization": {"localization", "localization_keys"},
    }
    accepted_targets = target_domains[domain]

    def norm(value: Any) -> str:
        return str(value or "").replace("\\", "/").strip().lower()

    def fallback_match(edge: dict[str, Any]) -> bool:
        kind = norm(edge.get("reference_kind"))
        value = norm(edge.get("referenced_value"))
        source = norm(edge.get("source_file"))
        pointer = norm(edge.get("source_pointer"))
        if domain == "geometry":
            return "geometry" in kind or value.startswith("geometry.") or "geometry" in pointer
        if domain == "animations":
            return ("animation" in kind and "controller" not in kind) or value.startswith("animation.") or "animations/" in pointer
        if domain == "controllers":
            return "controller" in kind or "controller" in value or "controller" in pointer
        if domain == "textures":
            return "texture" in kind or "textures/" in value or "texture" in pointer
        if domain == "ui":
            return "ui" in kind or "/ui/" in source or source.startswith("ui/") or "ui" in pointer
        if domain == "localization":
            return "localization" in kind or source.endswith((".lang", ".locres")) or "localization" in pointer
        return False

    def matches(edge: dict[str, Any]) -> bool:
        target = norm(edge.get("target_domain"))
        # Never let a heuristic override a known, different target domain.
        if target:
            return target in accepted_targets
        return fallback_match(edge)

    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict) and matches(edge)]
    definitions = graph.get("definitions", {})
    filtered_defs = {
        key: value for key, value in definitions.items()
        if key in accepted_targets
    }

    out = dict(graph)
    out["edges"] = edges
    out["edge_count"] = len(edges)
    out["definitions"] = filtered_defs
    counts: dict[str, int] = {}
    for edge in edges:
        state = str(edge.get("status", "unknown"))
        counts[state] = counts.get(state, 0) + 1
    out["status_counts"] = counts
    out["filter_domain"] = domain
    return out


def _inspect_archive(path: Path) -> dict[str, Any]:
    names: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    unsafe: list[str] = []
    file_count = 0
    entry_count = 0
    total_uncompressed = 0
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            raw = info.filename
            name = raw.replace("\\", "/")
            entry_count += 1
            file_count += 0 if info.is_dir() else 1
            total_uncompressed += info.file_size
            parts = Path(name).parts
            if name.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", name):
                unsafe.append(name)
            if name in seen:
                duplicates.append(name)
            seen.add(name)
            if len(names) < MAX_MEMBERS_RETURNED:
                names.append(name)
    return {
        "status": "completed",
        "archive": {"path": str(path), "size_bytes": path.stat().st_size, "is_zip": True},
        "member_count": file_count,
        "entry_count": entry_count,
        "uncompressed_bytes_declared": total_uncompressed,
        "members_truncated": entry_count > MAX_MEMBERS_RETURNED,
        "members": names,
        "duplicate_paths": sorted(set(duplicates)),
        "unsafe_paths": sorted(set(unsafe)),
        "payloads_read": False,
        "files_extracted": False,
        "mcp_server_version": SERVER_VERSION,
    }


_SEVERITY_RANK = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "BLOCKER": 4}
_UNRESOLVED_GRAPH_STATES = {"unresolved", "heuristic_unresolved", "ambiguous"}
_DIFF_SAMPLE_LIMIT = 100
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

def _validated_diff_path(value: Any, bucket: str) -> str:
    """Require a canonical POSIX-style relative pack path in a diff report."""
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise RuntimeError(f"analyzer file_diff.{bucket} contains an invalid path")
    # Pack reports use '/' as their one canonical separator. Do not silently
    # normalize alternate spellings: they could evade duplicate/overlap checks.
    if "\\" in value:
        raise RuntimeError(f"analyzer file_diff.{bucket} contains a non-canonical path separator")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise RuntimeError(f"analyzer file_diff.{bucket} contains an absolute path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise RuntimeError(f"analyzer file_diff.{bucket} contains a traversal or non-canonical path")
    return value


def _report_sha256(report: dict[str, Any], label: str) -> str | None:
    """Read an optional artifact digest and reject malformed provenance metadata."""
    artifact = report.get("candidate")
    if artifact is None:
        return None
    if not isinstance(artifact, dict):
        raise RuntimeError(f"{label} report candidate artifact has an invalid shape")
    digest = artifact.get("sha256")
    if digest is None:
        return None
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise RuntimeError(f"{label} report candidate SHA-256 is malformed")
    return digest.lower()


def _finding_key(item: dict[str, Any]) -> tuple[str, str | None]:
    title = item.get("title")
    path = item.get("path")
    if not isinstance(title, str) or not title.strip():
        raise RuntimeError("analyzer finding is missing a non-empty title")
    if path is not None and not isinstance(path, str):
        raise RuntimeError("analyzer finding path must be a string or null")
    return title, path


def _edge_key(edge: dict[str, Any]) -> tuple[str, str, str, str, str]:
    required = ("source_file", "source_pointer", "reference_kind", "referenced_value", "target_domain")
    for key in required:
        if key in edge and not isinstance(edge[key], str):
            raise RuntimeError(f"reference graph edge field {key} must be a string when present")
    return tuple(str(edge.get(key, "")) for key in required)  # type: ignore[return-value]


def _sample(items: list[Any]) -> dict[str, Any]:
    return {"count": len(items), "items": items[:_DIFF_SAMPLE_LIMIT], "truncated": len(items) > _DIFF_SAMPLE_LIMIT}

def _summarize_pack_diff(comparison: dict[str, Any], baseline_report: dict[str, Any]) -> dict[str, Any]:
    """Build an actionable diff without writing files or treating heuristics as confirmed defects."""
    raw_diff = comparison.get("file_diff")
    candidate_graph = comparison.get("reference_graph")
    baseline_graph = baseline_report.get("reference_graph")
    if not isinstance(raw_diff, dict) or not isinstance(candidate_graph, dict) or not isinstance(baseline_graph, dict):
        raise RuntimeError("analyzer reports are missing file_diff or reference_graph required for diff_packs")

    normalized_file_diff: dict[str, list[str]] = {}
    file_diff = {}
    for bucket in ("added", "removed", "modified"):
        values = raw_diff.get(bucket, [])
        if not isinstance(values, list):
            raise RuntimeError(f"analyzer file_diff.{bucket} has an invalid shape")
        validated = [_validated_diff_path(value, bucket) for value in values]
        if len(set(validated)) != len(validated):
            raise RuntimeError(f"analyzer file_diff.{bucket} contains duplicate paths")
        normalized_file_diff[bucket] = sorted(validated)
        file_diff[bucket] = _sample(normalized_file_diff[bucket])
    buckets = list(normalized_file_diff)
    for i, left in enumerate(buckets):
        for right in buckets[i + 1:]:
            overlap = set(normalized_file_diff[left]) & set(normalized_file_diff[right])
            if overlap:
                raise RuntimeError(f"analyzer file_diff buckets overlap: {left} and {right}")

    def scoped_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
        values = report.get("findings")
        if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
            raise RuntimeError("analyzer findings has an invalid shape")
        # Baseline notes and inventory-level diffs are excluded from the static-rule comparison.
        excluded = {"File removed relative to baseline", "File changed relative to baseline"}
        result = []
        for finding in values:
            _finding_key(finding)  # Reject malformed records rather than silently hiding them.
            severity = finding.get("severity", "INFO")
            if not isinstance(severity, str) or severity.upper() not in _SEVERITY_RANK:
                raise RuntimeError("analyzer finding severity is invalid")
            if not str(finding.get("title", "")).startswith("Baseline: ") and finding.get("title") not in excluded:
                result.append(finding)
        return result

    # When the analyzer provides SHA-256 provenance, ensure the baseline inside
    # the comparison report is the same artifact as the independently audited
    # baseline report. Missing digests are tolerated for legacy/synthetic reports,
    # but malformed or contradictory digests fail closed.
    current_hash = _report_sha256(comparison, "comparison")
    baseline_hash = _report_sha256(baseline_report, "baseline")
    comparison_baseline = comparison.get("baseline")
    comparison_baseline_hash = None
    if comparison_baseline is not None:
        if not isinstance(comparison_baseline, dict):
            raise RuntimeError("comparison report baseline artifact has an invalid shape")
        raw_baseline_hash = comparison_baseline.get("sha256")
        if raw_baseline_hash is not None:
            if not isinstance(raw_baseline_hash, str) or not _SHA256_RE.fullmatch(raw_baseline_hash):
                raise RuntimeError("comparison report baseline SHA-256 is malformed")
            comparison_baseline_hash = raw_baseline_hash.lower()
    if comparison_baseline_hash is not None and baseline_hash is not None and comparison_baseline_hash != baseline_hash:
        raise RuntimeError("baseline artifact SHA-256 mismatch between comparison and standalone audit reports")
    provenance_status = (
        "verified"
        if comparison_baseline_hash is not None and baseline_hash is not None and comparison_baseline_hash == baseline_hash
        else "not_available"
    )

    current_findings = scoped_findings(comparison)
    baseline_findings = scoped_findings(baseline_report)
    current_group: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
    baseline_group: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
    for item in current_findings:
        current_group.setdefault(_finding_key(item), []).append(item)
    for item in baseline_findings:
        baseline_group.setdefault(_finding_key(item), []).append(item)

    new_findings: list[dict[str, Any]] = []
    resolved_findings: list[dict[str, Any]] = []
    severity_escalations: list[dict[str, Any]] = []
    severity_deescalations: list[dict[str, Any]] = []
    all_finding_keys = set(current_group) | set(baseline_group)
    def severity_rank(item: dict[str, Any]) -> int:
        # `scoped_findings` already validates the severity enum.
        return _SEVERITY_RANK[str(item.get("severity", "INFO")).upper()]

    def stable_finding_key(item: dict[str, Any]) -> tuple[int, str]:
        return severity_rank(item), json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def pair_remaining_by_minimum_severity_distance(
        old_items: list[dict[str, Any]], new_items: list[dict[str, Any]]
    ) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Pair remaining duplicate fingerprints with minimum severity-rank distance.

        The lists are small in normal analyzer output. This dynamic program also
        chooses the closest old occurrence when counts differ, rather than always
        matching the first/least severe item and falsely labeling another as fixed.
        """
        old_sorted = sorted(old_items, key=stable_finding_key)
        new_sorted = sorted(new_items, key=stable_finding_key)
        n, m = len(old_sorted), len(new_sorted)
        if not n or not m:
            return [], old_sorted, new_sorted

        inf = 10**9
        if n <= m:
            # Pair every old occurrence and choose a minimum-cost ordered subset
            # from the new occurrences. Unselected new items are genuinely extra.
            dp = [[inf] * (m + 1) for _ in range(n + 1)]
            choice = [["skip_new"] * (m + 1) for _ in range(n + 1)]
            for j in range(m + 1):
                dp[n][j] = 0
            for i in range(n - 1, -1, -1):
                for j in range(m - 1, -1, -1):
                    match_cost = abs(severity_rank(old_sorted[i]) - severity_rank(new_sorted[j])) + dp[i + 1][j + 1]
                    skip_cost = dp[i][j + 1]
                    if match_cost <= skip_cost:
                        dp[i][j], choice[i][j] = match_cost, "pair"
                    else:
                        dp[i][j], choice[i][j] = skip_cost, "skip_new"
            pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
            unmatched_new: list[dict[str, Any]] = []
            i = j = 0
            while i < n and j < m:
                if choice[i][j] == "pair":
                    pairs.append((old_sorted[i], new_sorted[j])); i += 1; j += 1
                else:
                    unmatched_new.append(new_sorted[j]); j += 1
            unmatched_new.extend(new_sorted[j:])
            return pairs, [], unmatched_new

        # Pair every new occurrence and choose the closest ordered subset from
        # the old occurrences. Unselected old items are no longer reported.
        dp = [[inf] * (m + 1) for _ in range(n + 1)]
        choice = [["skip_old"] * (m + 1) for _ in range(n + 1)]
        for i in range(n + 1):
            dp[i][m] = 0
        for i in range(n - 1, -1, -1):
            for j in range(m - 1, -1, -1):
                match_cost = abs(severity_rank(old_sorted[i]) - severity_rank(new_sorted[j])) + dp[i + 1][j + 1]
                skip_cost = dp[i + 1][j]
                if match_cost <= skip_cost:
                    dp[i][j], choice[i][j] = match_cost, "pair"
                else:
                    dp[i][j], choice[i][j] = skip_cost, "skip_old"
        pairs = []
        unmatched_old: list[dict[str, Any]] = []
        i = j = 0
        while i < n and j < m:
            if choice[i][j] == "pair":
                pairs.append((old_sorted[i], new_sorted[j])); i += 1; j += 1
            else:
                unmatched_old.append(old_sorted[i]); i += 1
        unmatched_old.extend(old_sorted[i:])
        return pairs, unmatched_old, []

    for key in sorted(all_finding_keys, key=lambda v: (v[0], v[1] or "")):
        old_items = list(baseline_group.get(key, []))
        new_items = list(current_group.get(key, []))
        # Exact-severity occurrences are matched first. This prevents duplicate
        # fingerprints from fabricating severity drift when an unchanged finding
        # and a genuinely changed instance coexist under the same (title, path).
        exact_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
        matched_old_ids: set[int] = set()
        matched_new_ids: set[int] = set()
        for rank in sorted(set(_SEVERITY_RANK.values())):
            old_at_rank = [item for item in old_items if severity_rank(item) == rank and id(item) not in matched_old_ids]
            new_at_rank = [item for item in new_items if severity_rank(item) == rank and id(item) not in matched_new_ids]
            for old, new in zip(old_at_rank, new_at_rank):
                exact_pairs.append((old, new))
                matched_old_ids.add(id(old)); matched_new_ids.add(id(new))
        remaining_old = [item for item in old_items if id(item) not in matched_old_ids]
        remaining_new = [item for item in new_items if id(item) not in matched_new_ids]
        changed_pairs, unmatched_old, unmatched_new = pair_remaining_by_minimum_severity_distance(remaining_old, remaining_new)
        for item in unmatched_new:
            new_findings.append({k: item.get(k) for k in ("title", "path", "severity", "confidence", "evidence", "impact", "recommendation")})
        for item in unmatched_old:
            resolved_findings.append({k: item.get(k) for k in ("title", "path", "severity", "confidence", "evidence")})
        for old, new in exact_pairs + changed_pairs:
            old_rank = severity_rank(old)
            new_rank = severity_rank(new)
            if new_rank > old_rank:
                severity_escalations.append({"title": key[0], "path": key[1], "baseline": old.get("severity"), "candidate": new.get("severity")})
            elif old_rank > new_rank:
                severity_deescalations.append({"title": key[0], "path": key[1], "baseline": old.get("severity"), "candidate": new.get("severity")})

    def edges(report_graph: dict[str, Any]) -> list[dict[str, Any]]:
        values = report_graph.get("edges")
        if not isinstance(values, list) or not all(isinstance(edge, dict) for edge in values):
            raise RuntimeError("reference_graph.edges has an invalid shape")
        for edge in values:
            status = edge.get("status")
            if not isinstance(status, str) or not status:
                raise RuntimeError("reference graph edge is missing a non-empty status")
            _edge_key(edge)
        return values

    old_edges = edges(baseline_graph)
    new_edges = edges(candidate_graph)
    old_by_key: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    new_by_key: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for edge in old_edges:
        old_by_key.setdefault(_edge_key(edge), []).append(edge)
    for edge in new_edges:
        new_by_key.setdefault(_edge_key(edge), []).append(edge)

    new_unresolved: list[dict[str, Any]] = []
    regressed_edges: list[dict[str, Any]] = []
    # Treat repeated graph edges as a multiset. A boolean `any(resolved)` overcounts
    # identical duplicates: one old resolved occurrence must not label every new
    # unresolved occurrence as a regression.
    for key, candidates in new_by_key.items():
        prior = old_by_key.get(key, [])
        old_resolved = sum(1 for item in prior if item.get("status") == "resolved")
        old_unresolved = sum(1 for item in prior if item.get("status") in _UNRESOLVED_GRAPH_STATES)
        candidate_unresolved = [item for item in candidates if item.get("status") in _UNRESOLVED_GRAPH_STATES]
        regression_count = min(old_resolved, len(candidate_unresolved))
        for index, edge in enumerate(candidate_unresolved):
            item = {
                "source_file": edge.get("source_file"),
                "source_pointer": edge.get("source_pointer"),
                "reference_kind": edge.get("reference_kind"),
                "referenced_value": edge.get("referenced_value"),
                "target_domain": edge.get("target_domain"),
                "status": edge.get("status"),
                "confidence": edge.get("confidence", "LOW"),
            }
            if index < regression_count:
                item["baseline_status"] = "resolved"
                regressed_edges.append(item)
            elif index >= old_unresolved + regression_count and len(prior) == 0:
                new_unresolved.append(item)
            elif index >= old_unresolved + regression_count and len(candidates) > len(prior):
                # Additional duplicate references are new graph instances even if
                # the same fingerprint existed before.
                new_unresolved.append(item)

    candidate_severities = [str(f.get("severity", "INFO")).upper() for f in current_findings]
    has_critical = any(level in ("BLOCKER", "HIGH") for level in candidate_severities)
    has_medium = "MEDIUM" in candidate_severities
    has_file_removals = bool(raw_diff.get("removed"))
    has_regression_edges = bool(regressed_edges)
    if has_critical:
        recommendation = "HOLD"
    elif has_medium or has_file_removals or has_regression_edges or new_unresolved or new_findings or severity_escalations:
        recommendation = "REVIEW"
    else:
        recommendation = "STATIC CHECKS PASSED — RUNTIME NOT VERIFIED"

    return {
        "status": "completed",
        "candidate": comparison.get("candidate"),
        "baseline": comparison.get("baseline"),
        "analysis_versions": {"candidate": comparison.get("tool_version"), "baseline": baseline_report.get("tool_version")},
        "artifact_provenance": {
            "status": provenance_status,
            "candidate_sha256": current_hash,
            "baseline_sha256": baseline_hash or comparison_baseline_hash,
            "baseline_hash_match": provenance_status == "verified" if provenance_status != "not_available" else None,
        },
        "file_diff": file_diff,
        "finding_delta": {
            "new": _sample(new_findings),
            "no_longer_reported": _sample(resolved_findings),
            "severity_escalations": _sample(severity_escalations),
            "severity_deescalations": _sample(severity_deescalations),
        },
        "reference_delta": {
            "new_unresolved": _sample(new_unresolved),
            "resolved_to_unresolved": _sample(regressed_edges),
        },
        "summary": {
            "files_added": len(raw_diff.get("added", [])),
            "files_removed": len(raw_diff.get("removed", [])),
            "files_modified": len(raw_diff.get("modified", [])),
            "new_findings": len(new_findings),
            "resolved_findings": len(resolved_findings),
            "severity_escalations": len(severity_escalations),
            "severity_deescalations": len(severity_deescalations),
            "new_unresolved_references": len(new_unresolved),
            "reference_regressions": len(regressed_edges),
        },
        "recommendation": recommendation,
        "runtime_status": "NOT RUN",
        "mcp_server_version": SERVER_VERSION,
        "read_only": True,
        "sample_limit": _DIFF_SAMPLE_LIMIT,
    }


def _create_addon_item(args: dict[str, Any]) -> dict[str, Any]:
    """Write one small BP/RP item slice into a scaffold; never overwrite existing paths."""
    workspace = _workspace_root()
    project_name = args["project_directory"]
    target = workspace / project_name
    try:
        resolved_target = target.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"project directory does not exist: {project_name}") from exc
    try:
        resolved_target.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("project directory resolves outside the configured workspace") from exc
    if resolved_target != target.resolve() or not resolved_target.is_dir() or target.is_symlink():
        raise ValueError("project_directory must be an existing, real directory directly under the configured workspace")

    bp_candidates = list((resolved_target / "behavior_packs").glob(f"{project_name}_BP"))
    rp_candidates = list((resolved_target / "resource_packs").glob(f"{project_name}_RP"))
    if len(bp_candidates) != 1 or len(rp_candidates) != 1:
        raise ValueError("project must contain the linked BP/RP scaffold created by create_addon_project")
    bp_root, rp_root = bp_candidates[0], rp_candidates[0]
    # Reject symlinked pack roots and top-level pack containers. A valid project
    # scaffold consists of real directories beneath this project, not aliases
    # that could redirect writes outside the workspace.
    for pack_parent, pack_root in ((resolved_target / "behavior_packs", bp_root), (resolved_target / "resource_packs", rp_root)):
        if pack_parent.is_symlink() or not pack_parent.is_dir() or pack_root.is_symlink() or not pack_root.is_dir():
            raise ValueError("project BP/RP folder is missing or unsafe")
        try:
            pack_parent.resolve(strict=True).relative_to(resolved_target)
            pack_root.resolve(strict=True).relative_to(resolved_target)
        except (OSError, ValueError) as exc:
            raise ValueError("project BP/RP folder resolves outside the project") from exc
        manifest_path = pack_root / "manifest.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise ValueError("project BP/RP manifest is missing or unsafe")
    try:
        bp_manifest = json.loads((bp_root / "manifest.json").read_text(encoding="utf-8"))
        rp_manifest = json.loads((rp_root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"project manifest is invalid JSON or unreadable: {exc}") from exc
    rp_uuid = rp_manifest.get("header", {}).get("uuid") if isinstance(rp_manifest, dict) else None
    bp_deps = bp_manifest.get("dependencies") if isinstance(bp_manifest, dict) else None
    bp_uuid = bp_manifest.get("header", {}).get("uuid") if isinstance(bp_manifest, dict) else None
    if not isinstance(rp_uuid, str) or not isinstance(bp_uuid, str) or not isinstance(bp_deps, list) or not any(isinstance(dep, dict) and dep.get("uuid") == rp_uuid for dep in bp_deps):
        raise ValueError("project BP/RP manifests do not contain a valid BP-to-RP UUID dependency")
    if bp_manifest.get("header", {}).get("min_engine_version") != rp_manifest.get("header", {}).get("min_engine_version"):
        raise ValueError("project BP/RP target versions differ; refusing to add content")
    version_parts = [int(part) for part in args["target_game_version"].split(".")]
    if bp_manifest["header"].get("min_engine_version") != version_parts:
        raise ValueError("target_game_version does not match this project's BP/RP min_engine_version")

    slug = args["item_slug"]
    namespace = re.sub(r"[^a-z0-9_]", "_", project_name.lower().replace("-", "_"))
    if not namespace or not namespace[0].isalpha():
        namespace = f"addon_{namespace}"
    item_identifier = f"{namespace}:{slug}"
    item_json = {
        "format_version": "1.26.30",
        "minecraft:item": {
            "description": {
                "identifier": item_identifier,
                "menu_category": {"category": "items"}
            },
            "components": {
                "minecraft:display_name": {"value": f"item.{slug}.name"},
                "minecraft:icon": {"textures": {"default": slug}}
            }
        }
    }
    item_rel = Path("items") / f"{slug}.json"
    lang_rel = Path("texts") / "en_US.lang"
    lang_key = f"item.{slug}.name"
    atlas_rel = Path("textures") / "item_texture.json"
    # Use the standard texture atlas mapping and an explicitly tracked texture path.
    atlas = {"resource_pack_name": "vanilla", "texture_name": "atlas.items", "texture_data": {slug: {"textures": f"textures/items/{slug}"}}}
    writes: list[tuple[Path, bytes]] = [
        (bp_root / item_rel, (json.dumps(item_json, ensure_ascii=False, indent=2) + "\n").encode("utf-8")),
    ]
    lang_path = rp_root / lang_rel
    texture_path_value = args.get("texture_path")
    expected_texture = rp_root / "textures" / "items" / f"{slug}.png"
    if texture_path_value:
        try:
            texture_file = (resolved_target / texture_path_value).resolve(strict=True)
        except OSError as exc:
            raise ValueError("texture_path must identify an existing regular PNG file inside the project") from exc
        try:
            texture_file.relative_to(resolved_target)
        except ValueError as exc:
            raise ValueError("texture_path resolves outside the project") from exc
        if texture_file.suffix.lower() != ".png" or not texture_file.is_file() or texture_file.is_symlink():
            raise ValueError("texture_path must identify an existing regular PNG file inside the project")
        try:
            with texture_file.open("rb") as texture_stream:
                png_signature = texture_stream.read(8)
        except OSError as exc:
            raise ValueError("texture_path could not be read safely") from exc
        if png_signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError("texture_path file does not have a valid PNG signature")
        if texture_file.parent != expected_texture.parent or texture_file.name != expected_texture.name:
            raise ValueError("for this item template, texture_path must be RP/textures/items/<item_slug>.png")
    # Shared RP resources are merged conservatively. Only strict JSON atlas and
    # unambiguous en_US.lang key/value lines are accepted; comments/duplicate keys
    # or malformed content fail closed to avoid silently destroying user edits.
    atlas_path = rp_root / atlas_rel
    if atlas_path.is_symlink() or (atlas_path.exists() and not atlas_path.is_file()):
        raise ValueError("existing item_texture.json is not a safe regular file")
    if lang_path.is_symlink() or (lang_path.exists() and not lang_path.is_file()):
        raise ValueError("existing en_US.lang is not a safe regular file")
    if atlas_path.exists():
        try:
            old_atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"existing item_texture.json is not valid UTF-8 JSON: {exc}") from exc
        if not isinstance(old_atlas, dict) or not isinstance(old_atlas.get("texture_data"), dict):
            raise ValueError("existing item_texture.json must contain an object texture_data")
        old_texture_data = old_atlas["texture_data"]
        if slug in old_texture_data:
            raise ValueError(f"texture atlas already contains key {slug!r}; refusing to overwrite")
        merged_atlas = dict(old_atlas)
        merged_texture_data = dict(old_texture_data)
        merged_texture_data[slug] = atlas["texture_data"][slug]
        merged_atlas["texture_data"] = merged_texture_data
        atlas = merged_atlas
    if lang_path.exists():
        try:
            old_lang_text = lang_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"existing en_US.lang is not valid UTF-8: {exc}") from exc
        lang_lines = old_lang_text.splitlines()
        seen_lang_keys = set()
        for line_number, line in enumerate(lang_lines, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "=" not in line:
                raise ValueError(f"existing en_US.lang has a malformed line {line_number}; refusing to rewrite")
            key, _value = line.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(f"existing en_US.lang has an empty key on line {line_number}")
            if key in seen_lang_keys:
                raise ValueError(f"existing en_US.lang contains duplicate key {key!r}; refusing to rewrite")
            seen_lang_keys.add(key)
        if lang_key in seen_lang_keys:
            raise ValueError(f"localization key {lang_key!r} already exists; refusing to overwrite")
        new_lang_text = old_lang_text
        if new_lang_text and not new_lang_text.endswith("\n"):
            new_lang_text += "\n"
        new_lang_text += f"{lang_key}={args['item_name']}\n"
    else:
        new_lang_text = f"{lang_key}={args['item_name']}\n"
    atlas_bytes = (json.dumps(atlas, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    writes.extend([
        (rp_root / lang_rel, new_lang_text.encode("utf-8")),
        (rp_root / atlas_rel, atlas_bytes),
    ])
    # Check all destinations and parent paths before touching any file.
    rel_writes = []
    for path, content in writes:
        try:
            relative = path.resolve(strict=False).relative_to(resolved_target)
        except ValueError as exc:
            raise ValueError("generated file path escapes the project") from exc
        cursor = resolved_target
        for part in relative.parts[:-1]:
            cursor = cursor / part
            if cursor.exists() and (cursor.is_symlink() or not cursor.is_dir()):
                raise ValueError(f"unsafe parent path for generated file: {relative.as_posix()}")
        is_shared_merge = path in {lang_path, atlas_path}
        if (path.exists() or path.is_symlink()) and not is_shared_merge:
            raise ValueError(f"target file already exists; refusing to overwrite: {relative.as_posix()}")
        if path.is_symlink():
            raise ValueError(f"target file is a symlink; refusing to overwrite: {relative.as_posix()}")
        rel_writes.append((path, relative, content))
    created: list[str] = []
    replaced: list[tuple[Path, bytes, int]] = []
    created_dirs: list[Path] = []
    staged: list[tuple[Path, Path, Path, bytes, int | None]] = []
    try:
        # Re-check all paths and stage every payload before mutation. Shared
        # resources are replaced only through atomic same-directory rename.
        for path, relative, content in rel_writes:
            missing_parents = []
            parent = path.parent
            while parent != resolved_target and not parent.exists():
                missing_parents.append(parent)
                parent = parent.parent
            for directory in reversed(missing_parents):
                directory.mkdir()
                created_dirs.append(directory)
            if path.exists() and (path.is_symlink() or not path.is_file()):
                raise ValueError(f"unsafe output file: {relative.as_posix()}")
            original = path.read_bytes() if path.exists() else None
            mode = path.stat().st_mode & 0o777 if path.exists() else None
            temp_path = path.with_name(f".{path.name}.mbe-tmp-{uuid.uuid4().hex}")
            with temp_path.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            staged.append((temp_path, path, relative, content, mode))
            if original is not None:
                replaced.append((path, original, mode or 0o644))
        # Install atomically per file. If any step fails, restore already replaced
        # shared resources and remove newly created outputs.
        for temp_path, path, relative, content, mode in staged:
            existed = path.exists()
            os.replace(temp_path, path)
            if mode is not None:
                path.chmod(mode)
            if not existed:
                created.append(relative.as_posix())
    except Exception:
        for temp_path, _path, _relative, _content, _mode in staged:
            try: temp_path.unlink()
            except OSError: pass
        for path, original, mode in reversed(replaced):
            try:
                rollback_path = path.with_name(f".{path.name}.mbe-rollback-{uuid.uuid4().hex}")
                with rollback_path.open("xb") as stream:
                    stream.write(original)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(rollback_path, path)
                path.chmod(mode)
            except OSError:
                pass
        for rel in reversed(created):
            try: (resolved_target / rel).unlink()
            except OSError: pass
        for directory in reversed(created_dirs):
            try: directory.rmdir()
            except OSError: pass
        raise
    return {
        "status": "created",
        "project_directory": str(resolved_target),
        "item_identifier": item_identifier,
        "target_game_version": args["target_game_version"],
        "files_created": created,
        "texture_status": "mapped_existing_png" if texture_path_value else "texture_file_not_created",
        "texture_expected_path": f"resource_packs/{project_name}_RP/textures/items/{slug}.png",
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
        "shared_resource_policy": "Existing valid item_texture.json and en_US.lang are conservatively merged; duplicate keys or malformed data are rejected without overwriting user content.",
        "note": "Static item definition, localization and atlas entry were generated. A PNG texture asset must exist at the expected RP path before the item can render correctly in-game; Minecraft runtime was not tested.",
    }




def _create_addon_block(args: dict[str, Any]) -> dict[str, Any]:
    """Create a starter block definition and safely merge the RP terrain atlas."""
    workspace = _workspace_root()
    project_name = args["project_directory"]
    target = workspace / project_name
    try:
        resolved_target = target.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"project directory does not exist: {project_name}") from exc
    try:
        resolved_target.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("project directory resolves outside the configured workspace") from exc
    if resolved_target != target.resolve() or not resolved_target.is_dir() or target.is_symlink():
        raise ValueError("project_directory must be an existing, real directory directly under the configured workspace")
    bp_root = resolved_target / "behavior_packs" / f"{project_name}_BP"
    rp_root = resolved_target / "resource_packs" / f"{project_name}_RP"
    for parent, root in ((resolved_target / "behavior_packs", bp_root), (resolved_target / "resource_packs", rp_root)):
        if parent.is_symlink() or not parent.is_dir() or root.is_symlink() or not root.is_dir():
            raise ValueError("project BP/RP folder is missing or unsafe")
        try:
            parent.resolve(strict=True).relative_to(resolved_target)
            root.resolve(strict=True).relative_to(resolved_target)
        except (OSError, ValueError) as exc:
            raise ValueError("project BP/RP folder resolves outside the project") from exc
        manifest = root / "manifest.json"
        if not manifest.is_file() or manifest.is_symlink():
            raise ValueError("project BP/RP manifest is missing or unsafe")
    try:
        bp_manifest = json.loads((bp_root / "manifest.json").read_text(encoding="utf-8"))
        rp_manifest = json.loads((rp_root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"project manifest is invalid JSON or unreadable: {exc}") from exc
    bp_header = bp_manifest.get("header", {}) if isinstance(bp_manifest, dict) else {}
    rp_header = rp_manifest.get("header", {}) if isinstance(rp_manifest, dict) else {}
    rp_uuid = rp_header.get("uuid")
    bp_uuid = bp_header.get("uuid")
    bp_deps = bp_manifest.get("dependencies") if isinstance(bp_manifest, dict) else None
    if not isinstance(bp_uuid, str) or not isinstance(rp_uuid, str) or not isinstance(bp_deps, list) or not any(isinstance(dep, dict) and dep.get("uuid") == rp_uuid for dep in bp_deps):
        raise ValueError("project BP/RP manifests do not contain a valid BP-to-RP UUID dependency")
    if bp_header.get("min_engine_version") != rp_header.get("min_engine_version"):
        raise ValueError("project BP/RP target versions differ; refusing to add content")
    version_parts = [int(part) for part in args["target_game_version"].split(".")]
    if bp_header.get("min_engine_version") != version_parts:
        raise ValueError("target_game_version does not match this project's BP/RP min_engine_version")

    slug = args["block_slug"]
    namespace = re.sub(r"[^a-z0-9_]", "_", project_name.lower().replace("-", "_"))
    if not namespace or not namespace[0].isalpha():
        namespace = f"addon_{namespace}"
    identifier = f"{namespace}:{slug}"
    block_json = {
        "format_version": "1.26.30",
        "minecraft:block": {
            "description": {"identifier": identifier, "menu_category": {"category": "construction"}},
            "components": {
                "minecraft:destructible_by_mining": {"seconds_to_destroy": 1.5},
                "minecraft:destructible_by_explosion": {"explosion_resistance": 3.0},
                "minecraft:map_color": "#8A526B",
                "minecraft:geometry": "minecraft:geometry.full_block",
                "minecraft:material_instances": {
                    "*": {"texture": slug, "render_method": "opaque"}
                },
            },
        },
    }
    block_rel = Path("blocks") / f"{slug}.block.json"
    atlas_rel = Path("textures") / "terrain_texture.json"
    atlas_path = rp_root / atlas_rel
    expected_texture = rp_root / "textures" / "blocks" / f"{slug}.png"
    texture_path_value = args.get("texture_path")
    if texture_path_value:
        try:
            texture_file = (resolved_target / texture_path_value).resolve(strict=True)
        except OSError as exc:
            raise ValueError("texture_path must identify an existing regular PNG file inside the project") from exc
        try:
            texture_file.relative_to(resolved_target)
        except ValueError as exc:
            raise ValueError("texture_path resolves outside the project") from exc
        if texture_file.suffix.lower() != ".png" or not texture_file.is_file() or texture_file.is_symlink():
            raise ValueError("texture_path must identify an existing regular PNG file inside the project")
        try:
            with texture_file.open("rb") as stream:
                signature = stream.read(8)
        except OSError as exc:
            raise ValueError("texture_path could not be read safely") from exc
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError("texture_path file does not have a valid PNG signature")
        if texture_file.parent != expected_texture.parent or texture_file.name != expected_texture.name:
            raise ValueError("for this block template, texture_path must be RP/textures/blocks/<block_slug>.png")
    if atlas_path.is_symlink() or (atlas_path.exists() and not atlas_path.is_file()):
        raise ValueError("existing terrain_texture.json is not a safe regular file")
    if atlas_path.exists():
        try:
            atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"existing terrain_texture.json is not valid UTF-8 JSON: {exc}") from exc
        if not isinstance(atlas, dict) or not isinstance(atlas.get("texture_data"), dict):
            raise ValueError("existing terrain_texture.json must contain an object texture_data")
        if slug in atlas["texture_data"]:
            raise ValueError(f"terrain texture atlas already contains key {slug!r}; refusing to overwrite")
        merged = dict(atlas)
        data = dict(atlas["texture_data"])
        data[slug] = {"textures": f"textures/blocks/{slug}"}
        merged["texture_data"] = data
        atlas = merged
    else:
        atlas = {"resource_pack_name": "vanilla", "texture_name": "atlas.terrain", "padding": 8, "num_mip_levels": 4, "texture_data": {slug: {"textures": f"textures/blocks/{slug}"}}}
    atlas_bytes = (json.dumps(atlas, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    block_path = bp_root / block_rel
    writes = [(block_path, (json.dumps(block_json, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))]
    if atlas_path.exists():
        writes.append((atlas_path, atlas_bytes))
    else:
        writes.append((atlas_path, atlas_bytes))
    # Verify all targets and parent directories before any writes.
    rel_writes = []
    for path, content in writes:
        relative = path.resolve(strict=False).relative_to(resolved_target)
        cursor = resolved_target
        for part in relative.parts[:-1]:
            cursor = cursor / part
            if cursor.exists() and (cursor.is_symlink() or not cursor.is_dir()):
                raise ValueError(f"unsafe parent path for generated file: {relative.as_posix()}")
        if path.is_symlink():
            raise ValueError(f"target file is a symlink; refusing to overwrite: {relative.as_posix()}")
        if path.exists() and path != atlas_path:
            raise ValueError(f"target file already exists; refusing to overwrite: {relative.as_posix()}")
        rel_writes.append((path, relative, content))
    created: list[str] = []
    replaced: list[tuple[Path, bytes, int]] = []
    created_dirs: list[Path] = []
    staged: list[tuple[Path, Path, Path, int | None]] = []
    try:
        for path, relative, content in rel_writes:
            missing = []
            parent = path.parent
            while parent != resolved_target and not parent.exists():
                missing.append(parent); parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir(); created_dirs.append(directory)
            if path.exists() and (path.is_symlink() or not path.is_file()):
                raise ValueError(f"unsafe output file: {relative.as_posix()}")
            mode = path.stat().st_mode & 0o777 if path.exists() else None
            if path.exists():
                replaced.append((path, path.read_bytes(), mode or 0o644))
            temp_path = path.with_name(f".{path.name}.mbe-tmp-{uuid.uuid4().hex}")
            with temp_path.open("xb") as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            staged.append((temp_path, path, relative, mode))
        for temp_path, path, relative, mode in staged:
            existed = path.exists()
            os.replace(temp_path, path)
            if mode is not None: path.chmod(mode)
            if not existed: created.append(relative.as_posix())
    except Exception:
        for temp_path, _path, _relative, _mode in staged:
            try: temp_path.unlink()
            except OSError: pass
        for path, original, mode in reversed(replaced):
            try:
                backup = path.with_name(f".{path.name}.mbe-rollback-{uuid.uuid4().hex}")
                with backup.open("xb") as stream:
                    stream.write(original); stream.flush(); os.fsync(stream.fileno())
                os.replace(backup, path); path.chmod(mode)
            except OSError: pass
        for rel in reversed(created):
            try: (resolved_target / rel).unlink()
            except OSError: pass
        for directory in reversed(created_dirs):
            try: directory.rmdir()
            except OSError: pass
        raise
    return {
        "status": "created",
        "project_directory": str(resolved_target),
        "block_identifier": identifier,
        "target_game_version": args["target_game_version"],
        "files_created": [rel.as_posix() for _path, rel, _payload in rel_writes if _path != atlas_path or not replaced],
        "shared_resource_policy": "Existing valid terrain_texture.json is merged; unrelated entries are retained and duplicate/malformed state is rejected.",
        "texture_status": "mapped_existing_png" if texture_path_value else "texture_file_not_created",
        "texture_expected_path": f"resource_packs/{project_name}_RP/textures/blocks/{slug}.png",
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
        "note": "Starter block definition and atlas mapping were generated. A PNG texture asset must exist at the expected RP path for correct rendering; Minecraft runtime was not tested.",
    }


def _create_addon_recipe(args: dict[str, Any]) -> dict[str, Any]:
    """Create one shaped/shapeless crafting-table recipe without overwrites."""
    workspace = _workspace_root()
    project_name = args["project_directory"]
    target = workspace / project_name
    try:
        project = target.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"project directory does not exist: {project_name}") from exc
    try:
        project.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("project directory resolves outside the configured workspace") from exc
    if project != target.resolve() or not project.is_dir() or target.is_symlink():
        raise ValueError("project_directory must be an existing, real directory directly under the configured workspace")

    bp_root = project / "behavior_packs" / f"{project_name}_BP"
    rp_root = project / "resource_packs" / f"{project_name}_RP"
    for parent, pack_root in ((project / "behavior_packs", bp_root), (project / "resource_packs", rp_root)):
        if parent.is_symlink() or not parent.is_dir() or pack_root.is_symlink() or not pack_root.is_dir():
            raise ValueError("project BP/RP folder is missing or unsafe")
        try:
            parent.resolve(strict=True).relative_to(project)
            pack_root.resolve(strict=True).relative_to(project)
        except (OSError, ValueError) as exc:
            raise ValueError("project BP/RP folder resolves outside the project") from exc
        manifest_path = pack_root / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ValueError("project BP/RP manifest is missing or unsafe")
    try:
        bp_manifest = json.loads((bp_root / "manifest.json").read_text(encoding="utf-8"))
        rp_manifest = json.loads((rp_root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"project manifest is invalid JSON or unreadable: {exc}") from exc
    if not isinstance(bp_manifest, dict) or not isinstance(rp_manifest, dict):
        raise ValueError("project BP/RP manifests must be JSON objects")
    bp_header = bp_manifest.get("header", {})
    rp_header = rp_manifest.get("header", {})
    bp_deps = bp_manifest.get("dependencies")
    if not isinstance(bp_header, dict) or not isinstance(rp_header, dict) or not isinstance(bp_deps, list):
        raise ValueError("project manifests are missing expected header/dependency objects")
    rp_uuid = rp_header.get("uuid")
    if not isinstance(rp_uuid, str) or not any(isinstance(dep, dict) and dep.get("uuid") == rp_uuid for dep in bp_deps):
        raise ValueError("project BP/RP manifests do not contain a valid BP-to-RP UUID dependency")
    if bp_header.get("min_engine_version") != rp_header.get("min_engine_version"):
        raise ValueError("project BP/RP target versions differ; refusing to add content")
    version_parts = [int(part) for part in args["target_game_version"].split(".")]
    if bp_header.get("min_engine_version") != version_parts:
        raise ValueError("target_game_version does not match this project's BP/RP min_engine_version")

    # Resolve existing custom identifiers from the project's own item/block definitions.
    # Do not follow symlinked directories or read arbitrarily large files.
    known_ids: set[str] = set()
    for resource_dir, component_root, component_key, kind in (
        (bp_root / "items", bp_root, "minecraft:item", "item"),
        (bp_root / "blocks", bp_root, "minecraft:block", "block"),
    ):
        if resource_dir.is_symlink():
            raise ValueError(f"custom {kind} directory is a symlink; refusing to inspect it")
        if not resource_dir.exists():
            continue
        if not resource_dir.is_dir():
            raise ValueError(f"custom {kind} path is not a directory")
        for current, dirs, filenames in os.walk(resource_dir, followlinks=False):
            current_path = Path(current)
            if current_path.is_symlink():
                raise ValueError(f"custom {kind} path contains a symlinked directory")
            for directory in list(dirs):
                candidate_dir = current_path / directory
                if candidate_dir.is_symlink():
                    raise ValueError(f"custom {kind} path contains a symlinked directory")
            for filename in filenames:
                file_path = current_path / filename
                if file_path.suffix.lower() != ".json":
                    continue
                if file_path.is_symlink() or not file_path.is_file():
                    raise ValueError(f"custom {kind} definition is not a safe regular file")
                if file_path.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError(f"custom {kind} definition exceeds the 2 MiB inspection limit")
                try:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError(f"custom {kind} definition is invalid JSON: {file_path.relative_to(project).as_posix()}") from exc
                component = data.get(component_key) if isinstance(data, dict) else None
                description = component.get("description") if isinstance(component, dict) else None
                identifier = description.get("identifier") if isinstance(description, dict) else None
                if isinstance(identifier, str) and re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_.-]+", identifier):
                    known_ids.add(identifier)

    result_identifier = args["result_identifier"]
    ingredients: list[str]
    if args["recipe_type"] == "shapeless":
        ingredients = list(args["ingredients"])
    else:
        ingredients = list(dict.fromkeys(args["key_mapping"][symbol] for row in args["pattern"] for symbol in row if symbol != " "))
    for identifier in [result_identifier, *ingredients]:
        namespace = identifier.split(":", 1)[0]
        if namespace != "minecraft" and identifier not in known_ids:
            role = "result" if identifier == result_identifier else "ingredient"
            raise ValueError(f"custom recipe {role} {identifier!r} is not defined by an item/block JSON in this project's BP")

    namespace = re.sub(r"[^a-z0-9_]", "_", project_name.lower().replace("-", "_"))
    if not namespace or not namespace[0].isalpha():
        namespace = f"addon_{namespace}"
    recipe_identifier = f"{namespace}:{args['recipe_slug']}"
    if args["recipe_type"] == "shapeless":
        recipe_data = {
            "format_version": "1.20.10",
            "minecraft:recipe_shapeless": {
                "description": {"identifier": recipe_identifier},
                "tags": ["crafting_table"],
                "ingredients": [{"item": value} for value in args["ingredients"]],
                "unlock": [{"item": value} for value in dict.fromkeys(args["ingredients"])],
                "result": {"item": result_identifier, "count": args["result_count"]},
            },
        }
    else:
        recipe_data = {
            "format_version": "1.20.10",
            "minecraft:recipe_shaped": {
                "description": {"identifier": recipe_identifier},
                "tags": ["crafting_table"],
                "pattern": args["pattern"],
                "key": {symbol: {"item": value} for symbol, value in sorted(args["key_mapping"].items())},
                "unlock": [{"item": value} for value in dict.fromkeys(ingredients)],
                "result": {"item": result_identifier, "count": args["result_count"]},
            },
        }

    recipe_rel = Path("recipes") / f"{args['recipe_slug']}.json"
    recipe_path = bp_root / recipe_rel
    if recipe_path.is_symlink() or recipe_path.exists():
        raise ValueError(f"recipe output already exists or is a symlink; refusing to overwrite: {recipe_path.relative_to(project).as_posix()}")
    if recipe_path.parent.is_symlink() or not recipe_path.parent.is_dir():
        raise ValueError("BP recipes path is missing or unsafe; expected scaffold recipes directory")
    try:
        resolved_output = recipe_path.resolve(strict=False)
        resolved_output.relative_to(project)
    except (OSError, ValueError) as exc:
        raise ValueError("generated recipe path escapes the project") from exc
    for parent in (recipe_path.parent, bp_root):
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError("recipe output parent is unsafe")
    payload = (json.dumps(recipe_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        with recipe_path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise ValueError(f"recipe output already exists; refusing to overwrite: {recipe_path.relative_to(project).as_posix()}") from exc
    except Exception:
        try:
            if recipe_path.exists() and not recipe_path.is_symlink():
                recipe_path.unlink()
        except OSError:
            pass
        raise
    return {
        "status": "created",
        "project_directory": str(project),
        "recipe_identifier": recipe_identifier,
        "recipe_type": args["recipe_type"],
        "result_identifier": result_identifier,
        "result_count": args["result_count"],
        "ingredients": ingredients,
        "files_created": [recipe_path.relative_to(project).as_posix()],
        "target_game_version": args["target_game_version"],
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
        "note": "A static crafting-table recipe was generated using the version-labelled Mojang sample format. Custom identifiers were checked against this project's BP item/block definitions; vanilla identifiers are accepted. Import and crafting behavior were not tested in Minecraft.",
    }



def _create_addon_entity(args: dict[str, Any]) -> dict[str, Any]:
    """Create a safe, linked BP/RP entity slice without overwriting existing files."""
    workspace = _workspace_root()
    project_name = args["project_directory"]
    target = workspace / project_name
    try:
        project = target.resolve(strict=True)
        project.relative_to(workspace)
    except (OSError, ValueError) as exc:
        raise ValueError(f"project directory does not exist inside the configured workspace: {project_name}") from exc
    if target.is_symlink() or project != target or not project.is_dir():
        raise ValueError("project_directory must be a real directory directly under the configured workspace")

    bp_parent = project / "behavior_packs"
    rp_parent = project / "resource_packs"
    bp_root = bp_parent / f"{project_name}_BP"
    rp_root = rp_parent / f"{project_name}_RP"
    for parent, pack_root in ((bp_parent, bp_root), (rp_parent, rp_root)):
        if parent.is_symlink() or not parent.is_dir() or pack_root.is_symlink() or not pack_root.is_dir():
            raise ValueError("project BP/RP folder is missing or unsafe")
        try:
            parent.resolve(strict=True).relative_to(project)
            pack_root.resolve(strict=True).relative_to(project)
        except (OSError, ValueError) as exc:
            raise ValueError("project BP/RP folder resolves outside the project") from exc
        manifest_path = pack_root / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ValueError("project BP/RP manifest is missing or unsafe")

    try:
        bp_manifest = json.loads((bp_root / "manifest.json").read_text(encoding="utf-8"))
        rp_manifest = json.loads((rp_root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"project manifest is invalid JSON or unreadable: {exc}") from exc
    if not isinstance(bp_manifest, dict) or not isinstance(rp_manifest, dict):
        raise ValueError("project BP/RP manifests must be JSON objects")
    bp_header, rp_header = bp_manifest.get("header"), rp_manifest.get("header")
    bp_deps = bp_manifest.get("dependencies")
    if not isinstance(bp_header, dict) or not isinstance(rp_header, dict) or not isinstance(bp_deps, list):
        raise ValueError("project manifests are missing expected header/dependency objects")
    rp_uuid = rp_header.get("uuid")
    if not isinstance(rp_uuid, str) or not any(isinstance(dep, dict) and dep.get("uuid") == rp_uuid for dep in bp_deps):
        raise ValueError("project BP/RP manifests do not contain a valid BP-to-RP UUID dependency")
    if bp_header.get("min_engine_version") != rp_header.get("min_engine_version"):
        raise ValueError("project BP/RP target versions differ; refusing to add content")
    version_parts = [int(part) for part in args["target_game_version"].split(".")]
    if bp_header.get("min_engine_version") != version_parts:
        raise ValueError("target_game_version does not match this project's BP/RP min_engine_version")

    slug = args["entity_slug"]
    namespace = re.sub(r"[^a-z0-9_]", "_", project_name.lower().replace("-", "_"))
    if not namespace or not namespace[0].isalpha():
        namespace = f"addon_{namespace}"
    identifier = f"{namespace}:{slug}"
    geometry_id = f"geometry.{namespace}.{slug}"
    render_controller_id = f"controller.render.{namespace}.{slug}"
    expected_texture_rel = Path("textures") / "entity" / f"{slug}.png"
    texture_ref = (Path("textures") / "entity" / slug).as_posix()
    texture_path_arg = args.get("texture_path")
    texture_status = "texture_file_not_created"

    if texture_path_arg:
        candidate = project / Path(*texture_path_arg.split("/"))
        try:
            resolved_texture = candidate.resolve(strict=True)
            resolved_texture.relative_to(rp_root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise ValueError("texture_path must resolve to an existing file inside this project's Resource Pack") from exc
        if candidate.is_symlink() or not resolved_texture.is_file() or resolved_texture.suffix.lower() != ".png":
            raise ValueError("texture_path must be a regular PNG file, not a symlink or directory")
        current = candidate.parent
        while current != rp_root:
            if current.is_symlink():
                raise ValueError("texture_path contains a symlinked parent")
            current = current.parent
            if current == project or current == current.parent:
                raise ValueError("texture_path is not inside the Resource Pack")
        with resolved_texture.open("rb") as stream:
            if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError("texture_path does not have a PNG signature")
        texture_ref = resolved_texture.relative_to(rp_root.resolve(strict=True)).with_suffix("").as_posix()
        texture_status = "mapped_existing_png"

    bp_rel = Path("entities") / f"{slug}.json"
    client_rel = Path("entity") / f"{slug}.entity.json"
    geometry_rel = Path("models") / "entity" / f"{slug}.geo.json"
    controller_rel = Path("render_controllers") / f"{slug}.render_controllers.json"
    outputs = [(bp_root, bp_rel), (rp_root, client_rel), (rp_root, geometry_rel), (rp_root, controller_rel)]
    for pack_root, relative in outputs:
        destination = pack_root / relative
        parent = destination.parent
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError(f"required output folder is missing or unsafe: {destination.relative_to(project).as_posix()}")
        try:
            parent.resolve(strict=True).relative_to(pack_root.resolve(strict=True))
            destination.resolve(strict=False).relative_to(pack_root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise ValueError(f"generated entity path escapes its pack: {destination.relative_to(project).as_posix()}") from exc
        if destination.is_symlink() or destination.exists():
            raise ValueError(f"entity output already exists or is a symlink; refusing to overwrite: {destination.relative_to(project).as_posix()}")

    bp_entity = {
        "format_version": "1.20.50",
        "minecraft:entity": {
            "description": {"identifier": identifier, "is_spawnable": True, "is_summonable": True, "is_experimental": False},
            "components": {
                "minecraft:type_family": {"family": [namespace, "mob"]},
                "minecraft:health": {"value": 20, "max": 20},
                "minecraft:collision_box": {"width": 0.8, "height": 1.8},
                "minecraft:movement": {"value": 0.25},
                "minecraft:movement.basic": {},
                "minecraft:navigation.walk": {"can_path_over_water": True},
                "minecraft:jump.static": {},
                "minecraft:physics": {},
                "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
                "minecraft:behavior.float": {"priority": 0},
                "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 1.0},
                "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 8.0, "probability": 0.02},
                "minecraft:behavior.random_look_around": {"priority": 8}
            }
        }
    }
    client_entity = {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": identifier,
                "materials": {"default": "entity_alphatest"},
                "textures": {"default": texture_ref},
                "geometry": {"default": geometry_id},
                "render_controllers": [render_controller_id]
            }
        }
    }
    geometry = {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": geometry_id,
                "texture_width": 64,
                "texture_height": 64,
                "visible_bounds_width": 2.0,
                "visible_bounds_height": 2.5,
                "visible_bounds_offset": [0, 1.25, 0]
            },
            "bones": [
                {"name": "body", "pivot": [0, 12, 0], "cubes": [{"origin": [-4, 6, -2], "size": [8, 12, 4], "uv": [0, 0]}]},
                {"name": "head", "parent": "body", "pivot": [0, 24, 0], "cubes": [{"origin": [-4, 18, -4], "size": [8, 8, 8], "uv": [0, 16]}]},
                {"name": "left_leg", "pivot": [2, 12, 0], "cubes": [{"origin": [1, 0, -2], "size": [3, 6, 3], "uv": [0, 32]}]},
                {"name": "right_leg", "pivot": [-2, 12, 0], "cubes": [{"origin": [-4, 0, -2], "size": [3, 6, 3], "uv": [16, 32]}]}
            ]
        }]
    }
    render_controller = {
        "format_version": "1.8.0",
        "render_controllers": {
            render_controller_id: {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.default"]
            }
        }
    }

    contents = [
        (bp_root / bp_rel, json.dumps(bp_entity, ensure_ascii=False, indent=2) + "\n"),
        (rp_root / client_rel, json.dumps(client_entity, ensure_ascii=False, indent=2) + "\n"),
        (rp_root / geometry_rel, json.dumps(geometry, ensure_ascii=False, indent=2) + "\n"),
        (rp_root / controller_rel, json.dumps(render_controller, ensure_ascii=False, indent=2) + "\n"),
    ]
    created: list[Path] = []
    try:
        for destination, payload in contents:
            with destination.open("x", encoding="utf-8", newline="\n") as stream:
                created.append(destination)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        for destination in reversed(created):
            try:
                if destination.is_file() and not destination.is_symlink():
                    destination.unlink()
            except OSError:
                pass
        raise

    return {
        "status": "created",
        "project_directory": str(project),
        "entity_identifier": identifier,
        "geometry_identifier": geometry_id,
        "render_controller_identifier": render_controller_id,
        "files_created": [path.relative_to(project).as_posix() for path, _payload in contents],
        "texture_status": texture_status,
        "texture_expected_path": f"resource_packs/{project_name}_RP/{expected_texture_rel.as_posix()}",
        "texture_reference": texture_ref,
        "target_game_version": args["target_game_version"],
        "mcp_server_version": SERVER_VERSION,
        "runtime_status": "NOT RUN",
        "note": "Generated a coordinated BP entity, RP client-entity, geometry and render controller. A real PNG texture is still required if one was not supplied; animation, spawn-rule and in-game behavior were not tested."
    }


def call_tool(name: str, raw_args: Any) -> dict[str, Any]:
    try:
        args = _validate_arguments(name, raw_args)
        if name == "create_addon_project":
            return _create_addon_project(args)
        if name == "create_addon_item":
            return _create_addon_item(args)
        if name == "create_addon_block":
            return _create_addon_block(args)
        if name == "create_addon_recipe":
            return _create_addon_recipe(args)
        if name == "create_addon_entity":
            return _create_addon_entity(args)
        if name == "search_mojang_samples":
            return _search_mojang_samples(args)
        if name == "read_mojang_sample":
            return _read_mojang_sample(args)
        if name == "inspect_archive":
            path = _resolve_archive(args["archive_path"])
            return _inspect_archive(path)
        if name == "compare_baseline":
            candidate = _resolve_archive(args["candidate_path"])
            baseline = _resolve_archive(args["baseline_path"])
            return _run_audit(candidate, baseline)
        if name == "diff_packs":
            candidate = _resolve_archive(args["candidate_path"])
            baseline = _resolve_archive(args["baseline_path"])
            comparison = _run_audit(candidate, baseline)
            baseline_report = _run_audit(baseline)
            return _summarize_pack_diff(comparison, baseline_report)
        if name == "audit_pack":
            candidate = _resolve_archive(args["candidate_path"])
            return _run_audit(candidate)
        archive_arg = args["archive_path"]
        candidate = _resolve_archive(archive_arg)
        report = _run_audit(candidate)
        if name == "get_resource_graph":
            graph = report.get("reference_graph")
            if not isinstance(graph, dict):
                return _error("REPORT_SHAPE", "Analyzer report omitted reference_graph")
            return {"status": "completed", "candidate": report.get("candidate"), "reference_graph": _filter_graph(graph, args["domain"]), "runtime_status": "NOT RUN", "mcp_server_version": SERVER_VERSION}
        if name == "validate_manifest":
            return _select_report(report, "manifest")
        if name == "audit_geometry":
            return _select_report(report, "geometry")
        if name == "audit_animation":
            return _select_report(report, "animation")
        return _error("UNKNOWN_TOOL", f"unhandled tool {name!r}")
    except ValueError as exc:
        return _error("INVALID_ARGUMENT", str(exc))
    except TimeoutError as exc:
        return _error("TIMEOUT", str(exc))
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        return _error("ANALYSIS_FAILED", str(exc))
    except Exception as exc:  # Keep unexpected failures structured without leaking a stack trace.
        return _error("INTERNAL_ERROR", f"unexpected {type(exc).__name__}: {exc}")


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid JSON-RPC request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if not isinstance(method, str) or not isinstance(params, dict):
        return _jsonrpc_error(request_id, -32600, "Invalid method or params")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        requested = params.get("protocolVersion", "2025-03-26")
        supported = {"2024-11-05", "2025-03-26", "2025-06-18"}
        selected = requested if requested in supported else "2025-03-26"
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": selected,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-engineer", "version": SERVER_VERSION},
            "instructions": WORKFLOW_INSTRUCTIONS,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if not isinstance(name, str):
            payload = _error("INVALID_ARGUMENT", "tool name must be a string")
        else:
            payload = call_tool(name, args)
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": text}],
            "structuredContent": payload,
            "isError": payload.get("status") == "error",
        }}
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    # MCP stdio: one JSON-RPC message per line. stdout is protocol-only.
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
