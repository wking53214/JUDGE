"""Warden's list of failing tests (`failed_ids`) is read, and must agree with the counts (0.20.0, owner's OK 2026-11-28).

Warden 1.0.0's pytest runner adds `failed_ids` to each suite run: the ids of the tests that failed or errored, the first
ten. Up to 0.19.0 `judge decide` refused any record that carried it, so no real run record could be checked again by hand
(found by the whole-circuit run of 2026-11-28). The Judge now reads it and holds a run whose list names more failing
tests than its counts hold, which includes a list naming a failure in a suite whose counts say none failed. It is never
used to approve anything.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from judge import Judge
from judge.cli import evidence_from_data, main
from judge.cns_connector import JudgeGate
from judge.seat import ROW_ATTRIBUTES

RUN = Path(__file__).resolve().parent / "fixtures" / "circuit_run"
CONTRADICTS = "list of failing tests does not agree with its counts"


def _accepted(tmp_path: Path) -> dict[str, Any]:
    """The evidence of the recorded ACCEPT run, pointed at a folder that holds its one edited file."""
    case = json.loads((RUN / "accept.json").read_text(encoding="utf-8"))
    for path, text in case["files"].items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text, encoding="utf-8")
    return {**copy.deepcopy(case["record"]["evidence"]), "target": str(tmp_path)}


def _decide(data: dict[str, Any]):
    return Judge().decide(evidence_from_data(data))


def test_the_real_record_carries_the_list_and_is_accepted(tmp_path: Path) -> None:
    data = _accepted(tmp_path)
    assert data["suite_before"]["failed_ids"] == [] and data["suite_after"]["failed_ids"] == []
    assert _decide(data).decision == "ACCEPT"


def test_the_command_line_reads_the_real_record(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "evidence.json"
    source.write_text(json.dumps(_accepted(tmp_path)), encoding="utf-8")
    assert main(["decide", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "ACCEPT"


@pytest.mark.parametrize("end, label", [("suite_before", "starting"), ("suite_after", "final")])
def test_a_failure_named_in_a_suite_that_counts_none_is_held(tmp_path: Path, end: str, label: str) -> None:
    data = _accepted(tmp_path)
    data[end]["failed_ids"] = ["tests/test_calc.py::test_add"]
    verdict = _decide(data)
    assert verdict.decision == "INSUFFICIENT"
    said = [r for r in verdict.reasons if CONTRADICTS in r]
    assert len(said) == 1 and said[0].startswith(f"the {label} suite's")
    assert "tests/test_calc.py::test_add" in said[0] and "the evidence contradicts itself" in said[0]


def test_more_failures_named_than_counted_is_held_beside_the_harm(tmp_path: Path) -> None:
    # A red final suite is harm and outranks the hold; the contradiction is still found, so the run is never ACCEPT.
    data = _accepted(tmp_path)
    data["suite_after"].update(failed=1, passed=2, exit_code=1, failed_ids=["a", "b"])
    data["suite_after"]["test_outcomes"] = [["a", "failed"], ["t2", "passed"], ["t3", "passed"]]
    assert _decide(data).decision == "REJECT"


def test_fewer_failures_named_than_counted_is_allowed() -> None:
    # Warden keeps only the first ten ids, and none when its plugin's file was garbled; a short list is not a contradiction.
    from judge.seat import _Suite

    run = evidence_from_data({**_minimal(), "suite_after": {**_GREEN, "failed": 12, "failed_ids": ["x"] * 10}}).suite_after
    assert _Suite(run, "suite_after").failed_ids_mismatch == ""


@pytest.mark.parametrize("value", ["tests/test_calc.py::test_add", [1], [["a"]], {"a": 1}, [None]])
def test_a_list_that_is_not_test_ids_is_unreadable(tmp_path: Path, value: object) -> None:
    data = _accepted(tmp_path)
    data["suite_after"]["failed_ids"] = value
    verdict = _decide(data)
    assert verdict.decision == "INSUFFICIENT"
    assert any("failed_ids is not a list of test ids" in r for r in verdict.reasons)


def test_the_gate_digest_covers_the_list(tmp_path: Path) -> None:
    assert "failed_ids" in ROW_ATTRIBUTES
    clean, named = _accepted(tmp_path), _accepted(tmp_path)
    named["suite_after"]["failed_ids"] = ["tests/test_calc.py::test_add"]
    first, second = JudgeGate().check(evidence_from_data(clean)), JudgeGate().check(evidence_from_data(named))
    assert first.outcome.name == "PASS" and second.outcome.name == "RETRY"
    assert first.subject_digest and first.subject_digest != second.subject_digest


_GREEN = {"ran": True, "passed": 3, "failed": 0, "errors": 0, "skipped": 0, "reason": "", "xfailed": 0, "xpassed": 0,
          "exit_code": 0}


def _minimal() -> dict[str, Any]:
    return json.loads((RUN / "accept.json").read_text(encoding="utf-8"))["record"]["evidence"]
