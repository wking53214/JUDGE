"""Warden is pinned to a tag or commit, never to a moving branch."""

import re
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
WARDEN = re.compile(r"^warden @ git\+https://github\.com/wking53214/Warden\.git@(?P<ref>[^\s@]+)$")
PINNED = re.compile(r"^(?:[0-9a-f]{40}|v\d+\.\d+\.\d+)$")


def _warden_dependency() -> re.Match:
    deps = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    found = [m for d in deps if (m := WARDEN.match(d))]
    assert len(found) == 1, f"expected exactly one pinned Warden dependency, got {deps}"
    return found[0]


def test_warden_is_pinned_to_a_tag_or_a_full_commit():
    ref = _warden_dependency().group("ref")
    assert PINNED.match(ref), f"Warden is pinned to {ref!r}; use a vX.Y.Z tag or a full 40-character commit"
