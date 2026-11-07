#!/usr/bin/env python3
"""Versioned, evidence-aware project state for Minecraft Bedrock workspaces.

The utility stores metadata under <project>/.mbe/ and never edits add-on files.
Snapshots are read-only inventories (relative path, size and SHA-256), not file
backups. Restoring a state revision restores metadata only; it never rolls back
project files. All mutations require a revision precondition and use a lock plus
atomic replacement.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import stat
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "1.0.0"
STATE_DIR_NAME = ".mbe"
STATE_FILE_NAME = "project-state.json"
SNAPSHOT_DIR_NAME = "snapshots"
BACKUP_DIR_NAME = "backups"
LOCK_FILE_NAME = ".state.lock"
ZERO_HASH = "0" * 64
DEFAULT_IGNORES = {
    ".git", ".mbe", "node_modules", ".venv", "venv", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
}
STATUSES: dict[str, set[str]] = {
    "decision": {"PROPOSED", "APPROVED", "REJECTED", "SUPERSEDED"},
    "requirement": {"CONFIRMED", "APPROVED", "UNVERIFIED", "SUPERSEDED"},
    "feature": {"CONFIRMED_IN_SOURCE", "TESTED", "PLANNED", "UNVERIFIED", "REMOVED"},
    "issue": {"OPEN", "BLOCKED", "RESOLVED", "WONT_FIX"},
    "task": {"PLANNED", "IN_PROGRESS", "DONE", "PARTIAL", "BLOCKED", "NOT APPLIED"},
    "test": {"PASS", "FAIL", "NOT RUN", "BLOCKED"},
    "note": {"RECORDED"},
}


class StateError(ValueError):
    """Raised for unsafe paths, invalid state or rejected transitions."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path, *, expected_stat: os.stat_result | None = None) -> str:
    """Hash one regular file through a pinned descriptor; reject link/race changes.

    O_NOFOLLOW is used where the platform provides it. Descriptor identity and
    pre/post path metadata checks remain mandatory on every platform.
    """
    try:
        before = path.lstat()
    except OSError as exc:
        raise StateError(f"cannot stat file before hashing: {path}: {exc}") from exc
    if not stat.S_ISREG(before.st_mode):
        raise StateError(f"refusing to hash a non-regular file: {path}")
    if expected_stat is not None and (before.st_dev, before.st_ino) != (expected_stat.st_dev, expected_stat.st_ino):
        raise StateError(f"file identity changed before hashing: {path}")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise StateError(f"cannot safely open file for hashing: {path}: {exc}") from exc
    digest = hashlib.sha256()
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise StateError(f"opened object is not a regular file: {path}")
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise StateError(f"file identity changed while opening: {path}")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        after_fd = os.fstat(fd)
        after_path = path.lstat()
        identity_before = (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        identity_after = (after_fd.st_dev, after_fd.st_ino, after_fd.st_size, after_fd.st_mtime_ns, after_fd.st_ctime_ns)
        path_identity = (after_path.st_dev, after_path.st_ino)
        if identity_before != identity_after or path_identity != (opened.st_dev, opened.st_ino):
            raise StateError(f"file changed during hashing: {path}")
    except OSError as exc:
        raise StateError(f"cannot safely hash file: {path}: {exc}") from exc
    finally:
        os.close(fd)
    return digest.hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StateError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise StateError(f"non-finite JSON number is not allowed: {value}")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object, parse_constant=_reject_constant)
    except StateError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read JSON {path}: {exc}") from exc


