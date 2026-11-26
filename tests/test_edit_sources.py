"""`Evidence.edit_sources`: one label per listed edit, a cycle number or "finish" (CNS 4.2.0, filled by Warden).

KNOWN DEFECTS 1 of 0.8.0: with one applied cycle, two listed edits can be that cycle's two, or one of its and one of
the Finisher's, and nothing in the evidence said which, so a padded list was ACCEPTed. The labels say which. These tests
set the labels on hand-made evidence directly, so they run under any CNS; the rule for missing labels depends on whether
the installed CNS declares the field, and is tested both ways by setting `seat.CNS_DECLARES_EDIT_SOURCES`.

What the labels cannot do: evidence written by someone who controls every field can carry labels that agree with a
padded list. The labels make padding need a matching lie in two more places (`edit_sources` and `finisher_ran`); they
do not prove the evidence is true.
"""

import pytest
from conftest import PROJECT_DIR
from test_strict_evidence import _ev, _suite

from judge import seat
from judge.cns_connector import JudgeGate
from judge.seat import Judge

APPLIED_ONCE = ((1, "APPLIED"), (2, "NOTHING_TO_PROPOSE"))
TWO_EDITS = (("NOTE.md", "write"), ("README.md", "write"))
NO_LABELS = "does not say where each listed edit came from"


def _decide(sources=None, **kw):
    ev = _ev(**{"cycles": APPLIED_ONCE, "changed": TWO_EDITS, "scope": "code", **kw})
    # None means "no labels": the shared helper labels evidence under a CNS that declares the field, so undo that here.
    object.__setattr__(ev, "edit_sources", sources)
    return Judge().decide(ev)


def _reasons(v) -> str:
    return " ".join(v.reasons)


# what Warden writes is accepted

@pytest.mark.parametrize("kw,sources", [
    ({"changed": (("NOTE.md", "write"),)}, (1,)),
    ({}, (1, 1)),                                                      # one cycle edited two files
    ({"finisher_ran": True}, (1, "finish")),                           # one cycle's edit, then the Finisher's
    ({"finisher_ran": True}, (1, " Finish ")),                         # text is trimmed and lower-cased, as everywhere
    ({"cycles": ((1, "NOTHING_TO_PROPOSE"),), "changed": (("README.md", "write"),), "finisher_ran": True}, ("finish",)),
    ({"cycles": ((1, "APPLIED"), (2, "APPLIED"), (3, "NOTHING_TO_PROPOSE")),
      "changed": (("NOTE.md", "write"), ("NOTE.md", "write"))}, (1, 2)),  # one file in two cycles is normal
    ({"cycles": ((1, "NOTHING_TO_PROPOSE"),), "changed": ()}, ()),
])
def test_labels_that_match_the_edits_are_accepted(kw, sources):
    assert _decide(sources, **kw).decision == "ACCEPT"


# labels that contradict the edits are held

@pytest.mark.parametrize("kw,sources,said", [
    ({"changed": TWO_EDITS + (("pkg/x.md", "write"),)}, (1, 1), "names 2 source(s) for 3 listed edit(s)"),
    ({}, (1, 2), "cycle(s) 2 that applied nothing"),
    ({"cycles": ((1, "APPLIED"), (2, "APPLIED"), (3, "NOTHING_TO_PROPOSE"))}, (1, 1),
     "cycle(s) 2 applied a change but no listed edit is labelled with it"),
    ({"finisher_ran": False}, (1, "finish"), "does not say a finisher ran"),
    ({"finisher_ran": None}, (1, "finish"), "does not say a finisher ran"),
    ({"finisher_ran": True, "cycles": ((1, "APPLIED"),)}, (1, "finish"), "does not say a finisher ran"),
    ({"finisher_ran": True}, ("finish", 1), "out of order"),
    ({"cycles": ((1, "APPLIED"), (2, "APPLIED"), (3, "NOTHING_TO_PROPOSE"))}, (2, 1), "out of order"),
    ({"changed": (("NOTE.md", "write"), ("./NOTE.md", "write"))}, (1, 1), "the same file is listed twice"),
])
def test_labels_that_contradict_the_edits_are_held(kw, sources, said):
    v = _decide(sources, **kw)
    assert v.decision == "INSUFFICIENT"
    assert said in _reasons(v), v.reasons


@pytest.mark.parametrize("label", [True, 1.5, "cycle 1", "", None, ("1",)])
def test_a_label_that_is_neither_a_number_nor_finish_is_held(label):
    v = _decide((1, label), finisher_ran=True)
    assert v.decision == "INSUFFICIENT"
    assert "neither a cycle number nor" in _reasons(v)


@pytest.mark.parametrize("sources", ["1", {"a": 1}, 7])
def test_labels_that_are_not_a_list_are_unreadable(sources):
    v = _decide(sources)
    assert v.decision == "INSUFFICIENT" and "could not be read" in _reasons(v)


def test_harm_outranks_contradicting_labels():
    v = _decide((1, 2), suite_after=_suite(failed=1))
    assert v.decision == "REJECT" and "applied nothing" not in _reasons(v)


# missing labels: held when the installed CNS declares the field (owner's decision of 2026-11-26)

def test_missing_labels_after_an_applied_cycle_are_held_under_a_cns_that_declares_the_field(monkeypatch):
    """0.8.0 ACCEPTed this padded-looking run whatever finisher_ran said (KNOWN DEFECTS 1)."""
    monkeypatch.setattr(seat, "CNS_DECLARES_EDIT_SOURCES", True)
    for finisher_ran in (None, True, False):
        v = _decide(finisher_ran=finisher_ran)
        assert v.decision == "INSUFFICIENT" and NO_LABELS in _reasons(v), finisher_ran


def test_missing_labels_are_not_held_under_a_cns_that_cannot_carry_them(monkeypatch):
    monkeypatch.setattr(seat, "CNS_DECLARES_EDIT_SOURCES", False)
    assert _decide(finisher_ran=True).decision == "ACCEPT"


@pytest.mark.parametrize("kw", [
    {"cycles": ((1, "NOTHING_TO_PROPOSE"),), "changed": (("README.md", "write"),), "finisher_ran": True},  # left open
    {"cycles": ((1, "NOTHING_TO_PROPOSE"),), "changed": ()},
])
def test_missing_labels_without_an_applied_cycle_are_not_held(monkeypatch, kw):
    monkeypatch.setattr(seat, "CNS_DECLARES_EDIT_SOURCES", True)
    assert _decide(**kw).decision == "ACCEPT"


def test_the_flag_follows_the_installed_cns():
    from cns.seat import Evidence

    assert seat.CNS_DECLARES_EDIT_SOURCES is ("edit_sources" in Evidence.__dataclass_fields__)


# the CNS connector binds the labels

def test_the_digest_changes_with_the_labels():
    def check(sources):
        ev = _ev(cycles=APPLIED_ONCE, changed=TWO_EDITS, finisher_ran=True, target=PROJECT_DIR)
        object.__setattr__(ev, "edit_sources", sources)
        return JudgeGate().check(ev)

    one, other = check((1, 1)), check((1, "finish"))
    assert one.subject_digest != other.subject_digest
