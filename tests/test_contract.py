"""The Judge declares which version of Warden's shapes it was written for."""

from conftest import need_warden

need_warden()

import warden  # noqa: E402
from warden.cli import _load_seat  # noqa: E402

from judge.seat import Judge  # noqa: E402


def test_the_judge_declares_contract_1():
    assert Judge.requires_contract == "1"
    assert Judge().requires_contract == "1"


def test_the_declaration_matches_the_warden_it_runs_with():
    assert Judge.requires_contract == warden.CONTRACT


def test_warden_loads_the_judge_with_no_contract_warning():
    warnings: list[str] = []
    seat = _load_seat("judge.seat:Judge", warnings)
    assert isinstance(seat, Judge)
    assert warnings == []