def _atomic_write(path: Path, payload: bytes, *, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise StateError(f"refusing to overwrite existing file: {path}")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not overwrite:
            raise StateError(f"refusing to overwrite existing file: {path}")
        os.replace(temp_name, path)
        try:
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            # Directory fsync is not available on every supported platform.
            pass
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _state_paths(project_root: Path) -> tuple[Path, Path, Path, Path, Path]:
    state_dir = project_root / STATE_DIR_NAME
    if state_dir.is_symlink():
        raise StateError(f"state directory must not be a symlink: {state_dir}")
    for child in (STATE_FILE_NAME, SNAPSHOT_DIR_NAME, BACKUP_DIR_NAME, LOCK_FILE_NAME):
        candidate = state_dir / child
        if candidate.is_symlink():
            raise StateError(f"state component must not be a symlink: {candidate}")
    return (
        state_dir,
        state_dir / STATE_FILE_NAME,
        state_dir / SNAPSHOT_DIR_NAME,
        state_dir / BACKUP_DIR_NAME,
        state_dir / LOCK_FILE_NAME,
    )


class StateLock:
    """Cross-platform exclusive-create lock; stale locks fail closed."""
    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None

    def __enter__(self) -> "StateLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(self.fd, f"pid={os.getpid()}\ncreated={utc_now()}\n".encode("utf-8"))
            os.fsync(self.fd)
            return self
        except FileExistsError as exc:
            info = ""
            try:
                info = self.path.read_text(encoding="utf-8", errors="replace").strip()
                age = max(0, int(time.time() - self.path.stat().st_mtime))
                info = f" ({info}; age={age}s)"
            except OSError:
                pass
            raise StateError(f"project state is locked by another operation{info}; verify no process is active before removing {self.path}") from exc

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.fd is not None:
            os.close(self.fd)
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def _event_hash(event: dict[str, Any]) -> str:
    body = {key: value for key, value in event.items() if key != "event_hash"}
    return sha256_bytes(canonical_bytes(body))


def _state_hash(state: dict[str, Any]) -> str:
    body = dict(state)
    body.pop("integrity", None)
    return sha256_bytes(canonical_bytes(body))


def _seal_state(state: dict[str, Any]) -> dict[str, Any]:
    state["integrity"] = {"algorithm": "sha256", "state_sha256": _state_hash(state)}
    return state


def _verify_history(state: dict[str, Any]) -> None:
    history = state.get("history")
    revision = state.get("revision")
    if not isinstance(history, list) or not isinstance(revision, int) or revision < 1 or len(history) != revision:
        raise StateError("state history/revision mismatch; use verify and recover from a valid backup")
    previous = ZERO_HASH
    for expected_revision, event in enumerate(history, start=1):
        if not isinstance(event, dict) or event.get("revision") != expected_revision:
            raise StateError(f"invalid event sequence at revision {expected_revision}")
        if event.get("previous_event_hash") != previous:
            raise StateError(f"event hash chain is broken at revision {expected_revision}")
        actual = _event_hash(event)
        if event.get("event_hash") != actual:
            raise StateError(f"event hash mismatch at revision {expected_revision}")
        previous = actual
    if state.get("last_event_hash") != previous:
        raise StateError("state head does not match the final history event")


def _verify_state_document(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise StateError("project state root must be an object")
    required = {"schema_version", "project", "revision", "created_at", "updated_at", "latest_snapshot", "last_complete_snapshot", "records", "history", "last_event_hash", "integrity"}
    if set(state) != required:
        raise StateError(f"project state fields differ from contract; missing={sorted(required - set(state))}, unknown={sorted(set(state) - required)}")
    if state.get("schema_version") != SCHEMA_VERSION:
        raise StateError(f"unsupported project state schema version: {state.get('schema_version')!r}")
    project = state.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("id"), str) or not isinstance(project.get("name"), str):
        raise StateError("project identity is invalid")
    records = state.get("records")
    if not isinstance(records, dict) or set(records) != set(STATUSES):
        raise StateError("project records collection is invalid")
    for category, items in records.items():
        if not isinstance(items, list):
            raise StateError(f"records.{category} must be an array")
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in seen:
                raise StateError(f"records.{category} contains an invalid or duplicate record")
            seen.add(item["id"])
            if item.get("category") != category or item.get("status") not in STATUSES[category]:
                raise StateError(f"record {item['id']} has an invalid category/status")
    _verify_history(state)
    integrity = state.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256" or integrity.get("state_sha256") != _state_hash(state):
        raise StateError("project state checksum mismatch")
    return state


def _read_snapshot(snapshot_dir: Path, reference: dict[str, Any] | None) -> dict[str, Any] | None:
    if reference is None:
        return None
    if not isinstance(reference, dict) or not isinstance(reference.get("id"), str):
        raise StateError("snapshot reference is invalid")
    name = reference["id"]
    if not name.startswith("snapshot-") or "/" in name or "\\" in name or ".." in name:
        raise StateError("snapshot reference contains an unsafe identifier")
    path = snapshot_dir / f"{name}.json"
    snapshot = read_json(path)
    digest = sha256_bytes(canonical_bytes(snapshot))
    if digest != reference.get("sha256"):
        raise StateError(f"snapshot checksum mismatch: {name}")
    if not isinstance(snapshot, dict) or snapshot.get("snapshot_id") != name or not isinstance(snapshot.get("inventory"), dict):
        raise StateError(f"snapshot structure is invalid: {name}")
    return snapshot


def load_state(project_root: Path, *, verify_snapshots: bool = True) -> dict[str, Any]:
    _, state_path, snapshot_dir, _, _ = _state_paths(project_root)
    state = _verify_state_document(read_json(state_path))
    if verify_snapshots:
        _read_snapshot(snapshot_dir, state.get("latest_snapshot"))
        _read_snapshot(snapshot_dir, state.get("last_complete_snapshot"))
    return state


def _scan_project(project_root: Path, *, max_file_bytes: int, max_files: int, excludes: list[str]) -> dict[str, Any]:
    inventory: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, str]] = []
    ignored_dirs = set(DEFAULT_IGNORES)
    for pattern in excludes:
        if pattern.strip():
            ignored_dirs.add(pattern.strip())
    for current, dirnames, filenames in os.walk(project_root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept: list[str] = []
        for dirname in sorted(dirnames):
            absolute = current_path / dirname
            relative = absolute.relative_to(project_root).as_posix()
            if dirname in ignored_dirs or any(fnmatch.fnmatch(relative, pattern) for pattern in excludes):
                continue
            try:
                if absolute.is_symlink():
                    issues.append({"code": "SYMLINK_SKIPPED", "path": relative})
                    continue
            except OSError:
                issues.append({"code": "STAT_FAILED", "path": relative})
                continue
            kept.append(dirname)
        dirnames[:] = kept
        for filename in sorted(filenames):
            path = current_path / filename
            relative = path.relative_to(project_root).as_posix()
            if any(fnmatch.fnmatch(relative, pattern) for pattern in excludes):
                continue
            try:
                st = path.lstat()
                if stat.S_ISLNK(st.st_mode):
                    issues.append({"code": "SYMLINK_SKIPPED", "path": relative})
                    continue
                if not stat.S_ISREG(st.st_mode):
                    issues.append({"code": "NON_REGULAR_FILE_SKIPPED", "path": relative})
                    continue
                if st.st_size > max_file_bytes:
                    issues.append({"code": "FILE_TOO_LARGE", "path": relative})
                    continue
                if len(inventory) >= max_files:
                    issues.append({"code": "FILE_LIMIT_REACHED", "path": relative})
                    break
                digest = sha256_file(path, expected_stat=st)
                after = path.lstat()
                if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    issues.append({"code": "FILE_CHANGED_DURING_SCAN", "path": relative})
                    continue
                inventory[relative] = {"size_bytes": st.st_size, "sha256": digest}
            except OSError:
                issues.append({"code": "READ_FAILED", "path": relative})
        if any(item["code"] == "FILE_LIMIT_REACHED" for item in issues):
            break
    inventory = dict(sorted(inventory.items()))
    return {
        "inventory": inventory,
        "issues": sorted(issues, key=lambda item: (item["path"], item["code"])),
        "complete": not issues,
        "file_count": len(inventory),
        "total_bytes": sum(item["size_bytes"] for item in inventory.values()),
    }


def _diff_inventory(previous: dict[str, Any], current: dict[str, Any], *, complete: bool) -> dict[str, list[str]]:
    old = previous.get("inventory", {})
    new = current.get("inventory", {})
    old_paths, new_paths = set(old), set(new)
    modified = sorted(path for path in old_paths & new_paths if old[path].get("sha256") != new[path].get("sha256"))
    result = {
        "added": sorted(new_paths - old_paths),
        "modified": modified,
        "deleted": sorted(old_paths - new_paths) if complete else [],
    }
    return result


def _make_snapshot(project_id: str, scan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot_id = f"snapshot-{uuid.uuid4().hex}"
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "project_id": project_id,
        "created_at": utc_now(),
        "complete": scan["complete"],
        "file_count": scan["file_count"],
        "total_bytes": scan["total_bytes"],
        "inventory": scan["inventory"],
        "scan_issues": scan["issues"],
    }
    digest = sha256_bytes(canonical_bytes(snapshot))
    reference = {
        "id": snapshot_id,
        "sha256": digest,
        "created_at": snapshot["created_at"],
        "complete": snapshot["complete"],
        "file_count": snapshot["file_count"],
    }
    return snapshot, reference


def _append_event(state: dict[str, Any], kind: str, summary: str, payload: dict[str, Any]) -> None:
    revision = state["revision"] + 1
    event = {
        "revision": revision,
        "timestamp": utc_now(),
        "kind": kind,
        "summary": summary,
        "payload": payload,
        "previous_event_hash": state["last_event_hash"],
    }
    event["event_hash"] = _event_hash(event)
    state["history"].append(event)
    state["revision"] = revision
    state["updated_at"] = event["timestamp"]
    state["last_event_hash"] = event["event_hash"]
    _seal_state(state)


def _save_mutation(project_root: Path, state: dict[str, Any], kind: str, summary: str, payload: dict[str, Any]) -> dict[str, Any]:
    _, state_path, _, backup_dir, _ = _state_paths(project_root)
    current = load_state(project_root)
    backup_path = backup_dir / f"revision-{current['revision']:08d}-{current['integrity']['state_sha256'][:12]}.json"
    if not backup_path.exists():
        _atomic_write(backup_path, pretty_json(current).encode("utf-8"), overwrite=False)
    state = json.loads(json.dumps(state))
    _append_event(state, kind, summary, payload)
    _atomic_write(state_path, pretty_json(state).encode("utf-8"))
    return state


def _check_revision(state: dict[str, Any], expected: int | None) -> None:
    if expected is None:
        raise StateError("mutating commands require --expected-revision to prevent stale writes")
    if expected != state["revision"]:
        raise StateError(f"stale project state: expected revision {expected}, current revision is {state['revision']}; inspect and retry")


def init_project(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        raise StateError(f"project root is not a directory: {project_root}")
    state_dir, state_path, snapshot_dir, _, lock_path = _state_paths(project_root)
    with StateLock(lock_path):
        if state_path.exists():
            raise StateError(f"project state already exists: {state_path}")
        scan = _scan_project(project_root, max_file_bytes=args.max_file_bytes, max_files=args.max_files, excludes=args.exclude)
        if not scan["complete"] and not args.allow_partial:
            raise StateError(f"initial scan is incomplete ({len(scan['issues'])} issue(s)); use --allow-partial to record it explicitly")
        project_id = str(uuid.uuid4())
        snapshot, reference = _make_snapshot(project_id, scan)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write(snapshot_dir / f"{snapshot['snapshot_id']}.json", pretty_json(snapshot).encode("utf-8"), overwrite=False)
        now = utc_now()
        state: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "project": {
                "id": project_id,
                "name": args.project_name.strip() if args.project_name else project_root.name,
                "target_game_version": args.target_game_version,
                "source_of_truth": args.source_of_truth or "project files inspected at initialization",
                "pack_roots": args.pack_root or [],
                "constraints": args.constraint or [],
                "preserve": args.preserve or [],
            },
            "revision": 1,
            "created_at": now,
            "updated_at": now,
            "latest_snapshot": reference,
            "last_complete_snapshot": reference if scan["complete"] else None,
            "records": {category: [] for category in STATUSES},
            "history": [],
            "last_event_hash": ZERO_HASH,
            "integrity": {},
        }
        event = {
            "revision": 1,
            "timestamp": now,
            "kind": "project.initialized",
            "summary": "Created project state and captured initial file inventory.",
            "payload": {"snapshot_id": snapshot["snapshot_id"], "snapshot_sha256": reference["sha256"], "complete": scan["complete"], "file_count": scan["file_count"]},
            "previous_event_hash": ZERO_HASH,
        }
        event["event_hash"] = _event_hash(event)
        state["history"].append(event)
        state["last_event_hash"] = event["event_hash"]
        _seal_state(state)
        _atomic_write(state_path, pretty_json(state).encode("utf-8"), overwrite=False)
        return {"status": "INITIALIZED" if scan["complete"] else "INITIALIZED_PARTIAL", "state_path": str(state_path), "revision": 1, "project_id": project_id, "snapshot": reference, "scan_issues": scan["issues"], "integrity": state["integrity"]}


def inspect_project(project_root: Path, *, max_file_bytes: int, max_files: int, excludes: list[str]) -> dict[str, Any]:
    state = load_state(project_root)
    scan = _scan_project(project_root, max_file_bytes=max_file_bytes, max_files=max_files, excludes=excludes)
    _, _, snapshot_dir, _, _ = _state_paths(project_root)
    baseline_ref = state.get("last_complete_snapshot")
    baseline = _read_snapshot(snapshot_dir, baseline_ref) if baseline_ref else None
    delta = _diff_inventory(baseline, scan, complete=scan["complete"]) if baseline else {"added": [], "modified": [], "deleted": []}
    drift = bool(delta["added"] or delta["modified"] or delta["deleted"] or not scan["complete"])
    return {
        "status": "DRIFT" if drift else "CLEAN",
        "project": state["project"],
        "revision": state["revision"],
        "state_integrity": state["integrity"],
        "baseline_snapshot": baseline_ref,
        "scan": {"complete": scan["complete"], "file_count": scan["file_count"], "total_bytes": scan["total_bytes"], "issues": scan["issues"]},
        "delta": {key: {"count": len(value), "paths": value} for key, value in delta.items()},
    }


def capture_project(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    _, _, snapshot_dir, _, lock_path = _state_paths(project_root)
    with StateLock(lock_path):
        state = load_state(project_root)
        _check_revision(state, args.expected_revision)
        scan = _scan_project(project_root, max_file_bytes=args.max_file_bytes, max_files=args.max_files, excludes=args.exclude)
        if not scan["complete"] and not args.allow_partial:
            raise StateError(f"capture is incomplete ({len(scan['issues'])} issue(s)); no snapshot was committed; inspect issues or use --allow-partial")
        old_ref = state.get("last_complete_snapshot")
        old_snapshot = _read_snapshot(snapshot_dir, old_ref) if old_ref else {"inventory": {}}
        delta = _diff_inventory(old_snapshot, scan, complete=scan["complete"])
        snapshot, reference = _make_snapshot(state["project"]["id"], scan)
        _atomic_write(snapshot_dir / f"{snapshot['snapshot_id']}.json", pretty_json(snapshot).encode("utf-8"), overwrite=False)
        updated = json.loads(json.dumps(state))
        updated["latest_snapshot"] = reference
        if scan["complete"]:
            updated["last_complete_snapshot"] = reference
        result_state = _save_mutation(
            project_root, updated, "snapshot.captured", args.message or "Captured project file inventory.",
            {"snapshot_id": reference["id"], "snapshot_sha256": reference["sha256"], "complete": scan["complete"], "delta": delta, "scan_issues": scan["issues"]},
        )
        return {"status": "CAPTURED" if scan["complete"] else "CAPTURED_PARTIAL", "revision": result_state["revision"], "snapshot": reference, "delta": {key: {"count": len(value), "paths": value} for key, value in delta.items()}, "scan_issues": scan["issues"], "state_integrity": result_state["integrity"]}


def record_item(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    _, _, _, _, lock_path = _state_paths(project_root)
    with StateLock(lock_path):
        state = load_state(project_root)
        _check_revision(state, args.expected_revision)
        category = args.category
        if category not in STATUSES or args.status not in STATUSES[category]:
            raise StateError(f"invalid status {args.status!r} for {category}; allowed={sorted(STATUSES.get(category, set()))}")
        title = (args.title or "").strip()
        if not title:
            raise StateError("--title must be non-empty")
        updated = json.loads(json.dumps(state))
        revision = state["revision"] + 1
        now = utc_now()
        item = {
            "id": f"rec-{uuid.uuid4().hex}",
            "category": category,
            "title": title,
            "status": args.status,
            "details": args.details or "",
            "evidence": args.evidence or [],
            "source": args.source or "",
            "created_at": now,
            "updated_at": now,
            "created_revision": revision,
            "updated_revision": revision,
            "updates": [],
        }
        updated["records"][category].append(item)
        saved = _save_mutation(project_root, updated, f"record.{category}.created", f"Recorded {category}: {title}", {"record_id": item["id"], "status": item["status"], "evidence_count": len(item["evidence"])})
        return {"status": "RECORDED", "revision": saved["revision"], "record": item, "state_integrity": saved["integrity"]}


def update_item(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    _, _, _, _, lock_path = _state_paths(project_root)
    with StateLock(lock_path):
        state = load_state(project_root)
        _check_revision(state, args.expected_revision)
        updated = json.loads(json.dumps(state))
        found: dict[str, Any] | None = None
        for items in updated["records"].values():
            for item in items:
                if item["id"] == args.record_id:
                    found = item
                    break
            if found:
                break
        if found is None:
            raise StateError(f"record not found: {args.record_id}")
        category = found["category"]
        new_status = args.status or found["status"]
        if new_status not in STATUSES[category]:
            raise StateError(f"invalid status {new_status!r} for {category}; allowed={sorted(STATUSES[category])}")
        previous = {"status": found["status"], "details": found["details"], "evidence": list(found["evidence"])}
        if args.status is None and args.details is None and args.evidence is None:
            raise StateError("update requires at least one of --status, --details or --evidence")
        revision = state["revision"] + 1
        if args.status is not None:
            found["status"] = new_status
        if args.details is not None:
            found["details"] = args.details
        if args.evidence is not None:
            found["evidence"] = args.evidence
        found["updated_at"] = utc_now()
        found["updated_revision"] = revision
        found["updates"].append({"revision": revision, "timestamp": found["updated_at"], "previous": previous, "status": found["status"], "details": found["details"], "evidence": list(found["evidence"])})
        saved = _save_mutation(project_root, updated, "record.updated", f"Updated record {args.record_id}", {"record_id": args.record_id, "previous": previous, "current": {"status": found["status"], "details": found["details"], "evidence": found["evidence"]}})
        return {"status": "UPDATED", "revision": saved["revision"], "record": found, "state_integrity": saved["integrity"]}


def restore_revision(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    _, _, _, backup_dir, lock_path = _state_paths(project_root)
    with StateLock(lock_path):
        state = load_state(project_root)
        _check_revision(state, args.expected_revision)
        if not args.confirm_metadata_only:
            raise StateError("restoration changes project metadata only; pass --confirm-metadata-only to proceed")
        if args.revision < 1 or args.revision >= state["revision"]:
            raise StateError("restore target must be an earlier positive revision")
        candidates = sorted(backup_dir.glob(f"revision-{args.revision:08d}-*.json"))
        if not candidates:
            raise StateError(f"no backup exists for revision {args.revision}")
        restored = _verify_state_document(read_json(candidates[-1]))
        _read_snapshot(_state_paths(project_root)[2], restored.get("latest_snapshot"))
        _read_snapshot(_state_paths(project_root)[2], restored.get("last_complete_snapshot"))
        updated = json.loads(json.dumps(state))
        updated["project"] = restored["project"]
        updated["latest_snapshot"] = restored["latest_snapshot"]
        updated["last_complete_snapshot"] = restored["last_complete_snapshot"]
        updated["records"] = restored["records"]
        saved = _save_mutation(project_root, updated, "state.metadata_restored", f"Restored metadata from revision {args.revision}; project files were not changed.", {"restored_from_revision": args.revision, "project_files_changed": False})
        return {"status": "METADATA_RESTORED", "revision": saved["revision"], "restored_from_revision": args.revision, "project_files_changed": False, "state_integrity": saved["integrity"]}


def recover_project(args: argparse.Namespace) -> dict[str, Any]:
    """Rebuild the state generation from the newest valid metadata backup.

    Recovery rotates the project-state ID, resets the revision sequence to 1,
    captures the current workspace, and archives the damaged state document.
    It does not change any project file.
    """
    project_root = Path(args.project_root).expanduser().resolve()
    state_dir, state_path, snapshot_dir, backup_dir, lock_path = _state_paths(project_root)
    with StateLock(lock_path):
        if not args.confirm_recovery:
            raise StateError("recovery creates a new state generation from a backup; pass --confirm-recovery")
        try:
            load_state(project_root)
        except StateError:
            pass
        else:
            raise StateError("current project state is valid; use restore for metadata rollback instead of recovery")

        if not backup_dir.exists():
            raise StateError("no metadata backup directory exists; recovery is not possible")
        candidates = sorted(
            backup_dir.glob("revision-*.json"),
            key=lambda path: path.name,
            reverse=True,
        )
        recovered_from: dict[str, Any] | None = None
        recovered_path: Path | None = None
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for candidate in candidates:
            try:
                backup = _verify_state_document(read_json(candidate))
                _read_snapshot(snapshot_dir, backup.get("latest_snapshot"))
                _read_snapshot(snapshot_dir, backup.get("last_complete_snapshot"))
            except StateError:
                continue
            recovered_from = backup
            recovered_path = candidate
            break
        if recovered_from is None or recovered_path is None:
            raise StateError("no valid metadata backup with intact referenced snapshots was found")

        scan = _scan_project(project_root, max_file_bytes=args.max_file_bytes, max_files=args.max_files, excludes=args.exclude)
        if not scan["complete"] and not args.allow_partial:
            raise StateError(f"recovery scan is incomplete ({len(scan['issues'])} issue(s)); use --allow-partial only after reviewing skipped paths")

        new_project_id = str(uuid.uuid4())
        snapshot, reference = _make_snapshot(new_project_id, scan)
        _atomic_write(snapshot_dir / f"{snapshot['snapshot_id']}.json", pretty_json(snapshot).encode("utf-8"), overwrite=False)
        now = utc_now()
        old_project_id = recovered_from["project"]["id"]
        recovered_project = json.loads(json.dumps(recovered_from["project"]))
        recovered_project["id"] = new_project_id
        state: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "project": recovered_project,
            "revision": 1,
            "created_at": now,
            "updated_at": now,
            "latest_snapshot": reference,
            "last_complete_snapshot": reference if scan["complete"] else None,
            "records": json.loads(json.dumps(recovered_from["records"])),
            "history": [],
            "last_event_hash": ZERO_HASH,
            "integrity": {},
        }
        event = {
            "revision": 1,
            "timestamp": now,
            "kind": "state.recovered_from_backup",
            "summary": f"Created a new state generation from metadata backup revision {recovered_from['revision']}; project files were not changed.",
            "payload": {
                "backup_file": recovered_path.name,
                "backup_revision": recovered_from["revision"],
                "backup_state_sha256": recovered_from["integrity"]["state_sha256"],
                "previous_project_id": old_project_id,
                "project_files_changed": False,
                "current_scan_complete": scan["complete"],
                "snapshot_id": reference["id"],
            },
            "previous_event_hash": ZERO_HASH,
        }
        event["event_hash"] = _event_hash(event)
        state["history"].append(event)
        state["last_event_hash"] = event["event_hash"]
        _seal_state(state)

        if state_path.exists():
            damaged_copy = backup_dir / f"corrupt-state-{uuid.uuid4().hex}.corrupt"
            _atomic_write(damaged_copy, state_path.read_bytes(), overwrite=False)
        _atomic_write(state_path, pretty_json(state).encode("utf-8"))
        return {
            "status": "RECOVERED" if scan["complete"] else "RECOVERED_PARTIAL",
            "revision": 1,
            "new_project_id": new_project_id,
            "previous_project_id": old_project_id,
            "restored_records": sum(len(items) for items in state["records"].values()),
            "backup_revision": recovered_from["revision"],
            "damaged_state_archived": state_path.exists(),
            "project_files_changed": False,
            "snapshot": reference,
            "scan_issues": scan["issues"],
            "state_integrity": state["integrity"],
        }


def verify_project(project_root: Path) -> dict[str, Any]:
    state = load_state(project_root, verify_snapshots=True)
    _, _, snapshot_dir, backup_dir, _ = _state_paths(project_root)
    backups_checked = 0
    backup_errors: list[str] = []
    for path in sorted(backup_dir.glob("revision-*.json")) if backup_dir.exists() else []:
        try:
            backup = _verify_state_document(read_json(path))
            if backup["project"]["id"] == state["project"]["id"] and backup["revision"] >= state["revision"]:
                raise StateError("backup revision is not older than current state generation")
            _read_snapshot(snapshot_dir, backup.get("latest_snapshot"))
            _read_snapshot(snapshot_dir, backup.get("last_complete_snapshot"))
            backups_checked += 1
        except StateError as exc:
            backup_errors.append(f"{path.name}: {exc}")
    return {
        "status": "PASS" if not backup_errors else "PARTIAL",
        "project_id": state["project"]["id"],
        "revision": state["revision"],
        "state_sha256": state["integrity"]["state_sha256"],
        "history_events": len(state["history"]),
        "backups_checked": backups_checked,
        "backup_errors": backup_errors,
        "latest_snapshot_verified": state.get("latest_snapshot") is not None,
        "last_complete_snapshot_verified": state.get("last_complete_snapshot") is not None,
    }


def link_work_order(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    state = load_state(project_root)
    work_path = Path(args.work_order).expanduser().resolve()
    work = read_json(work_path)
    if not isinstance(work, dict):
        raise StateError("Work Order root must be an object")
    if work.get("project_state") is not None and not args.replace_link:
        raise StateError("Work Order already has project_state; pass --replace-link after confirming the new link")
    latest = state.get("latest_snapshot")
    work["project_state"] = {
        "project_id": state["project"]["id"],
        "revision": state["revision"],
        "state_path": f"{STATE_DIR_NAME}/{STATE_FILE_NAME}",
        "state_sha256": state["integrity"]["state_sha256"],
        "latest_snapshot_id": latest["id"] if latest else None,
        "latest_snapshot_sha256": latest["sha256"] if latest else None,
    }
    output = Path(args.output).expanduser().resolve()
    if output == work_path and not args.overwrite:
        raise StateError("writing over the input Work Order requires --overwrite")
    if output.exists() and not args.overwrite:
        raise StateError(f"output already exists (pass --overwrite): {output}")
    _atomic_write(output, pretty_json(work).encode("utf-8"), overwrite=args.overwrite)
    return {"status": "LINKED", "output": str(output), "project_state": work["project_state"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def root_arg(p: argparse.ArgumentParser) -> None:
        p.add_argument("--project-root", required=True, help="existing project folder")

    def scan_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--max-file-bytes", type=int, default=64 * 1024 * 1024)
        p.add_argument("--max-files", type=int, default=200000)
        p.add_argument("--exclude", action="append", default=[], help="additional relative path or glob to exclude")

    init = sub.add_parser("init", help="initialize state and capture the first inventory")
    root_arg(init); scan_args(init)
    init.add_argument("--project-name")
    init.add_argument("--target-game-version")
    init.add_argument("--source-of-truth")
    init.add_argument("--pack-root", action="append", default=[])
    init.add_argument("--constraint", action="append", default=[])
    init.add_argument("--preserve", action="append", default=[])
    init.add_argument("--allow-partial", action="store_true")

    inspect = sub.add_parser("inspect", help="compare current files with the latest complete snapshot")
    root_arg(inspect); scan_args(inspect)

    capture = sub.add_parser("capture", help="capture a new immutable file inventory")
    root_arg(capture); scan_args(capture)
    capture.add_argument("--expected-revision", type=int, required=True)
    capture.add_argument("--message")
    capture.add_argument("--allow-partial", action="store_true")

    record = sub.add_parser("record", help="append a decision, requirement, feature, issue, task, test or note")
    root_arg(record)
    record.add_argument("--expected-revision", type=int, required=True)
    record.add_argument("--category", choices=sorted(STATUSES), required=True)
    record.add_argument("--title", required=True)
    record.add_argument("--status", required=True)
    record.add_argument("--details", default="")
    record.add_argument("--evidence", action="append", default=[])
    record.add_argument("--source", default="")

    update = sub.add_parser("update", help="update a tracked record with revision history")
    root_arg(update)
    update.add_argument("--expected-revision", type=int, required=True)
    update.add_argument("--record-id", required=True)
    update.add_argument("--status", choices=sorted({s for values in STATUSES.values() for s in values}))
    update.add_argument("--details")
    update.add_argument("--evidence", action="append")

    restore = sub.add_parser("restore", help="restore metadata from a prior revision; never changes project files")
    root_arg(restore)
    restore.add_argument("--expected-revision", type=int, required=True)
    restore.add_argument("--revision", type=int, required=True)
    restore.add_argument("--confirm-metadata-only", action="store_true")

    recover = sub.add_parser("recover", help="rebuild a damaged state document from the newest valid metadata backup")
    root_arg(recover); scan_args(recover)
    recover.add_argument("--confirm-recovery", action="store_true")
    recover.add_argument("--allow-partial", action="store_true")

    verify = sub.add_parser("verify", help="verify state checksum, event chain, snapshots and backups")
    root_arg(verify)

    link = sub.add_parser("link-work-order", help="attach the current state revision to a Work Order")
    root_arg(link)
    link.add_argument("--work-order", required=True)
    link.add_argument("--output", required=True)
    link.add_argument("--overwrite", action="store_true")
    link.add_argument("--replace-link", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init_project(args)
        elif args.command == "inspect":
            result = inspect_project(Path(args.project_root).expanduser().resolve(), max_file_bytes=args.max_file_bytes, max_files=args.max_files, excludes=args.exclude)
        elif args.command == "capture":
            result = capture_project(args)
        elif args.command == "record":
            result = record_item(args)
        elif args.command == "update":
            result = update_item(args)
        elif args.command == "restore":
            result = restore_revision(args)
        elif args.command == "recover":
            result = recover_project(args)
        elif args.command == "verify":
            result = verify_project(Path(args.project_root).expanduser().resolve())
        elif args.command == "link-work-order":
            result = link_work_order(args)
        else:
            raise StateError(f"unsupported command: {args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if result.get("status") in {"DRIFT", "CAPTURED_PARTIAL", "INITIALIZED_PARTIAL", "PARTIAL"}:
            return 1
        return 0
    except StateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
