"""Owner's decision of 2026-11-26: when edits are listed and the project folder cannot be checked, the run is held.

The Judge follows symbolic links in edited paths by looking at the folder named in `target` on the machine it runs on.
Up to 0.7.0, when that folder was not there, the check was skipped and the run could still be ACCEPTed with a note
(KNOWN DEFECTS 3 in 0.7.0). From 0.8.0 a check that could not run is unknown, so the run is INSUFFICIENT.
"""

import pytest
from conftest import PROJECT_DIR, label_edits
from test_strict_evidence import _d, _suite

from judge.cli import evidence_from_data
from judge.seat import Judge

HOLD = "the check for symbolic links did not run"


@pytest.mark.parametrize("target", ["/no/such/project", "", "relative/not-here", "/dev/null", "bad\0name"])
def test_edits_with_a_folder_that_cannot_be_checked_are_held(target):
    v = _d(target=target)
    assert v.decision == "INSUFFICIENT", target
    assert any(HOLD in r and "nothing is approved" in r for r in v.reasons)


def test_a_real_folder_is_checked_and_accepted_without_the_sentence():
    v = _d(target=PROJECT_DIR)
    assert v.decision == "ACCEPT"
    assert not any("symbolic links" in r for r in v.reasons)


def test_a_run_with_no_edits_needs_no_folder():
    assert _d(target="/no/such/project", changed=(), cycles=((1, "NOTHING_TO_PROPOSE"),)).decision == "ACCEPT"


def test_harm_beside_a_missing_folder_still_rejects_and_says_nothing_about_the_check():
    v = _d(target="/no/such/project", suite_after=_suite(failed=1))
    assert v.decision == "REJECT"
    assert not any(HOLD in r for r in v.reasons)


def test_the_hold_keeps_company_with_other_unknowns():
    v = _d(target="/no/such/project", attacks=None)
    assert v.decision == "INSUFFICIENT"
    assert any(HOLD in r for r in v.reasons) and any("attacks" in r for r in v.reasons)


def test_the_command_line_and_the_python_interface_agree():
    data = {
        "target": "/no/such/project", "scope": "code", "cycles": [[1, "APPLIED"]], "changed": [["pkg/a.py", "write"]],
        "judging_files_touched": [], "suite_before": {"ran": True, "passed": 10, "exit_code": 0},
        "suite_after": {"ran": True, "passed": 10, "exit_code": 0}, "ghost_before": ["g"], "ghost_after": ["g"],
        "declined": [], "swizzle_proofs": True, "attacks": [{"scenario": "a", "severity": "high", "status": "held"}],
        "unmeasured": [], "assay": {"key_proven": True, "failure_modes": 5, "caught": 3, "floor": 0},
        "ghost_baseline_before": {"path": None, "suppressed": 0}, "ghost_baseline_after": {"path": None, "suppressed": 0},
    }
    from_json = Judge().decide(evidence_from_data(label_edits(data)))
    by_hand = _d(target="/no/such/project")
    assert from_json.decision == by_hand.decision == "INSUFFICIENT"
    assert from_json.reasons == by_hand.reasons
