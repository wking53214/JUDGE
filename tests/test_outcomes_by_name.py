"""Tests compared by name, not only by count (0.16.0, was KNOWN DEFECTS 2).

Up to 0.15.0 the Judge compared how many tests passed before and after. A run that removed one passing test and added
another, or that skipped one test and un-skipped another, kept every count equal and was ACCEPTed, whatever the test was
called or written in. When the suite runs name each test and its outcome (`test_outcomes`, a list of (test id, outcome)
pairs), a test that passed at the start must pass at the end. When neither run names its tests, nothing changes.
"""

import copy
import json
from pathlib import Path

import pytest
from test_strict_evidence import _d

from cns.suite import SuiteRun
from judge import cli
from judge.cns_connector import JudgeGate
from cns import gate

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "accept.json"
LOST = "a test that passed at the start did not pass at the end"


def _run(outcomes, **counts):
    """A suite run whose counts are worked out from the named outcomes, unless given."""
    words = [w for _, w in outcomes]
    base = {"passed": words.count("passed"), "failed": words.count("failed"), "errors": words.count("error"),
            "skipped": words.count("skipped"), "xfailed": words.count("xfailed"), "xpassed": words.count("xpassed")}
    run = SuiteRun(ran=True, exit_code=0, **{**base, **counts})
    object.__setattr__(run, "test_outcomes", tuple(tuple(o) for o in outcomes))
    return run


TEN = [(f"tests/test_a.py::t{i}", "passed") for i in range(10)]


def test_the_same_tests_passing_at_both_ends_is_accepted():
    v = _d(suite_before=_run(TEN), suite_after=_run(TEN))
    assert v.decision == "ACCEPT", v.reasons


def test_a_new_test_added_is_accepted():
    v = _d(suite_before=_run(TEN), suite_after=_run(TEN + [("tests/test_a.py::new", "passed")]))
    assert v.decision == "ACCEPT", v.reasons


def test_one_test_swapped_for_another_is_rejected_though_the_counts_are_equal():
    after = TEN[1:] + [("tests/test_a.py::replacement", "passed")]
    v = _d(suite_before=_run(TEN), suite_after=_run(after))
    assert v.decision == "REJECT"
    assert any(LOST in r and "no longer there" in r and "tests/test_a.py::t0" in r for r in v.reasons), v.reasons


def test_a_skip_moved_from_one_test_to_another_is_rejected_though_the_counts_are_equal():
    before = TEN + [("tests/test_a.py::slow", "skipped")]
    after = TEN[1:] + [("tests/test_a.py::t0", "skipped"), ("tests/test_a.py::slow", "passed")]
    v = _d(suite_before=_run(before), suite_after=_run(after))
    assert v.decision == "REJECT"
    assert any(LOST in r and "no longer passing" in r and "t0" in r for r in v.reasons), v.reasons


def test_a_test_that_was_skipped_at_the_start_may_be_removed():
    before = TEN + [("tests/test_a.py::old", "skipped")]
    v = _d(suite_before=_run(before), suite_after=_run(TEN), scope="documentation", changed=(("README.md", "write"),))
    assert v.decision == "ACCEPT", v.reasons


def test_names_that_disagree_with_the_counts_are_held():
    v = _d(suite_before=_run(TEN), suite_after=_run(TEN, passed=11))
    assert v.decision == "INSUFFICIENT"
    assert any("do not agree with its counts" in r for r in v.reasons), v.reasons


@pytest.mark.parametrize("which", ["before", "after"])
def test_tests_named_at_one_end_only_are_held(which):
    named, plain = _run(TEN), SuiteRun(ran=True, passed=10, exit_code=0)
    kw = {"suite_before": named, "suite_after": plain} if which == "after" else {"suite_before": plain, "suite_after": named}
    v = _d(**kw)
    assert v.decision == "INSUFFICIENT"
    assert any("named at one end of the run but not at the other" in r for r in v.reasons), v.reasons


def test_with_no_names_at_either_end_nothing_changes():
    plain = SuiteRun(ran=True, passed=10, exit_code=0)
    assert _d(suite_before=plain, suite_after=plain).decision == "ACCEPT"


@pytest.mark.parametrize("bad", [
    "tests/test_a.py::t0 passed",                            # not a list
    (("tests/test_a.py::t0",),),                             # not a pair
    (("tests/test_a.py::t0", 1),),                           # outcome not text
    (("tests/test_a.py::t0", "ok"),),                        # a word the Judge does not know
    (("tests/test_a.py::t0", "passed"), ("tests/test_a.py::t0", "passed")),   # one test twice
])
def test_names_in_a_shape_the_judge_does_not_know_are_unreadable(bad):
    run = SuiteRun(ran=True, passed=10, exit_code=0)
    object.__setattr__(run, "test_outcomes", bad)
    v = _d(suite_before=_run(TEN), suite_after=run)
    assert v.decision == "INSUFFICIENT"
    assert any("could not be read" in r or "test_outcomes" in r for r in v.reasons), v.reasons


def test_a_test_id_is_shown_without_control_characters_and_cut_short():
    weird = "tests/test_a.py::t\x1b[31m" + "x" * 500
    v = _d(suite_before=_run([(weird, "passed")] + TEN[1:]), suite_after=_run(TEN))
    reason = next(r for r in v.reasons if LOST in r)
    assert "\x1b" not in reason and "x" * 200 not in reason


def test_the_command_line_reads_the_names(tmp_path, capsys):
    data = copy.deepcopy(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    data["target"] = str(tmp_path)
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    for key, outcomes in (("suite_before", TEN), ("suite_after", TEN[1:] + [("tests/test_a.py::other", "passed")])):
        data[key] = {**data[key], "test_outcomes": [list(o) for o in outcomes]}
    path = tmp_path / "e.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert cli.main(["decide", str(path)]) == 1
    assert LOST in capsys.readouterr().out


def test_the_cns_connector_sees_the_names():
    from test_strict_evidence import _ev
    swapped = _ev(suite_before=_run(TEN), suite_after=_run(TEN[1:] + [("tests/test_a.py::other", "passed")]))
    result = JudgeGate().check(swapped)
    assert result.outcome is gate.GateOutcome.TERMINAL_BREACH
    assert LOST in result.reason
