"""The Judge's rules, one at a time, on hand-made evidence."""

from dataclasses import replace

import pytest

from cns.seat import Evidence
from cns.suite import SuiteRun

from judge import Judge

GREEN = SuiteRun(ran=True, passed=10, exit_code=0)
CLEAN_BASELINE = {"path": None, "suppressed": 0}
MISSING = object()
HELD = ({"scenario": "a", "severity": "high", "status": "held"},)

ASSAY = {"key_proven": True, "failure_modes": 5, "caught": 3, "floor": 0}


def _evidence(**kw) -> Evidence:
    base = dict(
        target="/t", scope="documentation", cycles=((1, "APPLIED"),), changed=(("README.md", "write"),),
        judging_files_touched=(), suite_before=GREEN, suite_after=GREEN,
        ghost_before=("ghost-a",), ghost_after=("ghost-a",), declined=(), swizzle_proofs=True,
        attacks=HELD, unmeasured=(), assay=ASSAY)
    base.update(kw)
    extra = {k: base.pop(k) for k in ("ghost_baseline_before", "ghost_baseline_after") if k in base}
    ev = Evidence(**base)
    # Ghost's baseline report is not an Evidence field in the pinned Warden yet; the Judge reads it if present.
    for k, v in {"ghost_baseline_before": CLEAN_BASELINE, "ghost_baseline_after": CLEAN_BASELINE, **extra}.items():
        if v is not MISSING:
            object.__setattr__(ev, k, v)
    return ev


def _decide(**kw):
    return Judge().decide(_evidence(**kw))


def test_complete_clean_evidence_is_accepted():
    v = _decide()
    assert v.decision == "ACCEPT" and v.judge.startswith("judge")


def test_a_run_that_changed_nothing_is_accepted_only_with_complete_evidence():
    # no edits listed, so no cycle may claim to have applied one (cycles are the only line that changed)
    assert _decide(changed=(), cycles=((1, "NOTHING_TO_PROPOSE"),)).decision == "ACCEPT"
    assert _decide(changed=(), cycles=((1, "NOTHING_TO_PROPOSE"),), attacks=None).decision == "INSUFFICIENT"


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


@pytest.mark.parametrize("path", ["specimens/pairs/x.py", "tests/fixtures/y.json", "golden/z.txt", "corpus/w.py",
                                  "pkg/testdata/v.py", "__snapshots__/u.snap"])
def test_a_fixture_or_specimen_is_judging_material_even_under_a_code_grant(path):
    v = _decide(changed=((path, "write"),), scope="code")
    assert v.decision == "INSUFFICIENT" and any("tests or test settings were changed" in r for r in v.reasons), v.reasons


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


def test_a_missing_assay_grade_is_insufficient_never_accept():
    assert _decide(assay=None).decision == "INSUFFICIENT"


def test_an_unproven_answer_key_is_rejected():
    v = _decide(assay={**ASSAY, "key_proven": False})
    assert v.decision == "REJECT" and "answer key" in v.reasons[0]


def test_ghost_below_the_floor_is_rejected_and_at_the_floor_is_accepted():
    assert _decide(assay={**ASSAY, "floor": 4}).decision == "REJECT"
    assert _decide(assay={**ASSAY, "floor": 3}).decision == "ACCEPT"


# ---- evidence that contradicts itself is never accepted ---------------------------------------------------

def _says(v, *words):
    return v.decision == "INSUFFICIENT" and any(all(w in r for w in words) for r in v.reasons)


@pytest.mark.parametrize("cycles", [(), ((1, "NOTHING_TO_PROPOSE"), (2, "DECLINED")), ((1, "PUT_BACK"),), ((1, "DECLINED"),)])
def test_a_listed_change_that_no_cycle_applied_is_not_accepted(cycles):
    assert _says(_decide(cycles=cycles), "no cycle applied")


def test_a_cycle_outcome_the_judge_does_not_know_is_not_accepted():
    assert _says(_decide(cycles=((1, "REVERTED"),)), "does not know", "REVERTED")
    assert _says(_decide(cycles=((1, "applied"),)), "does not know")


def test_more_applied_cycles_than_listed_edits_is_not_accepted():
    assert _says(_decide(cycles=((1, "APPLIED"), (2, "APPLIED"), (3, "NOTHING_TO_PROPOSE"))), "2 cycle(s)", "1 edit(s)")
    assert _says(_decide(cycles=((1, "APPLIED"),), changed=()), "1 cycle(s)", "0 edit(s)")


def test_two_cycles_with_one_number_are_not_accepted():
    assert _says(_decide(cycles=((1, "APPLIED"), (1, "NOTHING_TO_PROPOSE"))), "share one number")


def test_declined_removals_with_no_declined_cycle_are_not_accepted():
    assert _says(_decide(declined=("ghost-x",)), "declined")


def test_the_cycle_lists_warden_really_writes_are_still_accepted():
    # a loop that applied one change, then converged
    assert _decide(cycles=((1, "APPLIED"), (2, "NOTHING_TO_PROPOSE"))).decision == "ACCEPT"
    # a loop that proposed nothing, then a finishing change (listed, but in no cycle)
    assert _decide(cycles=((1, "NOTHING_TO_PROPOSE"),)).decision == "ACCEPT"
    # a declined removal beside an applied change is normal, not a contradiction
    assert _decide(cycles=((1, "DECLINED"), (2, "APPLIED"), (3, "NOTHING_TO_PROPOSE")), declined=("ghost-x",)).decision == "ACCEPT"
    # nothing listed, nothing applied
    assert _decide(cycles=((1, "NOTHING_TO_PROPOSE"),), changed=()).decision == "ACCEPT"


def test_harm_still_rejects_when_the_cycles_also_contradict():
    v = _decide(cycles=(), suite_after=SuiteRun(ran=True, passed=9, failed=1))
    assert v.decision == "REJECT"


@pytest.mark.parametrize("cycles", [None, "APPLIED", [1], [(1,)], [("1", "APPLIED")], [(True, "APPLIED")], [(1, 2)]])
def test_unreadable_cycles_are_insufficient_not_an_error(cycles):
    assert _decide(cycles=cycles).decision == "INSUFFICIENT"


def test_unreadable_declined_is_insufficient_not_an_error():
    assert _decide(declined="ghost-x").decision == "INSUFFICIENT"
    assert _decide(declined=(1,)).decision == "INSUFFICIENT"
