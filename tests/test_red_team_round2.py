"""Red-team round 2: holes in protected-file detection, Ghost's baseline, the ASSAY floor and suite evidence."""

import os

import pytest

from warden.roles import Evidence
from warden.suite import SuiteRun

from judge import Judge

GREEN = SuiteRun(ran=True, passed=10)
HELD = ({"scenario": "a", "severity": "high", "status": "held"},)
ASSAY = {"key_proven": True, "failure_modes": 5, "caught": 3, "floor": 1}
BASE = {"path": None, "suppressed": 0}


def _ev(baseline_before=BASE, baseline_after=BASE, **kw):
    base = dict(
        target="/nonexistent-target", scope="code", cycles=((1, "APPLIED"),), changed=(("pkg/a.py", "write"),),
        judging_files_touched=(), suite_before=GREEN, suite_after=GREEN, ghost_before=("g",), ghost_after=("g",),
        declined=(), swizzle_proofs=True, attacks=HELD, unmeasured=(), assay=ASSAY)
    base.update(kw)
    ev = Evidence(**base)
    for k, v in (("ghost_baseline_before", baseline_before), ("ghost_baseline_after", baseline_after)):
        if v is not None:
            object.__setattr__(ev, k, v)
    return ev


def _d(**kw):
    return Judge().decide(_ev(**kw))


def test_the_clean_baseline_case_is_accepted():
    assert _d().decision == "ACCEPT"


# 1. protected files

PROTECTED = [
    "PYTEST.INI", ".pytest.ini", "pytest.ini", "sub/Pytest.ini", "tox.ini", "TOX.INI", "setup.cfg", "setup.py", "Setup.py",
    "noxfile.py", "a/b/conftest.py", "CONFTEST.PY", "tests.py", "test_x.py", "Test_X.py", "x_test.py", "x_TEST.py",
    "tests/a.py", "Tests/a.py", "TESTS/sub/a.py", "testing/a.py", "Testing/a.py", "tests /a.py", "tests./a.py",
    ".gitlab-ci.yml", "Jenkinsfile", "JENKINSFILE", ".circleci/config.yml", "azure-pipelines.yml", ".github/workflows/x.yml",
    ".GITHUB/x.yml", ".githooks/pre-commit", ".husky/pre-commit", "hooks/pre-push", "poetry.lock", "Pipfile", "Pipfile.lock",
    "uv.lock", "requirements.txt", "requirements-dev.txt", "Requirements_test.txt", "constraints.txt", "constraints-3.txt",
    ".gitmodules", "Dockerfile", "dockerfile.prod", "docker-compose.yml", "Docker-Compose.override.yaml",
    "pyproject.toml", "PyProject.toml", ".ghost_baseline.json", "x/.ghost_baseline.json", ".ghost_config.json",
    ".GHOST_BASELINE.JSON", "sitecustomize.py", "evil.pth", "Makefile", ".coveragerc", "pkg\\tests\\a.py", "./tests/a.py",
]


@pytest.mark.parametrize("path", PROTECTED)
def test_protected_paths_are_rejected(path):
    v = _d(changed=((path, "write"),))
    assert v.decision == "REJECT", path


@pytest.mark.parametrize("path", [".ghost_baseline.json", "sub/.GHOST_BASELINE.JSON", ".ghost_anything"])
def test_any_change_to_a_ghost_file_is_rejected_and_says_so(path):
    v = _d(changed=((path, "write"),), scope="documentation")
    assert v.decision == "REJECT" and any("baseline" in r and ".ghost_" in r for r in v.reasons)


@pytest.mark.parametrize("path", ["pkg/a.py", "pkg/latest.py", "docs/contest.md", "src/testimony.py", "README.md"])
def test_ordinary_files_are_not_flagged(path):
    assert _d(changed=((path, "write"),)).decision == "ACCEPT"


