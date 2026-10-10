"""Red-team cases: the Judge used to approve what it did not recognize. Each case here fails closed."""

import pytest

from warden.roles import Evidence
from warden.suite import SuiteRun

from judge import Judge

GREEN = SuiteRun(ran=True, passed=10)
CLEAN_BASELINE = {"path": None, "suppressed": 0}
MISSING = object()
HELD = ({"scenario": "a", "severity": "high", "status": "held"},)
ASSAY = {"key_proven": True, "failure_modes": 5, "caught": 3, "floor": 0}


def _ev(**kw) -> Evidence:
    base = dict(
        target="/t", scope="code", cycles=((1, "APPLIED"),), changed=(("pkg/a.py", "write"),),
        judging_files_touched=(), suite_before=GREEN, suite_after=GREEN,
        ghost_before=("g",), ghost_after=("g",), declined=(), swizzle_proofs=True,
        attacks=HELD, unmeasured=(), assay=ASSAY)
    base.update(kw)
    extra = {k: base.pop(k) for k in ("ghost_baseline_before", "ghost_baseline_after") if k in base}
    ev = Evidence(**base)
    # Ghost's baseline report is not an Evidence field in the pinned Warden yet; the Judge reads it if present.
    for k, v in {"ghost_baseline_before": CLEAN_BASELINE, "ghost_baseline_after": CLEAN_BASELINE, **extra}.items():
        if v is not MISSING:
            object.__setattr__(ev, k, v)
    return ev


def _d(**kw):
    return Judge().decide(_ev(**kw))


def _atk(status="held", severity="high", scenario="X"):
    return ({"scenario": scenario, "severity": severity, "status": status},)


def _suite(**kw):
    return SuiteRun(ran=True, **{"passed": 10, **kw})


# 1. attacks

@pytest.mark.parametrize("status", ["Violated", " violated", "VIOLATED "])
def test_status_spelling_does_not_hide_a_violation(status):
    assert _d(attacks=_atk(status)).decision == "REJECT"


@pytest.mark.parametrize("severity", ["High", "critical", "severe", "medium", " MEDIUM", "", "banana", None, 5])
def test_violated_with_any_severity_but_low_is_harm(severity):
    assert _d(attacks=_atk("violated", severity)).decision == "REJECT"


def test_violated_with_missing_severity_key_is_harm():
    assert _d(attacks=({"scenario": "x", "status": "violated"},)).decision == "REJECT"


def test_violated_low_is_over_caution_and_the_sentence_says_so():
    v = _d(attacks=_atk("violated", "Low"))
    assert v.decision == "ACCEPT" and "low severity" in v.reasons[0] and "0 of 1 attacks" in v.reasons[0]


@pytest.mark.parametrize("status", ["error", "timeout", "crashed", "unknown", "", "not_run", None, 0, "NaN"])
def test_an_attack_without_a_clean_answer_is_insufficient(status):
    v = _d(attacks=_atk(status))
    assert v.decision == "INSUFFICIENT" and any("did not give a clean answer" in r and "'X'" in r for r in v.reasons)


def test_missing_status_key_is_insufficient():
    assert _d(attacks=({"scenario": "x", "severity": "high"},)).decision == "INSUFFICIENT"


def test_error_reason_names_the_status():
    assert "(status 'error')" in _d(attacks=_atk("error")).reasons[0]


def test_harm_outranks_an_attack_with_no_clean_answer():
    v = _d(attacks=_atk("error") + _atk("violated", "high", "Y"))
    assert v.decision == "REJECT" and "'Y'" in v.reasons[0]


@pytest.mark.parametrize("attacks", [("not a mapping",), (None,), (5,), (HELD[0], "x"), ((),)])
def test_a_non_mapping_attack_entry_is_insufficient(attacks):
    assert _d(attacks=attacks).decision == "INSUFFICIENT"


