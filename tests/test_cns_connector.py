"""The Judge as a CNS gate."""

import cns.gate as gate
import pytest
from test_judge import _evidence
from cns.seat import Verdict
from cns.suite import SuiteRun

from judge import Judge
from judge.cns_connector import DEFAULT_SUBJECT, JudgeGate, cns_chain

RED = SuiteRun(ran=True, passed=9, failed=1)


class _FixedJudge:
    """A stand-in that answers whatever it is told, to reach answers the real Judge never gives."""

    def __init__(self, decision, reasons=("because",)):
        self._verdict = Verdict(decision, reasons, "fixed")

    def decide(self, evidence):
        return self._verdict


def test_the_gate_satisfies_the_cns_protocol_at_the_outcome_end():
    g = JudgeGate()
    assert isinstance(g, gate.Gate)
    assert g.name == "judge.verdict" and g.position is gate.GatePosition.OMEGA


@pytest.mark.parametrize("kw,outcome", [
    ({}, gate.GateOutcome.PASS),
    ({"suite_after": None}, gate.GateOutcome.RETRY),
    ({"suite_after": RED}, gate.GateOutcome.TERMINAL_BREACH)])
def test_each_answer_maps_to_its_outcome_and_keeps_the_judges_reasons(kw, outcome):
    ev = _evidence(**kw)
    result = JudgeGate().check(ev)
    assert result.outcome is outcome
    assert result.reason == "; ".join(Judge().decide(ev).reasons)
    assert result.position is gate.GatePosition.OMEGA and result.gate == "judge.verdict"


def test_an_answer_the_connector_does_not_know_is_a_breach_never_a_pass():
    for odd in ("MAYBE", "accept", "", None, ["ACCEPT"]):
        result = JudgeGate(_FixedJudge(odd)).check(_evidence())
        assert result.outcome is gate.GateOutcome.TERMINAL_BREACH, odd
        assert "never read as permission" in result.reason


def test_an_exception_from_the_judge_is_not_turned_into_a_pass():
    class Broken:
        def decide(self, evidence):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        JudgeGate(Broken()).check(_evidence())


def test_the_verdict_is_bound_to_the_evidence_it_judged():
    ev = _evidence()
    result = JudgeGate(subject="run-42").check(ev)
    assert result.bound() and result.subject == "run-42"
    again = JudgeGate(subject="run-42").check(_evidence())
    assert again.subject_digest == result.subject_digest
    other = JudgeGate(subject="run-42").check(_evidence(suite_after=RED))
    assert other.subject_digest != result.subject_digest
    assert not result.binds("run-42", other.subject_digest)
    assert not result.binds("another-run", result.subject_digest)
    assert gate.unbound([result, other]) == ()


def test_the_default_subject_label_is_used_when_none_is_given():
    assert JudgeGate().check(_evidence()).subject == DEFAULT_SUBJECT


def test_the_digest_covers_attributes_the_judge_reads_that_are_not_declared_fields():
    """Suite flags and Ghost's baseline are read by the Judge but are not Evidence fields, so a digest over
    declared fields alone would let two different judgments share one binding."""
    plain = JudgeGate().check(_evidence())
    own_suite = SuiteRun(ran=True, passed=10, exit_code=0)  # not the shared fixture: setting a flag on that would leak
    forged = _evidence(suite_after=own_suite)
    object.__setattr__(own_suite, "forged", True)
    flagged = JudgeGate().check(forged)
    assert plain.outcome is gate.GateOutcome.PASS and flagged.outcome is gate.GateOutcome.TERMINAL_BREACH
    assert plain.subject_digest != flagged.subject_digest

    grew = _evidence(ghost_baseline_after={"path": None, "suppressed": 3})
    assert JudgeGate().check(grew).subject_digest != plain.subject_digest


def _cycle():
    d: dict = {}
    d["me"] = d
    return d


@pytest.mark.parametrize("candidate", [
    "not evidence", None, 7, ["a"], object(),
    _evidence(assay={"floor": float("nan")}),
    _evidence(assay={"floor": float("inf")}),
    _evidence(assay={"modes": {1, 2}}),
    _evidence(assay={1: "a", "1": "b"}),
    _evidence(assay=_cycle())])
def test_evidence_that_cannot_be_bound_is_a_breach_and_unbound(candidate):
    result = JudgeGate().check(candidate)
    assert result.outcome is gate.GateOutcome.TERMINAL_BREACH
    assert "cannot be bound" in result.reason
    assert not result.bound() and result.blocking()


def test_the_chain_holds_the_judge_at_the_outcome_end_only():
    chain = cns_chain()
    assert chain.alpha == () and len(chain.omega) == 1 and isinstance(chain.omega[0], JudgeGate)
    assert chain.complete() is False and chain.misplaced() == ()


def test_resolve_treats_the_judge_like_any_other_gate():
    ev = _evidence()
    refuse = type("Deny", (), {"name": "other.alpha", "position": gate.GatePosition.ALPHA,
                               "check": lambda self, c: gate.GateResult(
                                   "other.alpha", gate.GatePosition.ALPHA, gate.GateOutcome.RETRY, "later",
                                   "x", "y")})()
    assert gate.resolve([JudgeGate().check(ev)]) is gate.GateOutcome.PASS
    assert gate.resolve([JudgeGate().check(ev), refuse.check(ev)]) is gate.GateOutcome.RETRY
    assert gate.resolve([JudgeGate().check(_evidence(suite_after=RED)), refuse.check(ev)]) \
        is gate.GateOutcome.TERMINAL_BREACH

