#!/usr/bin/env python3
"""Read-only Bedrock geometry UV and texture-canvas auditor.

Checks classic box UV rectangles and alternate per-face UV rectangles against
geometry texture dimensions and, when explicitly supplied, a real PNG texture.
It never rewrites geometry or textures and does not claim to preview rendering.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
from png_validation import PngValidationError, validate_png_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
try:
    SERVER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    SERVER_VERSION = "unknown"

PROJECT_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
MAX_GEOMETRY_FILES = 500
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PNG_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 16_777_216
MAX_FINDINGS = 5000
FACE_DIMENSIONS = {
    "north": (0, 1),
    "south": (0, 1),
    "east": (2, 1),
    "west": (2, 1),
    "up": (0, 2),
    "down": (0, 2),
}


class DuplicateJsonKey(ValueError):
    pass


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKey(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _tool() -> dict[str, Any]:
    return {
        "name": "audit_geometry_uvs",
        "description": (
            "Read-only Minecraft Bedrock geometry UV auditor. Scans one .geo.json file or the existing "
            "Resource Pack models/entity directory, parses minecraft:geometry variants, and validates classic "
            "box UV rectangles plus alternate per-face UV/uv_size/uv_rotation mappings. Checks bounds against "
            "the geometry's declared texture canvas and can deeply validate one explicitly supplied PNG texture. "
            "The PNG is not auto-associated with entity aliases; when supplied, it is the user's asserted texture "
            "for the selected geometry file. Reports missing/invalid UVs, out-of-bounds faces, malformed geometry, "
            "canvas mismatches, scan limits and unsupported mesh UV coverage. It never changes files. "
            "Static validation only; Minecraft runtime and visual rendering remain NOT RUN."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_directory": {
                    "type": "string", "minLength": 1, "maxLength": 63,
                    "description": "Existing project directory directly under MINECRAFT_BEDROCK_WORKSPACE.",
                },
                "geometry_path": {
                    "type": "string", "minLength": 1, "maxLength": 512,
                    "description": "Optional project-relative .json path inside resource_packs/<project>_RP/models/entity/. Omit to scan that directory recursively.",
                },
                "texture_path": {
                    "type": "string", "minLength": 1, "maxLength": 512,
                    "description": "Optional project-relative PNG path inside resource_packs/<project>_RP/textures/. Requires geometry_path because the texture is asserted for that one geometry file.",
                },
            },
            "required": ["project_directory"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
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


def _validate_args(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("arguments must be a JSON object")
    allowed = {"project_directory", "geometry_path", "texture_path"}
    extra = set(raw) - allowed
    if extra:
        raise ValueError(f"unexpected argument(s): {', '.join(sorted(extra))}")
    project_name = raw.get("project_directory")
    if not isinstance(project_name, str) or not PROJECT_RE.fullmatch(project_name) or "--" in project_name:
        raise ValueError("project_directory must be one lowercase kebab-case directory name, not a path")
    geometry_path = raw.get("geometry_path")
    texture_path = raw.get("texture_path")
    if geometry_path is not None:
        _validate_relative_path(geometry_path, "geometry_path")
        parts = geometry_path.split("/")
        expected = ["resource_packs", f"{project_name}_RP", "models", "entity"]
        if len(parts) < 5 or parts[:4] != expected or not geometry_path.endswith(".json"):
            raise ValueError(f"geometry_path must be a .json file inside resource_packs/{project_name}_RP/models/entity/")
    if texture_path is not None:
        if geometry_path is None:
            raise ValueError("texture_path requires geometry_path so the PNG-to-geometry association is explicit")
        _validate_relative_path(texture_path, "texture_path")
        parts = texture_path.split("/")
        expected = ["resource_packs", f"{project_name}_RP", "textures"]
        if len(parts) < 5 or parts[:3] != expected or not texture_path.endswith(".png"):
            raise ValueError(f"texture_path must be a .png file inside resource_packs/{project_name}_RP/textures/")
    result = {"project_directory": project_name}
    if geometry_path is not None:
        result["geometry_path"] = geometry_path
    if texture_path is not None:
        result["texture_path"] = texture_path
    return result


def _validate_relative_path(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{label} must be a non-empty relative POSIX path of at most 512 characters")
    if "\\" in value or "\x00" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"{label} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must not contain empty, dot or parent-traversal segments")


def _workspace_root() -> Path:
    raw = os.environ.get("MINECRAFT_BEDROCK_WORKSPACE")
    root = Path(raw).expanduser() if raw else Path.cwd()
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"configured workspace does not exist: {root}") from exc
    if not resolved.is_dir():
        raise ValueError("configured workspace must be a directory")
    return resolved


def _resolve_project(project_name: str) -> tuple[Path, Path, Path]:
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
    rp_container = project / "resource_packs"
    rp_root = rp_container / f"{project_name}_RP"
    for path in (rp_container, rp_root):
        if path.is_symlink():
            raise ValueError(f"unsafe symlink in Resource Pack path: {path.name}")
    try:
        resolved_container = rp_container.resolve(strict=True)
        resolved_rp = rp_root.resolve(strict=True)
        resolved_container.relative_to(project)
        resolved_rp.relative_to(resolved_container)
    except (OSError, ValueError) as exc:
        raise ValueError("the expected Resource Pack directory must exist inside the selected project") from exc
    if not resolved_container.is_dir() or not resolved_rp.is_dir():
        raise ValueError("the expected Resource Pack path must be a directory")
    manifest = resolved_rp / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("Resource Pack manifest.json is missing or unsafe")
    return workspace, project, resolved_rp


def _safe_resolve(root: Path, relative_path: str, *, label: str) -> Path:
    current = root
    for part in relative_path.split("/"):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} path contains a symlink")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} is missing or resolves outside the Resource Pack") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} is not a regular file")
    return resolved


def _walk_geometry_files(root: Path, project: Path, findings: list[dict[str, Any]]) -> list[Path]:
    results: list[Path] = []
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Resource Pack models/entity directory is missing or unsafe")
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        keep: list[str] = []
        for name in sorted(dirs):
            child = current_path / name
            if child.is_symlink():
                findings.append(_finding("error", "UNSAFE_GEOMETRY_DIRECTORY", _relative(child, project), "symlinked geometry directory was skipped"))
            else:
                keep.append(name)
        dirs[:] = keep
        for name in sorted(files):
            if not name.endswith(".json"):
                continue
            path = current_path / name
            if path.is_symlink():
                findings.append(_finding("error", "UNSAFE_GEOMETRY_FILE", _relative(path, project), "symlinked geometry file was skipped"))
                continue
            results.append(path)
            if len(results) > MAX_GEOMETRY_FILES:
                findings.append(_finding("error", "GEOMETRY_SCAN_LIMIT", _relative(root, project), f"scan exceeded {MAX_GEOMETRY_FILES} geometry files; analysis is incomplete"))
                return results[:MAX_GEOMETRY_FILES]
    return results


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return "<outside-project>"


def _read_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError("geometry path is not a regular non-symlink file")
    size = path.stat().st_size
    if size > MAX_JSON_BYTES:
        raise ValueError(f"geometry JSON exceeds {MAX_JSON_BYTES} bytes")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateJsonKey) as exc:
        raise ValueError(str(exc)) from exc


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _pair(value: Any, label: str) -> tuple[float, float] | None:
    if not isinstance(value, list) or len(value) != 2 or not all(_finite_number(part) for part in value):
        return None
    return float(value[0]), float(value[1])


def _size3(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, list) or len(value) != 3 or not all(_finite_number(part) for part in value):
        return None
    return float(value[0]), float(value[1]), float(value[2])


def _finding(severity: str, code: str, path: str, message: str, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"severity": severity, "code": code, "path": path, "message": message}
    item.update(extra)
    return item


def _add_finding(findings: list[dict[str, Any]], *args: Any, **kwargs: Any) -> None:
    if len(findings) < MAX_FINDINGS:
        findings.append(_finding(*args, **kwargs))


def _rect_bounds(uv: tuple[float, float], uv_size: tuple[float, float]) -> tuple[float, float, float, float]:
    x1, y1 = uv
    x2, y2 = x1 + uv_size[0], y1 + uv_size[1]
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def _out_of_bounds(bounds: tuple[float, float, float, float], width: int, height: int) -> bool:
    left, top, right, bottom = bounds
    return left < 0 or top < 0 or right > width or bottom > height


def _check_rect(
    *,
    findings: list[dict[str, Any]],
    path: str,
    geometry_id: str,
    bone: str,
    cube_index: int,
    face: str,
    uv: tuple[float, float],
    uv_size: tuple[float, float],
    width: int | None,
    height: int | None,
    source: str,
    actual_texture_size: tuple[int, int] | None = None,
) -> dict[str, Any]:
    bounds = _rect_bounds(uv, uv_size)
    record: dict[str, Any] = {
        "geometry_identifier": geometry_id,
        "bone": bone,
        "cube_index": cube_index,
        "face": face,
        "mapping": source,
        "uv": [uv[0], uv[1]],
        "uv_size": [uv_size[0], uv_size[1]],
        "bounds": [bounds[0], bounds[1], bounds[2], bounds[3]],
        "texture_bounds_checked": width is not None and height is not None,
    }
    if width is not None and height is not None and _out_of_bounds(bounds, width, height):
        _add_finding(
            findings, "error", "UV_OUT_OF_BOUNDS", path,
            f"{geometry_id} bone {bone!r} cube {cube_index} face {face!r} UV rectangle exceeds declared/effective {width}x{height} canvas",
            geometry_identifier=geometry_id, bone=bone, cube_index=cube_index, face=face,
            bounds=list(bounds), texture_size=[width, height], mapping=source,
        )
        record["out_of_bounds"] = True
    if actual_texture_size is not None and (actual_texture_size != (width, height)) and _out_of_bounds(bounds, *actual_texture_size):
        _add_finding(
            findings, "error", "UV_OUTSIDE_ACTUAL_TEXTURE", path,
            f"{geometry_id} bone {bone!r} cube {cube_index} face {face!r} UV rectangle exceeds the supplied PNG's actual {actual_texture_size[0]}x{actual_texture_size[1]} dimensions",
            geometry_identifier=geometry_id, bone=bone, cube_index=cube_index, face=face,
            bounds=list(bounds), actual_texture_size=list(actual_texture_size), mapping=source,
        )
        record["outside_actual_texture"] = True
    return record


def _audit_classic_box(
    cube: dict[str, Any], *, bone_name: str, cube_index: int, geometry_id: str,
    file_path: str, width: int | None, height: int | None,
    findings: list[dict[str, Any]], actual_texture_size: tuple[int, int] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    uv = _pair(cube.get("uv"), "cube.uv")
    if uv is None:
        _add_finding(findings, "warning", "MISSING_OR_INVALID_BOX_UV", file_path,
                     f"{geometry_id} bone {bone_name!r} cube {cube_index} has no valid two-number classic box UV origin",
                     geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index)
        return [], 0
    size = _size3(cube.get("size"))
    if size is None or any(part < 0 for part in size):
        _add_finding(findings, "error", "INVALID_CUBE_SIZE", file_path,
                     f"{geometry_id} bone {bone_name!r} cube {cube_index} needs a finite non-negative three-number size for UV extent calculation",
                     geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index)
        return [], 0
    x, y, z = size
    uv_size = (2.0 * (x + z), y + z)
    record = _check_rect(
        findings=findings, path=file_path, geometry_id=geometry_id, bone=bone_name,
        cube_index=cube_index, face="box", uv=uv, uv_size=uv_size,
        width=width, height=height, source="classic_box_uv", actual_texture_size=actual_texture_size,
    )
    return [record], 6


def _audit_per_face(
    cube: dict[str, Any], *, bone_name: str, cube_index: int, geometry_id: str,
    file_path: str, width: int | None, height: int | None,
    findings: list[dict[str, Any]], actual_texture_size: tuple[int, int] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    uv_map = cube.get("uv")
    if not isinstance(uv_map, dict):
        _add_finding(findings, "warning", "INVALID_PER_FACE_UV", file_path,
                     f"{geometry_id} bone {bone_name!r} cube {cube_index} per-face UV mapping must be an object",
                     geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index)
        return [], 0
    size = _size3(cube.get("size"))
    records: list[dict[str, Any]] = []
    recognized_faces = [key for key in uv_map if key in FACE_DIMENSIONS]
    unknown_faces = [key for key in uv_map if key not in FACE_DIMENSIONS]
    for face in unknown_faces:
        _add_finding(findings, "error", "UNKNOWN_UV_FACE", file_path,
                     f"{geometry_id} bone {bone_name!r} cube {cube_index} uses unknown UV face {face!r}",
                     geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index, face=face)
    if not recognized_faces:
        _add_finding(findings, "info", "NO_RENDERED_UV_FACES", file_path,
                     f"{geometry_id} bone {bone_name!r} cube {cube_index} has no recognized face mappings; this may be intentional",
                     geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index)
        return [], 0
    for face in sorted(recognized_faces):
        face_data = uv_map[face]
        face_path = f"{face}"
        if not isinstance(face_data, dict):
            _add_finding(findings, "error", "INVALID_UV_FACE_ENTRY", file_path,
                         f"{geometry_id} bone {bone_name!r} cube {cube_index} face {face!r} must be an object",
                         geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index, face=face)
            continue
        uv = _pair(face_data.get("uv"), f"{face}.uv")
        if uv is None:
            _add_finding(findings, "error", "INVALID_UV_FACE_ORIGIN", file_path,
                         f"{geometry_id} bone {bone_name!r} cube {cube_index} face {face!r} needs a finite two-number uv origin",
                         geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index, face=face)
            continue
        uv_size_raw = face_data.get("uv_size")
        if uv_size_raw is None:
            if size is None:
                _add_finding(findings, "warning", "UNKNOWN_DEFAULT_FACE_UV_SIZE", file_path,
                             f"{geometry_id} bone {bone_name!r} cube {cube_index} face {face!r} omits uv_size and has no valid cube size",
                             geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index, face=face)
                continue
            axis_pair = FACE_DIMENSIONS[face]
            uv_size = (size[axis_pair[0]], size[axis_pair[1]])
        else:
            uv_size = _pair(uv_size_raw, f"{face}.uv_size")
            if uv_size is None:
                _add_finding(findings, "error", "INVALID_UV_FACE_SIZE", file_path,
                             f"{geometry_id} bone {bone_name!r} cube {cube_index} face {face!r} uv_size must be a finite two-number array",
                             geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index, face=face)
                continue
        rotation = face_data.get("uv_rotation", 0)
        if isinstance(rotation, bool) or not isinstance(rotation, int) or rotation not in {0, 90, 180, 270}:
            _add_finding(findings, "error", "INVALID_UV_ROTATION", file_path,
                         f"{geometry_id} bone {bone_name!r} cube {cube_index} face {face!r} uv_rotation must be 0, 90, 180 or 270",
                         geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index, face=face)
            continue
        if rotation in {90, 270}:
            uv_size = (uv_size[1], uv_size[0])
        record = _check_rect(
            findings=findings, path=file_path, geometry_id=geometry_id, bone=bone_name,
            cube_index=cube_index, face=face, uv=uv, uv_size=uv_size,
            width=width, height=height, source="per_face_uv", actual_texture_size=actual_texture_size,
        )
        record["uv_rotation"] = rotation
        records.append(record)
    return records, len(records)


def _audit_geometry_file(
    path: Path, *, project: Path, rp_root: Path,
    png_size: tuple[int, int] | None,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    relative = _relative(path, project)
    try:
        root = _read_json(path)
    except (OSError, ValueError) as exc:
        _add_finding(findings, "error", "INVALID_GEOMETRY_JSON", relative, str(exc))
        return {"path": relative, "status": "invalid", "geometry_count": 0, "bone_count": 0, "cube_count": 0, "uv_mappings_checked": 0}
    geometries = root.get("minecraft:geometry") if isinstance(root, dict) else None
    if not isinstance(geometries, list) or not geometries:
        _add_finding(findings, "error", "MISSING_GEOMETRY_ARRAY", relative, "file must contain a non-empty minecraft:geometry array")
        return {"path": relative, "status": "invalid", "geometry_count": 0, "bone_count": 0, "cube_count": 0, "uv_mappings_checked": 0}
    file_summary = {"path": relative, "status": "audited", "geometry_count": len(geometries), "bone_count": 0, "cube_count": 0, "uv_mappings_checked": 0, "faces_checked": 0, "geometry": []}
    for geometry_index, geometry in enumerate(geometries):
        if not isinstance(geometry, dict):
            _add_finding(findings, "error", "INVALID_GEOMETRY_ENTRY", relative, f"minecraft:geometry[{geometry_index}] must be an object")
            file_summary["status"] = "partial"
            continue
        description = geometry.get("description")
        if not isinstance(description, dict):
            _add_finding(findings, "error", "INVALID_GEOMETRY_DESCRIPTION", relative, f"geometry[{geometry_index}].description must be an object")
            file_summary["status"] = "partial"
            continue
        geometry_id = description.get("identifier") if isinstance(description.get("identifier"), str) else f"<geometry[{geometry_index}]>"
        declared_width = description.get("texture_width")
        declared_height = description.get("texture_height")
        width = declared_width if isinstance(declared_width, int) and not isinstance(declared_width, bool) and 1 <= declared_width <= MAX_DIMENSION else None
        height = declared_height if isinstance(declared_height, int) and not isinstance(declared_height, bool) and 1 <= declared_height <= MAX_DIMENSION else None
        if declared_width is not None and width is None:
            _add_finding(findings, "error", "INVALID_TEXTURE_WIDTH", relative, f"{geometry_id} texture_width must be an integer from 1 to {MAX_DIMENSION}", geometry_identifier=geometry_id)
            file_summary["status"] = "partial"
        if declared_height is not None and height is None:
            _add_finding(findings, "error", "INVALID_TEXTURE_HEIGHT", relative, f"{geometry_id} texture_height must be an integer from 1 to {MAX_DIMENSION}", geometry_identifier=geometry_id)
            file_summary["status"] = "partial"
        if (width is None) != (height is None):
            _add_finding(findings, "warning", "INCOMPLETE_TEXTURE_CANVAS", relative, f"{geometry_id} declares only one texture dimension; UV bounds require both", geometry_identifier=geometry_id)
            width = height = None
            file_summary["status"] = "partial"
        if width is not None and height is not None and png_size is not None and (width, height) != png_size:
            _add_finding(findings, "warning", "TEXTURE_CANVAS_DIMENSION_MISMATCH", relative,
                         f"{geometry_id} declares {width}x{height}, but the explicitly supplied PNG is {png_size[0]}x{png_size[1]}",
                         geometry_identifier=geometry_id, declared_texture_size=[width, height], actual_texture_size=list(png_size))
        if width is None or height is None:
            if png_size is not None:
                width, height = png_size
                _add_finding(findings, "info", "PNG_DIMENSIONS_USED", relative,
                             f"{geometry_id} has no complete declared texture canvas; bounds are checked against the supplied PNG dimensions",
                             geometry_identifier=geometry_id, texture_size=[width, height])
            else:
                _add_finding(findings, "warning", "TEXTURE_CANVAS_UNKNOWN", relative,
                             f"{geometry_id} has no complete texture_width/texture_height and no PNG was supplied; UV bounds cannot be proven",
                             geometry_identifier=geometry_id)
                file_summary["status"] = "partial"
        bones = geometry.get("bones")
        if not isinstance(bones, list):
            _add_finding(findings, "error", "INVALID_BONES_ARRAY", relative, f"{geometry_id} bones must be an array", geometry_identifier=geometry_id)
            file_summary["status"] = "partial"
            continue
        geom_summary = {"identifier": geometry_id, "texture_size_used": [width, height] if width and height else None, "bones": len(bones), "cubes": 0, "uv_mappings_checked": 0, "faces_checked": 0}
        for bone_index, bone in enumerate(bones):
            if not isinstance(bone, dict):
                _add_finding(findings, "error", "INVALID_BONE_ENTRY", relative, f"{geometry_id} bone[{bone_index}] must be an object", geometry_identifier=geometry_id)
                file_summary["status"] = "partial"
                continue
            bone_name = bone.get("name") if isinstance(bone.get("name"), str) else f"<bone[{bone_index}]>"
            cubes = bone.get("cubes", [])
            if not isinstance(cubes, list):
                _add_finding(findings, "error", "INVALID_CUBES_ARRAY", relative, f"{geometry_id} bone {bone_name!r} cubes must be an array", geometry_identifier=geometry_id, bone=bone_name)
                file_summary["status"] = "partial"
                continue
            for cube_index, cube in enumerate(cubes):
                geom_summary["cubes"] += 1
                if not isinstance(cube, dict):
                    _add_finding(findings, "error", "INVALID_CUBE_ENTRY", relative, f"{geometry_id} bone {bone_name!r} cube[{cube_index}] must be an object", geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index)
                    file_summary["status"] = "partial"
                    continue
                uv = cube.get("uv")
                if isinstance(uv, dict):
                    records, faces = _audit_per_face(cube, bone_name=bone_name, cube_index=cube_index, geometry_id=geometry_id,
                                                     file_path=relative, width=width, height=height, findings=findings, actual_texture_size=png_size)
                elif isinstance(uv, list):
                    records, faces = _audit_classic_box(cube, bone_name=bone_name, cube_index=cube_index, geometry_id=geometry_id,
                                                        file_path=relative, width=width, height=height, findings=findings, actual_texture_size=png_size)
                else:
                    _add_finding(findings, "warning", "MISSING_CUBE_UV", relative,
                                 f"{geometry_id} bone {bone_name!r} cube {cube_index} has no supported UV mapping",
                                 geometry_identifier=geometry_id, bone=bone_name, cube_index=cube_index)
                    records, faces = [], 0
                    file_summary["status"] = "partial"
                geom_summary["uv_mappings_checked"] += len(records)
                geom_summary["faces_checked"] += faces
                file_summary["uv_mappings_checked"] += len(records)
                file_summary["faces_checked"] += faces
                for poly_key in ("poly_mesh", "texture_meshes"):
                    if poly_key in bone:
                        _add_finding(findings, "warning", "UNSUPPORTED_MESH_UV_SCOPE", relative,
                                     f"{geometry_id} bone {bone_name!r} contains {poly_key}; this tool currently audits cube UVs only",
                                     geometry_identifier=geometry_id, bone=bone_name, resource=poly_key)
                        file_summary["status"] = "partial"
        file_summary["bone_count"] += len(bones)
        file_summary["cube_count"] += geom_summary["cubes"]
        file_summary["geometry"].append(geom_summary)
    return file_summary


def audit_geometry_uvs(raw_args: Any) -> dict[str, Any]:
    args = _validate_args(raw_args)
    _, project, rp_root = _resolve_project(args["project_directory"])
    findings: list[dict[str, Any]] = []
    texture_size: tuple[int, int] | None = None
    texture_record: dict[str, Any] | None = None
    if "texture_path" in args:
        texture_rel = "/".join(args["texture_path"].split("/")[2:])
        texture = _safe_resolve(rp_root, texture_rel, label="texture_path")
        try:
            texture_size = validate_png_file(texture, max_bytes=MAX_PNG_BYTES, max_dimension=MAX_DIMENSION, max_pixels=MAX_PIXELS)
            texture_record = {"path": _relative(texture, project), "width": texture_size[0], "height": texture_size[1], "status": "valid_png"}
        except PngValidationError as exc:
            _add_finding(findings, "error", "INVALID_TEXTURE_PNG", _relative(texture, project), str(exc))
            texture_record = {"path": _relative(texture, project), "status": "invalid_png"}
    if "geometry_path" in args:
        geometry_rel = "/".join(args["geometry_path"].split("/")[2:])
        geometry = _safe_resolve(rp_root, geometry_rel, label="geometry_path")
        files = [geometry]
    else:
        geometry_root = rp_root / "models" / "entity"
        current = rp_root
        for part in ("models", "entity"):
            current = current / part
            if current.is_symlink():
                raise ValueError("Resource Pack models/entity path contains a symlink")
        try:
            geometry_root = geometry_root.resolve(strict=True)
            geometry_root.relative_to(rp_root)
        except (OSError, ValueError) as exc:
            raise ValueError("Resource Pack models/entity directory is missing or resolves outside the Resource Pack") from exc
        if not geometry_root.is_dir():
            raise ValueError("Resource Pack models/entity directory is missing or unsafe")
        files = _walk_geometry_files(geometry_root, project, findings)
    if not files:
        _add_finding(findings, "warning", "NO_GEOMETRY_FILES", "resource_packs/<RP>/models/entity", "no geometry JSON files were discovered")
    summaries = [_audit_geometry_file(path, project=project, rp_root=rp_root, png_size=texture_size if texture_record and texture_record.get("status") == "valid_png" else None, findings=findings) for path in files]
    if len(findings) >= MAX_FINDINGS:
        findings.append(_finding("warning", "FINDING_LIMIT", "", f"findings were truncated at {MAX_FINDINGS}"))
    incomplete_codes = {
        "UNSAFE_GEOMETRY_DIRECTORY", "UNSAFE_GEOMETRY_FILE", "GEOMETRY_SCAN_LIMIT", "INVALID_GEOMETRY_JSON",
        "MISSING_GEOMETRY_ARRAY", "INVALID_GEOMETRY_ENTRY", "INVALID_GEOMETRY_DESCRIPTION", "INVALID_BONES_ARRAY",
        "INVALID_BONE_ENTRY", "INVALID_CUBES_ARRAY", "INVALID_CUBE_ENTRY", "UNKNOWN_UV_FACE",
        "INVALID_UV_FACE_ENTRY", "INVALID_UV_FACE_ORIGIN", "INVALID_UV_FACE_SIZE", "INVALID_UV_ROTATION", "INVALID_TEXTURE_PNG",
        "NO_GEOMETRY_FILES",
        "INVALID_CUBE_SIZE", "MISSING_OR_INVALID_BOX_UV", "MISSING_CUBE_UV", "TEXTURE_CANVAS_UNKNOWN",
        "INCOMPLETE_TEXTURE_CANVAS", "UNSUPPORTED_MESH_UV_SCOPE", "INVALID_TEXTURE_WIDTH", "INVALID_TEXTURE_HEIGHT",
    }
    analysis_complete = not any(item["code"] in incomplete_codes for item in findings)
    counts = {"errors": 0, "warnings": 0, "informational_findings": 0}
    for item in findings:
        if item["severity"] == "error":
            counts["errors"] += 1
        elif item["severity"] == "warning":
            counts["warnings"] += 1
        else:
            counts["informational_findings"] += 1
    totals = {
        "geometry_files_scanned": len(files),
        "geometry_variants": sum(item.get("geometry_count", 0) for item in summaries),
        "bones_scanned": sum(item.get("bone_count", 0) for item in summaries),
        "cubes_scanned": sum(item.get("cube_count", 0) for item in summaries),
        "uv_mappings_checked": sum(item.get("uv_mappings_checked", 0) for item in summaries),
        "faces_checked": sum(item.get("faces_checked", 0) for item in summaries),
        "analysis_complete": analysis_complete,
        **counts,
    }
    return {
        "status": "issues_found" if counts["errors"] else ("ok" if analysis_complete else "partial"),
        "project_directory": args["project_directory"],
        "texture": texture_record,
        "summary": totals,
        "files": summaries,
        "findings": findings,
        "scope_note": (
            "Checks classic box UV bounding rectangles and alternate per-face UV/uv_size/uv_rotation mappings. "
            "A supplied PNG is explicitly associated only with the selected geometry file and is fully validated; "
            "texture aliases are not auto-resolved from client-entity JSON. Poly meshes and texture meshes are "
            "reported as outside current UV coverage. This is static bounds validation, not a pixel preview or proof "
            "of correct texture painting, UV orientation, material behavior or Minecraft rendering. Runtime NOT RUN."
        ),
        "runtime_status": "NOT RUN",
    }


def _tool_result(request_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0", "id": request_id,
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
        return None
    if method == "initialize":
        requested = params.get("protocolVersion", "2024-11-05")
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": requested,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "minecraft-bedrock-geometry-uv-auditor", "version": SERVER_VERSION},
            "instructions": "Use audit_geometry_uvs on an existing project. It is read-only, handles classic and per-face cube UV mappings, can validate an explicitly provided PNG, and does not prove visual rendering. Runtime NOT RUN.",
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in TOOL_BY_NAME:
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = audit_geometry_uvs(arguments)
        except ValueError as exc:
            payload = _error("INVALID_ARGUMENT", str(exc))
        except OSError as exc:
            payload = _error("AUDIT_IO_ERROR", f"could not inspect project safely: {exc}")
        except Exception as exc:  # no traceback through MCP stdio
            payload = _error("INTERNAL_ERROR", f"unexpected {type(exc).__name__}: {exc}")
        return _tool_result(request_id, payload)
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle_message(json.loads(line))
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
