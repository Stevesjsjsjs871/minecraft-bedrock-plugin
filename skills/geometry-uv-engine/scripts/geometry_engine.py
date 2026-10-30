#!/usr/bin/env python3
"""Dependency-free static parser and bounded UV analyzer for Bedrock .geo.json."""
from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import stat
import sys
from pathlib import Path

FACES = ("north", "south", "east", "west", "up", "down")
FACE_AXES = {
    "north": (0, 1),
    "south": (0, 1),
    "east": (2, 1),
    "west": (2, 1),
    "up": (0, 2),
    "down": (0, 2),
}
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_GEOMETRIES = 128
MAX_BONES = 1024
MAX_CUBES = 6000
MAX_REGIONS = 6000
MAX_FINDINGS = 5000
MAX_CANVAS_DIMENSION = 4096
MAX_OVERLAP_COMPARISONS = 250_000
MAX_REPORTED_OVERLAPS = 2000


class GeometryError(ValueError):
    """Raised when a geometry document cannot be analyzed safely."""


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GeometryError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_constant(value):
    raise GeometryError(f"non-finite JSON constant is not allowed: {value}")


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GeometryError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise GeometryError(f"{label} must be a finite number")
    return result


def _vec3(value, label, *, positive=False):
    if not isinstance(value, list) or len(value) != 3:
        raise GeometryError(f"{label} must be a three-number array")
    result = tuple(_finite_number(item, f"{label}[{index}]") for index, item in enumerate(value))
    if positive and any(item <= 0 for item in result):
        raise GeometryError(f"{label} dimensions must be positive")
    return result


