"""The owner's two rulings of 2026-10-28, each loosening one REJECT to INSUFFICIENT.

INSUFFICIENT means Warden puts the tree back and holds the result by digest for a named human (`warden keep`); the
machine does not approve it. Nothing else about the decision changed: harm is found first, unknown is not approved,
the verdict is deterministic and the Judge never raises. The two rulings are: a changed test or test setting is held,
not rejected (rule 1), and a new Ghost finding whose own severity is minor or informational is held, not rejected
(rule 2). Both are owner decisions, not findings; this file holds them to the code.
"""

import json

from cns.suite import SuiteRun
from test_strict_evidence import _d

from judge.cli import main

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
