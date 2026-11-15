"""The Judge reads CNS's ``Evidence.finisher_ran``. This file holds what that does, and what it still cannot do.

When the field is exactly False and no cycle applied anything, a listed edit has no source, so the Judge holds. When the field
is True or None (older evidence), a converged loop may have had a finishing change, so nothing new is questioned. A run where
some cycle did apply an edit can still carry padded edits, whatever the field says: that limit is held here too.
"""

import dataclasses
from pathlib import Path

from cns.seat import Evidence
from test_strict_evidence import _d

ROOT = Path(__file__).resolve().parent.parent
SEAT = (ROOT / "judge" / "seat.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

CONVERGED_EMPTY = dict(cycles=((1, "NOTHING_TO_PROPOSE"),), changed=(("README.md", "write"),))
CONVERGED_APPLIED = dict(cycles=((1, "APPLIED"), (2, "NOTHING_TO_PROPOSE")), changed=(("README.md", "write"),))


def test_the_pinned_cns_evidence_has_a_finisher_ran_field():
    fields = {f.name: f for f in dataclasses.fields(Evidence)}
    assert "finisher_ran" in fields and fields["finisher_ran"].default is None


def test_no_finisher_and_an_edit_that_no_cycle_applied_is_held():
    verdict = _d(**CONVERGED_EMPTY, finisher_ran=False)
    assert verdict.decision == "INSUFFICIENT"
    assert "no finisher ran" in " ".join(verdict.reasons)


def test_a_finisher_that_ran_or_an_unknown_answer_keeps_the_old_reading():
    assert {_d(**CONVERGED_EMPTY, finisher_ran=value).decision for value in (None, True)} == {"ACCEPT"}


def test_a_run_with_no_listed_edit_is_not_held_for_finisher_ran_false():
    assert _d(cycles=((1, "NOTHING_TO_PROPOSE"),), changed=(), finisher_ran=False).decision == "ACCEPT"


def test_known_limit_a_padded_edit_list_on_a_run_that_applied_something_is_not_caught():
    """If this fails, the Judge now catches padded lists: update KNOWN DEFECTS 1 in the README and the comments in judge/seat.py."""
    assert {_d(**CONVERGED_APPLIED, finisher_ran=value).decision for value in (None, True, False)} == {"ACCEPT"}


def test_a_finisher_ran_that_is_not_true_false_or_empty_is_unreadable():
    for bad in ("no", 0, 1, [], "False"):
        assert _d(**CONVERGED_EMPTY, finisher_ran=bad).decision == "INSUFFICIENT"


def test_the_comments_in_seat_py_say_the_field_is_read():
    flat = " ".join(SEAT.split())
    assert "reads the `finisher_ran` field of the Evidence" in flat
    assert "The Judge does not read that field yet" not in flat


def test_the_readme_states_the_field_is_read_and_the_remaining_limit():
    flat = " ".join(README.split())
    assert "Judge reads `finisher_ran`" in flat
    assert "Judge does not read it, and adopting it is deferred" not in flat


def test_the_comments_in_seat_py_do_not_say_the_field_is_missing():
    """Kept under its old name: the README ledger entry for 0.4.11 cites it."""
    flat = " ".join(SEAT.split())
    assert "which is a change to CNS and the owner's call" not in flat
