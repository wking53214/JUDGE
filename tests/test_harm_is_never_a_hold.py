"""Harm stays a REJECT when a test file, or a minor new finding, is also present, and says nothing about a hold.

The owner's rulings of 2026-10-28 loosen exactly two things (a changed test file, a new minor or informational Ghost
finding) from REJECT to INSUFFICIENT. A round-8 audit mutated `judge/seat.py` so that each of nine harm classes became a
hold whenever a test file was also changed, and all of the existing tests still passed. These tests close that gap: for
each harm class, evidence that carries the harm AND a changed test file AND a new minor finding must give REJECT, must
name the harm, and must contain no hold sentence at all. Tests only; no rule changed.

Each class was run against a local mutation of `seat.py` that turns that harm into a hold when a test file is changed
(`harm.append(` becomes `(unknown if judging else harm).append(` at that one site); every test below fails under its own
mutation (the commit message that added this file lists the nine mutations).
"""

import pytest
from test_strict_evidence import ASSAY, _ev

from judge import Judge

HOLD = "the machine does not approve that; a named human keeps or drops the held result"
MINOR_HOLD = "are held for a named human"
TEST_FILE = (("tests/test_a.py", "write"),)
ALSO_TEST_FILE = (("pkg/a.py", "write"),) + TEST_FILE


def _with_company(**kw):
    """Evidence carrying the harm in `kw`, plus a changed test file and a new finding whose own word is `minor`."""
    base = dict(changed=ALSO_TEST_FILE, judging_files_touched=("tests/test_a.py",),
                ghost_before=("g",), ghost_after=("g", "n"))
    base.update(kw)
    ev = _ev(**base)
    object.__setattr__(ev, "ghost_severity", {"n": "minor"})
    return ev


HARM = {
    "swizzle_attack_violated": dict(attacks=({"scenario": "x", "severity": "high", "status": "violated"},)),
    "swizzle_proofs_false": dict(swizzle_proofs=False),
    "assay_key_false": dict(assay={**ASSAY, "key_proven": False}),
    "assay_below_floor": dict(assay={**ASSAY, "caught": 1, "floor": 3}),
    "assay_numbers_contradict": dict(assay={**ASSAY, "caught": 9, "failure_modes": 5}),
    "ghost_baseline_grown": dict(ghost_baseline_after={"path": None, "suppressed": 4}),
    "ghost_baseline_path_changed": dict(ghost_baseline_after={"path": "other.json", "suppressed": 0}),
    "edit_outside_the_project": dict(changed=(("../outside.py", "write"),) + TEST_FILE),
    "code_changed_with_no_final_suite": dict(suite_after=None),
}
#: what each harm sentence must contain, so the test knows it is looking at the right REJECT
WORDS = {
    "swizzle_attack_violated": "violated invariant",
    "swizzle_proofs_false": "own proofs failed",
    "assay_key_false": "answer key was not proven",
    "assay_below_floor": "below the floor",
    "assay_numbers_contradict": "contradict themselves",
    "ghost_baseline_grown": "baseline now ignores more findings",
    "ghost_baseline_path_changed": "baseline file changed",
    "edit_outside_the_project": "outside the project",
    "code_changed_with_no_final_suite": "no final suite result",
}


def test_the_table_covers_the_nine_classes():
    assert set(HARM) == set(WORDS) and len(HARM) == 9


@pytest.mark.parametrize("name", sorted(HARM))
def test_the_harm_alone_is_a_reject_with_its_sentence(name):
    """The control: with no test file and no minor finding the harm is already a REJECT (so the next test measures company)."""
    kw = dict(HARM[name])
    kw.setdefault("changed", (("pkg/a.py", "write"),))
    v = Judge().decide(_ev(**kw))
    assert v.decision == "REJECT" and any(WORDS[name] in r for r in v.reasons), (name, v.reasons)


@pytest.mark.parametrize("name", sorted(HARM))
def test_harm_beside_a_changed_test_file_and_a_minor_finding_is_a_reject_with_no_hold_sentence(name):
    v = Judge().decide(_with_company(**HARM[name]))
    assert v.decision == "REJECT", (name, v.decision, v.reasons)
    assert any(WORDS[name] in r for r in v.reasons), (name, v.reasons)
    joined = " | ".join(v.reasons)
    assert HOLD not in joined, (name, v.reasons)
    assert "tests or test settings were changed" not in joined, (name, v.reasons)
    assert MINOR_HOLD not in joined, (name, v.reasons)


def test_the_same_company_without_harm_is_still_held_not_rejected():
    """The company on its own is what the rulings hold: a test file and a minor finding give INSUFFICIENT with both sentences."""
    v = Judge().decide(_with_company())
    assert v.decision == "INSUFFICIENT"
    joined = " | ".join(v.reasons)
    assert HOLD in joined and MINOR_HOLD in joined


def test_two_harms_and_the_company_report_both_harms_and_no_hold():
    kw = {**HARM["swizzle_proofs_false"], **HARM["assay_key_false"]}
    v = Judge().decide(_with_company(**kw))
    assert v.decision == "REJECT" and len(v.reasons) == 2
    assert not any(HOLD in r or MINOR_HOLD in r for r in v.reasons)


def test_unreadable_evidence_is_checked_before_harm():
    """A red suite plus one malformed field is INSUFFICIENT with only the 'could not be read' reason, not REJECT."""
    from cns.suite import SuiteRun
    v = Judge().decide(_ev(suite_after=SuiteRun(ran=True, passed=9, failed=1, exit_code=1), declined="oops"))
    assert v.decision == "INSUFFICIENT" and len(v.reasons) == 1 and "could not be read" in v.reasons[0]


def test_the_accept_sentence_says_which_edits_it_measures():
    v = Judge().decide(_ev())
    assert v.decision == "ACCEPT"
    assert "no edit that Warden applied left the project" in v.reasons[0]
    assert "what the suite itself did is not measured" in v.reasons[0]
    assert "no edit left the project" not in v.reasons[0]