def test_symlink_to_a_protected_file_is_protected(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text("x\n")
    os.symlink("tests/t.py", tmp_path / "helper.py")
    v = _d(target=str(tmp_path), changed=(("helper.py", "write"),))
    assert v.decision == "REJECT" and any("helper.py" in r for r in v.reasons)


def test_symlinked_directory_into_tests_is_protected(tmp_path):
    (tmp_path / "tests").mkdir()
    os.symlink("tests", tmp_path / "pkg")
    assert _d(target=str(tmp_path), changed=(("pkg/new.py", "write"),)).decision == "REJECT"


def test_symlink_out_of_the_project_is_outside(tmp_path):
    proj, other = tmp_path / "p", tmp_path / "o"
    proj.mkdir(), other.mkdir()
    os.symlink(other, proj / "out")
    v = _d(target=str(proj), changed=(("out/a.py", "write"),))
    assert v.decision == "REJECT" and any("outside" in r for r in v.reasons)


def test_prose_named_symlink_to_code_is_code_under_a_documentation_grant(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x\n")
    os.symlink("pkg/a.py", tmp_path / "NOTES.md")
    v = _d(target=str(tmp_path), scope="documentation", changed=(("NOTES.md", "write"),))
    assert v.decision == "REJECT" and any("code changed" in r for r in v.reasons)


def test_a_plain_file_in_a_real_folder_is_not_mistaken_for_a_symlink(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x\n")
    assert _d(target=str(tmp_path), changed=(("pkg/a.py", "write"),)).decision == "ACCEPT"


# 2. Ghost's baseline

def test_suppressed_growing_is_rejected():
    v = _d(baseline_after={"path": None, "suppressed": 1})
    assert v.decision == "REJECT" and any("baseline" in r for r in v.reasons)


def test_suppressed_staying_or_shrinking_is_fine():
    assert _d(baseline_before={"path": "b.json", "suppressed": 3}, baseline_after={"path": "b.json", "suppressed": 2}).decision == "ACCEPT"


def test_a_baseline_appearing_or_moving_is_rejected():
    assert _d(baseline_after={"path": "b.json", "suppressed": 0}).decision == "REJECT"


def test_a_missing_baseline_report_is_unknown_not_approved():
    v = _d(baseline_before=None, baseline_after=None)
    assert v.decision == "INSUFFICIENT" and any("baseline" in r for r in v.reasons)
    assert _d(baseline_before=None).decision == "INSUFFICIENT"


@pytest.mark.parametrize("bad", ["x", 5, {"path": None}, {"path": 3, "suppressed": 0}, {"path": None, "suppressed": -1},
                                 {"path": None, "suppressed": "0"}, {"path": None, "suppressed": True}])
def test_a_malformed_baseline_report_is_unknown(bad):
    assert _d(baseline_after=bad).decision == "INSUFFICIENT"


def test_a_pair_shaped_baseline_field_is_read_too():
    ev = _ev(baseline_before=None, baseline_after=None)
    object.__setattr__(ev, "ghost_baseline", {"before": BASE, "after": {"path": None, "suppressed": 2}})
    assert Judge().decide(ev).decision == "REJECT"


# 3. the ASSAY floor

def test_a_missing_floor_is_insufficient_not_zero():
    v = _d(assay={"key_proven": True, "failure_modes": 5, "caught": 0})
    assert v.decision == "INSUFFICIENT" and any("floor was not given" in r for r in v.reasons)


def test_an_explicit_zero_floor_is_allowed_and_shown():
    v = _d(assay={**ASSAY, "floor": 0, "caught": 0})
    assert v.decision == "ACCEPT" and "floor of zero" in v.reasons[0]


def test_an_answer_key_with_no_failure_modes_proves_nothing():
    v = _d(assay={**ASSAY, "failure_modes": 0, "caught": 0, "floor": 0})
    assert v.decision == "INSUFFICIENT" and any("no failure modes" in r for r in v.reasons)


# 4. suite evidence

def _run(**kw):
    r = SuiteRun(ran=True, passed=10)
    for k, v in kw.items():
        object.__setattr__(r, k, v)
    return r


def test_a_nonzero_exit_code_beats_green_looking_text():
    v = _d(suite_after=_run(exit_code=1))
    assert v.decision == "REJECT" and any("exit code 1" in r for r in v.reasons)


def test_returncode_is_read_too():
    assert _d(suite_after=_run(returncode=2)).decision == "REJECT"


def test_a_zero_exit_code_with_failures_in_the_text_is_not_green():
    assert _d(suite_after=SuiteRun(ran=True, passed=10, failed=1)).decision == "REJECT"
    assert _d(suite_after=_run(exit_code=0, failed=1)).decision == "REJECT"


@pytest.mark.parametrize("marker", ["forged", "forged_output"])
def test_a_forged_marker_is_rejected(marker):
    v = _d(suite_after=_run(**{marker: True}))
    assert v.decision == "REJECT" and any("forged" in r for r in v.reasons)


def test_a_forged_starting_suite_is_rejected():
    assert _d(suite_before=_run(forged=True)).decision == "REJECT"


def test_a_non_numeric_exit_code_is_insufficient():
    assert _d(suite_after=_run(exit_code="0")).decision == "INSUFFICIENT"


def test_text_only_counts_are_called_text_derived_in_the_reason():
    v = _d()
    assert v.decision == "ACCEPT" and any("derived from printed text" in r for r in v.reasons)
    v = _d(suite_after=_run(text_only=True))
    assert any("text-only" in r for r in v.reasons)


def test_an_exit_code_of_zero_removes_the_text_derived_note():
    v = _d(suite_after=_run(exit_code=0), suite_before=_run(exit_code=0))
    assert v.decision == "ACCEPT" and not any("printed text" in r for r in v.reasons)
