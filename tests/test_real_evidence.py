"""Evidence captured from the real Warden loop must still be accepted, and altering what the Judge reads must not be.

`tests/fixtures/real/*.json` are the evidence Warden handed the Judge in nine real runs (a scratch project, Ghost,
SWIZZLE and ASSAY stubbed to fixed answers; the target path is neutralised). `tests/fixtures/accept.json` is a copy of
`examples/accept.json`. Every one of them is ACCEPT today. The mutations below are the hand-made evidence a fuzzing audit
used to get a false ACCEPT; none of them may be ACCEPT, and no real file may be turned away by the same rules.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from judge import Judge
from judge.cli import evidence_from_data, main

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REAL = sorted((FIXTURES / "real").glob("*.json"))
ALL = REAL + [FIXTURES / "accept.json"]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _decision(data: dict[str, Any]) -> str:
    return Judge().decide(evidence_from_data(data)).decision


def _ids(paths: list[Path]) -> list[str]:
    return [p.stem for p in paths]


def test_the_nine_real_evidence_files_are_present():
    assert len(REAL) == 9, [p.name for p in REAL]


@pytest.mark.parametrize("path", ALL, ids=_ids(ALL))
def test_real_evidence_is_accepted(path):
    data = _load(path)
    verdict = Judge().decide(evidence_from_data(data))
    assert verdict.decision == "ACCEPT", verdict.reasons


@pytest.mark.parametrize("path", ALL, ids=_ids(ALL))
def test_real_evidence_is_accepted_by_the_command_line(path, capsys):
    assert main(["decide", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "ACCEPT"


def test_every_real_file_ends_on_a_converged_cycle_and_has_a_green_start():
    """What the Judge now relies on is what Warden writes: a converged record and a suite run before."""
    for path in REAL:
        data = _load(path)
        assert data["cycles"][-1][1] == "NOTHING_TO_PROPOSE", path.name
        before = data["suite_before"]
        assert before and before["ran"] and before["failed"] == 0 and before["errors"] == 0 and before["exit_code"] == 0, path.name


# ---- mutations: each is something a hand-made record can do; none may be ACCEPT ------------------------------

Mutation = Callable[[dict[str, Any]], None]


def _set(key: str, value: Any) -> Mutation:
    def apply(d: dict[str, Any]) -> None:
        d[key] = value
    return apply


def _suite(which: str, **fields: Any) -> Mutation:
    def apply(d: dict[str, Any]) -> None:
        if d[which] is None:
            return
        d[which].update(fields)
    return apply


def _add_edit(path: str, kind: str = "write") -> Mutation:
    def apply(d: dict[str, Any]) -> None:
        d["changed"].append([path, kind])
        d["cycles"].insert(len(d["cycles"]) - 1, [max(n for n, _ in d["cycles"]) + 1, "APPLIED"])
        for i, c in enumerate(d["cycles"]):
            c[0] = i + 1
    return apply


def _last_cycle(outcome: str) -> Mutation:
    def apply(d: dict[str, Any]) -> None:
        d["cycles"][-1][1] = outcome
    return apply


def _append_cycle(outcome: str) -> Mutation:
    def apply(d: dict[str, Any]) -> None:
        d["cycles"].append([d["cycles"][-1][0] + 1, outcome])
    return apply


def _edit_kind(kind: str) -> Mutation:
    def apply(d: dict[str, Any]) -> None:
        if d["changed"]:
            d["changed"][0][1] = kind
        else:
            d["changed"].append(["NOTE.md", kind])
            d["cycles"].insert(0, [0, "APPLIED"])
            for i, c in enumerate(d["cycles"]):
                c[0] = i + 1
    return apply


def _ghost_new(d: dict[str, Any]) -> None:
    d["ghost_after"] = d["ghost_after"] + ["ghost-new"]


def _baseline_grows(d: dict[str, Any]) -> None:
    d["ghost_baseline_after"] = {"path": None, "suppressed": 1}


def _violated(d: dict[str, Any]) -> None:
    d["attacks"][0]["status"] = "violated"


def _assay_below_floor(d: dict[str, Any]) -> None:
    d["assay"]["caught"] = d["assay"]["floor"] - 1


def _fewer_pass(d: dict[str, Any]) -> None:
    d["suite_after"]["passed"] = max(0, d["suite_before"]["passed"] - 1) if d["suite_before"] else 0


def _declined_without_a_cycle(d: dict[str, Any]) -> None:
    d["declined"] = ["ghost-x"]
    for c in d["cycles"]:
        if c[1] == "DECLINED":
            c[1] = "NOTHING_TO_PROPOSE"


MUTATIONS: dict[str, Mutation] = {
    # (1) and (2): the starting suite
    "suite_before null": _set("suite_before", None),
    "suite_before failed 5 errors 3 exit 1": _suite("suite_before", failed=5, errors=3, exit_code=1),
    "suite_before ran false": _suite("suite_before", ran=False),
    "suite_before failed 1": _suite("suite_before", failed=1),
    "suite_before errors 1": _suite("suite_before", errors=1),
    "suite_before exit 1": _suite("suite_before", exit_code=1),
    "suite_before forged": _suite("suite_before", forged=True),
    # (3): exit-code names that disagree or are not numbers
    "after exit_code 0 beside returncode 1": _suite("suite_after", exit_code=0, returncode=1),
    "after returncode 1 beside exit_code 0": _suite("suite_after", returncode=1),
    "after exitcode 2 beside exit_code 0": _suite("suite_after", exitcode=2),
    "after exit_status 3 beside exit_code 0": _suite("suite_after", exit_status=3),
    "before exit_code 0 beside returncode 1": _suite("suite_before", returncode=1),
    "after exit_code string": _suite("suite_after", exit_code="0"),
    "after returncode string": _suite("suite_after", returncode="1"),
    "after exit_code true": _suite("suite_after", exit_code=True),
    "after returncode float": _suite("suite_after", returncode=0.0),
    "after exit_code null with returncode 1": _suite("suite_after", exit_code=None, returncode=1),
    # (4): unknown scope, kind and target
    "scope banana": _set("scope", "banana"),
    "scope empty": _set("scope", ""),
    "scope spaces": _set("scope", "   "),
    "scope number": _set("scope", 3),
    "scope null": _set("scope", None),
    "edit kind banana": _edit_kind("banana"),
    "edit kind empty": _edit_kind(""),
    "target null": _set("target", None),
    "target number": _set("target", 7),
    "target list": _set("target", ["/x"]),
    # (5): a record that does not end converged
    "last cycle REFUSED": _last_cycle("REFUSED"),
    "last cycle PUT_BACK": _last_cycle("PUT_BACK"),
    "last cycle SUITE_RED": _last_cycle("SUITE_RED"),
    "REFUSED appended": _append_cycle("REFUSED"),
    "PUT_BACK appended": _append_cycle("PUT_BACK"),
    "SUITE_RED appended": _append_cycle("SUITE_RED"),
    # (6): protected paths
    "edit testing.txt": _add_edit("testing.txt"),
    "edit tests.txt": _add_edit("tests.txt"),
    "edit test.txt": _add_edit("test.txt"),
    "edit docs/testing.txt": _add_edit("docs/testing.txt"),
    "edit TESTS.TXT": _add_edit("TESTS.TXT"),
    "edit venv/README.md": _add_edit("venv/README.md"),
    "edit env/README.md": _add_edit("env/README.md"),
    "edit .tox/README.md": _add_edit(".tox/README.md"),
    "edit .nox/README.md": _add_edit(".nox/README.md"),
    "edit .eggs/README.md": _add_edit(".eggs/README.md"),
    "edit node_modules/pkg/README.md": _add_edit("node_modules/pkg/README.md"),
    "edit lib/site-packages/x/README.md": _add_edit("lib/site-packages/x/README.md"),
    "edit .venv/README.md": _add_edit(".venv/README.md"),
    # other fields the Judge reads
    "suite_after null": _set("suite_after", None),
    "suite_after red": _suite("suite_after", failed=1),
    "suite_after did not run": _suite("suite_after", ran=False),
    "fewer tests pass": _fewer_pass,
    "ghost new finding": _ghost_new,
    "ghost_before null": _set("ghost_before", None),
    "swizzle proofs false": _set("swizzle_proofs", False),
    "swizzle proofs null": _set("swizzle_proofs", None),
    "attack violated": _violated,
    "attacks null": _set("attacks", None),
    "attacks empty": _set("attacks", []),
    "assay null": _set("assay", None),
    "assay below floor": _assay_below_floor,
    "baseline grows": _baseline_grows,
    "baseline null": _set("ghost_baseline_after", None),
    "unmeasured ghost": _set("unmeasured", ["ghost"]),
    "cycles unknown outcome": _last_cycle("REVERTED"),
    "declined with no declined cycle": _declined_without_a_cycle,
}


@pytest.mark.parametrize("path", ALL, ids=_ids(ALL))
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_mutation_of_real_evidence_is_never_accepted(path, name):
    data = copy.deepcopy(_load(path))
    MUTATIONS[name](data)
    assert _decision(data) != "ACCEPT", f"{name} on {path.name} was accepted"


@pytest.mark.parametrize("path", ALL, ids=_ids(ALL))
def test_stacking_mutations_is_never_accepted(path):
    names = sorted(MUTATIONS)
    for i in range(0, len(names), 7):
        data = copy.deepcopy(_load(path))
        for name in names[i:i + 7]:
            MUTATIONS[name](data)
        assert _decision(data) != "ACCEPT", names[i:i + 7]


# ---- the named holes, one at a time, with the reason the Judge gives ----------------------------------------

def _reasons(data: dict[str, Any]) -> str:
    return " | ".join(Judge().decide(evidence_from_data(data)).reasons)


def _base() -> dict[str, Any]:
    return copy.deepcopy(_load(FIXTURES / "real" / "one_applied_cycle.json"))


def test_a_missing_starting_suite_is_insufficient_and_says_so():
    d = _base()
    d["suite_before"] = None
    assert _decision(d) == "INSUFFICIENT" and "starting suite run was not given" in _reasons(d)


def test_a_starting_suite_that_was_not_green_is_insufficient_and_says_so():
    d = _base()
    d["suite_before"].update(failed=5, errors=3, exit_code=1)
    assert _decision(d) == "INSUFFICIENT" and "starting suite was not green" in _reasons(d)


def test_exit_codes_that_disagree_are_insufficient_and_name_both():
    d = _base()
    d["suite_after"].update(returncode=1)
    assert _decision(d) == "INSUFFICIENT"
    assert "disagree" in _reasons(d) and "exit_code 0" in _reasons(d) and "returncode 1" in _reasons(d)


def test_agreeing_exit_code_names_are_still_accepted():
    d = _base()
    d["suite_after"].update(returncode=0, exitcode=0, exit_status=0)
    d["suite_before"].update(returncode=0)
    assert _decision(d) == "ACCEPT"


def test_an_unknown_scope_is_insufficient_when_only_prose_changed():
    d = _base()
    d["scope"] = "banana"
    assert _decision(d) == "INSUFFICIENT" and "scope" in _reasons(d)


def test_an_unknown_edit_kind_is_insufficient():
    d = _base()
    d["changed"][0][1] = "banana"
    assert _decision(d) == "INSUFFICIENT" and "kind" in _reasons(d)


@pytest.mark.parametrize("kind", ["write", "replace", "delete", " Write ", "REPLACE"])
def test_the_edit_kinds_warden_writes_are_known(kind):
    d = _base()
    d["changed"][0][1] = kind
    assert _decision(d) == "ACCEPT"


@pytest.mark.parametrize("scope", ["documentation", "code", "all", " Documentation ", "CODE"])
def test_the_scopes_warden_grants_are_known(scope):
    d = _base()
    d["scope"] = scope
    assert _decision(d) == "ACCEPT"


def test_a_last_cycle_that_did_not_converge_is_insufficient_even_with_no_edits():
    d = copy.deepcopy(_load(FIXTURES / "real" / "nothing_to_propose.json"))
    d["cycles"] = [[1, "REFUSED"]]
    assert _decision(d) == "INSUFFICIENT" and "did not converge" in _reasons(d)


def test_a_refused_last_cycle_with_edits_listed_is_not_accepted():
    d = _base()
    d["cycles"] = [[1, "APPLIED"], [2, "REFUSED"]]
    assert _decision(d) == "INSUFFICIENT"


@pytest.mark.parametrize("name", ["testing.txt", "tests.txt", "test.txt", "docs/testing.txt", "Tests.TXT", "testing.txt."])
def test_a_prose_file_pytest_collects_as_a_doctest_is_judged_like_a_test(name):
    d = _base()
    d["changed"].append([name, "write"])
    d["cycles"] = [[1, "APPLIED"], [2, "APPLIED"], [3, "NOTHING_TO_PROPOSE"]]
    verdict = Judge().decide(evidence_from_data(d))
    if name.endswith("."):  # not prose either, so under this documentation grant the harm "code changed" outranks the hold
        assert verdict.decision == "REJECT" and any("code changed" in r for r in verdict.reasons)
    else:
        assert verdict.decision == "INSUFFICIENT" and any("tests or test settings" in r for r in verdict.reasons)


@pytest.mark.parametrize("name", ["NOTES.txt", "docs/contest.txt", "latest.txt", "attest.md", "docs/testing.md"])
def test_other_prose_is_not_mistaken_for_a_test(name):
    d = _base()
    d["changed"].append([name, "write"])
    d["cycles"] = [[1, "APPLIED"], [2, "APPLIED"], [3, "NOTHING_TO_PROPOSE"]]
    assert _decision(d) == "ACCEPT"


@pytest.mark.parametrize("folder", ["venv", "env", ".tox", ".nox", ".eggs", "node_modules", "site-packages", "Venv", "lib/site-packages"])
def test_environment_folders_are_outside_the_project(folder):
    d = _base()
    d["changed"].append([f"{folder}/pkg/README.md", "write"])
    d["cycles"] = [[1, "APPLIED"], [2, "APPLIED"], [3, "NOTHING_TO_PROPOSE"]]
    verdict = Judge().decide(evidence_from_data(d))
    assert verdict.decision == "REJECT" and any("outside the project" in r for r in verdict.reasons)


@pytest.mark.parametrize("name", ["environment/README.md", "docs/envelope.md", "docs/environ.md", "inventory/README.md"])
def test_folders_that_only_look_like_environments_are_not_outside(name):
    d = _base()
    d["changed"].append([name, "write"])
    d["cycles"] = [[1, "APPLIED"], [2, "APPLIED"], [3, "NOTHING_TO_PROPOSE"]]
    assert _decision(d) == "ACCEPT"
