"""The owner's two rulings of 2026-10-28, each loosening one REJECT to INSUFFICIENT.

INSUFFICIENT means Warden puts the tree back and holds the result by digest for a named human (`warden keep`); the
machine does not approve it. Nothing else about the decision changed: harm is found first, unknown is not approved,
the verdict is deterministic and the Judge never raises. The two rulings are: a changed test or test setting is held,
not rejected (rule 1), and a new Ghost finding whose own severity is minor or informational is held, not rejected
(rule 2). Both are owner decisions, not findings; this file holds them to the code.
"""

import dataclasses
import json
from pathlib import Path

import pytest
from cns.seat import Evidence
from cns.suite import SuiteRun
from test_strict_evidence import MISSING, _d, _ev

from judge import Judge, seat
from judge.cli import evidence_from_data, main

HOLD = "the machine does not approve that; a named human keeps or drops the held result"


# ---- rule 1: a changed test or test setting is held, not rejected --------------------------------------------

def test_a_changed_test_file_is_held_for_a_named_human_with_the_sentence():
    v = _d(changed=(("tests/test_a.py", "write"),))
    assert v.decision == "INSUFFICIENT"
    assert v.reasons[0] == f"tests or test settings were changed (tests/test_a.py); {HOLD}"


def test_a_file_warden_lists_as_judging_is_held_under_either_grant():
    for scope in ("code", "documentation", "all"):
        v = _d(scope=scope, changed=(("README.md", "write"),), judging_files_touched=("pyproject.toml",))
        assert v.decision == "INSUFFICIENT" and any(f"(pyproject.toml); {HOLD}" in r for r in v.reasons), scope


def test_a_changed_ghost_file_is_still_harm():
    for path in (".ghost_baseline.json", "sub/.ghost_config.json"):
        v = _d(changed=((path, "write"),))
        assert v.decision == "REJECT" and any(".ghost_" in r for r in v.reasons), path
        assert not any(HOLD in r for r in v.reasons), path


def test_an_edit_that_left_the_project_is_still_harm():
    v = _d(changed=(("../tests/test_a.py", "write"),))
    assert v.decision == "REJECT" and any("outside the project" in r for r in v.reasons)


def test_harm_beside_a_changed_test_file_still_rejects_and_says_nothing_about_a_hold():
    v = _d(changed=(("tests/test_a.py", "write"),), suite_after=SuiteRun(ran=True, passed=9, failed=1, exit_code=1))
    assert v.decision == "REJECT" and any("not green" in r for r in v.reasons)
    assert not any(HOLD in r for r in v.reasons)


def test_a_changed_test_file_is_never_an_accept_however_complete_the_rest():
    v = _d(changed=(("tests/test_a.py", "write"),), scope="all")
    assert v.decision == "INSUFFICIENT" and len(v.reasons) == 1
    assert not any("no tests or test settings were changed" in r for r in v.reasons)


def test_the_hold_keeps_company_with_the_other_unknowns():
    v = _d(changed=(("tests/test_a.py", "write"),), attacks=None)
    assert v.decision == "INSUFFICIENT"
    assert any(HOLD in r for r in v.reasons) and any("attacks" in r for r in v.reasons)


