"""The real Warden names its tests, and the Judge compares them (live from the Warden pin `6feb031`).

JUDGE 0.16.0 compares a suite before and after by test name when both runs carry `test_outcomes`; Warden PR #83 made
its pytest runner fill them. These tests run the pinned Warden's suite runner on real projects and hand the results to
the Judge, so a Warden that stopped naming its tests, or named them in a shape the Judge cannot read, fails here.
"""

import sys

from conftest import need_warden

need_warden()

from test_strict_evidence import _d  # noqa: E402
from warden.suite import run_suite  # noqa: E402


def _suite(root, body):
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_x.py").write_text(body, encoding="utf-8")
    return run_suite(root, sys.executable)


def test_the_pinned_warden_names_its_tests(tmp_path):
    run = _suite(tmp_path, "def test_one():\n    pass\n")
    assert run.ran and run.passed == 1
    assert run.test_outcomes == (("tests/test_x.py::test_one", "passed"),)


def test_a_swapped_test_from_the_real_warden_is_rejected(tmp_path):
    before = _suite(tmp_path / "a", "def test_one():\n    pass\n")
    after = _suite(tmp_path / "b", "def test_two():\n    pass\n")
    assert (before.passed, after.passed) == (1, 1)
    v = _d(suite_before=before, suite_after=after)
    assert v.decision == "REJECT"
    assert any("did not pass at the end" in r and "test_one" in r for r in v.reasons), v.reasons


def test_the_same_tests_from_the_real_warden_are_accepted(tmp_path):
    body = "def test_one():\n    pass\n"
    v = _d(suite_before=_suite(tmp_path / "a", body), suite_after=_suite(tmp_path / "b", body))
    assert v.decision == "ACCEPT", v.reasons
