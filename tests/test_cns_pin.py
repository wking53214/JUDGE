"""CNS is the one runtime dependency, pinned by release tag, never to a moving branch."""

import re
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
CNS = re.compile(r"^cns @ git\+https://github\.com/wking53214/CNS\.git@(?P<ref>v\d+\.\d+\.\d+)$")


def _project() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]


def test_cns_is_pinned_to_a_release_tag():
    deps = _project()["dependencies"]
    found = [m for d in deps if (m := CNS.match(d))]
    assert len(found) == 1, f"expected exactly one CNS dependency pinned to a release tag, got {deps}"


def test_cns_is_the_only_runtime_dependency():
    assert [d.split()[0] for d in _project()["dependencies"]] == ["cns"]


def test_the_cns_pin_names_its_commit_in_a_comment():
    line = next(x for x in PYPROJECT.read_text(encoding="utf-8").splitlines() if x.strip().startswith('"cns @'))
    assert re.search(r"#\s*v\d+\.\d+\.\d+ = [0-9a-f]{40}\s*$", line), f"say which commit the CNS tag peels to: {line!r}"