def test_no_attacks_attempted_is_insufficient():
    v = _d(attacks=())
    assert v.decision == "INSUFFICIENT" and any("no attacks" in r for r in v.reasons)


# 2. malformed evidence

def _unreadable(v):
    return v.decision == "INSUFFICIENT" and v.reasons[0].startswith("the evidence could not be read (") \
        and v.reasons[0].endswith("so nothing can be approved")


@pytest.mark.parametrize("kw", [
    {"scope": None}, {"scope": 3}, {"changed": None}, {"changed": "abc"}, {"changed": (("a.py",),)},
    {"changed": ((1, "write"),)}, {"changed": (("a.py", None),)}, {"changed": (None,)},
    {"judging_files_touched": None}, {"judging_files_touched": (1,)}, {"unmeasured": None},
    {"ghost_before": (1,), "ghost_after": (1,)}, {"ghost_after": 5}, {"attacks": 5}, {"attacks": "held"},
    {"assay": 5}, {"assay": "yes"},
    {"suite_after": SuiteRun(ran=True, passed=float("nan"))},
    {"suite_after": SuiteRun(ran=True, passed=-1)},
    {"suite_after": SuiteRun(ran=True, passed=True)},
    {"suite_after": SuiteRun(ran=True, passed=10.0)},
    {"suite_after": SuiteRun(ran=True, passed=10, failed=None)},
    {"suite_after": SuiteRun(ran=True, passed=10, skipped="2")},
    {"suite_before": SuiteRun(ran="yes", passed=10)},
    {"suite_after": object()}, {"suite_after": 7},
])
def test_malformed_evidence_is_insufficient_never_an_exception(kw):
    assert _unreadable(_d(**kw))


def test_nan_in_a_count_names_the_type():
    assert "float" in _d(suite_after=SuiteRun(ran=True, passed=float("nan"))).reasons[0]


def test_a_missing_field_does_not_raise():
    class Bare:
        scope = "code"
    assert _unreadable(Judge().decide(Bare()))
    assert _unreadable(Judge().decide(None))


def test_an_exception_while_reading_fails_closed():
    class Boom(list):
        def __iter__(self):
            raise RuntimeError("x")
    v = _d(attacks=Boom([1]))
    assert v.decision == "INSUFFICIENT" and "RuntimeError" in v.reasons[0]


def test_caught_greater_than_failure_modes_is_a_contradiction():
    v = _d(assay={**ASSAY, "caught": 9, "failure_modes": 5})
    assert v.decision == "REJECT" and any("contradict" in r for r in v.reasons)


# 3. strict types

@pytest.mark.parametrize("value", [None, 0, 1, "False", "True", "true", [], 1.0])
def test_swizzle_proofs_must_be_exactly_true(value):
    v = _d(swizzle_proofs=value)
    assert v.decision == "INSUFFICIENT"


def test_swizzle_proofs_false_is_harm():
    assert _d(swizzle_proofs=False).decision == "REJECT"


@pytest.mark.parametrize("value", [1, "True", "yes", None, 0, "False"])
def test_key_proven_must_be_exactly_true(value):
    assert _d(assay={**ASSAY, "key_proven": value}).decision == "INSUFFICIENT"


def test_key_proven_missing_is_insufficient_and_false_is_reject():
    assert _d(assay={"failure_modes": 5, "caught": 3, "floor": 0}).decision == "INSUFFICIENT"
    assert _d(assay={**ASSAY, "key_proven": False}).decision == "REJECT"


@pytest.mark.parametrize("floor", [-1, "3", None, 2.5, 3.0, True, [3]])
@pytest.mark.parametrize("caught", [0, 3])
def test_a_bad_floor_is_insufficient(floor, caught):
    v = _d(assay={**ASSAY, "floor": floor, "caught": caught})
    assert v.decision == "INSUFFICIENT" and any("floor" in r for r in v.reasons)


