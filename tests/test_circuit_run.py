"""The whole-circuit run of 2026-11-28 (README ROAD TO 1.0.0, must-have 3), held to what was recorded.

`tests/fixtures/circuit_run/` holds the three Warden run records of that run: the five circuit repositories at the
commits the README names, live Ghost (with gitleaks), SWIZZLE and ASSAY, on a scratch project, one claimed change each.
These tests check that the records show what the README says (ACCEPT, REJECT and INSUFFICIENT once each, at the pins in
`pyproject.toml`), and that the Judge in this checkout, given the same evidence again, still says the same thing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from judge import Judge
from judge.cli import evidence_from_data

HERE = Path(__file__).resolve().parent
RUN = HERE / "fixtures" / "circuit_run"
ROOT = HERE.parent

#: Warden's decision for each case, the Judge's verdict inside it, and whether Warden put the tree back.
EXPECTED = {
    "accept": ("ACCEPT", "ACCEPT", False),
    "reject": ("JUDGE_REJECTED", "REJECT", True),
    "hold": ("ACCEPT_UNVERIFIED", "INSUFFICIENT", True),
}


def _load(name: str) -> dict[str, Any]:
    data = json.loads((RUN / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _pin(name: str) -> str:
    """The commit or tag after the `@` of the pinned dependency `name` in `pyproject.toml`."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    found = re.search(rf'"{name} @ git\+https://github\.com/wking53214/\w+\.git@([^"]+)"', text)
    assert found, f"no {name} pin in pyproject.toml"
    return found.group(1)


def test_the_run_has_exactly_the_three_cases() -> None:
    assert sorted(p.stem for p in RUN.glob("*.json")) == sorted(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_record_shows_the_verdict_the_readme_names(name: str) -> None:
    record = _load(name)["record"]
    warden_decision, judge_decision, put_back = EXPECTED[name]
    assert record["decision"] == warden_decision
    assert record["verdict"]["decision"] == judge_decision
    assert record["put_back"] is put_back
    assert record["converged"] is True
    assert record["unmeasured"] == []
    assert record["ghost_scan"]["status"] == "ok"


def test_the_three_cases_give_each_verdict_once() -> None:
    assert sorted(_load(n)["record"]["verdict"]["decision"] for n in EXPECTED) == ["ACCEPT", "INSUFFICIENT", "REJECT"]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_record_ran_the_live_circuit_at_the_pins(name: str) -> None:
    versions = _load(name)["record"]["versions"]
    assert versions["warden"]["commit"] == _pin("warden")
    assert versions["warden"]["dirty"] is False
    judge = versions["seats"]["judge"]
    assert judge["spec"] == "judge.seat:Judge"
    assert judge["isolated"] is True
    assert judge["dirty"] is False
    for seat in ("ghost_tools", "swizzle", "assay"):
        assert re.fullmatch(r"[0-9a-f]{40}", versions[seat]["commit"]), seat
        assert versions[seat]["dirty"] is False, seat
    assert {j["version"] for j in versions["joins"]} >= {judge["version"]}


def test_the_record_names_the_cns_release_in_the_pin() -> None:
    # Warden's record carries no CNS version, so the run's CNS is the one written beside the pin; this keeps the README's
    # claim that the run used the pinned CNS tied to the pin text.
    assert _pin("cns") == "v4.2.0"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_the_same_evidence_judged_again_gets_the_same_verdict(name: str, tmp_path: Path) -> None:
    case = _load(name)
    for path, text in case["files"].items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    evidence = {**case["record"]["evidence"], "target": str(tmp_path)}
    verdict = Judge().decide(evidence_from_data(evidence))
    recorded = case["record"]["verdict"]
    assert verdict.decision == recorded["decision"]
    assert list(verdict.reasons) == recorded["reasons"]
