#!/usr/bin/env python3
"""Deterministic, read-only segmentation of a Bedrock model reference PNG.

This local utility labels connected alpha/color regions and can rank those
regions against supported cube UV faces. It never infers semantic body parts
or modifies project files. All candidate mappings require visual review.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[2]
for relative in (
    "skills/texture-painting-pipeline/scripts",
    "skills/visual-resource-pipeline/scripts",
    "skills/geometry-uv-engine/scripts",
):
    target = str(PLUGIN_ROOT / relative)
    if target not in sys.path:
        sys.path.insert(0, target)

import geometry_engine
import texture_painter
import uv_template_engine

_png_validator_path = PLUGIN_ROOT / "skills/visual-resource-pipeline/scripts/png_engine.py"
_png_spec = importlib.util.spec_from_file_location("mbe_visual_reference_png_validator", _png_validator_path)
if _png_spec is None or _png_spec.loader is None:
    raise RuntimeError("could not load the shared PNG validator")
png_engine = importlib.util.module_from_spec(_png_spec)
_png_spec.loader.exec_module(png_engine)

PROJECT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_REFERENCE_BYTES = 16 * 1024 * 1024
MAX_REFERENCE_DIMENSION = 2048
MAX_REFERENCE_PIXELS = 1_048_576
MAX_RUNS = 120_000
MAX_MATCHABLE_UV_REGIONS = 512
MAX_REGIONS = 96
MAX_UV_MATCHES = 3
MAX_GEOMETRY_BYTES = 2 * 1024 * 1024


class ReferenceAnalysisError(ValueError):
    """Invalid project input, unsupported data or an analyzer safety limit."""


def _safe_relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ReferenceAnalysisError(f"{label} must be a non-empty relative POSIX path up to 512 characters")
    if "\\" in value or "\x00" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ReferenceAnalysisError(f"{label} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReferenceAnalysisError(f"{label} must not contain empty, dot or traversal path segments")
    return value


def _resolve_project(project_root: str | Path) -> tuple[Path, str]:
    supplied = Path(project_root).expanduser()
    if supplied.is_symlink():
        raise ReferenceAnalysisError("project root must not be a symlink")
    try:
        root = supplied.resolve(strict=True)
    except OSError as exc:
        raise ReferenceAnalysisError(f"project root is unavailable: {supplied}") from exc
    if not root.is_dir() or not PROJECT_RE.fullmatch(root.name):
        raise ReferenceAnalysisError("project root must be an existing directory with a lowercase kebab-case name")
    rp = root / "resource_packs" / f"{root.name}_RP"
    for candidate in (root / "resource_packs", rp, rp / "manifest.json"):
        if candidate.is_symlink():
            raise ReferenceAnalysisError(f"unsafe symlink in Resource Pack path: {candidate}")
    if not rp.is_dir() or not (rp / "manifest.json").is_file():
        raise ReferenceAnalysisError(f"expected Resource Pack manifest is missing: resource_packs/{root.name}_RP/manifest.json")
    return root, root.name


def _resolve_project_file(root: Path, relative: str, label: str) -> Path:
    relative = _safe_relative(relative, label)
    candidate = root
    for part in relative.split("/"):
        candidate = candidate / part
        if candidate.is_symlink():
            raise ReferenceAnalysisError(f"{label} contains a symlink")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ReferenceAnalysisError(f"{label} is missing or resolves outside the project") from exc
    if not resolved.is_file():
        raise ReferenceAnalysisError(f"{label} must be a regular file")
    return resolved


def _new_node(parent: list[int], area: list[int], bounds: list[list[int]], sums: list[list[int]],
              x0: int, y: int, x1: int, color_sums: tuple[int, int, int, int]) -> int:
    node = len(parent)
    run_area = x1 - x0
    parent.append(node)
    area.append(run_area)
    bounds.append([x0, y, x1, y + 1])
    sums.append([
        (x0 + x1 - 1) * run_area // 2,
        y * run_area,
        color_sums[0], color_sums[1], color_sums[2], color_sums[3],
    ])
    return node


def _find(parent: list[int], node: int) -> int:
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]
    return node


def _union(parent: list[int], area: list[int], bounds: list[list[int]], sums: list[list[int]], a: int, b: int) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra == rb:
        return
    if area[ra] < area[rb]:
        ra, rb = rb, ra
    parent[rb] = ra
    area[ra] += area[rb]
    ba, bb = bounds[ra], bounds[rb]
    ba[0], ba[1], ba[2], ba[3] = min(ba[0], bb[0]), min(ba[1], bb[1]), max(ba[2], bb[2]), max(ba[3], bb[3])
    sa, sb = sums[ra], sums[rb]
    for index in range(6):
        sa[index] += sb[index]


def _pixel_label(rgba: bytearray, offset: int, mode: str, alpha_threshold: int, bucket: int) -> tuple[int, ...] | None:
    red, green, blue, alpha = rgba[offset:offset + 4]
    if alpha < alpha_threshold:
        return None
    if mode == "alpha_components":
        return (1,)
    return red // bucket, green // bucket, blue // bucket


def segment_rgba(width: int, height: int, rgba: bytearray, *, mode: str = "color_components",
                 alpha_threshold: int = 8, color_bucket_size: int = 16,
                 min_region_area: int = 8, max_regions: int = 48,
                 max_runs: int = MAX_RUNS) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Find deterministic 4-connected same-label regions in an RGBA buffer."""
    if mode not in {"alpha_components", "color_components"}:
        raise ReferenceAnalysisError("mode must be alpha_components or color_components")
    for label, value, low, high in (
        ("width", width, 1, MAX_REFERENCE_DIMENSION),
        ("height", height, 1, MAX_REFERENCE_DIMENSION),
        ("alpha_threshold", alpha_threshold, 1, 255),
        ("min_region_area", min_region_area, 1, MAX_REFERENCE_PIXELS),
        ("max_regions", max_regions, 1, MAX_REGIONS),
        ("max_runs", max_runs, 1, MAX_RUNS),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ReferenceAnalysisError(f"{label} must be an integer from {low} to {high}")
    if isinstance(color_bucket_size, bool) or not isinstance(color_bucket_size, int) or color_bucket_size not in {4, 8, 16, 32, 64}:
        raise ReferenceAnalysisError("color_bucket_size must be one of 4, 8, 16, 32 or 64")
    if width * height > MAX_REFERENCE_PIXELS or len(rgba) != width * height * 4:
        raise ReferenceAnalysisError("RGBA buffer size or canvas area is invalid")

    parent: list[int] = []
    areas: list[int] = []
    bounds: list[list[int]] = []
    sums: list[list[int]] = []
    previous: list[tuple[int, int, tuple[int, ...], int]] = []
    total_runs = 0

    for y in range(height):
        current: list[tuple[int, int, tuple[int, ...], int]] = []
        x = 0
        while x < width:
            offset = (y * width + x) * 4
            label = _pixel_label(rgba, offset, mode, alpha_threshold, color_bucket_size)
            if label is None:
                x += 1
                continue
            x0 = x
            red_sum = green_sum = blue_sum = alpha_sum = 0
            while x < width:
                offset = (y * width + x) * 4
                if _pixel_label(rgba, offset, mode, alpha_threshold, color_bucket_size) != label:
                    break
                red_sum += rgba[offset]
                green_sum += rgba[offset + 1]
                blue_sum += rgba[offset + 2]
                alpha_sum += rgba[offset + 3]
                x += 1
            node = _new_node(parent, areas, bounds, sums, x0, y, x, (red_sum, green_sum, blue_sum, alpha_sum))
            current.append((x0, x, label, node))
            total_runs += 1
            if total_runs > max_runs:
                raise ReferenceAnalysisError(
                    f"reference segmentation exceeded the {max_runs}-run complexity budget; "
                    "increase color_bucket_size or use alpha_components"
                )

        prev_start = 0
        for x0, x1, label, node in current:
            while prev_start < len(previous) and previous[prev_start][1] <= x0:
                prev_start += 1
            cursor = prev_start
            while cursor < len(previous) and previous[cursor][0] < x1:
                px0, px1, prior_label, prior_node = previous[cursor]
                if px1 > x0 and prior_label == label:
                    _union(parent, areas, bounds, sums, node, prior_node)
                cursor += 1
        previous = current

    roots: dict[int, int] = {}
    for node in range(len(parent)):
        root = _find(parent, node)
        roots[root] = root

    components: list[dict[str, Any]] = []
    for root in roots:
        area = areas[root]
        if area < min_region_area:
            continue
        left, top, right, bottom = bounds[root]
        stat = sums[root]
        average = [max(0, min(255, round(stat[index] / area))) for index in (2, 3, 4, 5)]
        components.append({
            "source_rect": {"x": left, "y": top, "width": right - left, "height": bottom - top},
            "pixel_area": area,
            "centroid": [round(stat[0] / area, 2), round(stat[1] / area, 2)],
            "aspect_ratio": round((right - left) / max(1, bottom - top), 4),
            "average_color": "#" + "".join(f"{value:02X}" for value in average[:3]),
            "average_alpha": average[3],
            "edge_contact": {"left": left == 0, "top": top == 0, "right": right == width, "bottom": bottom == height},
        })
    components.sort(key=lambda item: (-item["pixel_area"], item["source_rect"]["y"], item["source_rect"]["x"]))
    total_qualifying = len(components)
    components = components[:max_regions]
    for index, component in enumerate(components, 1):
        component["region_id"] = f"region_{index:03d}"
        component["coverage"] = round(component["pixel_area"] / (width * height), 6)
        edge_count = sum(bool(value) for value in component["edge_contact"].values())
        component["background_candidate"] = bool(
            mode == "color_components" and component["coverage"] >= 0.15 and edge_count >= 2
        )
    return components, {
        "run_count": total_runs,
        "connected_component_count_after_min_area": total_qualifying,
        "returned_region_count": len(components),
        "truncated": total_qualifying > len(components),
        "discarded_below_min_area": len(roots) - total_qualifying,
    }


def candidate_matches(uv_regions: list[dict[str, Any]], components: list[dict[str, Any]],
                      source_width: int, source_height: int,
                      canvas_width: int, canvas_height: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    source_area = source_width * source_height
    canvas_area = canvas_width * canvas_height
    for target in uv_regions[:MAX_MATCHABLE_UV_REGIONS]:
        left, top = float(target["u"]), float(target["v"])
        right, bottom = left + abs(float(target["width"])), top + abs(float(target["height"]))
        target_width, target_height = max(0.001, right - left), max(0.001, bottom - top)
        target_aspect = target_width / target_height
        target_fraction = (target_width * target_height) / canvas_area
        ranked = []
        for source in components:
            rect = source["source_rect"]
            source_aspect = rect["width"] / max(1, rect["height"])
            source_fraction = source["pixel_area"] / source_area
            aspect_score = math.exp(-abs(math.log(max(1e-9, source_aspect / target_aspect))))
            area_score = math.exp(-abs(math.log(max(1e-9, source_fraction / max(1e-9, target_fraction)))))
            score = 0.8 * aspect_score + 0.2 * area_score
            ranked.append({
                "region_id": source["region_id"],
                "source_rect": rect,
                "score": round(score, 4),
                "aspect_score": round(aspect_score, 4),
                "relative_area_score": round(area_score, 4),
            })
        ranked.sort(key=lambda item: (-item["score"], item["region_id"]))
        results.append({
            "target": {
                "bone": target["bone"], "cube_index": target["cube_index"], "face": target["face"],
                "uv_bounds": [round(left, 4), round(top, 4), round(right, 4), round(bottom, 4)],
                "uv_size": [round(target_width, 4), round(target_height, 4)],
            },
            "candidates": ranked[:MAX_UV_MATCHES],
            "matching_basis": "aspect ratio (80%) + normalized source/target area (20%); no semantic recognition",
        })
    return results


def _validate_geometry_path(relative: str, project: str) -> str:
    value = _safe_relative(relative, "geometry_path")
    parts = value.split("/")
    if len(parts) < 5 or parts[:4] != ["resource_packs", f"{project}_RP", "models", "entity"] or not value.endswith(".json"):
        raise ReferenceAnalysisError(f"geometry_path must be JSON under resource_packs/{project}_RP/models/entity/")
    return value


def analyze_reference(project_root: str | Path, reference_image_path: str, *,
                      segmentation_mode: str = "color_components", alpha_threshold: int = 8,
                      color_bucket_size: int = 16, min_region_area: int = 8,
                      max_regions: int = 48, geometry_path: str | None = None,
                      geometry_identifier: str | None = None) -> dict[str, Any]:
    root, project = _resolve_project(project_root)
    ref_relative = _safe_relative(reference_image_path, "reference_image_path")
    parts = ref_relative.split("/")
    if len(parts) < 5 or parts[:3] != ["resource_packs", f"{project}_RP", "textures"] or not ref_relative.endswith(".png"):
        raise ReferenceAnalysisError(f"reference_image_path must be PNG under resource_packs/{project}_RP/textures/")
    if geometry_identifier is not None and (not isinstance(geometry_identifier, str) or not geometry_identifier or len(geometry_identifier) > 128):
        raise ReferenceAnalysisError("geometry_identifier must be a non-empty string up to 128 characters")
    if geometry_path is None and geometry_identifier is not None:
        raise ReferenceAnalysisError("geometry_identifier requires geometry_path")

    ref_path = _resolve_project_file(root, ref_relative, "reference_image_path")
    try:
        ref_size = ref_path.stat().st_size
        if ref_size < 45 or ref_size > MAX_REFERENCE_BYTES:
            raise ReferenceAnalysisError(f"reference PNG must be between 45 bytes and {MAX_REFERENCE_BYTES} bytes")
        payload = ref_path.read_bytes()
    except OSError as exc:
        raise ReferenceAnalysisError(f"reference PNG could not be read: {exc}") from exc
    if len(payload) != ref_size:
        raise ReferenceAnalysisError("reference PNG changed while it was being read")
    try:
        metadata = png_engine.inspect_png(
            payload, max_bytes=MAX_REFERENCE_BYTES,
            max_dimension=MAX_REFERENCE_DIMENSION, max_pixels=MAX_REFERENCE_PIXELS,
        )
    except (png_engine.PNGValidationError, ValueError) as exc:
        raise ReferenceAnalysisError(f"reference PNG validation failed: {exc}") from exc
    if metadata["interlaced"] or metadata["bit_depth"] != 8:
        raise ReferenceAnalysisError("only validated 8-bit non-interlaced PNG images are supported")
    try:
        width, height, rgba = texture_painter._decode_png_rgba(payload)
    except (texture_painter.PaintError, ValueError) as exc:
        raise ReferenceAnalysisError(f"reference PNG decoding failed: {exc}") from exc

    components, segmentation = segment_rgba(
        width, height, rgba, mode=segmentation_mode,
        alpha_threshold=alpha_threshold, color_bucket_size=color_bucket_size,
        min_region_area=min_region_area, max_regions=max_regions,
    )
    if not components:
        raise ReferenceAnalysisError("no visible connected regions met min_region_area; lower the threshold or use color_components")

    alpha_nontransparent = sum(1 for index in range(3, len(rgba), 4) if rgba[index] >= alpha_threshold)
    geometry_info = None
    matches: list[dict[str, Any]] = []
    geometry_findings: list[dict[str, Any]] = []
    if geometry_path is not None:
        geometry_relative = _validate_geometry_path(geometry_path, project)
        geometry_file = _resolve_project_file(root, geometry_relative, "geometry_path")
        try:
            geometry_size = geometry_file.stat().st_size
            if geometry_size > MAX_GEOMETRY_BYTES:
                raise ReferenceAnalysisError(f"geometry JSON exceeds the {MAX_GEOMETRY_BYTES}-byte limit")
            geometry_payload = geometry_file.read_bytes()
            if len(geometry_payload) != geometry_size:
                raise ReferenceAnalysisError("geometry JSON changed while it was being read")
            geometry_raw = geometry_payload.decode("utf-8-sig")
            geometry_data = json.loads(
                geometry_raw,
                object_pairs_hook=geometry_engine._pairs_no_duplicates,
                parse_constant=lambda value: (_ for _ in ()).throw(geometry_engine.GeometryError(f"non-finite JSON constant {value}")),
            )
            analysis, uv_regions = uv_template_engine.extract_regions(geometry_data, geometry_identifier)
        except (OSError, UnicodeError, json.JSONDecodeError, geometry_engine.GeometryError, ValueError) as exc:
            raise ReferenceAnalysisError(f"geometry analysis failed: {exc}") from exc
        canvas = analysis["texture_canvas"]
        matches = candidate_matches(
            uv_regions, components, width, height,
            int(canvas["width"]), int(canvas["height"]),
        )
        geometry_info = {
            "identifier": analysis["geometry_identifier"],
            "path": geometry_relative,
            "texture_canvas": [canvas["width"], canvas["height"]],
            "uv_face_regions": len(uv_regions),
            "uv_candidate_matches": len(matches),
            "uv_matching_truncated": len(uv_regions) > len(matches),
        }
        geometry_findings = analysis.get("findings", [])

    warnings: list[dict[str, str]] = []
    if segmentation_mode == "alpha_components" and len(components) == 1 and not segmentation["truncated"]:
        warnings.append({"code": "SINGLE_ALPHA_SILHOUETTE", "message": "The visible subject is one connected silhouette. Use color_components or supply separated transparent regions to inspect internal parts."})
    if segmentation["truncated"]:
        warnings.append({"code": "REGION_RESULTS_TRUNCATED", "message": "More components met min_region_area than max_regions; only the largest are returned."})
    if any(region.get("background_candidate") for region in components):
        warnings.append({"code": "POSSIBLE_BACKGROUND_REGION", "message": "One or more large color components touch multiple image edges. They may be background; inspect before assigning them to a UV face."})
    if geometry_info and geometry_info["uv_matching_truncated"]:
        warnings.append({"code": "UV_CANDIDATE_MATCHING_TRUNCATED", "message": f"Only the first {MAX_MATCHABLE_UV_REGIONS} UV face regions were ranked against reference components."})
    if any(item.get("code") == "UNSUPPORTED_MESH_UV_SCOPE" for item in geometry_findings):
        warnings.append({"code": "UNSUPPORTED_GEOMETRY_UV", "message": "Some geometry mesh UVs are outside this cube-face analyzer."})

    return {
        "status": "success",
        "reference": {
            "path": ref_relative, "width": width, "height": height, "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "alpha_nontransparent_pixels": alpha_nontransparent,
            "segmentation_mode": segmentation_mode,
        },
        "segmentation": segmentation,
        "regions": components,
        "geometry": geometry_info,
        "geometric_candidates": matches,
        "geometry_findings": geometry_findings[:100],
        "warnings": warnings,
        "scope_note": (
            "This is deterministic 4-connected segmentation, not AI image understanding. Region IDs have no semantic meaning; "
            "matching scores use only aspect ratio and normalized area and are not semantic confidence. Visually confirm each "
            "source_rect before explicitly passing it to UV Mapping Assistant. No project files were written or modified. "
            "Minecraft runtime/rendering: NOT RUN."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", help="existing project folder containing resource_packs/<project>_RP/")
    parser.add_argument("reference_image", help="project-relative PNG under resource_packs/<project>_RP/textures/")
    parser.add_argument("--mode", choices=("alpha_components", "color_components"), default="color_components")
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--color-bucket-size", type=int, choices=(4, 8, 16, 32, 64), default=16)
    parser.add_argument("--min-region-area", type=int, default=8)
    parser.add_argument("--max-regions", type=int, default=48)
    parser.add_argument("--geometry", help="optional project-relative .geo.json under models/entity/")
    parser.add_argument("--geometry-identifier", help="exact geometry identifier when the file contains multiple geometries")
    args = parser.parse_args(argv)
    try:
        result = analyze_reference(
            args.project_root, args.reference_image,
            segmentation_mode=args.mode, alpha_threshold=args.alpha_threshold,
            color_bucket_size=args.color_bucket_size, min_region_area=args.min_region_area,
            max_regions=args.max_regions, geometry_path=args.geometry,
            geometry_identifier=args.geometry_identifier,
        )
    except (ReferenceAnalysisError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
