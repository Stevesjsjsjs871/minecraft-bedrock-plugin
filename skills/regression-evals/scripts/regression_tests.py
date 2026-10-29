#!/usr/bin/env python3
"""Synthetic regression tests for Minecraft Bedrock Engineer's static audit CLI."""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile, uuid, zipfile
from pathlib import Path


def uid(): return str(uuid.uuid4())

def manifest(pack_type, module_type, module_uuid, dependencies=None):
    header_uuid = uid()
    out = {
        "format_version": 2,
        "header": {"name": f"Regression {pack_type}", "description": "Synthetic regression fixture", "uuid": header_uuid, "version": [1, 0, 0], "min_engine_version": [1, 26, 50]},
        "modules": [{"type": module_type, "uuid": module_uuid, "version": [1, 0, 0]}]
    }
    if dependencies: out["dependencies"] = dependencies
    return out, header_uuid


def make_archive(path: Path, case: str):
    bp_manifest, bp_header = manifest("BP", "data", uid())
    rp_manifest, rp_header = manifest("RP", "resources", uid(), [{"uuid": bp_header, "version": [1, 0, 0]}])
    files = {
        "BP/manifest.json": json.dumps(bp_manifest),
        "RP/manifest.json": json.dumps(rp_manifest),
        "RP/models/entity/test.geo.json": json.dumps({
            "format_version": "1.12.0",
            "minecraft:geometry": [{"description": {"identifier": "geometry.regression_test", "texture_width": 16, "texture_height": 16, "visible_bounds_width": 2, "visible_bounds_height": 2, "visible_bounds_offset": [0, 1, 0]}, "bones": [{"name": "root", "pivot": [0, 0, 0], "cubes": [{"origin": [0, 0, 0], "size": [1, 1, 1], "uv": [0, 0]}]}]}]
        }),
        "RP/animations/test.animation.json": json.dumps({"format_version": "1.8.0", "animations": {"animation.regression_test": {"animation_length": 1.0, "bones": {"root": {"rotation": {"0.0": [0, 0, 0], "1.0": [0, 90, 0]}}}}}}),
        "RP/render_controllers/test.render_controllers.json": json.dumps({"format_version": "1.8.0", "render_controllers": {"controller.render.regression_test": {"geometry": "geometry.regression_test", "materials": [{"*": "material.default"}], "textures": ["default"]}}}),
        "RP/entity/test.entity.json": json.dumps({"format_version": "1.10.0", "minecraft:client_entity": {"description": {"identifier": "test:regression_entity", "geometry": {"default": "geometry.regression_test"}, "animations": {"idle": "animation.regression_test"}, "render_controllers": ["controller.render.regression_test"], "textures": {"default": "textures/entity/test"}}}}),
        "RP/textures/entity/test.png": b"synthetic-not-a-real-png"
    }
    if case == "missing_geometry":
        data = json.loads(files["RP/entity/test.entity.json"])
        data["minecraft:client_entity"]["description"]["geometry"]["default"] = "geometry.definitely_missing"
        files["RP/entity/test.entity.json"] = json.dumps(data)
    elif case == "invalid_json":
        files["RP/entity/broken.entity.json"] = '{not valid json'
    elif case == "dynamic_reference":
        data = json.loads(files["RP/entity/test.entity.json"])
        data["minecraft:client_entity"]["description"]["geometry"]["default"] = "query.test ? geometry.regression_test : geometry.other"
        files["RP/entity/test.entity.json"] = json.dumps(data)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, value in files.items(): zf.writestr(name, value)
        if case == "unsafe_path": zf.writestr("../escape.json", "{}")


def run_case(auditor: Path, case: str):
    with tempfile.TemporaryDirectory(prefix="mbe-eval-") as td:
        archive = Path(td) / f"{case}.mcaddon"
        make_archive(archive, case)
        proc = subprocess.run([sys.executable, str(auditor), str(archive)], capture_output=True, text=True, timeout=60)
        try: report = json.loads(proc.stdout)
        except Exception as exc:
            return False, f"CLI did not emit parseable JSON (exit={proc.returncode}): {exc}; stderr={proc.stderr[-500:]}"
        findings = report.get("findings", [])
        graph = report.get("reference_graph", {})
        edges = graph.get("edges", []) if isinstance(graph, dict) else []
        titles = [str(f.get("title", "" )).lower() for f in findings]
        if not all(k in report for k in ("tool_version", "candidate", "checks", "findings", "file_diff", "runtime_status", "recommendation")):
            return False, "Required top-level report keys missing"
        if report.get("runtime_status") != "NOT RUN":
            return False, f"Static CLI incorrectly reported runtime_status={report.get('runtime_status')!r}"
        if not isinstance(graph, dict) or not isinstance(graph.get("scope", {}).get("coverage"), dict):
            return False, "Reference graph coverage metadata missing"
        if case == "valid":
            want = {"geometry.regression_test", "animation.regression_test"}
            resolved = {str(e.get("referenced_value")) for e in edges if e.get("status") == "resolved"}
            if not want.issubset(resolved): return False, f"Expected resolved geometry/animation edges; found {sorted(resolved)}"
        elif case == "missing_geometry":
            if not any(e.get("referenced_value") == "geometry.definitely_missing" and e.get("status") == "unresolved" for e in edges):
                return False, "Missing literal geometry was not retained as unresolved edge"
        elif case == "invalid_json":
            if not any("invalid json" in t for t in titles): return False, "Malformed JSON did not produce an Invalid JSON finding"
        elif case == "unsafe_path":
            if not any("unsafe archive member path" in t for t in titles): return False, "Unsafe archive member path not reported"
        elif case == "dynamic_reference":
            if not any(e.get("status") == "dynamic_or_expression" and "query.test" in str(e.get("referenced_value")) for e in edges):
                return False, "Expression-like reference was not classified as dynamic"
        return True, f"{case}: report contract OK; findings={len(findings)}; graph_edges={len(edges)}; exit={proc.returncode}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--auditor", type=Path, default=Path(__file__).resolve().parents[2] / "automated-validation" / "scripts" / "bedrock_audit.py")
    args = ap.parse_args()
    if not args.auditor.is_file():
        print(f"SKIP: analyzer not found: {args.auditor}", file=sys.stderr)
        return 2
    cases = ["valid", "missing_geometry", "invalid_json", "unsafe_path", "dynamic_reference"]
    failures = 0
    for case in cases:
        ok, detail = run_case(args.auditor.resolve(), case)
        print(("PASS" if ok else "FAIL") + " " + detail)
        failures += not ok
    print(f"SUMMARY: {len(cases)-failures}/{len(cases)} passed; runtime tests NOT RUN")
    return 1 if failures else 0

if __name__ == "__main__": raise SystemExit(main())
