"""CNS is pinned to a tag or a full commit, never to a moving branch."""

import re
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
CNS = re.compile(r"^cns @ git\+https://github\.com/wking53214/(?:CNS|cns)\.git@(?P<ref>[^\s@]+)$")
PINNED = re.compile(r"^(?:[0-9a-f]{40}|v\d+\.\d+\.\d+)$")


def test_cns_is_pinned_to_a_tag_or_a_full_commit():
    deps = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    found = [m for d in deps if (m := CNS.match(d))]
    assert len(found) == 1, f"expected exactly one pinned CNS dependency, got {deps}"
    ref = found[0].group("ref")
    assert PINNED.match(ref), f"CNS is pinned to {ref!r}; use a vX.Y.Z tag or a full 40-character commit"