def test_a_missing_floor_is_not_zero():
    a = {"key_proven": True, "failure_modes": 5, "caught": 0}
    v = _d(assay=a)
    assert v.decision == "INSUFFICIENT" and any("floor was not given" in r for r in v.reasons)


@pytest.mark.parametrize("floor", [0, -1, "3", None])
def test_caught_99_of_5_is_a_contradiction_whatever_the_floor(floor):
    v = _d(assay={**ASSAY, "floor": floor, "caught": 99})
    assert v.decision == "REJECT" and any("contradict" in r for r in v.reasons)


def test_missing_caught_never_reads_caught_0_of_none():
    v = _d(assay={"key_proven": True, "failure_modes": 5, "floor": 0})
    assert v.decision == "INSUFFICIENT"
    assert not any("None" in r for r in v.reasons)
    v = _d(assay={"key_proven": True, "floor": 2})
    assert v.decision == "INSUFFICIENT" and not any("None" in r for r in v.reasons)


def test_below_floor_still_rejects():
    assert _d(assay={**ASSAY, "floor": 4}).decision == "REJECT"


# 4. judging files

def test_a_listed_judging_file_rejects_whatever_the_scope_or_suite():
    for scope in ("code", "documentation"):
        v = _d(scope=scope, changed=(), judging_files_touched=("tests/test_a.py",))
        assert v.decision == "REJECT" and "tests or test settings were changed" in v.reasons[0]


def test_test_file_deletion_with_equal_pass_count_is_rejected_even_if_warden_forgot_to_list_it():
    v = _d(changed=(("tests/test_a.py", "delete"),), suite_after=SuiteRun(ran=True, passed=10))
    assert v.decision == "REJECT" and "tests or test settings" in v.reasons[0]


@pytest.mark.parametrize("path", [
    "tests/x.py", "test/x.py", "pkg/tests/sub/y.py", "pkg/test_x.py", "pkg/x_test.py", "conftest.py",
    "pkg/conftest.py", "pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg", "noxfile.py", ".coveragerc",
    "Makefile", ".github/workflows/ci.yml", "./tests/a.py", ".\\tests\\a.py", "TESTS/A.PY", "PyProject.TOML",
    "./././Makefile", "tests"])
def test_judging_paths_are_caught_by_their_shape(path):
    v = _d(changed=((path, "write"),))
    assert v.decision == "REJECT", path


@pytest.mark.parametrize("path", ["pkg/contest.py", "pkg/attest.py", "pkg/testing_helpers.py", "README.md", "pkg/a.py"])
def test_ordinary_paths_are_not_judging_files(path):
    assert _d(changed=((path, "write"),)).decision == "ACCEPT"


@pytest.mark.parametrize("path", ["../x.py", "a/../../x.py", "/etc/passwd", "C:\\x.py", "c:/x.py", ".git/config",
                                  "pkg/.git/hooks/pre-commit", ".venv/lib/x.py", "a\\..\\..\\b.py", "~/x.py"])
def test_edits_outside_the_project_are_harm(path):
    v = _d(changed=((path, "write"),))
    assert v.decision == "REJECT" and any("outside the project" in r for r in v.reasons)


def test_gitignore_is_not_the_git_folder():
    assert _d(changed=((".gitignore", "write"),)).decision == "ACCEPT"


# 5. skipped tests

def test_skips_growing_from_zero_to_500_is_rejected():
    v = _d(suite_after=_suite(skipped=500))
    assert v.decision == "REJECT" and any("skipped" in r for r in v.reasons)


def test_xfail_growth_is_rejected_too():
    assert _d(suite_after=_suite(xfailed=1)).decision == "REJECT"


def test_skips_not_growing_is_fine():
    assert _d(suite_before=_suite(skipped=2), suite_after=_suite(skipped=2), changed=(("README.md", "write"),)).decision == "ACCEPT"
    assert _d(suite_before=_suite(skipped=2), suite_after=_suite(skipped=1), changed=(("README.md", "write"),)).decision == "ACCEPT"


