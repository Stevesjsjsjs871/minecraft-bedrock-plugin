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
        "RP/animation_controllers/test.animation_controllers.json": json.dumps({"format_version": "1.10.0", "animation_controllers": {"controller.animation.regression_test": {"initial_state": "default", "states": {"default": {"transitions": [{"attack": "query.is_delayed_attacking"}]}, "attack": {"transitions": [{"default": "query.all_animations_finished"}]}}}}}),
        "RP/render_controllers/test.render_controllers.json": json.dumps({"format_version": "1.8.0", "render_controllers": {"controller.render.regression_test": {"geometry": "geometry.regression_test", "materials": [{"*": "material.default"}], "textures": ["default"]}}}),
        "RP/entity/test.entity.json": json.dumps({"format_version": "1.10.0", "minecraft:client_entity": {"description": {"identifier": "test:regression_entity", "geometry": {"default": "geometry.regression_test"}, "animations": {"idle": "animation.regression_test"}, "render_controllers": ["controller.render.regression_test"], "textures": {"default": "textures/entity/test"}}}}),
        "RP/textures/entity/test.png": b"synthetic-not-a-real-png",
        "RP/ui/_ui_defs.json": json.dumps({"ui_defs": ["ui/test_screen.json"]}),
        "RP/ui/test_screen.json": json.dumps({"namespace": "regression", "test_screen": {"type": "label", "text": "$gui.regression_title"}}),
        "RP/texts/en_US.lang": "gui.regression_title=Regression title\n"
    }
    if case == "missing_ui_definition":
        data = json.loads(files["RP/ui/_ui_defs.json"])
        data["ui_defs"] = ["ui/does_not_exist.json"]
        files["RP/ui/_ui_defs.json"] = json.dumps(data)
    elif case == "duplicate_localization_key":
        files["RP/texts/en_US.lang"] += "gui.regression_title=Duplicate regression title\n"
    elif case == "duplicate_ui_definition":
        data = json.loads(files["RP/ui/_ui_defs.json"])
        data["ui_defs"] = ["ui/test_screen.json", "ui/test_screen.json"]
        files["RP/ui/_ui_defs.json"] = json.dumps(data)
    elif case == "missing_ui_control_reference":
        data = json.loads(files["RP/ui/test_screen.json"])
        data["test_screen"]["extends"] = "missing_namespace.missing_control"
        files["RP/ui/test_screen.json"] = json.dumps(data)
    elif case == "missing_ui_localization_graph_edge":
        data = json.loads(files["RP/ui/test_screen.json"])
        data["test_screen"]["text"] = "$gui.missing_title"
        files["RP/ui/test_screen.json"] = json.dumps(data)
    elif case == "component_loot_table_resolves":
        files["BP/blocks/test.block.json"] = json.dumps({"format_version": "1.21.0", "minecraft:block": {"description": {"identifier": "test:component_block"}, "components": {"minecraft:loot": {"table": "loot_tables/blocks/test_loot.json"}}}})
        files["BP/loot_tables/blocks/test_loot.json"] = json.dumps({"pools": [{"rolls": 1, "entries": [{"type": "item", "name": "minecraft:stone"}]}]})
    elif case == "component_loot_table_missing":
        files["BP/blocks/test.block.json"] = json.dumps({"format_version": "1.21.0", "minecraft:block": {"description": {"identifier": "test:component_block"}, "components": {"minecraft:loot": {"table": "loot_tables/blocks/not_here.json"}}}})
    elif case == "loot_table_cycle":
        files["BP/loot_tables/blocks/a.json"] = json.dumps({"pools": [{"rolls": 1, "entries": [{"type": "loot_table", "name": "loot_tables/blocks/b.json"}]}]})
        files["BP/loot_tables/blocks/b.json"] = json.dumps({"pools": [{"rolls": 1, "entries": [{"type": "loot_table", "name": "loot_tables/blocks/a.json"}]}]})
    elif case == "malformed_loot_table_pool":
        files["BP/loot_tables/blocks/malformed.json"] = json.dumps({"pools": [
            {"rolls": 1, "entries": "not-an-array"},
            {"rolls": 0, "entries": [{"type": "item", "name": "minecraft:stone"}]}
        ]})
    elif case == "missing_localization_key":
        data = json.loads(files["RP/ui/test_screen.json"])
        data["test_screen"]["text"] = "$gui.missing_title"
        files["RP/ui/test_screen.json"] = json.dumps(data)
    elif case == "missing_geometry":
        data = json.loads(files["RP/entity/test.entity.json"])
        data["minecraft:client_entity"]["description"]["geometry"]["default"] = "geometry.definitely_missing"
        files["RP/entity/test.entity.json"] = json.dumps(data)
    elif case == "invalid_json":
        files["RP/entity/broken.entity.json"] = '{not valid json'
    elif case == "dynamic_reference":
        data = json.loads(files["RP/entity/test.entity.json"])
        data["minecraft:client_entity"]["description"]["geometry"]["default"] = "query.test ? geometry.regression_test : geometry.other"
        files["RP/entity/test.entity.json"] = json.dumps(data)
    elif case == "missing_animation_bone":
        data = json.loads(files["RP/animations/test.animation.json"])
        animation = next(iter(data["animations"].values()))
        animation["bones"] = {"ghost_bone": {"rotation": {"0.0": [0, 0, 0]}}}
        files["RP/animations/test.animation.json"] = json.dumps(data)
    elif case == "missing_controller_state":
        data = json.loads(files["RP/animation_controllers/test.animation_controllers.json"])
        controller = next(iter(data["animation_controllers"].values()))
        controller["states"]["default"]["transitions"] = [{"missing_state": "query.is_delayed_attacking"}]
        files["RP/animation_controllers/test.animation_controllers.json"] = json.dumps(data)
    elif case == "missing_controller_initial_state":
        data = json.loads(files["RP/animation_controllers/test.animation_controllers.json"])
        controller = next(iter(data["animation_controllers"].values()))
        controller["initial_state"] = "missing_initial"
        files["RP/animation_controllers/test.animation_controllers.json"] = json.dumps(data)
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
        version_path = auditor.resolve().parents[3] / "VERSION"
        expected_version = version_path.read_text(encoding="utf-8").strip()
        if report.get("tool_version") != expected_version:
            return False, f"Analyzer version mismatch: expected {expected_version}, got {report.get('tool_version')!r}"
        schema_path = auditor.resolve().parents[1] / "references" / "report-schema.json"
        try:
            import jsonschema
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            errors = list(jsonschema.Draft202012Validator(schema).iter_errors(report))
        except ImportError:
            return False, "report schema validation requires dependency jsonschema; install it with python -m pip install jsonschema"
        except Exception as exc:
            return False, f"Could not validate report schema: {type(exc).__name__}: {exc}"
        if errors:
            first = errors[0]
            return False, f"Report-schema violation at {list(first.absolute_path)}: {first.message} (total={len(errors)})"
        if report.get("runtime_status") != "NOT RUN":
            return False, f"Static CLI incorrectly reported runtime_status={report.get('runtime_status')!r}"
        if not isinstance(graph, dict) or not isinstance(graph.get("scope", {}).get("coverage"), dict):
            return False, "Reference graph coverage metadata missing"
        if graph.get("edge_count") != len(edges):
            return False, f"Graph edge_count={graph.get('edge_count')!r} does not match actual edges={len(edges)}"
        status_counts = graph.get("status_counts", {})
        actual_counts = {}
        for edge in edges:
            status = str(edge.get("status", "unknown"))
            actual_counts[status] = actual_counts.get(status, 0) + 1
        if status_counts != actual_counts:
            return False, f"Graph status_counts mismatch: expected computed {actual_counts}, report has {status_counts}"
        if case == "valid":
            want = {"geometry.regression_test", "animation.regression_test"}
            resolved = {str(e.get("referenced_value")) for e in edges if e.get("status") == "resolved"}
            if not want.issubset(resolved): return False, f"Expected resolved geometry/animation edges; found {sorted(resolved)}"
            if not any(e.get("reference_kind") == "ui_definition_import" and e.get("referenced_value") == "ui/test_screen.json" and e.get("status") == "resolved" for e in edges):
                return False, "Expected resolved ui_defs import edge in the valid fixture"
            if not any(e.get("reference_kind") == "ui_localization_key" and e.get("referenced_value") == "gui.regression_title" and e.get("status") == "resolved" for e in edges):
                return False, "Expected resolved literal UI localization edge in the valid fixture"
            golden_path = auditor.resolve().parents[1] / "../regression-evals/references/golden-graph.json"
            try:
                golden = json.loads(golden_path.resolve().read_text(encoding="utf-8"))
            except Exception as exc:
                return False, f"Could not read golden graph fixture: {type(exc).__name__}: {exc}"
            projection_keys = ("source_file", "source_pointer", "reference_kind", "referenced_value", "target_domain", "status")
            actual_projection = sorted([{key: edge.get(key) for key in projection_keys} for edge in edges], key=lambda item: (item["source_file"], item["source_pointer"], item["reference_kind"]))
            expected_projection = sorted([{key: edge.get(key) for key in projection_keys} for edge in golden.get("edges", [])], key=lambda item: (item["source_file"], item["source_pointer"], item["reference_kind"]))
            if len(edges) != golden.get("expected_edge_count"):
                return False, f"Golden graph edge count differs: expected {golden.get('expected_edge_count')}, got {len(edges)}"
            if actual_counts != golden.get("expected_status_counts"):
                return False, f"Golden graph status counts differ: expected {golden.get('expected_status_counts')}, got {actual_counts}"
            if actual_projection != expected_projection:
                return False, f"Golden graph edge projection differs; expected {expected_projection}, got {actual_projection}"
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
        elif case == "missing_animation_bone":
            if not any(f.get("title") == "Possible unresolved animation bone target" and "ghost_bone" in f.get("evidence", "") and f.get("severity") == "INFO" for f in findings):
                return False, "Missing animation bone was not reported as an INFO/LOW heuristic"
        elif case == "missing_controller_state":
            if not any(f.get("title") == "Unresolved animation controller transition state" and "missing_state" in f.get("evidence", "") for f in findings):
                return False, "Missing literal animation-controller transition target was not reported"
        elif case == "missing_controller_initial_state":
            if not any(f.get("title") == "Unresolved animation controller initial state" and "missing_initial" in f.get("evidence", "") for f in findings):
                return False, "Missing literal animation-controller initial state was not reported"
        elif case == "missing_ui_definition":
            if not any(f.get("title") == "Possible unresolved UI definition path" and "does_not_exist" in f.get("evidence", "") and f.get("severity") == "INFO" for f in findings):
                return False, "Missing ui_defs path was not reported as an INFO/LOW heuristic"
        elif case == "duplicate_localization_key":
            if not any(f.get("title") == "Duplicate localization key in file" and "gui.regression_title" in f.get("evidence", "") and f.get("severity") == "MEDIUM" for f in findings):
                return False, "Duplicate .lang key in one file was not reported"
        elif case == "missing_localization_key":
            if not any(f.get("title") == "Possible unresolved UI localization key" and "gui.missing_title" in f.get("evidence", "") and f.get("severity") == "INFO" for f in findings):
                return False, "Missing literal UI localization lookup was not reported as an INFO/LOW heuristic"
        elif case == "duplicate_ui_definition":
            if not any(f.get("title") == "Duplicate UI definition entry" and "ui/test_screen.json" in f.get("evidence", "") and f.get("severity") == "INFO" for f in findings):
                return False, "Repeated ui_defs entry was not reported as an INFO heuristic"
        elif case == "missing_ui_control_reference":
            if not any(f.get("title") == "Possible unresolved UI control reference" and "missing_namespace.missing_control" in f.get("evidence", "") and f.get("severity") == "INFO" for f in findings):
                return False, "Missing literal UI control reference was not reported as an INFO/LOW heuristic"
        elif case == "missing_ui_localization_graph_edge":
            if not any(e.get("reference_kind") == "ui_localization_key" and e.get("referenced_value") == "gui.missing_title" and e.get("status") == "heuristic_unresolved" and e.get("confidence") == "LOW" for e in edges):
                return False, "Missing UI localization lookup was not represented as a low-confidence graph edge"
        elif case == "component_loot_table_resolves":
            if not any(e.get("reference_kind") == "component_loot_table_path" and e.get("referenced_value") == "loot_tables/blocks/test_loot.json" and e.get("status") == "resolved" and e.get("source_pointer", "").endswith("/minecraft:loot/table") for e in edges):
                return False, "Documented minecraft:loot.table path did not resolve to the indexed in-archive loot table"
        elif case == "component_loot_table_missing":
            if not any(e.get("reference_kind") == "component_loot_table_path" and e.get("referenced_value") == "loot_tables/blocks/not_here.json" and e.get("status") == "heuristic_unresolved" and e.get("confidence") == "LOW" for e in edges):
                return False, "Missing literal block loot table path was not reported as a low-confidence heuristic"
        elif case == "loot_table_cycle":
            if not any(f.get("title") == "Recursive loot-table reference cycle" and f.get("severity") == "MEDIUM" for f in findings):
                return False, "Resolved in-archive recursive loot-table cycle was not reported"
            link_edges = [e for e in edges if e.get("reference_kind") == "loot_table_entry_reference" and e.get("status") == "resolved"]
            if len(link_edges) < 2:
                return False, f"Expected two resolved nested loot-table graph edges, got {len(link_edges)}"
        elif case == "malformed_loot_table_pool":
            if not any(f.get("title") == "Loot table pool entries has an invalid type" and f.get("path") == "BP/loot_tables/blocks/malformed.json" for f in findings):
                return False, "Malformed loot pool entries shape was not reported"
            if not any(f.get("title") == "Loot table pool rolls has an invalid shape" and f.get("path") == "BP/loot_tables/blocks/malformed.json" for f in findings):
                return False, "Invalid loot pool roll count was not reported"
            if report.get("recommendation") != "REVIEW":
                return False, f"MEDIUM-severity loot-table findings should recommend REVIEW, got {report.get('recommendation')!r}"
        elif case == "valid":
            if any(f.get("title") in ("Unresolved animation controller initial state", "Unresolved animation controller transition state", "Possible unresolved animation bone target") for f in findings):
                return False, "Valid animation/controller fixture produced a cross-resource animation finding"
        return True, f"{case}: report/schema contract OK; findings={len(findings)}; graph_edges={len(edges)}; exit={proc.returncode}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--auditor", type=Path, default=Path(__file__).resolve().parents[2] / "automated-validation" / "scripts" / "bedrock_audit.py")
    args = ap.parse_args()
    if not args.auditor.is_file():
        print(f"SKIP: analyzer not found: {args.auditor}", file=sys.stderr)
        return 2
    cases = ["valid", "missing_geometry", "invalid_json", "unsafe_path", "dynamic_reference", "missing_animation_bone", "missing_controller_state", "missing_controller_initial_state", "missing_ui_definition", "duplicate_localization_key", "missing_localization_key", "duplicate_ui_definition", "missing_ui_control_reference", "missing_ui_localization_graph_edge", "component_loot_table_resolves", "component_loot_table_missing", "loot_table_cycle", "malformed_loot_table_pool"]
    failures = 0
    for case in cases:
        ok, detail = run_case(args.auditor.resolve(), case)
        print(("PASS" if ok else "FAIL") + " " + detail)
        failures += not ok
    print(f"SUMMARY: {len(cases)-failures}/{len(cases)} passed; runtime tests NOT RUN")
    return 1 if failures else 0

if __name__ == "__main__": raise SystemExit(main())
