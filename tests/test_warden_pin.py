"""Warden is a test-time extra, pinned to a full commit, and CI checks out that same commit."""

import re
import tomllib
from pathlib import Path

import pytest
from conftest import HAVE_WARDEN, REQUIRE_WARDEN

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
WARDEN = re.compile(r"^warden @ git\+https://github\.com/wking53214/Warden\.git@(?P<sha>[0-9a-f]{40})$")


def _extras() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["optional-dependencies"]


def _pin() -> str:
    found = [m for d in _extras()["warden"] if (m := WARDEN.match(d))]
    assert len(found) == 1, f"expected exactly one Warden pin to a 40-character commit, got {_extras()['warden']}"
    return found[0].group("sha")


def test_warden_is_pinned_to_a_full_commit_in_the_warden_extra():
    assert len(_pin()) == 40


def test_warden_is_not_a_runtime_dependency():
    deps = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    assert not [d for d in deps if d.lower().startswith("warden")]


def test_the_dev_extra_includes_the_warden_extra():
    assert any(d.startswith("judge[") and "warden" in d for d in _extras()["dev"])


def test_ci_checks_out_the_pinned_warden_commit():
    text = WORKFLOW.read_text(encoding="utf-8")
    refs = re.findall(r"repository: wking53214/Warden\s+ref: (\S+)", text)
    assert refs == [_pin()], f"CI checks out Warden at {refs}, pyproject pins {_pin()}: bump both together"


def test_ci_makes_a_missing_warden_a_failure_not_a_skip():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'JUDGE_REQUIRE_WARDEN: "1"' in text


def test_the_pin_comment_names_the_warden_version_it_is():
    """The comment on the pin line says which Warden it is; when Warden is installed it must be true."""
    line = next(x for x in PYPROJECT.read_text(encoding="utf-8").splitlines() if x.strip().startswith('"warden @'))
    said = re.search(r"#\s*Warden (\d+\.\d+\.\d+)", line)
    assert said, f"name the Warden version in a comment on the pin line: {line!r}"
    if not HAVE_WARDEN:
        if REQUIRE_WARDEN:
            pytest.fail("JUDGE_REQUIRE_WARDEN=1 but Warden is not installed")
        pytest.skip("Warden is not installed")
    import warden

    assert warden.__version__ == said.group(1), (
        f"pyproject says the pin is Warden {said.group(1)} but Warden {warden.__version__} is installed: update the comment")