def test_skips_swapped_for_xfails_counts_as_growth_only_in_total():
    assert _d(suite_before=_suite(skipped=3), suite_after=_suite(xfailed=3), changed=()).decision == "ACCEPT"
    assert _d(suite_before=_suite(skipped=3), suite_after=_suite(xfailed=4), changed=()).decision == "REJECT"


def test_xfailed_missing_from_an_older_suite_run_counts_as_zero():
    class Old:
        ran, passed, failed, errors, skipped = True, 10, 0, 0, 0
    assert _d(suite_before=Old(), suite_after=Old(), changed=()).decision == "ACCEPT"


@pytest.mark.parametrize("kind", ["write", "delete", "Write"])
def test_code_change_when_some_tests_did_not_run_before_is_insufficient(kind):
    v = _d(suite_before=_suite(skipped=1), suite_after=_suite(skipped=1), changed=(("pkg/a.py", kind),))
    assert v.decision == "INSUFFICIENT" and any("some tests did not run, so a code change cannot be shown safe" in r for r in v.reasons)


def test_xfailed_before_also_counts():
    v = _d(suite_before=_suite(xfailed=1), suite_after=_suite(xfailed=1))
    assert v.decision == "INSUFFICIENT"


def test_prose_change_with_skips_before_is_still_fine():
    assert _d(suite_before=_suite(skipped=1), suite_after=_suite(skipped=1), changed=(("README.md", "write"),)).decision == "ACCEPT"


# 6. ghost multiset

def test_a_duplicated_finding_is_new():
    v = _d(ghost_before=("a",), ghost_after=("a", "a"))
    assert v.decision == "REJECT" and any("1 finding" in r and "a" in r for r in v.reasons)


def test_same_multiset_in_other_order_is_fine_and_set_rule_still_applies():
    assert _d(ghost_before=("a", "b", "a"), ghost_after=("a", "a", "b")).decision == "ACCEPT"
    assert _d(ghost_before=("a",), ghost_after=("a", "z")).decision == "REJECT"
    assert _d(ghost_before=("a", "a"), ghost_after=("a",)).decision == "ACCEPT"


# 7. the accept sentence

def test_accept_sentence_states_what_was_checked_with_numbers():
    v = _d(suite_before=_suite(skipped=1), suite_after=_suite(passed=12, skipped=1, xfailed=0),
           changed=(("README.md", "write"),), attacks=_atk() + _atk("held", "low", "Y"),
           assay={"key_proven": True, "failure_modes": 5, "caught": 4, "floor": 3})
    s = v.reasons[0]
    assert v.decision == "ACCEPT"
    for part in ("12 passed", "1 skipped", "0 xfailed", "2 of 2 attacks", "caught 4 of 5", "floor 3", "1 change"):
        assert part in s
    assert "none of its attacks" not in s


def test_accept_sentence_never_claims_no_violation_unless_all_held():
    s = _d(attacks=_atk("held") + _atk("violated", "low", "Y")).reasons[0]
    assert "1 of 2 attacks" in s and "none of" not in s


# 8. unmeasured

def test_unmeasured_checks_block_accept():
    v = _d(unmeasured=("ghost",))
    assert v.decision == "INSUFFICIENT" and any("ghost" in r for r in v.reasons)


def test_only_judge_in_unmeasured_is_allowed():
    assert _d(unmeasured=("judge",)).decision == "ACCEPT"
    assert _d(unmeasured=(" Judge ",)).decision == "ACCEPT"
    assert _d(unmeasured=("judge", "swizzle", "suite")).decision == "INSUFFICIENT"


# 9. determinism and no mutation

def test_same_evidence_gives_same_verdict():
    e = _ev(attacks=_atk("error"))
    assert Judge().decide(e) == Judge().decide(e)
