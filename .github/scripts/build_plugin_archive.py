#!/usr/bin/env python3
"""Build a deterministic plugin tar.gz from the committed Git tree."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT_FILES = {
    ".codex-plugin/plugin.json", ".mcp.json", "CHANGELOG.md", "README.md",
    "VERSION", "archive_safety.py", "mcp.json", "plugin.json",
}
ROOT_DIRS = ("server/", "skills/")
CACHE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".venv", "venv"}
CACHE_SUFFIXES = {".pyc", ".pyo", ".pyd", ".tmp", ".swp"}
PROVENANCE = "BUILD_PROVENANCE.json"
MAX_FILES = 20_000
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024


class BuildError(Exception):
    pass


def git(root: Path, *args: str, binary: bool = False):
    try:
        p = subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as exc:
        err = getattr(exc, "stderr", b"")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        raise BuildError(f"git {' '.join(args)} failed: {err or exc}") from exc
    return p.stdout if binary else p.stdout.decode("utf-8").strip()


def package_path(path: str) -> bool:
    return path in ROOT_FILES or any(path.startswith(prefix) for prefix in ROOT_DIRS)


def read_tree(root: Path):
    commit = git(root, "rev-parse", "HEAD")
    epoch = int(git(root, "show", "-s", "--format=%ct", "HEAD"))
    records = git(root, "ls-tree", "-rz", "--full-tree", "HEAD", binary=True)
    files = {}
    for record in records.split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode_raw, kind_raw, oid_raw = meta.split(b" ", 2)
        path = raw_path.decode("utf-8")
        if path == PROVENANCE:
            raise BuildError(f"{PROVENANCE} is generated and must not be tracked")
        if not package_path(path):
            continue
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or "\\" in path or pure.as_posix() != path:
            raise BuildError(f"unsafe package path: {path!r}")
        if any(part in CACHE_DIRS for part in pure.parts) or pure.suffix.lower() in CACHE_SUFFIXES:
            raise BuildError(f"generated/cache file is tracked: {path}")
        mode, kind, oid = int(mode_raw, 8), kind_raw.decode(), oid_raw.decode()
        if kind != "blob" or mode not in (0o100644, 0o100755):
            raise BuildError(f"non-regular Git object in package: {path} (mode={mode:o}, type={kind})")
        data = git(root, "cat-file", "blob", oid, binary=True)
        if len(data) > MAX_FILE:
            raise BuildError(f"file exceeds size limit: {path}")
        files[path] = (data, mode)
    missing = sorted(ROOT_FILES - files.keys())
    missing += [p.rstrip("/") for p in ROOT_DIRS if not any(k.startswith(p) for k in files)]
    if missing:
        raise BuildError("required package entries missing: " + ", ".join(missing))
    if len(files) > MAX_FILES or sum(len(v[0]) for v in files.values()) > MAX_TOTAL:
        raise BuildError("package exceeds configured file-count or total-size limit")
    return commit, epoch, dict(sorted(files.items()))


def validate(files: dict[str, tuple[bytes, int]]) -> str:
    def read_json(path):
        try:
            return json.loads(files[path][0].decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BuildError(f"invalid JSON: {path}: {exc}") from exc

    version = files["VERSION"][0].decode("utf-8").strip()
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", version):
        raise BuildError(f"invalid SemVer in VERSION: {version!r}")
    root, compat = read_json("plugin.json"), read_json(".codex-plugin/plugin.json")
    if root.get("name") != "minecraft-bedrock-engineer" or compat.get("name") != root.get("name"):
        raise BuildError("plugin names do not match")
    if root.get("version") != version or compat.get("version") != version:
        raise BuildError("VERSION and manifests do not match")
    prompts = root.get("extensions", {}).get("com.openai", {}).get("interface", {}).get("defaultPrompt")
    if not isinstance(prompts, list) or len(prompts) < 3 or prompts != compat.get("interface", {}).get("defaultPrompt"):
        raise BuildError("the two manifests must have identical prompt lists with at least three entries")
    if any(not isinstance(x, str) or not x.strip() for x in prompts) or len(prompts) != len(set(prompts)):
        raise BuildError("default prompts must be unique, non-empty strings")

    configs = [read_json(p).get("mcpServers") for p in (".mcp.json", "mcp.json")]
    if not all(isinstance(x, dict) and x for x in configs) or set(configs[0]) != set(configs[1]):
        raise BuildError("MCP server registries are missing or have different names")
    for name in configs[0]:
        for field in ("type", "command", "args"):
            if configs[0][name].get(field) != configs[1][name].get(field):
                raise BuildError(f"MCP server {name!r} differs between configs ({field})")
        for config in configs:
            server = config[name]
            if server.get("type") != "stdio" or not isinstance(server.get("args"), list):
                raise BuildError(f"MCP server {name!r} must be stdio with args")
            for arg in server["args"]:
                if isinstance(arg, str) and "$" + "{PLUGIN_ROOT}/" in arg:
                    rel = arg.split("$" + "{PLUGIN_ROOT}/", 1)[1].replace("\\", "/")
                    pure = PurePosixPath(rel)
                    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != rel or rel not in files:
                        raise BuildError(f"MCP server {name!r} references unsafe or missing path {rel!r}")
    return version


def build(root: Path, output: Path):
    root = root.resolve(strict=True)
    commit, epoch, files = read_tree(root)
    version = validate(files)
    records = [{"path": p, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for p, (data, _) in files.items()]
    canonical = "".join(f"{x['path']}\0{x['size_bytes']}\0{x['sha256']}\n" for x in records).encode()
    provenance = (json.dumps({
        "schema_version": 1, "plugin": "minecraft-bedrock-engineer", "version": version,
        "git_commit": commit, "source_date_epoch": epoch, "archive_format": "tar.gz",
        "payload_file_count": len(records), "payload_total_bytes": sum(x["size_bytes"] for x in records),
        "payload_sha256": hashlib.sha256(canonical).hexdigest(),
        "provenance_file_excluded_from_payload_hash": True, "files": records,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()

    output = Path(os.path.abspath(output.expanduser()))
    sidecar = output.with_name(output.name + ".sha256")
    if output == sidecar:
        raise BuildError("archive and checksum paths collide")
    for target in (output, sidecar):
        try:
            relative = target.relative_to(root)
        except ValueError:
            continue
        if not relative.parts or relative.parts[0] not in {"dist", "artifacts"}:
            raise BuildError("output inside the repository must be under dist/ or artifacts/")
    for target in (output, sidecar):
        current = Path(target.anchor)
        for part in target.parts[1:]:
            current /= part
            if current.is_symlink():
                raise BuildError(f"output path contains symlink: {current}")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".plugin-archive-", suffix=".tmp", dir=output.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        with temp.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
                with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                    for path, (data, mode) in files.items():
                        info = tarfile.TarInfo(path)
                        info.size, info.mode, info.mtime = len(data), (0o755 if mode == 0o100755 else 0o644), epoch
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        tar.addfile(info, io.BytesIO(data))
                    info = tarfile.TarInfo(PROVENANCE)
                    info.size, info.mode, info.mtime = len(provenance), 0o644, epoch
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    tar.addfile(info, io.BytesIO(provenance))
        digest = hashlib.sha256()
        with temp.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        archive_hash = digest.hexdigest()
        os.replace(temp, output)
        fd, side_temp_name = tempfile.mkstemp(prefix=".plugin-checksum-", suffix=".tmp", dir=output.parent)
        with os.fdopen(fd, "w", encoding="ascii", newline="\n") as stream:
            stream.write(f"{archive_hash}  {output.name}\n")
        os.replace(side_temp_name, sidecar)
    finally:
        temp.unlink(missing_ok=True)
    return {"archive": str(output), "sha256": archive_hash, "version": version, "git_commit": commit, "payload_files": len(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.repo_root, args.output), sort_keys=True))
        return 0
    except (BuildError, OSError, tarfile.TarError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
