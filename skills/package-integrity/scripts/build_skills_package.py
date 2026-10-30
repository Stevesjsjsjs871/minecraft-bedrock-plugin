#!/usr/bin/env python3
"""Build a deterministic Skills-only tar.gz candidate with per-file provenance and a SHA-256 sidecar."""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from package_provenance import PackageSafetyError, build_archive

EXCLUDE = {".git", ".github", "dist", "docs/engineering", "GITHUB_SYNC_NOTES.md", "DEVELOPMENT_LOG.md"}


def git_value(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PackageSafetyError(f"cannot read Git build metadata: {type(exc).__name__}: {exc}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", nargs="?", default=".")
    parser.add_argument("output", help="new archive path outside package_root")
    parser.add_argument("--source-commit")
    parser.add_argument("--source-ref", default=os.environ.get("GITHUB_REF"))
    parser.add_argument("--source-date-epoch", type=int)
    args = parser.parse_args(argv)
    root = Path(args.package_root).absolute()
    commit = args.source_commit or os.environ.get("GITHUB_SHA") or git_value(root, "rev-parse", "HEAD")
    epoch = args.source_date_epoch
    if epoch is None:
        epoch = int(git_value(root, "show", "-s", "--format=%ct", commit))
    result = build_archive(root, Path(args.output), commit, epoch, args.source_ref, EXCLUDE)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PackageSafetyError as exc:
        raise SystemExit(f"ERROR: {exc}")