def test_the_command_line_holds_a_changed_test_file_with_exit_1(tmp_path, capsys):
    data = {
        "target": "/t", "scope": "code", "cycles": [[1, "APPLIED"]], "changed": [["tests/test_a.py", "write"]],
        "judging_files_touched": ["tests/test_a.py"], "suite_before": {"ran": True, "passed": 10, "exit_code": 0},
        "suite_after": {"ran": True, "passed": 10, "exit_code": 0}, "ghost_before": ["g"], "ghost_after": ["g"],
        "declined": [], "swizzle_proofs": True, "attacks": [{"scenario": "a", "severity": "high", "status": "held"}],
        "unmeasured": [], "assay": {"key_proven": True, "failure_modes": 5, "caught": 3, "floor": 0},
        "ghost_baseline_before": {"path": None, "suppressed": 0}, "ghost_baseline_after": {"path": None, "suppressed": 0},
    }
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["decide", str(path)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "INSUFFICIENT" and out["reasons"] == [f"tests or test settings were changed (tests/test_a.py); {HOLD}"]


# ---- rule 2: a new Ghost finding of minor or informational severity is held, not rejected -------------------

GHOST_HOLD = "new finding(s) of minor or informational severity"
GHOST_HARM = "finding(s) it did not report at the start"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CNS_DECLARES_THE_FIELD = "ghost_severity" in {f.name for f in dataclasses.fields(Evidence)}


def _ghost(after, severity=MISSING, **kw):
    """Decide hand-made evidence whose Ghost list grew to ``after``, with ``severity`` as the ghost_severity mapping."""
    ev = _ev(ghost_before=("g",), ghost_after=after, **kw)
    if severity is not MISSING:
        object.__setattr__(ev, "ghost_severity", severity)  # CNS 2.1.0 declares the field; under 2.0.0 the Judge still reads it
    return Judge().decide(ev)


@pytest.mark.parametrize("word", ["minor", "informational"])
def test_a_new_minor_or_informational_finding_is_held_with_the_sentence(word):
    v = _ghost(("g", "n"), {"n": word})
    assert v.decision == "INSUFFICIENT"
    assert v.reasons == (f"1 {GHOST_HOLD} (n) are held for a named human",)


@pytest.mark.parametrize("word", ["major", "critical"])
def test_a_new_major_or_critical_finding_is_harm_as_before(word):
    v = _ghost(("g", "n"), {"n": word})
    assert v.decision == "REJECT" and v.reasons == (f"Ghost reports 1 {GHOST_HARM} (n)",)


def test_no_severity_mapping_is_harm_as_before():
    assert _ghost(("g", "n")).decision == "REJECT"
    assert _ghost(("g", "n"), None).decision == "REJECT"


def test_an_id_the_mapping_does_not_name_is_harm():
    v = _ghost(("g", "n"), {"g": "minor", "other": "informational"})
    assert v.decision == "REJECT" and any(GHOST_HARM in r for r in v.reasons)


@pytest.mark.parametrize("word", ["medium", "low", "high", "severe", "info", "", " ", "banana", None, 5, True, ["minor"]])
def test_a_word_that_is_not_one_of_ghosts_two_held_words_is_harm(word):
    """Warden's remapped scale (critical, high, medium, low) must not reach here; if it does, the id has no readable severity."""
    v = _ghost(("g", "n"), {"n": word})
    assert v.decision == "REJECT" and any(GHOST_HARM in r for r in v.reasons), word
    assert not any(GHOST_HOLD in r for r in v.reasons)


@pytest.mark.parametrize("word", [" Minor ", "MINOR", "Informational", "\tinformational\n"])
def test_the_word_is_compared_stripped_and_lower_cased(word):
    assert _ghost(("g", "n"), {"n": word}).decision == "INSUFFICIENT"


@pytest.mark.parametrize("bad", ["minor", 5, ["n", "minor"], ("n",), {("n",): "minor"}])
def test_a_severity_field_that_is_not_a_mapping_is_harm_never_an_error(bad):
    v = _ghost(("g", "n"), bad)
    assert v.decision == "REJECT" and any(GHOST_HARM in r for r in v.reasons), bad


def test_one_minor_beside_one_major_is_harm_and_says_nothing_about_a_hold():
    v = _ghost(("g", "m", "n"), {"m": "minor", "n": "major"})
    assert v.decision == "REJECT"
    assert v.reasons == (f"Ghost reports 1 {GHOST_HARM} (n)",)


def test_a_repeated_minor_finding_counts_one_by_one_and_is_held_twice():
    v = _ghost(("g", "n", "n"), {"n": "minor"})
    assert v.decision == "INSUFFICIENT" and v.reasons == (f"2 {GHOST_HOLD} (n, n) are held for a named human",)


def test_the_words_of_findings_that_are_not_new_do_not_matter():
    assert _ghost(("g",), {"g": "critical"}).decision == "ACCEPT"
    assert _ghost((), {"g": "banana"}).decision == "ACCEPT"


def test_harm_beside_a_held_finding_still_rejects():
    v = _ghost(("g", "n"), {"n": "minor"}, suite_after=SuiteRun(ran=True, passed=9, failed=1, exit_code=1))
    assert v.decision == "REJECT" and not any(GHOST_HOLD in r for r in v.reasons)


def test_a_held_finding_keeps_company_with_the_other_unknowns_and_is_never_an_accept():
    v = _ghost(("g", "n"), {"n": "informational"}, attacks=None, scope="all")
    assert v.decision == "INSUFFICIENT"
    assert any(GHOST_HOLD in r for r in v.reasons) and any("attacks" in r for r in v.reasons)


def test_both_rulings_together_are_held_with_both_sentences_in_order():
    v = _ghost(("g", "n"), {"n": "minor"}, changed=(("tests/test_a.py", "write"),))
    assert v.decision == "INSUFFICIENT"
    assert v.reasons == (f"tests or test settings were changed (tests/test_a.py); {HOLD}",
                         f"1 {GHOST_HOLD} (n) are held for a named human")


def test_the_two_severity_scales_are_kept_apart():
    assert seat._HARM_SEVERITIES == {"high", "medium", "critical", "severe"}
    assert seat._HELD_GHOST_SEVERITIES == frozenset({"minor", "informational"})
    assert not (seat._HELD_GHOST_SEVERITIES & seat._HARM_SEVERITIES)
    # SWIZZLE's "medium" is still harm, and Ghost's "medium" (Warden's word for minor) is not a hold
    assert _d(attacks=({"scenario": "x", "severity": "medium", "status": "violated"},)).decision == "REJECT"
    assert _ghost(("g", "n"), {"n": "medium"}).decision == "REJECT"


def test_the_decision_is_deterministic():
    first = [_ghost(("g", "n"), {"n": "minor"}, changed=(("tests/test_a.py", "write"),)) for _ in range(3)]
    assert all(v == first[0] for v in first)


def test_the_falsifier_02_record_replayed_is_held_with_both_sentences():
    """The falsifier's two-rule run on ghost_tools e5eccc0, reconstructed from its record (see the fixture's notes)."""
    data = json.loads((FIXTURES / "held" / "falsifier_02_e5eccc0.json").read_text(encoding="utf-8"))
    severity = data.pop("ghost_severity")
    if CNS_DECLARES_THE_FIELD:
        data["ghost_severity"] = severity
    ev = evidence_from_data(data)
    if not CNS_DECLARES_THE_FIELD:
        object.__setattr__(ev, "ghost_severity", severity)
    assert len(ev.ghost_before) == 134 and len(ev.ghost_after) == 135
    v = Judge().decide(ev)
    assert v.decision == "INSUFFICIENT"
    assert v.reasons == (
        f"tests or test settings were changed (Tests/test_finding_identity.py); {HOLD}",
        f"1 {GHOST_HOLD} (ghost-3a1c99957a4b) are held for a named human",
        "these checks never ran: ghost_partial",
        "some tests did not run, so a code change cannot be shown safe",
    )


def test_the_falsifier_02_record_without_ghosts_word_is_rejected_as_before():
    data = json.loads((FIXTURES / "held" / "falsifier_02_e5eccc0.json").read_text(encoding="utf-8"))
    data.pop("ghost_severity")
    v = Judge().decide(evidence_from_data(data))
    assert v.decision == "REJECT" and v.reasons == (f"Ghost reports 1 {GHOST_HARM} (ghost-3a1c99957a4b)",)


def test_the_command_line_reads_ghost_severity_only_when_the_installed_cns_declares_it(tmp_path, capsys):
    """Under the pinned CNS (2.0.0) the field is unknown to `judge decide`, so the record is turned away; either way exit 1."""
    data = json.loads((FIXTURES / "held" / "falsifier_02_e5eccc0.json").read_text(encoding="utf-8"))
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["decide", str(path)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "INSUFFICIENT"
    if CNS_DECLARES_THE_FIELD:
        assert any(GHOST_HOLD in r for r in out["reasons"])
    else:
        assert out["reasons"] == ["the decision input could not be judged (unknown field(s): ghost_severity), so nothing can be approved"]
