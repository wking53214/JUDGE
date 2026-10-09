"""The Judge's rules, one at a time, on hand-made evidence."""

from dataclasses import replace

import pytest

from warden.roles import Evidence
from warden.suite import SuiteRun

from judge import Judge

GREEN = SuiteRun(ran=True, passed=10)
HELD = ({"scenario": "a", "severity": "high", "status": "held"},)


def _evidence(**kw) -> Evidence:
    base = dict(
        target="/t", scope="documentation", cycles=((1, "APPLIED"),), changed=(("README.md", "write"),),
        judging_files_touched=(), suite_before=GREEN, suite_after=GREEN,
        ghost_before=("ghost-a",), ghost_after=("ghost-a",), declined=(), swizzle_proofs=True,
        attacks=HELD, unmeasured=())
    base.update(kw)
    return Evidence(**base)


def _decide(**kw):
    return Judge().decide(_evidence(**kw))


def test_complete_clean_evidence_is_accepted():
    v = _decide()
    assert v.decision == "ACCEPT" and v.judge.startswith("judge")


def test_a_run_that_changed_nothing_is_accepted_only_with_complete_evidence():
    assert _decide(changed=()).decision == "ACCEPT"
    assert _decide(changed=(), attacks=None).decision == "INSUFFICIENT"


@pytest.mark.parametrize("missing,words", [
    ({"suite_after": None}, "suite"), ({"ghost_before": None}, "Ghost"), ({"ghost_after": None}, "Ghost"),
    ({"swizzle_proofs": None}, "proofs"), ({"attacks": None}, "attacks")])
def test_a_missing_measurement_is_never_an_accept(missing, words):
    v = _decide(**missing)
    assert v.decision == "INSUFFICIENT" and any(words in r for r in v.reasons)


def test_a_red_suite_is_rejected():
    v = _decide(suite_after=SuiteRun(ran=True, passed=9, failed=1))
    assert v.decision == "REJECT" and any("not green" in r for r in v.reasons)


def test_fewer_passing_tests_is_rejected_even_if_green():
    v = _decide(suite_after=SuiteRun(ran=True, passed=4))
    assert v.decision == "REJECT" and any("fewer tests pass" in r for r in v.reasons)


def test_a_new_ghost_finding_is_rejected():
    v = _decide(ghost_after=("ghost-a", "ghost-new"))
    assert v.decision == "REJECT" and any("ghost-new" in r for r in v.reasons)


def test_a_closed_ghost_finding_is_fine():
    assert _decide(ghost_after=()).decision == "ACCEPT"


def test_failed_swizzle_proofs_are_rejected():
    assert _decide(swizzle_proofs=False).decision == "REJECT"


@pytest.mark.parametrize("severity,decision", [("high", "REJECT"), ("medium", "REJECT"), ("low", "ACCEPT")])
def test_a_violated_attack_rejects_unless_it_is_only_over_caution(severity, decision):
    attacks = ({"scenario": "x", "severity": severity, "status": "violated"},)
    assert _decide(attacks=attacks).decision == decision


def test_code_under_a_documentation_grant_is_rejected():
    v = _decide(changed=(("pkg/a.py", "write"),), scope="documentation")
    assert v.decision == "REJECT" and any("documentation" in r for r in v.reasons)
    assert _decide(changed=(("pkg/a.py", "write"),), scope="code").decision == "ACCEPT"


def test_reasons_are_always_given():
    for kw in ({}, {"attacks": None}, {"swizzle_proofs": False}):
        assert _decide(**kw).reasons


def test_harm_outranks_missing_evidence():
    v = _decide(suite_after=SuiteRun(ran=True, passed=3, failed=2), attacks=None)
    assert v.decision == "REJECT"


def test_the_judge_does_not_mutate_the_evidence():
    e = _evidence()
    snapshot = replace(e)
    Judge().decide(e)
    assert e == snapshot