def _uv_pair(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise GeometryError(f"{label} must be a two-number array")
    return tuple(_finite_number(item, f"{label}[{index}]") for index, item in enumerate(value))


def _canvas(description, findings):
    width_present = "texture_width" in description
    height_present = "texture_height" in description
    if not width_present and not height_present:
        findings.append({
            "severity": "WARN",
            "code": "TEXTURE_CANVAS_UNKNOWN",
            "message": "geometry does not declare texture_width or texture_height; UV bounds cannot be proven",
        })
        return None
    if width_present != height_present:
        findings.append({
            "severity": "WARN",
            "code": "INCOMPLETE_TEXTURE_CANVAS",
            "message": "geometry declares only one texture canvas dimension; UV bounds cannot be proven",
        })
        return None

    dimensions = []
    for key in ("texture_width", "texture_height"):
        value = description[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise GeometryError(f"{key} must be an integer according to the Bedrock geometry schema")
        if not 1 <= value <= MAX_CANVAS_DIMENSION:
            raise GeometryError(
                f"{key} must be between 1 and {MAX_CANVAS_DIMENSION} (an analyzer safety limit)"
            )
        dimensions.append(value)
    return tuple(dimensions)


def _rect(selector, u, v, width, height, canvas):
    values = (u, v, width, height)
    if not all(math.isfinite(value) for value in values) or width < 0 or height < 0:
        raise GeometryError(f"invalid UV rectangle for {selector}")
    u2 = u + width
    v2 = v + height
    if not math.isfinite(u2) or not math.isfinite(v2):
        raise GeometryError(f"UV rectangle overflows numeric range for {selector}")
    out_of_bounds = None
    if canvas is not None:
        texture_width, texture_height = canvas
        out_of_bounds = u < 0 or v < 0 or u2 > texture_width or v2 > texture_height
    return {
        "selector": selector,
        "u": u,
        "v": v,
        "width": width,
        "height": height,
        "u2": u2,
        "v2": v2,
        "out_of_bounds": out_of_bounds,
    }


def _intersects(left, right):
    return (
        min(left["u2"], right["u2"]) > max(left["u"], right["u"])
        and min(left["v2"], right["v2"]) > max(left["v"], right["v"])
    )


def _overlaps(regions):
    """Sweep-line overlap check with an explicit comparison budget."""
    ordered = sorted(enumerate(regions), key=lambda item: (item[1]["u"], item[1]["v"]))
    active = {}
    expiry = []
    overlaps = []
    total = 0
    comparisons = 0
    complete = True

    for index, region in ordered:
        while expiry and expiry[0][0] <= region["u"]:
            _, expired_index = heapq.heappop(expiry)
            active.pop(expired_index, None)

        for old_index, old_region in active.items():
            comparisons += 1
            if comparisons > MAX_OVERLAP_COMPARISONS:
                complete = False
                break
            if _intersects(old_region, region):
                total += 1
                if len(overlaps) < MAX_REPORTED_OVERLAPS:
                    overlaps.append({
                        "a": old_region["selector"],
                        "b": region["selector"],
                        "intersection": {
                            "u": max(old_region["u"], region["u"]),
                            "v": max(old_region["v"], region["v"]),
                            "u2": min(old_region["u2"], region["u2"]),
                            "v2": min(old_region["v2"], region["v2"]),
                        },
                    })
        if not complete:
            break
        active[index] = region
        heapq.heappush(expiry, (region["u2"], index))

    return overlaps, total, comparisons, complete


def _add_finding(findings, severity, code, message, **details):
    if len(findings) < MAX_FINDINGS:
        item = {"severity": severity, "code": code, "message": message}
        item.update(details)
        findings.append(item)


def analyze_geometry(data, *, geometry_identifier=None):
    if not isinstance(data, dict):
        raise GeometryError("geometry document root must be an object")
    format_version = data.get("format_version")
    if format_version is not None and not isinstance(format_version, str):
        raise GeometryError("format_version must be a string")

    geometries = data.get("minecraft:geometry")
    if not isinstance(geometries, list) or not geometries:
        raise GeometryError("minecraft:geometry must be a non-empty array")
    if len(geometries) > MAX_GEOMETRIES:
        raise GeometryError(f"geometry count exceeds the safety limit of {MAX_GEOMETRIES}")
    if geometry_identifier is not None and (
        not isinstance(geometry_identifier, str) or not geometry_identifier
    ):
        raise GeometryError("geometry_identifier must be a non-empty string")

    candidates = []
    identifiers = {}
    for index, geometry in enumerate(geometries):
        if not isinstance(geometry, dict):
            raise GeometryError(f"minecraft:geometry[{index}] must be an object")
        description = geometry.get("description")
        if not isinstance(description, dict):
            raise GeometryError(f"minecraft:geometry[{index}].description must be an object")
        identifier = description.get("identifier")
        if not isinstance(identifier, str) or not identifier:
            raise GeometryError(f"minecraft:geometry[{index}].description.identifier is required")
        identifiers.setdefault(identifier, []).append(index)
        if geometry_identifier is None or identifier == geometry_identifier:
            candidates.append((index, geometry, description))

    if geometry_identifier is None and len(geometries) != 1:
        raise GeometryError("multiple geometries found; pass --geometry-identifier to select one")
    if not candidates:
        raise GeometryError(f"geometry identifier not found: {geometry_identifier}")
    if len(candidates) != 1:
        raise GeometryError(f"geometry identifier is ambiguous: {geometry_identifier!r}")
    selected_index, geometry, description = candidates[0]

    identifier = description["identifier"]
    findings = []
    canvas = _canvas(description, findings)
    bones = geometry.get("bones", [])
    if not isinstance(bones, list):
        raise GeometryError("bones must be an array")
    if len(bones) > MAX_BONES:
        raise GeometryError(f"bone count exceeds the safety limit of {MAX_BONES}")
    if not bones:
        _add_finding(findings, "WARN", "NO_BONES", "selected geometry contains no bones")

    regions = []
    bone_names = set()
    cube_count = 0
    for bone_index, bone in enumerate(bones):
        if not isinstance(bone, dict):
            raise GeometryError(f"bones[{bone_index}] must be an object")
        bone_name = bone.get("name")
        if not isinstance(bone_name, str) or not bone_name:
            raise GeometryError(f"bones[{bone_index}].name is required")
        if bone_name in bone_names:
            _add_finding(
                findings, "WARN", "DUPLICATE_BONE_NAME",
                f"duplicate bone name {bone_name!r}", bone=bone_name, bone_index=bone_index,
            )
        bone_names.add(bone_name)

        # The official geometry schema places both mesh forms on a bone, not on a cube.
        for mesh_key in ("poly_mesh", "texture_meshes"):
            if mesh_key in bone:
                _add_finding(
                    findings, "WARN", "UNSUPPORTED_MESH_UV",
                    f"bone {bone_name!r} contains {mesh_key}; this analyzer only covers cube UVs",
                    bone=bone_name, bone_index=bone_index, resource=mesh_key,
                )

        cubes = bone.get("cubes", [])
        if not isinstance(cubes, list):
            raise GeometryError(f"bone {bone_name!r} cubes must be an array")
        cube_count += len(cubes)
        if cube_count > MAX_CUBES:
            raise GeometryError(f"cube count exceeds the safety limit of {MAX_CUBES}")

        for cube_index, cube in enumerate(cubes):
            if not isinstance(cube, dict):
                raise GeometryError(f"bone {bone_name!r} cube {cube_index} must be an object")
            size = _vec3(cube.get("size"), f"{bone_name}.cubes[{cube_index}].size", positive=True)
            _vec3(cube.get("origin"), f"{bone_name}.cubes[{cube_index}].origin")
            selector = {"bone": bone_name, "cube_index": cube_index}
            uv = cube.get("uv")

            if isinstance(uv, list):
                u, v = _uv_pair(uv, f"{bone_name}.cubes[{cube_index}].uv")
                width = 2 * (size[0] + size[2])
                height = size[1] + size[2]
                regions.append(_rect({**selector, "face": "box"}, u, v, width, height, canvas))
            elif isinstance(uv, dict):
                if not uv:
                    _add_finding(
                        findings, "INFO", "NO_UV_FACES",
                        f"bone {bone_name!r} cube {cube_index} declares no rendered UV faces",
                        **selector,
                    )
                for face, face_data in uv.items():
                    if face not in FACES:
                        _add_finding(
                            findings, "WARN", "UNKNOWN_UV_FACE",
                            f"unsupported UV face key {face!r}", **selector, face=face,
                        )
                        continue
                    if not isinstance(face_data, dict):
                        raise GeometryError(
                            f"{bone_name}.cubes[{cube_index}].uv.{face} must be an object"
                        )
                    u, v = _uv_pair(
                        face_data.get("uv"),
                        f"{bone_name}.cubes[{cube_index}].uv.{face}.uv",
                    )
                    axes = FACE_AXES[face]
                    default_size = (size[axes[0]], size[axes[1]])
                    raw_size = face_data.get("uv_size")
                    face_width, face_height = (
                        default_size if raw_size is None else _uv_pair(
                            raw_size,
                            f"{bone_name}.cubes[{cube_index}].uv.{face}.uv_size",
                        )
                    )
                    rotation = face_data.get("uv_rotation", 0)
                    if (
                        isinstance(rotation, bool)
                        or not isinstance(rotation, int)
                        or rotation not in (0, 90, 180, 270)
                    ):
                        raise GeometryError(
                            f"{bone_name}.cubes[{cube_index}].uv.{face}.uv_rotation "
                            "must be an integer: 0, 90, 180 or 270"
                        )
                    face_width, face_height = abs(face_width), abs(face_height)
                    if rotation in (90, 270):
                        face_width, face_height = face_height, face_width
                    if face_width == 0 or face_height == 0:
                        _add_finding(
                            findings, "WARN", "ZERO_AREA_UV",
                            f"bone {bone_name!r} cube {cube_index} face {face!r} has a zero-area UV rectangle",
                            **selector, face=face,
                        )
                    regions.append(
                        _rect(
                            {**selector, "face": face},
                            u, v, face_width, face_height, canvas,
                        )
                    )
            else:
                raise GeometryError(
                    f"bone {bone_name!r} cube {cube_index} uv must be a classic array or per-face object"
                )

            for mesh_key in ("poly_mesh", "texture_meshes"):
                if mesh_key in cube:
                    _add_finding(
                        findings, "WARN", "MESH_PROPERTY_AT_CUBE_LEVEL",
                        f"{mesh_key} is not a supported cube UV field; official geometry places mesh data on bones",
                        **selector, resource=mesh_key,
                    )
            if len(regions) > MAX_REGIONS:
                raise GeometryError(f"UV region count exceeds the safety limit of {MAX_REGIONS}")

    if cube_count == 0:
        _add_finding(findings, "WARN", "NO_CUBES", "selected geometry contains no cubes to analyze")

    if canvas is not None:
        for region in regions:
            if region["out_of_bounds"]:
                _add_finding(
                    findings, "FAIL", "UV_OUT_OF_BOUNDS",
                    "UV rectangle exceeds the declared texture canvas",
                    region=region,
                )

    overlaps, overlap_count, comparisons, overlap_complete = _overlaps(regions)
    if overlap_count:
        _add_finding(
            findings, "WARN", "UV_OVERLAP",
            "UV rectangles share positive-area regions; intentional mirroring or reuse is possible",
            count=overlap_count,
            reported_count=len(overlaps),
        )
    if not overlap_complete:
        _add_finding(
            findings, "WARN", "OVERLAP_ANALYSIS_TRUNCATED",
            f"overlap comparison budget ({MAX_OVERLAP_COMPARISONS}) was reached",
            comparisons=comparisons,
        )
    if overlap_count > len(overlaps):
        _add_finding(
            findings, "WARN", "OVERLAP_REPORT_TRUNCATED",
            f"only the first {len(overlaps)} of {overlap_count} overlap pairs are included",
        )
    if len(findings) >= MAX_FINDINGS:
        findings.append({
            "severity": "WARN",
            "code": "FINDING_LIMIT",
            "message": f"finding output was truncated at {MAX_FINDINGS}",
        })

    status = (
        "FAIL" if any(item["severity"] == "FAIL" for item in findings)
        else "WARN" if any(item["severity"] == "WARN" for item in findings)
        else "PASS"
    )
    return {
        "geometry_identifier": identifier,
        "geometry_index": selected_index,
        "format_version": format_version,
        "texture_canvas": (
            {"width": canvas[0], "height": canvas[1]} if canvas is not None else None
        ),
        "bone_count": len(bones),
        "cube_count": cube_count,
        "regions": regions,
        "overlaps": overlaps,
        "findings": findings,
        "summary": {
            "regions": len(regions),
            "overlaps": overlap_count,
            "reported_overlaps": len(overlaps),
            "out_of_bounds": sum(1 for region in regions if region["out_of_bounds"] is True),
            "bounds_checked": canvas is not None,
            "overlap_comparisons": comparisons,
            "overlap_analysis_complete": overlap_complete,
            "status": status,
        },
    }


def analyze_file(path, *, geometry_identifier=None):
    source = Path(path).expanduser()
    if source.is_symlink() or not source.is_file():
        raise GeometryError("geometry path must be a regular non-symlink file")
    try:
        size = source.stat().st_size
        if size > MAX_JSON_BYTES:
            raise GeometryError(f"geometry JSON exceeds the {MAX_JSON_BYTES}-byte safety limit")
        payload = source.read_bytes()
    except OSError as exc:
        raise GeometryError(f"geometry file could not be read: {exc}") from exc
    if len(payload) != size:
        raise GeometryError("geometry file changed while it was being read")
    try:
        text = payload.decode("utf-8-sig")
        data = json.loads(
            text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_nonfinite_constant,
        )
    except UnicodeDecodeError as exc:
        raise GeometryError("geometry JSON must be UTF-8 encoded") from exc
    except json.JSONDecodeError as exc:
        raise GeometryError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    return analyze_geometry(data, geometry_identifier=geometry_identifier)


def _write_new_report(path, rendered):
    target = Path(path).expanduser()
    try:
        parent = target.parent.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise GeometryError(f"report parent directory does not exist: {target.parent}") from exc
    if not parent.is_dir() or not target.name or target.name in {".", ".."}:
        raise GeometryError("report parent must exist and report path must name a file")
    destination = parent / target.name
    if destination.exists() or destination.is_symlink():
        raise GeometryError("report already exists; refusing to overwrite it")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(destination, flags, 0o600)
    except FileExistsError as exc:
        raise GeometryError("report already exists; refusing to overwrite it") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geometry", help="Path to one Bedrock .geo.json file")
    parser.add_argument("--geometry-identifier", help="Exact description.identifier when selecting one geometry")
    parser.add_argument("--report", help="Write JSON report to a new path; existing files are never overwritten")
    args = parser.parse_args(argv)

    try:
        result = analyze_file(args.geometry, geometry_identifier=args.geometry_identifier)
        rendered = json.dumps(result, indent=2, ensure_ascii=False)
        if args.report:
            _write_new_report(args.report, rendered)
    except Exception as exc:
        print(json.dumps({
            "status": "FAIL",
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }, indent=2, ensure_ascii=False))
        return 2

    print(rendered)
    return 1 if result["summary"]["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
