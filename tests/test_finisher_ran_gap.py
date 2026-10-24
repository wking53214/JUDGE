"""CNS's Evidence has a ``finisher_ran`` field; the Judge does not read it yet. The comments and the README say so, truthfully.

Adopting the field is deferred by the owner. This file holds the three facts the README and the comments in ``judge/seat.py``
state about it, so none of them can go stale unnoticed: the field exists in the pinned CNS, the Judge's verdict ignores it
(a known gap), and the comments no longer say it is missing.
"""

import dataclasses
from pathlib import Path

from cns.seat import Evidence
from test_strict_evidence import _d

ROOT = Path(__file__).resolve().parent.parent
SEAT = (ROOT / "judge" / "seat.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_pinned_cns_evidence_has_a_finisher_ran_field():
    fields = {f.name: f for f in dataclasses.fields(Evidence)}
    assert "finisher_ran" in fields and fields["finisher_ran"].default is None


def test_known_gap_the_verdict_does_not_depend_on_finisher_ran():
    """If this fails, the Judge now reads the field: update the README (KNOWN DEFECTS 1) and the comments in judge/seat.py."""
    base = dict(cycles=((1, "NOTHING_TO_PROPOSE"),), changed=(("README.md", "write"),))
    seen = {_d(**base, finisher_ran=value).decision for value in (None, True, False)}
    assert seen == {"ACCEPT"}


def test_the_comments_in_seat_py_do_not_say_the_field_is_missing():
    flat = " ".join(SEAT.split())
    assert "CNS 2.0.0 gives the Evidence shape a `finisher_ran` field" in flat
    assert "which is a change to CNS and the owner's call" not in flat


def test_the_readme_states_the_gap_as_open():
    flat = " ".join(README.split())
    assert "`finisher_ran` field (default `None`). Judge does not read it, and adopting it is deferred." in flat
