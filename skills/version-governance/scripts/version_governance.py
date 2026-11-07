#!/usr/bin/env python3
"""Calculate and validate Minecraft Bedrock Engineer version successors."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass

_VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class VersionError(ValueError):
    """Raised when a version cannot be parsed or advanced safely."""


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = _VERSION_RE.fullmatch(value.strip())
        if not match:
            raise VersionError(
                f"Invalid version {value!r}; expected three non-negative numeric components"
            )
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def is_new_format(self) -> bool:
        return all(0 <= part <= 9 for part in (self.major, self.minor, self.patch))


def validate_new_version(value: str) -> Version:
    version = Version.parse(value)
    if not version.is_new_format:
        raise VersionError(
            f"{value!r} is legacy; every new MAJOR.MINOR.PATCH component must be 0..9"
        )
    return version


def next_version(value: str) -> str:
    """Return the next version under the one-digit sequence and legacy migration."""
    current = Version.parse(value)
    major, minor, patch = current.major, current.minor, current.patch

    # A legacy PATCH overflow carries into MINOR, preserving the published
    # historical string and ensuring the generated candidate is one-digit.
    if patch > 9:
        if minor < 9:
            return str(Version(major, minor + 1, 0))
        if major < 9:
            return str(Version(major + 1, 0, 0))
        raise VersionError("Cannot migrate legacy PATCH overflow: no one-digit successor exists")

    # A legacy MINOR overflow carries into MAJOR.
    if minor > 9:
        if major < 9:
            return str(Version(major + 1, 0, 0))
        raise VersionError("Cannot migrate legacy MINOR overflow: no one-digit successor exists")

    # A multi-digit MAJOR cannot be represented in the requested format.
    if major > 9:
        raise VersionError("Legacy MAJOR exceeds 9; user decision required before versioning")

    if patch < 9:
        return str(Version(major, minor, patch + 1))
    if minor < 9:
        return str(Version(major, minor + 1, 0))
    if major < 9:
        return str(Version(major + 1, 0, 0))
    raise VersionError("Version 9.9.9 has no successor under the one-digit policy")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_next = sub.add_parser("next", help="calculate the next version")
    p_next.add_argument("current")
    p_validate = sub.add_parser("validate", help="validate a new-format version")
    p_validate.add_argument("candidate")
    args = parser.parse_args(argv)
    try:
        if args.command == "next":
            result = {"current": args.current, "next": next_version(args.current)}
        else:
            parsed = validate_new_version(args.candidate)
            result = {"candidate": str(parsed), "valid": True, "component_limit": 9}
    except VersionError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"status": "PASS", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
