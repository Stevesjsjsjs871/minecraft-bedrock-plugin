#!/usr/bin/env python3
"""Local CLI adapter for the existing Bedrock geometry UV audit/template engines.

The adapter calls the tested Python functions directly. It does not start an MCP
transport and does not yet extract their implementation into a pure library.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ENV = "MINECRAFT_BEDROCK_WORKSPACE"
MAX_TEMPLATE_BYTES = 64 * 1024 * 1024
MAX_TEMPLATE_DIMENSION = 8192
MAX_TEMPLATE_PIXELS = 8_388_608


def _load_backend(root: Path):
    server_dir = root / "server"
    required = (
        "geometry_uv_audit_mcp.py",
        "geometry_uv_template_mcp.py",
        "png_validation.py",
    )
    missing = [name for name in required if not (server_dir / name).is_file()]
    if missing:
        raise RuntimeError(
            "Geometry UV backend is incomplete; missing server source: "
            + ", ".join(missing)
        )
    server_path = str(server_dir.resolve())
    if server_path not in sys.path:
        sys.path.insert(0, server_path)
    try:
        auditor = importlib.import_module("geometry_uv_audit_mcp")
        template = importlib.import_module("geometry_uv_template_mcp")
        png_module = importlib.import_module("png_validation")
    except Exception as exc:
        raise RuntimeError(
            f"Could not load the preserved geometry backend: {type(exc).__name__}: {exc}"
        ) from exc
    validator = getattr(png_module, "validate_png_file", None)
    if not callable(validator):
        raise RuntimeError("server/png_validation.py has no validate_png_file function")
    return auditor, template, validator


def _resolve_workspace(raw: str) -> Path:
    try:
        workspace = Path(raw).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"workspace does not exist or cannot be resolved: {raw}") from exc
    if not workspace.is_dir():
        raise ValueError("workspace must be an existing directory")
    return workspace


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_generated_png(
    workspace: Path,
    project_name: str,
    relative_path: str,
    payload: dict[str, Any],
    validator,
) -> None:
    if (
        not isinstance(relative_path, str)
        or not relative_path
        or "\\" in relative_path
        or relative_path.startswith("/")
        or re.match(r"^[A-Za-z]:", relative_path)
    ):
        raise ValueError("generated output path is not a safe relative POSIX path")
    parts = relative_path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("generated output path contains an unsafe path segment")

    project_root = (workspace / project_name).resolve(strict=True)
    current = project_root
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("generated output path contains a symlink")
    output = current.resolve(strict=True)
    output.relative_to(project_root)
    if not output.is_file():
        raise ValueError("generated template is not a regular file")

    width, height = validator(
        output,
        max_bytes=MAX_TEMPLATE_BYTES,
        max_dimension=MAX_TEMPLATE_DIMENSION,
        max_pixels=MAX_TEMPLATE_PIXELS,
    )
    digest = _sha256_file(output)
    expected = payload.get("template", {}).get("sha256")
    if not isinstance(expected, str) or digest != expected:
        raise RuntimeError("generated PNG SHA-256 does not match the template report")
    payload["template"]["png_validation"] = {
        "valid": True,
        "width": width,
        "height": height,
        "file_bytes": output.stat().st_size,
    }
    payload["template"]["sha256_verified"] = True


def _execution_info(module: str) -> dict[str, str]:
    return {
        "mode": "local-cli-adapter",
        "transport": "direct-python-call",
        "backend_module": module,
        "mcp_transport_started": "false",
    }


def _execute(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    workspace = _resolve_workspace(args.workspace)
    auditor, template_engine, validate_png_file = _load_backend(ROOT)

    had_previous = WORKSPACE_ENV in os.environ
    previous = os.environ.get(WORKSPACE_ENV)
    os.environ[WORKSPACE_ENV] = str(workspace)
    try:
        if args.command == "audit":
            raw: dict[str, Any] = {"project_directory": args.project}
            if args.geometry_path:
                raw["geometry_path"] = args.geometry_path
            if args.texture_path:
                raw["texture_path"] = args.texture_path
            result = auditor.audit_geometry_uvs(raw)
            result["execution"] = _execution_info("server/geometry_uv_audit_mcp.py")
            status = result.get("status")
            exit_code = {"ok": 0, "issues_found": 1, "partial": 2}.get(status, 1)
            return exit_code, result

        raw = {
            "project_directory": args.project,
            "geometry_path": args.geometry_path,
            "output_path": args.output_path,
            "geometry_identifier": args.geometry_id,
            "pixel_scale": args.pixel_scale,
            "include_labels": not args.no_labels,
            "include_grid": not args.no_grid,
        }
        result = template_engine.generate_geometry_uv_template(raw)
        result["execution"] = _execution_info("server/geometry_uv_template_mcp.py")
        if result.get("status") != "success":
            return 1, result

        try:
            _verify_generated_png(
                workspace,
                args.project,
                args.output_path,
                result,
                validate_png_file,
            )
        except Exception as exc:
            result["status"] = "validation_failed"
            result["validation_error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            return 1, result

        findings = result.get("uv_analysis", {}).get("findings", [])
        errors = sum(1 for item in findings if item.get("severity") == "error")
        warnings = sum(1 for item in findings if item.get("severity") == "warning")
        overlaps = result.get("uv_analysis", {}).get("detected_overlap_pairs", 0)
        result["quality_status"] = (
            "FAIL" if errors else "WARN" if warnings or overlaps else "PASS"
        )
        result["runtime_status"] = "NOT RUN"
        return (1 if errors else 0), result
    finally:
        if had_previous:
            os.environ[WORKSPACE_ENV] = previous or ""
        else:
            os.environ.pop(WORKSPACE_ENV, None)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit Bedrock geometry UVs or generate a separate UV guide PNG."
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Existing workspace directory containing the project directory.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Read-only geometry UV and PNG audit.")
    audit.add_argument("--project", required=True)
    audit.add_argument("--geometry-path")
    audit.add_argument("--texture-path")

    template = sub.add_parser("template", help="Generate a new labeled UV guide PNG.")
    template.add_argument("--project", required=True)
    template.add_argument("--geometry-path", required=True)
    template.add_argument("--output-path", required=True)
    template.add_argument("--geometry-id")
    template.add_argument("--pixel-scale", type=int, default=4)
    template.add_argument("--no-labels", action="store_true")
    template.add_argument("--no-grid", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        exit_code, result = _execute(args)
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        result = {
            "status": "error",
            "error": {
                "code": "GEOMETRY_UV_CLI_ERROR",
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "runtime_status": "NOT RUN",
        }
        exit_code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
